import json
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (Availability, Carrier, CarrierQuote, DistanceMatrix, FleetVehicle, Location, Order, Pallet,
                      Plan, Scenario, VehicleClass)
from .packing import check_vehicle_load
from .pricing import internal_cost, quote_cost


def _clock_min(value):
    h, m = (value or "00:00").split(":")[:2]
    return int(h) * 60 + int(m)


def _as_vehicle(v, class_rank, kind, quote=None, carrier=None):
    return {"id": v["id"], "name": carrier.get("name") if kind == "CARRIER" and carrier else v["id"], "kind": kind,
            "class_id": v["vehicle_class_id"], "class_rank": class_rank, "capacity_kg": v["capacity_kg"],
            "usable_volume_m3": v["usable_volume_m3"], "inner_length_cm": v["inner_length_cm"],
            "inner_width_cm": v["inner_width_cm"], "inner_height_cm": v["inner_height_cm"],
            "available_from": v["available_from"], "available_until": v["available_until"],
            "fixed_cost_vnd": v.get("fixed_cost_vnd", quote["callout_fee_vnd"] if quote else 0),
            "cost_per_km_vnd": v.get("cost_per_km_vnd", quote["rate_per_km_vnd"] if quote else 0),
            "quote": quote, "carrier_id": carrier.get("id") if carrier else None,
            "carrier_name": carrier.get("name") if carrier else None}


def optimize(db: Session, run_id: str, org_id: str, user_id: str, config: dict) -> dict:
    scenario = db.scalar(select(Scenario).where(Scenario.organization_id == org_id).order_by(Scenario.operation_date.desc()))
    if not scenario: raise ValueError("No operating scenario is configured")
    locations = db.scalars(select(Location).where(Location.organization_id == org_id, Location.scenario_id == scenario.id)).all()
    loc_map = {x.id: x for x in locations}
    depot = loc_map.get(scenario.depot_id)
    locked_routes = config.get("locked_routes", [])
    locked_order_ids = {s["order_id"] for r in locked_routes for s in r.get("stops", [])}
    orders_db = db.scalars(select(Order).where(Order.organization_id == org_id, Order.scenario_id == scenario.id,
                                               Order.status.in_(["READY", "VALIDATED", "PENDING"]))).all()
    orders_db = [o for o in orders_db if o.id not in locked_order_ids]
    pallets_db = db.scalars(select(Pallet).where(Pallet.organization_id == org_id, Pallet.scenario_id == scenario.id)).all()
    pmap = {}
    for p in pallets_db:
        pmap.setdefault(p.order_id, []).append({"pallet_id": p.id, "length_cm": p.length_cm, "width_cm": p.width_cm,
                "height_cm": p.height_cm, "weight_kg": p.weight_kg, "volume_m3": p.volume_m3,
                "rotation_rule": p.rotation_rule, "description": p.description})
    order_map = {o.id: {"id": o.id, "external_id": o.external_id, "customer_id": o.customer_id,
                "drop_location_id": o.drop_location_id, "ready_at": o.ready_at, "due_at": o.due_at,
                "service_min": o.service_min, "priority": o.priority, "total_weight_kg": o.total_weight_kg,
                "total_volume_m3": o.total_volume_m3, "minimum_vehicle_class": o.minimum_vehicle_class,
                "pallets": pmap.get(o.id, []), "notes": o.notes} for o in orders_db}
    classes = {c.id: c.class_rank for c in db.scalars(select(VehicleClass).where(VehicleClass.organization_id == org_id)).all()}
    vehicles = []
    locked_vehicle_ids = {r.get("vehicle_id") for r in locked_routes}
    for v in db.scalars(select(FleetVehicle).where(FleetVehicle.organization_id == org_id, FleetVehicle.scenario_id == scenario.id,
                                                   FleetVehicle.status == "AVAILABLE")).all():
        if v.id in locked_vehicle_ids: continue
        vehicles.append(_as_vehicle({"id": v.id, "plate_number": v.plate_number, "vehicle_class_id": v.vehicle_class_id,
            "capacity_kg": v.capacity_kg, "usable_volume_m3": v.usable_volume_m3, "inner_length_cm": v.inner_length_cm,
            "inner_width_cm": v.inner_width_cm, "inner_height_cm": v.inner_height_cm, "available_from": v.available_from,
            "available_until": v.available_until, "fixed_cost_vnd": v.fixed_cost_vnd, "cost_per_km_vnd": v.cost_per_km_vnd},
            classes.get(v.vehicle_class_id, 99), "INTERNAL"))
    if config.get("include_carriers", True):
        avail = db.scalars(select(Availability).where(Availability.organization_id == org_id, Availability.scenario_id == scenario.id,
                                                      Availability.confirmation_status == "CONFIRMED", Availability.vehicles_available > 0)).all()
        quote_rows = db.scalars(select(CarrierQuote).where(CarrierQuote.organization_id == org_id,
                CarrierQuote.scenario_id == scenario.id, CarrierQuote.status.in_(["DEMO_VALID", "VALID", "ACTIVE"]))).all()
        carriers = {c.id: c for c in db.scalars(select(Carrier).where(Carrier.organization_id == org_id)).all()}
        qby = {}
        for q in quote_rows: qby.setdefault((q.carrier_id, q.vehicle_class_id), []).append(q)
        for av in avail:
            choices = qby.get((av.carrier_id, av.vehicle_class_id), [])
            if not choices: continue
            q = min(choices, key=lambda x: (x.minimum_fare_vnd, x.rate_per_km_vnd))
            car = carriers.get(av.carrier_id)
            for n in range(min(av.vehicles_available, 3)):
                vehicle_id=f"{av.id}-{n+1}"
                if vehicle_id in locked_vehicle_ids: continue
                vehicles.append(_as_vehicle({"id": vehicle_id, "vehicle_class_id": q.vehicle_class_id,
                    "capacity_kg": q.capacity_kg, "usable_volume_m3": q.usable_volume_m3, "inner_length_cm": q.inner_length_cm,
                    "inner_width_cm": q.inner_width_cm, "inner_height_cm": q.inner_height_cm,
                    "available_from": av.window_start, "available_until": av.window_end}, classes.get(q.vehicle_class_id, 99),
                    "CARRIER", {"id": q.id, "rate_per_km_vnd": q.rate_per_km_vnd, "callout_fee_vnd": q.callout_fee_vnd,
                    "minimum_fare_vnd": q.minimum_fare_vnd, "waiting_free_min": q.waiting_free_min,
                    "waiting_fee_per_hour_vnd": q.waiting_fee_per_hour_vnd, "stop_fee_vnd": q.stop_fee_vnd,
                    "return_trip_rule": q.return_trip_rule, "vat_rate_assumption": q.vat_rate_assumption},
                    {"id": car.id, "name": car.name} if car else None))
    vehicles = vehicles[:30]
    ready_orders = sorted(order_map.values(), key=lambda o: (_clock_min(o["due_at"].strftime("%H:%M")),
        0 if o["priority"] == "HIGH" else 1, o["id"]))
    if not ready_orders:
        output = {"routes": locked_routes, "unassigned": [], "summary": {"orders_total": len(locked_order_ids), "assigned": len(locked_order_ids),
                  "unassigned": 0, "vehicles_used": len(locked_routes), "distance_km": round(sum(r.get("distance_km",0) for r in locked_routes),1),
                  "cost_vnd": sum(r.get("cost_vnd",0) for r in locked_routes)}, "solver": "FleetMix deterministic insertion heuristic"}
        return _save_plan(db, run_id, org_id, user_id, scenario.id, config, output)
    matrix_rows = db.scalars(select(DistanceMatrix).where(DistanceMatrix.organization_id == org_id,
                                                          DistanceMatrix.scenario_id == scenario.id)).all()
    distances = {(r.from_location_id, r.to_location_id): (r.distance_km, r.drive_time_min) for r in matrix_rows}
    def leg(a, b):
        if a == b: return 0.0, 0
        if (a,b) in distances: return distances[(a,b)]
        if (b,a) in distances: return distances[(b,a)]
        la, lb = loc_map[a], loc_map[b]
        # Synthetic straight-line fallback only; displayed as approximate.
        km = (((la.latitude-lb.latitude)**2 + (la.longitude-lb.longitude)**2)**0.5) * 111 * 1.35
        return km, int(km / 22 * 60)
    locations_ids = [scenario.depot_id] + [o["drop_location_id"] for o in ready_orders]
    n = len(ready_orders)
    # Different orders may share a customer location; node dimension deliberately remains per-order.
    matrix_km = [[leg(locations_ids[i], locations_ids[j])[0] for j in range(n+1)] for i in range(n+1)]
    matrix_min = [[leg(locations_ids[i], locations_ids[j])[1] for j in range(n+1)] for i in range(n+1)]
    viable_vehicles = []
    for v in vehicles:
        if v["kind"] == "INTERNAL" and v["name"]:
            # Skip maintenance / unavailable are excluded above.
            pass
        viable_vehicles.append(v)
    # Deterministic cheapest-insertion heuristic. It is intentionally transparent and
    # keeps all hard constraints in one evaluator so unsafe assignments stay unplanned.
    from .packing import pack_floor
    routes_by_vehicle: dict[str, dict] = {}
    assigned_ids: set[str] = set()
    unassigned: list[dict] = []

    def evaluate(vehicle, stops):
        load = check_vehicle_load([o["id"] for o in stops], order_map, vehicle)
        if not load["feasible"]: return None
        start = max(_clock_min(vehicle["available_from"].strftime("%H:%M")), _clock_min(scenario.planning_start.strftime("%H:%M")))
        end = min(_clock_min(vehicle["available_until"].strftime("%H:%M")), _clock_min(scenario.planning_end.strftime("%H:%M")))
        clock = start; total_km = 0.0; previous = scenario.depot_id; scheduled = []; duration = 0
        for seq, order in enumerate(stops, 1):
            target = order["drop_location_id"]; km, drive_min = leg(previous, target)
            total_km += km; clock += drive_min; duration += drive_min
            ready = _clock_min(order["ready_at"].strftime("%H:%M")); due = _clock_min(order["due_at"].strftime("%H:%M"))
            arrival = max(clock, ready)
            if arrival > due: return None
            clock = arrival + order["service_min"]; duration += order["service_min"]
            loc = loc_map[target]
            scheduled.append({"sequence":seq,"order_id":order["id"],"external_id":order["external_id"],"location_id":target,
                "location_name":loc.name,"latitude":loc.latitude,"longitude":loc.longitude,"eta":f"{arrival//60:02d}:{arrival%60:02d}",
                "due_at":order["due_at"].strftime("%H:%M"),"weight_kg":order["total_weight_kg"],"volume_m3":order["total_volume_m3"],
                "priority":order["priority"],"pallet_count":len(order["pallets"])})
            previous = target
        km, drive_min = leg(previous, scenario.depot_id); total_km += km; duration += drive_min; clock += drive_min
        if clock > end: return None
        cost = quote_cost(total_km,len(stops),vehicle["quote"]) if vehicle["kind"]=="CARRIER" else internal_cost(total_km,vehicle)
        return {"load":load,"stops":scheduled,"distance_km":round(total_km,1),"duration_min":duration,"cost_vnd":cost,
                "vehicle":{**{k:vehicle[k] for k in ["capacity_kg","usable_volume_m3","inner_length_cm","inner_width_cm","inner_height_cm"]},
                    "class_id":vehicle["class_id"],"class_rank":vehicle["class_rank"],"available_from":vehicle["available_from"].strftime("%H:%M"),
                    "available_until":vehicle["available_until"].strftime("%H:%M")}}

    used_ids = set(locked_vehicle_ids)
    for order in ready_orders:
        required_rank = classes.get(order["minimum_vehicle_class"], 1) if order["minimum_vehicle_class"] != "ANY_COMPATIBLE" else 0
        candidates = []
        for vehicle in viable_vehicles:
            if vehicle["class_rank"] < required_rank or vehicle["id"] in locked_vehicle_ids: continue
            current = routes_by_vehicle.get(vehicle["id"])
            if current:
                old_orders = current["_orders"]
                positions = range(len(old_orders)+1)
                old_cost = current["cost_vnd"]
            elif vehicle["id"] not in used_ids:
                old_orders = []; positions = (0,); old_cost = 0
            else: continue
            for position in positions:
                trial = old_orders[:position]+[order]+old_orders[position:]
                result = evaluate(vehicle, trial)
                if result is None: continue
                incremental = result["cost_vnd"]-old_cost
                candidates.append((incremental,result["distance_km"],vehicle["id"],vehicle,trial,result))
        if not candidates:
            reasons=[]
            class_vehicles=[v for v in viable_vehicles if v["class_rank"]>=required_rank]
            if not class_vehicles: reasons.append("MINIMUM_VEHICLE_CLASS_UNAVAILABLE")
            elif not any(order["total_weight_kg"]<=v["capacity_kg"] and order["total_volume_m3"]<=v["usable_volume_m3"] for v in class_vehicles): reasons.append("WEIGHT_OR_VOLUME_LIMIT")
            elif not any(pack_floor(order["pallets"],v["inner_length_cm"],v["inner_width_cm"],v["inner_height_cm"])["status"].startswith("PASS") for v in class_vehicles): reasons.append("PALLET_FLOOR_INFEASIBLE")
            else: reasons.append("TIME_WINDOW_OR_ROUTE_CAPACITY")
            unassigned.append({"order_id":order["id"],"reason":reasons[0]})
            continue
        _,_,vehicle_id,vehicle,chosen_orders,result=min(candidates,key=lambda c:(c[0],c[1],c[2]))
        used_ids.add(vehicle_id);assigned_ids.add(order["id"])
        route={"route_key":vehicle_id,"vehicle_id":vehicle_id,"vehicle_name":vehicle["name"],"kind":vehicle["kind"],
               "carrier_id":vehicle["carrier_id"],"carrier_name":vehicle["carrier_name"],"quote_id":vehicle["quote"]["id"] if vehicle["quote"] else None,
               "state":"PLANNED","status":"DRAFT","distance_km":result["distance_km"],"duration_min":result["duration_min"],
               "cost_vnd":result["cost_vnd"],"load":result["load"],"vehicle":result["vehicle"],"stops":result["stops"],"_orders":chosen_orders}
        routes_by_vehicle[vehicle_id]=route
    routes=[]
    for route in routes_by_vehicle.values():
        route.pop("_orders",None); routes.append(route)
    routes.sort(key=lambda r:r["route_key"])
    routes=list(locked_routes)+routes
    output = {"routes": routes, "unassigned": unassigned,
              "summary": {"orders_total":n+len(locked_order_ids),"assigned":len(assigned_ids)+len(locked_order_ids),"unassigned":len(unassigned),
                          "vehicles_used":len(routes),"distance_km":round(sum(r.get("distance_km",0) for r in routes),1),
                          "cost_vnd":sum(r.get("cost_vnd",0) for r in routes)},
              "solver":"FleetMix deterministic cheapest-insertion heuristic",
              "optimality":"feasible, constraint-checked heuristic; a global cost optimum is not guaranteed",
              "synthetic_data":scenario.data_provenance=="SYNTHETIC_SAMPLE"}
    return _save_plan(db, run_id, org_id, user_id, scenario.id, config, output)


def _save_plan(db, run_id, org_id, user_id, scenario_id, config, output):
    plan = Plan(id=str(uuid.uuid4()), organization_id=org_id, scenario_id=scenario_id, optimization_run_id=run_id,
                version=1, status="DRAFT", objective=config.get("objective", "BALANCED"),
                total_cost_vnd=output.get("summary", {}).get("cost_vnd", 0), result_json=json.dumps(output, ensure_ascii=False),
                created_by_id=user_id)
    db.add(plan); db.commit()
    output["plan_id"] = plan.id; output["plan_status"] = plan.status
    return output
