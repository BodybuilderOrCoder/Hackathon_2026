"""Deterministic route planner shared by optimisation runs and manual dispatch edits.

Business rules (see the workbook Data Dictionary):
- ``Order.ready_at`` is when goods are ready to leave the warehouse, so a trip cannot depart before every
  order on it is ready.
- ``Order.due_at`` is the delivery deadline and ``Location.open_from/open_until`` are the customer's receiving
  hours. Service at a stop starts no earlier than opening time and no later than the deadline or closing time.
- Internal vehicles may run several trips per shift (return to depot, reload, depart again). Their fixed cost
  applies per trip. Carrier vehicles are booked for a single trip each.
- Carrier tariffs bill the loaded distance; the empty return leg is billed only for round-trip tariffs.
"""
import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (Availability, Carrier, CarrierQuote, DistanceMatrix, FleetVehicle, Location, Order, Pallet,
                      Plan, Scenario, VehicleClass)
from .packing import check_vehicle_load, pack_floor
from .pricing import internal_cost, quote_cost

PLANNABLE_STATUSES = ("READY", "VALIDATED", "PENDING")
MAX_TRIPS_PER_VEHICLE = 4
DEFAULT_RELOAD_MIN = 30
MAX_CARRIER_UNITS_PER_AVAILABILITY = 3


class RoutingError(ValueError):
    """A manual edit violates a planning constraint. ``code`` is machine readable."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def clock_min(value) -> int:
    if value is None:
        return 0
    if hasattr(value, "hour"):
        return value.hour * 60 + value.minute
    h, m = str(value).split(":")[:2]
    return int(h) * 60 + int(m)


def hm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


class RoutingContext:
    """Scenario data and timing rules used by every route evaluation."""

    def __init__(self, db: Session, org_id: str, scenario: Scenario):
        self.db = db
        self.org_id = org_id
        self.scenario = scenario
        self.depot_id = scenario.depot_id
        self.locations = {x.id: x for x in db.scalars(select(Location).where(
            Location.organization_id == org_id, Location.scenario_id == scenario.id)).all()}
        rows = db.scalars(select(DistanceMatrix).where(DistanceMatrix.organization_id == org_id,
                                                       DistanceMatrix.scenario_id == scenario.id)).all()
        self.distances = {(r.from_location_id, r.to_location_id): (float(r.distance_km), int(r.drive_time_min)) for r in rows}
        self.class_rank = {c.id: c.class_rank for c in db.scalars(select(VehicleClass).where(VehicleClass.organization_id == org_id)).all()}
        self.plan_start = clock_min(scenario.planning_start)
        self.plan_end = clock_min(scenario.planning_end)
        depot = self.locations.get(self.depot_id)
        self.reload_min = int(depot.service_min_default) if depot and depot.service_min_default else DEFAULT_RELOAD_MIN
        self._trip_cache: dict = {}

    def leg(self, a: str, b: str) -> tuple[float, int]:
        if a == b:
            return 0.0, 0
        if (a, b) in self.distances:
            return self.distances[(a, b)]
        if (b, a) in self.distances:
            return self.distances[(b, a)]
        la, lb = self.locations.get(a), self.locations.get(b)
        if la is None or lb is None:
            raise RoutingError("UNKNOWN_LOCATION", f"Thiếu tọa độ hoặc khoảng cách cho điểm {a if la is None else b}")
        # Synthetic straight-line fallback only; displayed as approximate.
        km = (((la.latitude - lb.latitude) ** 2 + (la.longitude - lb.longitude) ** 2) ** 0.5) * 111 * 1.35
        return km, int(km / 22 * 60)

    def receiving_window(self, location_id: str) -> tuple[int, int]:
        loc = self.locations.get(location_id)
        if loc is None:
            return 0, 24 * 60
        return clock_min(loc.open_from or "00:00"), clock_min(loc.open_until or "23:59")

    def required_rank(self, order: dict) -> int:
        if order["minimum_vehicle_class"] in (None, "", "ANY_COMPATIBLE"):
            return 0
        return self.class_rank.get(order["minimum_vehicle_class"], 99)

    def load_orders(self, order_ids=None, plannable_only: bool = True) -> dict[str, dict]:
        query = select(Order).where(Order.organization_id == self.org_id, Order.scenario_id == self.scenario.id)
        if order_ids is not None:
            query = query.where(Order.id.in_(list(order_ids)))
        if plannable_only:
            query = query.where(Order.status.in_(PLANNABLE_STATUSES))
        orders = self.db.scalars(query).all()
        ids = [o.id for o in orders]
        pallets: dict[str, list] = {}
        if ids:
            for p in self.db.scalars(select(Pallet).where(Pallet.organization_id == self.org_id, Pallet.order_id.in_(ids))).all():
                pallets.setdefault(p.order_id, []).append({
                    "pallet_id": p.id, "length_cm": p.length_cm, "width_cm": p.width_cm, "height_cm": p.height_cm,
                    "weight_kg": p.weight_kg, "volume_m3": p.volume_m3, "rotation_rule": p.rotation_rule,
                    "description": p.description})
        return {o.id: {"id": o.id, "external_id": o.external_id, "customer_id": o.customer_id,
                       "drop_location_id": o.drop_location_id, "ready_min": clock_min(o.ready_at),
                       "due_min": clock_min(o.due_at), "service_min": int(o.service_min or 0), "priority": o.priority,
                       "total_weight_kg": o.total_weight_kg, "total_volume_m3": o.total_volume_m3,
                       "minimum_vehicle_class": o.minimum_vehicle_class, "pallets": pallets.get(o.id, []),
                       "notes": o.notes} for o in orders}

    def evaluate_trip(self, vehicle: dict, stops: list[dict], window_start: int, window_end: int) -> dict | None:
        """Schedule one depot-to-depot trip, or return None when any hard constraint fails."""
        if not stops:
            return None
        key = (vehicle["id"], tuple(o["id"] for o in stops), window_start, window_end)
        if key in self._trip_cache:
            return self._trip_cache[key]
        result = self._evaluate_trip(vehicle, stops, window_start, window_end)
        self._trip_cache[key] = result
        return result

    def _evaluate_trip(self, vehicle, stops, window_start, window_end):
        load = check_vehicle_load([o["id"] for o in stops], {o["id"]: o for o in stops}, vehicle)
        if not load["feasible"]:
            return None
        # Goods must be ready before departure; leave late enough to avoid idling at the first stop.
        earliest = max([window_start] + [o["ready_min"] for o in stops])
        first_open, _ = self.receiving_window(stops[0]["drop_location_id"])
        _, first_drive = self.leg(self.depot_id, stops[0]["drop_location_id"])
        departure = max(earliest, first_open - first_drive)
        clock, previous, loaded_km, waiting, scheduled = departure, self.depot_id, 0.0, 0, []
        for seq, order in enumerate(stops, 1):
            target = order["drop_location_id"]
            km, drive_min = self.leg(previous, target)
            loaded_km += km
            clock += drive_min
            open_from, open_until = self.receiving_window(target)
            service_start = max(clock, open_from)
            if service_start > min(order["due_min"], open_until):
                return None
            wait = service_start - clock
            waiting += wait
            loc = self.locations.get(target)
            scheduled.append({"sequence": seq, "order_id": order["id"], "external_id": order["external_id"],
                              "location_id": target, "location_name": loc.name if loc else target,
                              "latitude": loc.latitude if loc else 0, "longitude": loc.longitude if loc else 0,
                              "arrival": hm(clock), "eta": hm(service_start), "wait_min": wait,
                              "due_at": hm(order["due_min"]), "weight_kg": order["total_weight_kg"],
                              "volume_m3": order["total_volume_m3"], "priority": order["priority"],
                              "pallet_count": len(order["pallets"])})
            clock = service_start + order["service_min"]
            previous = target
        return_km, return_min = self.leg(previous, self.depot_id)
        clock += return_min
        if clock > window_end:
            return None
        total_km = loaded_km + return_km
        if vehicle["kind"] == "CARRIER":
            cost = quote_cost(loaded_km, len(stops), vehicle["quote"], waiting_min=waiting, return_km=return_km)
        else:
            cost = internal_cost(total_km, vehicle)
        return {"load": load, "stops": scheduled, "distance_km": round(total_km, 1), "loaded_km": round(loaded_km, 1),
                "return_km": round(return_km, 1), "duration_min": clock - departure, "waiting_min": waiting,
                "departure_min": departure, "return_min": clock, "cost_vnd": cost}

    def evaluate_schedule(self, vehicle: dict, trips: list[list[dict]]) -> list[dict] | None:
        """Chain trips for one vehicle: each trip departs after the previous one returns and reloads."""
        results, cursor = [], vehicle["shift_start_min"]
        for trip in trips:
            result = self.evaluate_trip(vehicle, trip, cursor, vehicle["shift_end_min"])
            if result is None:
                return None
            results.append(result)
            cursor = result["return_min"] + self.reload_min
        return results


def _vehicle(ctx: RoutingContext, *, id, kind, class_id, dims, available_from, available_until, name,
             fixed_cost=0, cost_per_km=0, quote=None, carrier=None, plate_number=None, unit_no=None):
    start = max(clock_min(available_from), ctx.plan_start)
    end = min(clock_min(available_until), ctx.plan_end)
    return {"id": id, "name": name, "kind": kind, "class_id": class_id, "class_rank": ctx.class_rank.get(class_id, 99),
            **dims, "shift_start_min": start, "shift_end_min": end, "fixed_cost_vnd": fixed_cost,
            "cost_per_km_vnd": cost_per_km, "quote": quote, "carrier_id": carrier.id if carrier else None,
            "carrier_name": carrier.name if carrier else None, "plate_number": plate_number, "unit_no": unit_no,
            "multi_trip": kind == "INTERNAL", "trip_offset": 0}


def _quote_dict(q: CarrierQuote) -> dict:
    return {"id": q.id, "rate_per_km_vnd": q.rate_per_km_vnd, "callout_fee_vnd": q.callout_fee_vnd,
            "minimum_fare_vnd": q.minimum_fare_vnd, "waiting_free_min": q.waiting_free_min,
            "waiting_fee_per_hour_vnd": q.waiting_fee_per_hour_vnd, "stop_fee_vnd": q.stop_fee_vnd,
            "return_trip_rule": q.return_trip_rule, "vat_rate_assumption": q.vat_rate_assumption}


def _dims(row) -> dict:
    return {"capacity_kg": row.capacity_kg, "usable_volume_m3": row.usable_volume_m3, "inner_length_cm": row.inner_length_cm,
            "inner_width_cm": row.inner_width_cm, "inner_height_cm": row.inner_height_cm}


def available_vehicles(ctx: RoutingContext, include_carriers: bool = True) -> list[dict]:
    db, org_id, scenario = ctx.db, ctx.org_id, ctx.scenario
    vehicles = []
    for v in db.scalars(select(FleetVehicle).where(FleetVehicle.organization_id == org_id, FleetVehicle.scenario_id == scenario.id,
                                                   FleetVehicle.status == "AVAILABLE").order_by(FleetVehicle.id)).all():
        vehicles.append(_vehicle(ctx, id=v.id, kind="INTERNAL", class_id=v.vehicle_class_id, dims=_dims(v),
                                 available_from=v.available_from, available_until=v.available_until, name=v.id,
                                 fixed_cost=v.fixed_cost_vnd, cost_per_km=v.cost_per_km_vnd, plate_number=v.plate_number))
    if not include_carriers:
        return vehicles
    operation_day = scenario.operation_date.date() if scenario.operation_date else None
    avail = db.scalars(select(Availability).where(Availability.organization_id == org_id, Availability.scenario_id == scenario.id,
                                                  Availability.confirmation_status == "CONFIRMED", Availability.vehicles_available > 0)
                       .order_by(Availability.id)).all()
    quote_rows = db.scalars(select(CarrierQuote).where(CarrierQuote.organization_id == org_id, CarrierQuote.scenario_id == scenario.id,
                                                       CarrierQuote.status.in_(["DEMO_VALID", "VALID", "ACTIVE"]))).all()
    carriers = {c.id: c for c in db.scalars(select(Carrier).where(Carrier.organization_id == org_id)).all()}
    quotes_by_key: dict = {}
    for q in quote_rows:
        if operation_day and q.valid_from and q.valid_until and not (q.valid_from.date() <= operation_day <= q.valid_until.date()):
            continue  # tariff not in force on the operating date
        quotes_by_key.setdefault((q.carrier_id, q.vehicle_class_id), []).append(q)
    for av in avail:
        choices = quotes_by_key.get((av.carrier_id, av.vehicle_class_id), [])
        if not choices:
            continue
        q = min(choices, key=lambda x: (x.minimum_fare_vnd, x.rate_per_km_vnd, x.id))
        carrier = carriers.get(av.carrier_id)
        for n in range(min(av.vehicles_available, MAX_CARRIER_UNITS_PER_AVAILABILITY)):
            vehicles.append(_vehicle(ctx, id=f"{av.id}-{n + 1}", kind="CARRIER", class_id=q.vehicle_class_id, dims=_dims(q),
                                     available_from=av.window_start, available_until=av.window_end,
                                     name=carrier.name if carrier else av.carrier_id, quote=_quote_dict(q), carrier=carrier,
                                     unit_no=n + 1))
    return vehicles


def _route_from_trip(vehicle: dict, trip_no: int, result: dict, window_start: int, window_end: int) -> dict:
    route_key = vehicle["id"] if trip_no == 1 else f"{vehicle['id']}-T{trip_no}"
    return {"route_key": route_key, "vehicle_id": vehicle["id"], "vehicle_name": vehicle["name"], "kind": vehicle["kind"],
            "plate_number": vehicle.get("plate_number"), "unit_no": vehicle.get("unit_no"), "trip_no": trip_no,
            "carrier_id": vehicle["carrier_id"], "carrier_name": vehicle["carrier_name"],
            "quote_id": vehicle["quote"]["id"] if vehicle["quote"] else None, "state": "PLANNED", "status": "DRAFT",
            "departure": hm(result["departure_min"]), "return_at": hm(result["return_min"]),
            "distance_km": result["distance_km"], "loaded_km": result["loaded_km"], "return_km": result["return_km"],
            "duration_min": result["duration_min"], "waiting_min": result["waiting_min"], "cost_vnd": result["cost_vnd"],
            "load": result["load"], "stops": result["stops"],
            "vehicle": {**{k: vehicle[k] for k in ["capacity_kg", "usable_volume_m3", "inner_length_cm", "inner_width_cm", "inner_height_cm"]},
                        "class_id": vehicle["class_id"], "class_rank": vehicle["class_rank"],
                        "available_from": hm(window_start), "available_until": hm(window_end),
                        "shift_end": hm(vehicle["shift_end_min"])}}


def _summary(routes: list[dict], unassigned: list[dict]) -> dict:
    assigned = sum(len(r.get("stops", [])) for r in routes)
    return {"orders_total": assigned + len(unassigned), "assigned": assigned, "unassigned": len(unassigned),
            "vehicles_used": len({r.get("vehicle_id", r.get("route_key")) for r in routes}), "trips": len(routes),
            "distance_km": round(sum(r.get("distance_km", 0) for r in routes), 1),
            "cost_vnd": sum(r.get("cost_vnd", 0) for r in routes)}


def _unassigned_reason(ctx: RoutingContext, order: dict, vehicles: list[dict]) -> str:
    required = ctx.required_rank(order)
    class_vehicles = [v for v in vehicles if v["class_rank"] >= required]
    if not class_vehicles:
        return "MINIMUM_VEHICLE_CLASS_UNAVAILABLE"
    if not any(order["total_weight_kg"] <= v["capacity_kg"] and order["total_volume_m3"] <= v["usable_volume_m3"] for v in class_vehicles):
        return "WEIGHT_OR_VOLUME_LIMIT"
    if not any(pack_floor(order["pallets"], v["inner_length_cm"], v["inner_width_cm"], v["inner_height_cm"])["status"].startswith("PASS")
               for v in class_vehicles):
        return "PALLET_FLOOR_INFEASIBLE"
    if not any(ctx.evaluate_trip(v, [order], v["shift_start_min"], v["shift_end_min"]) for v in class_vehicles):
        return "DELIVERY_WINDOW_UNREACHABLE"
    return "TIME_WINDOW_OR_ROUTE_CAPACITY"


def _insertion_plan(ctx: RoutingContext, vehicles: list[dict], ready_orders: list[dict]):
    """Deterministic cheapest insertion over multi-trip schedules.

    Every hard constraint lives in RoutingContext.evaluate_trip, so unsafe assignments stay unplanned
    instead of being forced onto a vehicle.
    """
    schedules: dict[str, list[list[dict]]] = {}
    evaluations: dict[str, list[dict]] = {}
    unassigned: list[dict] = []
    for order in ready_orders:
        required = ctx.required_rank(order)
        best = None
        for vehicle in vehicles:
            if vehicle["class_rank"] < required:
                continue
            trips = schedules.get(vehicle["id"], [])
            old_cost = sum(r["cost_vnd"] for r in evaluations.get(vehicle["id"], []))
            options = []
            for ti, trip in enumerate(trips):
                for pos in range(len(trip) + 1):
                    options.append(trips[:ti] + [trip[:pos] + [order] + trip[pos:]] + trips[ti + 1:])
            if not trips or (vehicle["multi_trip"] and vehicle["trip_offset"] + len(trips) < MAX_TRIPS_PER_VEHICLE):
                for index in range(len(trips) + 1):
                    options.append(trips[:index] + [[order]] + trips[index:])
            for option in options:
                results = ctx.evaluate_schedule(vehicle, option)
                if results is None:
                    continue
                incremental = sum(r["cost_vnd"] for r in results) - old_cost
                rank = (incremental, sum(r["distance_km"] for r in results), vehicle["id"])
                if best is None or rank < best[0]:
                    best = (rank, vehicle["id"], option, results)
        if best is None:
            unassigned.append({"order_id": order["id"], "reason": _unassigned_reason(ctx, order, vehicles)})
            continue
        _, vehicle_id, option, results = best
        schedules[vehicle_id] = option
        evaluations[vehicle_id] = results
    return schedules, evaluations, unassigned


def optimize(db: Session, run_id: str, org_id: str, user_id: str, config: dict) -> dict:
    scenario = db.scalar(select(Scenario).where(Scenario.organization_id == org_id).order_by(Scenario.operation_date.desc()))
    if not scenario:
        raise ValueError("No operating scenario is configured")
    ctx = RoutingContext(db, org_id, scenario)
    locked_routes = list(config.get("locked_routes", []))
    locked_order_ids = {s["order_id"] for r in locked_routes for s in r.get("stops", [])}
    order_map = {k: v for k, v in ctx.load_orders().items() if k not in locked_order_ids}

    vehicles = []
    for vehicle in available_vehicles(ctx, config.get("include_carriers", True)):
        locked = [r for r in locked_routes if r.get("vehicle_id", r.get("route_key")) == vehicle["id"]]
        if locked:
            # Started trips keep the vehicle busy; an internal vehicle may take new trips after its last locked return.
            if vehicle["kind"] != "INTERNAL" or not all(r.get("return_at") for r in locked):
                continue
            vehicle["shift_start_min"] = max(vehicle["shift_start_min"], max(clock_min(r["return_at"]) for r in locked) + ctx.reload_min)
            vehicle["trip_offset"] = max(int(r.get("trip_no") or 1) for r in locked)
            if vehicle["shift_start_min"] >= vehicle["shift_end_min"]:
                continue
        vehicles.append(vehicle)

    ready_orders = sorted(order_map.values(), key=lambda o: (o["due_min"], 0 if o["priority"] == "HIGH" else 1, o["id"]))
    schedules, evaluations, unassigned = _insertion_plan(ctx, vehicles, ready_orders)
    if any(v["kind"] == "CARRIER" for v in vehicles):
        # Greedy insertion can hire a carrier early that the internal fleet could have absorbed later.
        # Keep the internal-only plan when it serves at least as many orders for no more money.
        internal = [v for v in vehicles if v["kind"] == "INTERNAL"]
        alt = _insertion_plan(ctx, internal, ready_orders)
        cost = lambda ev: sum(r["cost_vnd"] for results in ev.values() for r in results)
        if len(alt[2]) <= len(unassigned) and cost(alt[1]) <= cost(evaluations):
            schedules, evaluations, unassigned = alt
    vehicle_by_id = {v["id"]: v for v in vehicles}

    routes = []
    for vehicle_id in sorted(schedules):
        vehicle = vehicle_by_id[vehicle_id]
        results = evaluations[vehicle_id]
        for index, result in enumerate(results):
            window_start = vehicle["shift_start_min"] if index == 0 else results[index - 1]["return_min"] + ctx.reload_min
            window_end = results[index + 1]["departure_min"] - ctx.reload_min if index + 1 < len(results) else vehicle["shift_end_min"]
            routes.append(_route_from_trip(vehicle, vehicle["trip_offset"] + index + 1, result, window_start, window_end))
    routes = locked_routes + routes
    output = {"routes": routes, "unassigned": unassigned, "summary": _summary(routes, unassigned),
              "solver": "FleetMix deterministic cheapest-insertion heuristic (multi-trip)",
              "optimality": "feasible, constraint-checked heuristic; a global cost optimum is not guaranteed",
              "rules": {"reload_min": ctx.reload_min, "max_trips_per_vehicle": MAX_TRIPS_PER_VEHICLE},
              "synthetic_data": scenario.data_provenance == "SYNTHETIC_SAMPLE"}
    return _save_plan(db, run_id, org_id, user_id, scenario.id, config, output)


def _route_vehicle(ctx: RoutingContext, route: dict) -> dict:
    """Rebuild the planner's vehicle record for an existing route so manual edits use current tariffs."""
    info = route.get("vehicle", {})
    if route["kind"] == "CARRIER":
        quote = ctx.db.scalar(select(CarrierQuote).where(CarrierQuote.id == route.get("quote_id"), CarrierQuote.organization_id == ctx.org_id))
        if not quote:
            raise RoutingError("QUOTE_UNAVAILABLE", "Biểu giá của nhà xe không còn hiệu lực")
        vehicle = _vehicle(ctx, id=route["vehicle_id"], kind="CARRIER", class_id=quote.vehicle_class_id, dims=_dims(quote),
                           available_from=info.get("available_from", "00:00"), available_until=info.get("available_until", "23:59"),
                           name=route.get("vehicle_name"), quote=_quote_dict(quote))
    else:
        fleet = ctx.db.scalar(select(FleetVehicle).where(FleetVehicle.id == route["vehicle_id"], FleetVehicle.organization_id == ctx.org_id))
        if not fleet:
            raise RoutingError("VEHICLE_UNAVAILABLE", "Xe nội bộ không còn trong danh mục")
        vehicle = _vehicle(ctx, id=fleet.id, kind="INTERNAL", class_id=fleet.vehicle_class_id, dims=_dims(fleet),
                           available_from=info.get("available_from", fleet.available_from), available_until=info.get("available_until", fleet.available_until),
                           name=fleet.id, fixed_cost=fleet.fixed_cost_vnd, cost_per_km=fleet.cost_per_km_vnd, plate_number=fleet.plate_number)
    return vehicle


def insert_order_into_route(db: Session, org_id: str, scenario: Scenario, route: dict, order_id: str) -> dict:
    """Return ``route`` with ``order_id`` inserted at its cheapest feasible position, or raise RoutingError."""
    ctx = RoutingContext(db, org_id, scenario)
    vehicle = _route_vehicle(ctx, route)
    existing_ids = [s["order_id"] for s in route.get("stops", [])]
    orders = ctx.load_orders(existing_ids + [order_id], plannable_only=False)
    new_order = orders.get(order_id)
    if new_order is None:
        raise RoutingError("ORDER_NOT_FOUND", "Không tìm thấy lệnh giao hàng trong kịch bản đang mở")
    if vehicle["class_rank"] < ctx.required_rank(new_order):
        raise RoutingError("VEHICLE_CLASS", "Hạng xe của tuyến thấp hơn hạng xe tối thiểu của lệnh")
    current = [orders[x] for x in existing_ids if x in orders]
    load = check_vehicle_load([o["id"] for o in current + [new_order]], {o["id"]: o for o in current + [new_order]}, vehicle)
    if "WEIGHT_LIMIT" in load["errors"] or "VOLUME_LIMIT" in load["errors"]:
        raise RoutingError("CAPACITY", "Lệnh vượt tải trọng hoặc thể tích còn lại của xe")
    if not load["feasible"]:
        raise RoutingError("FLOOR", "Pallet không xếp vừa mặt sàn thùng xe")
    window_start, window_end = vehicle["shift_start_min"], vehicle["shift_end_min"]
    best = None
    for pos in range(len(current) + 1):
        result = ctx.evaluate_trip(vehicle, current[:pos] + [new_order] + current[pos:], window_start, window_end)
        if result and (best is None or (result["cost_vnd"], result["distance_km"]) < (best["cost_vnd"], best["distance_km"])):
            best = result
    if best is None:
        raise RoutingError("TIME_WINDOW", "Không thể thêm điểm giao: sẽ trễ hạn giao, ngoài giờ nhận hàng hoặc vượt ca xe")
    updated = dict(route)
    updated.update({"departure": hm(best["departure_min"]), "return_at": hm(best["return_min"]),
                    "distance_km": best["distance_km"], "loaded_km": best["loaded_km"], "return_km": best["return_km"],
                    "duration_min": best["duration_min"], "waiting_min": best["waiting_min"], "cost_vnd": best["cost_vnd"],
                    "load": best["load"], "stops": best["stops"]})
    return updated


def recompute_summary(data: dict) -> dict:
    data["summary"] = _summary(data.get("routes", []), data.get("unassigned", []))
    return data["summary"]


def _save_plan(db, run_id, org_id, user_id, scenario_id, config, output):
    plan = Plan(id=str(uuid.uuid4()), organization_id=org_id, scenario_id=scenario_id, optimization_run_id=run_id,
                version=1, status="DRAFT", objective=config.get("objective", "BALANCED"),
                total_cost_vnd=output.get("summary", {}).get("cost_vnd", 0), result_json=json.dumps(output, ensure_ascii=False),
                created_by_id=user_id)
    db.add(plan); db.commit()
    output["plan_id"] = plan.id; output["plan_status"] = plan.status
    return output
