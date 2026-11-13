import json
import re
import tempfile
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import SessionLocal, get_db, init_db
from .models import (Approval, AuditEvent, Availability, BookingDraft, Carrier, CarrierQuote, Customer, DistanceMatrix,
                     FleetVehicle, Location, OptimizationRun, Order, Organization, Pallet, Plan, Product, Scenario, User, VehicleClass)
from .schemas import ApprovalRequest, AssignRequest, OptimizeRequest
from .services.optimizer import PLANNABLE_STATUSES, RoutingError, insert_order_into_route, recompute_summary
from .services.seed import SHARED_ACTOR_ID, _clock, _dt, ensure_shared_actor, load_workbook_rows, seed_database

@asynccontextmanager
async def lifespan(_app):
    init_db()
    with SessionLocal() as db:
        if not db.scalar(select(Scenario).limit(1)):
            seed_database(db)
        ensure_shared_actor(db)
    yield


app = FastAPI(title="FleetMix AI Operations API", version="1.0.0", lifespan=lifespan)


def audit(db, user, action, entity_type, entity_id, details=None):
    details = {"actor_name": user.full_name, "employee_code": user.employee_code, **(details or {})}
    db.add(AuditEvent(organization_id=user.organization_id, user_id=user.id, action=action, entity_type=entity_type,
                      entity_id=str(entity_id), details_json=json.dumps(details, ensure_ascii=False)))


def shared_actor(db: Session = Depends(get_db)) -> User:
    actor = db.get(User, SHARED_ACTOR_ID)
    if actor is None:
        raise HTTPException(status_code=503, detail="Chưa khởi tạo người thao tác dùng chung")
    return actor


@app.get("/health")
def health():
    return {"status": "ok", "service": "fleetmix-api", "environment": get_settings().app_env}


@app.get("/api/employees")
def employees(db: Session=Depends(get_db),user: User=Depends(shared_actor)):
    rows=db.scalars(select(User).where(User.organization_id==user.organization_id, User.role=="LOGISTICS_STAFF").order_by(User.employee_code)).all()
    return {"employees":[{"id":x.id,"employee_code":x.employee_code,"name":x.full_name,"email":x.email,"department":x.department,
        "position":x.position,"active":x.active} for x in rows]}


@app.post("/api/employees")
def create_employee(body: dict, db: Session=Depends(get_db), user: User=Depends(shared_actor)):
    name=str(body.get("name", "")).strip(); email=str(body.get("email", "")).strip().lower()
    code=str(body.get("employee_code", "")).strip()
    if len(name)<2 or "@" not in email or not code:
        raise HTTPException(422,"Nhập đủ mã nhân viên, họ tên và email công việc hợp lệ")
    if db.scalar(select(User).where(func.lower(User.email)==email)) or db.scalar(select(User).where(User.organization_id==user.organization_id,User.employee_code==code)):
        raise HTTPException(409,"Email hoặc mã nhân viên đã tồn tại")
    member=User(id=str(uuid.uuid4()),organization_id=user.organization_id,full_name=name,email=email,employee_code=code,
        department="LOGISTICS",position=str(body.get("position", "Logistics staff")),role="LOGISTICS_STAFF",password_hash="",active=True)
    db.add(member);audit(db,user,"EMPLOYEE_CREATED","Employee",member.id,{"employee_code":code});db.commit()
    return {"employee":{"id":member.id,"employee_code":member.employee_code,"name":member.full_name,"email":member.email,
        "department":member.department,"position":member.position,"active":member.active}}


def _scenario(db, user):
    value = db.scalar(select(Scenario).where(Scenario.organization_id == user.organization_id).order_by(Scenario.operation_date.desc()))
    if not value: raise HTTPException(status_code=404, detail="Chưa có kịch bản vận hành")
    return value


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(shared_actor)):
    scenario = _scenario(db, user)
    organization = db.get(Organization, user.organization_id)
    depot = db.get(Location, scenario.depot_id)
    orders = db.scalars(select(Order).where(Order.organization_id == user.organization_id, Order.scenario_id == scenario.id)).all()
    fleet = db.scalars(select(FleetVehicle).where(FleetVehicle.organization_id == user.organization_id, FleetVehicle.scenario_id == scenario.id)).all()
    current_plan = db.scalar(select(Plan).where(Plan.organization_id == user.organization_id, Plan.scenario_id == scenario.id).order_by(Plan.created_at.desc()))
    result = json.loads(current_plan.result_json) if current_plan else None
    return {"organization": {"id": user.organization_id, "name": organization.name if organization else "Logistics Operations",
                               "display_name": organization.display_name if organization else "Logistics Operations",
                               "business_unit": organization.business_unit if organization else "LOGISTICS"},
            "scenario": {"id": scenario.id, "name": scenario.name, "operation_date": scenario.operation_date.isoformat(),
                          "depot_id": scenario.depot_id, "depot_name": depot.name if depot else scenario.depot_id,
                          "depot_latitude": depot.latitude if depot else 10.801, "depot_longitude": depot.longitude if depot else 106.652,
                          "timezone": scenario.timezone, "provenance": scenario.data_provenance},
            "metrics": {"orders_total": len(orders), "orders_ready": sum(o.status in {"READY", "VALIDATED", "PENDING"} for o in orders),
                        "vehicles_available": sum(v.status == "AVAILABLE" for v in fleet),
                        "vehicles_total": len(fleet), "plan_status": current_plan.status if current_plan else "NOT_PLANNED",
                        "cost_vnd": current_plan.total_cost_vnd if current_plan else 0,
                        "assigned": result.get("summary", {}).get("assigned", 0) if result else 0,
                        "unassigned": result.get("summary", {}).get("unassigned", len(orders)) if result else len(orders)},
            "synthetic_data": scenario.data_provenance == "SYNTHETIC_SAMPLE", "ai_status": "AI_GATEWAY_OPTIONAL_LOCAL_RULES_AVAILABLE"}


@app.get("/api/orders")
def list_orders(db: Session = Depends(get_db), user: User = Depends(shared_actor)):
    scenario = _scenario(db, user)
    orders = db.scalars(select(Order).where(Order.organization_id == user.organization_id, Order.scenario_id == scenario.id).order_by(Order.due_at)).all()
    customers = {x.id: x for x in db.scalars(select(Customer).where(Customer.organization_id == user.organization_id)).all()}
    products = {x.id: x for x in db.scalars(select(Product).where(Product.organization_id == user.organization_id)).all()}
    output = []
    for o in orders:
        pallets = db.scalars(select(Pallet).where(Pallet.organization_id == user.organization_id, Pallet.order_id == o.id)).all()
        loc = db.get(Location, o.drop_location_id)
        customer = customers.get(o.customer_id)
        output.append({"id": o.id, "external_id": o.external_id, "customer_id": o.customer_id,
            "customer_name": customer.display_name if customer else o.customer_id, "order_type": o.order_type,
            "location_id": o.drop_location_id, "location_name": loc.name if loc else o.drop_location_id,
            "zone": loc.zone if loc else "", "latitude": loc.latitude if loc else 0, "longitude": loc.longitude if loc else 0,
            "address": loc.address if loc else "", "ready_at": o.ready_at.strftime("%H:%M"), "due_at": o.due_at.strftime("%H:%M"),
            "service_min": o.service_min, "priority": o.priority, "status": o.status, "split_allowed": o.split_allowed,
            "total_weight_kg": o.total_weight_kg, "total_volume_m3": o.total_volume_m3,
            "minimum_vehicle_class": o.minimum_vehicle_class, "notes": o.notes,
            "pallets": [{"id": p.id, "sku_id": p.sku_id, "sku_name": products[p.sku_id].name if p.sku_id in products else p.description,
                "base_uom": products[p.sku_id].base_uom if p.sku_id in products else "", "description": p.description, "weight_kg": p.weight_kg,
                "length_cm": p.length_cm, "width_cm": p.width_cm, "height_cm": p.height_cm, "volume_m3": p.volume_m3,
                "stackable": p.stackable, "rotation_rule": p.rotation_rule, "handling_code": p.handling_code} for p in pallets]})
    return {"scenario_id": scenario.id, "orders": output}


@app.get("/api/customers")
def customers_list(db: Session = Depends(get_db), user: User = Depends(shared_actor)):
    rows = db.scalars(select(Customer).where(Customer.organization_id == user.organization_id).order_by(Customer.id)).all()
    return {"customers": [{"id": x.id, "legal_name": x.legal_name, "display_name": x.display_name,
        "customer_segment": x.customer_segment, "sales_channel": x.sales_channel, "payment_terms": x.payment_terms,
        "service_level": x.service_level, "status": x.status} for x in rows]}


@app.get("/api/products")
def products_list(db: Session = Depends(get_db), user: User = Depends(shared_actor)):
    rows = db.scalars(select(Product).where(Product.organization_id == user.organization_id).order_by(Product.id)).all()
    return {"products": [{"id": x.id, "name": x.name, "category": x.category, "base_uom": x.base_uom,
        "handling_code": x.handling_code, "stackable_default": x.stackable_default, "rotation_rule": x.rotation_rule,
        "status": x.status} for x in rows]}


@app.get("/api/fleet")
def fleet(db: Session = Depends(get_db), user: User = Depends(shared_actor)):
    scenario = _scenario(db, user)
    vehicles = db.scalars(select(FleetVehicle).where(FleetVehicle.organization_id == user.organization_id, FleetVehicle.scenario_id == scenario.id)).all()
    result = []
    for v in vehicles:
        vc = db.get(VehicleClass, v.vehicle_class_id)
        result.append({"id": v.id, "name": v.id, "asset_code": v.id, "plate_number": v.plate_number,
            "fleet_type": v.fleet_type, "class_id": v.vehicle_class_id,
            "class_rank": vc.class_rank if vc else 0, "capacity_kg": v.capacity_kg, "usable_volume_m3": v.usable_volume_m3,
            "inner_length_cm": v.inner_length_cm, "inner_width_cm": v.inner_width_cm, "inner_height_cm": v.inner_height_cm,
            "status": v.status, "available_from": v.available_from.strftime("%H:%M"), "available_until": v.available_until.strftime("%H:%M"),
            "synthetic": v.is_synthetic})
    return {"vehicles": result}


@app.get("/api/quotes")
def quotes(db: Session = Depends(get_db), user: User = Depends(shared_actor)):
    scenario = _scenario(db, user)
    av = db.scalars(select(Availability).where(Availability.organization_id == user.organization_id, Availability.scenario_id == scenario.id)).all()
    carr = {c.id:c.name for c in db.scalars(select(Carrier).where(Carrier.organization_id == user.organization_id)).all()}
    quote_rows = db.scalars(select(CarrierQuote).where(CarrierQuote.organization_id == user.organization_id, CarrierQuote.scenario_id == scenario.id)).all()
    return {"quotes": [{"id":q.id,"carrier_id":q.carrier_id,"carrier_name":carr.get(q.carrier_id),"class_id":q.vehicle_class_id,
        "capacity_kg":q.capacity_kg,"usable_volume_m3":q.usable_volume_m3,"rate_per_km_vnd":q.rate_per_km_vnd,
        "callout_fee_vnd":q.callout_fee_vnd,"minimum_fare_vnd":q.minimum_fare_vnd,"stop_fee_vnd":q.stop_fee_vnd,
        "return_trip_rule":q.return_trip_rule,"vat_rate_assumption":q.vat_rate_assumption,"status":q.status,"synthetic":q.is_synthetic} for q in quote_rows],
        "availability": [{"id":a.id,"carrier_name":carr.get(a.carrier_id),"class_id":a.vehicle_class_id,"vehicles_available":a.vehicles_available,
        "status":a.confirmation_status,"window_start":a.window_start.strftime("%H:%M"),"window_end":a.window_end.strftime("%H:%M")} for a in av]}


@app.post("/api/optimization-runs", status_code=202)
def create_optimization(body: OptimizeRequest, db: Session = Depends(get_db), user: User = Depends(shared_actor)):
    scenario = _scenario(db, user); rid = str(uuid.uuid4())
    config = body.model_dump()
    prior = db.scalar(select(Plan).where(Plan.organization_id == user.organization_id, Plan.scenario_id == scenario.id).order_by(Plan.created_at.desc()))
    if prior:
        prior_data = json.loads(prior.result_json)
        config["locked_routes"] = [r for r in prior_data.get("routes", []) if r.get("state") in {"ACTIVE", "COMPLETED"}]
    job = OptimizationRun(id=rid, organization_id=user.organization_id, scenario_id=scenario.id, created_by_id=user.id,
        status="QUEUED", progress=0, config_json=json.dumps(config), input_snapshot_json="{}", result_json="{}")
    db.add(job); audit(db,user,"OPTIMIZATION_QUEUED","OptimizationRun",rid,body.model_dump()); db.commit()
    return {"id": rid, "status": job.status, "status_url": f"/api/optimization-runs/{rid}"}


@app.get("/api/optimization-runs/{run_id}")
def optimization_status(run_id: str, db: Session = Depends(get_db), user: User = Depends(shared_actor)):
    job = db.scalar(select(OptimizationRun).where(OptimizationRun.id == run_id, OptimizationRun.organization_id == user.organization_id))
    if not job: raise HTTPException(404, "Không tìm thấy lượt tối ưu")
    return {"id":job.id,"status":job.status,"progress":job.progress,"error":job.error_message,
            "result":json.loads(job.result_json) if job.status == "SUCCEEDED" else None}


@app.get("/api/plans/latest")
def latest_plan(db: Session = Depends(get_db), user: User = Depends(shared_actor)):
    scenario = _scenario(db, user)
    p = db.scalar(select(Plan).where(Plan.organization_id == user.organization_id, Plan.scenario_id == scenario.id).order_by(Plan.created_at.desc()))
    if not p: return {"plan":None}
    data=json.loads(p.result_json); data.update({"plan_id":p.id,"plan_status":p.status,"version":p.version,"objective":p.objective})
    return {"plan":data}


def _latest_plan_id(db, user):
    scenario = _scenario(db, user)
    return db.scalar(select(Plan.id).where(Plan.organization_id == user.organization_id, Plan.scenario_id == scenario.id).order_by(Plan.created_at.desc()))


@app.post("/api/plans/{plan_id}/approval")
def approve_plan(plan_id: str, body: ApprovalRequest, db: Session = Depends(get_db), user: User = Depends(shared_actor)):
    p=db.scalar(select(Plan).where(Plan.id==plan_id,Plan.organization_id==user.organization_id))
    if not p: raise HTTPException(404,"Không tìm thấy kế hoạch")
    if p.status != "DRAFT": raise HTTPException(409,"Chỉ duyệt hoặc trả lại được kế hoạch ở trạng thái bản nháp")
    if p.id != _latest_plan_id(db,user): raise HTTPException(409,"Kế hoạch này đã được thay bằng phương án mới hơn")
    p.status = "APPROVED" if body.decision == "APPROVE" else "REJECTED"
    db.add(Approval(id=str(uuid.uuid4()),organization_id=user.organization_id,plan_id=p.id,user_id=user.id,decision=body.decision,comment=body.comment))
    audit(db,user,"PLAN_"+body.decision,"Plan",p.id,{"comment":body.comment}); db.commit()
    return {"plan_id":p.id,"status":p.status}


ROUTE_TRANSITIONS = {"PLANNED": {"ACTIVE"}, "ACTIVE": {"COMPLETED"}, "COMPLETED": set()}


@app.patch("/api/plans/{plan_id}/routes/{route_key}/state")
def set_route_state(plan_id: str, route_key: str, body: dict, db: Session=Depends(get_db), user: User=Depends(shared_actor)):
    state=str(body.get("state", "")).upper()
    if state not in {"ACTIVE","COMPLETED"}: raise HTTPException(422,"Trạng thái tuyến chỉ nhận ACTIVE hoặc COMPLETED")
    p=db.scalar(select(Plan).where(Plan.id==plan_id,Plan.organization_id==user.organization_id))
    if not p: raise HTTPException(404,"Không tìm thấy kế hoạch")
    if p.id != _latest_plan_id(db,user): raise HTTPException(409,"Chỉ cập nhật tuyến trên kế hoạch hiện hành")
    data=json.loads(p.result_json);route=next((r for r in data.get("routes",[]) if r["route_key"]==route_key),None)
    if not route: raise HTTPException(404,"Không tìm thấy tuyến")
    current=route.get("state","PLANNED")
    if state not in ROUTE_TRANSITIONS.get(current,set()):
        raise HTTPException(409,"Tuyến phải đi theo thứ tự Đề xuất → Đang chạy → Hoàn tất")
    if state=="ACTIVE" and p.status!="APPROVED":
        raise HTTPException(409,"Kế hoạch phải được xác nhận trước khi cho tuyến xuất phát")
    route["state"]=state;route["status"]=state
    p.result_json=json.dumps(data,ensure_ascii=False);audit(db,user,"ROUTE_STATE_CHANGED","Route",route_key,{"state":state,"plan_id":p.id});db.commit()
    return {"plan_id":p.id,"route_key":route_key,"state":state}


@app.post("/api/plans/{plan_id}/booking-drafts")
def create_booking_drafts(plan_id: str, db: Session = Depends(get_db), user: User = Depends(shared_actor)):
    p=db.scalar(select(Plan).where(Plan.id==plan_id,Plan.organization_id==user.organization_id))
    if not p: raise HTTPException(404,"Không tìm thấy kế hoạch")
    if p.status != "APPROVED": raise HTTPException(409,"Kế hoạch phải được xác nhận trước khi lập bản nháp yêu cầu xe")
    data=json.loads(p.result_json); created=[]; existing=0
    for route in data.get("routes",[]):
        if route.get("kind") != "CARRIER": continue
        already=db.scalar(select(BookingDraft).where(BookingDraft.organization_id==user.organization_id,BookingDraft.plan_id==p.id,BookingDraft.route_key==route["route_key"]))
        if already: existing+=1; continue
        draft=BookingDraft(id=str(uuid.uuid4()),organization_id=user.organization_id,plan_id=p.id,route_key=route["route_key"],
            carrier_id=route.get("carrier_id"),quote_id=route.get("quote_id"),status="DRAFT",
            request_json=json.dumps({"stops":route["stops"],"departure":route.get("departure"),"estimated_cost_vnd":route["cost_vnd"],"synthetic_data":True},ensure_ascii=False),created_by_id=user.id)
        db.add(draft); created.append(draft.id)
    if created:
        audit(db,user,"BOOKING_DRAFTS_PREPARED","Plan",p.id,{"count":len(created),"external_submission":False})
    db.commit()
    return {"plan_id":p.id,"booking_drafts_created":len(created),"booking_drafts_existing":existing,"draft_ids":created,"external_submission":False}


@app.post("/api/plans/{plan_id}/assign")
def manual_assign(plan_id: str, body: AssignRequest, db: Session = Depends(get_db), user: User = Depends(shared_actor)):
    p=db.scalar(select(Plan).where(Plan.id==plan_id,Plan.organization_id==user.organization_id))
    if not p: raise HTTPException(404,"Không tìm thấy kế hoạch")
    if p.status != "DRAFT": raise HTTPException(409,"Chỉ chỉnh sửa được kế hoạch ở trạng thái bản nháp; hãy lập lại phương án")
    data=json.loads(p.result_json); routes=data.get("routes",[])
    index=next((i for i,r in enumerate(routes) if r["route_key"]==body.route_key),None)
    if index is None: raise HTTPException(404,"Không tìm thấy tuyến")
    route=routes[index]
    if route.get("state") != "PLANNED": raise HTTPException(409,"Tuyến đã bắt đầu; không thể thêm lệnh giao hàng")
    if any(s["order_id"]==body.order_id for r in routes for s in r.get("stops",[])):
        raise HTTPException(409,"Lệnh đã nằm trong một tuyến của kế hoạch")
    scenario=_scenario(db,user)
    if not db.scalar(select(Order).where(Order.id==body.order_id,Order.organization_id==user.organization_id,Order.scenario_id==scenario.id,
                                         Order.status.in_(PLANNABLE_STATUSES))):
        raise HTTPException(404,"Không tìm thấy lệnh giao hàng đang chờ điều vận")
    try:
        routes[index]=insert_order_into_route(db,user.organization_id,scenario,route,body.order_id)
    except RoutingError as exc:
        raise HTTPException(422,{"code":exc.code,"message":str(exc)}) from exc
    data["unassigned"]=[x for x in data.get("unassigned",[]) if x["order_id"]!=body.order_id]
    summary=recompute_summary(data)
    p.result_json=json.dumps(data,ensure_ascii=False); p.total_cost_vnd=summary["cost_vnd"]
    audit(db,user,"ORDER_MANUALLY_ASSIGNED","Order",body.order_id,{"plan_id":p.id,"route_key":route["route_key"]}); db.commit()
    return {"plan_id":p.id,"route_key":route["route_key"],"order_id":body.order_id,"status":"ASSIGNED"}


def _number(value, cast=float):
    try:
        return cast(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _time(value):
    try:
        return _dt(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _validate_import_rows(rows):
    orders = rows.get("orders", [])
    pallets = rows.get("pallets", [])
    locations = rows.get("locations", [])
    customers = rows.get("customers", [])
    products = rows.get("products", [])
    errors = []
    order_ids = {str(x.get("order_id") or "") for x in orders}
    location_ids = {str(x.get("location_id") or "") for x in locations}
    customer_ids = {str(x.get("customer_id") or "") for x in customers}
    product_ids = {str(x.get("sku_id") or "") for x in products}
    if not rows.get("scenario"): errors.append("Thiếu sheet Scenario")
    if not orders: errors.append("Cần ít nhất một lệnh giao hàng")
    if not customers: errors.append("Sheet Customers cần ít nhất một khách hàng")
    if not products: errors.append("Sheet Products cần ít nhất một mã SKU")
    if len(order_ids) != len(orders) or "" in order_ids: errors.append("Có order_id trống hoặc trùng lặp")
    if len({str(x.get("pallet_id") or "") for x in pallets}) != len(pallets): errors.append("Có pallet_id trống hoặc trùng lặp")
    if customers and len(customer_ids) != len(customers): errors.append("Có customer_id trống hoặc trùng lặp")
    if products and len(product_ids) != len(products): errors.append("Có sku_id trống hoặc trùng lặp")
    weights = {}; volumes = {}; counts = {}
    for loc in locations:
        cid = str(loc.get("customer_id") or "")
        if cid and customers and cid not in customer_ids: errors.append(f"{loc.get('location_id')}: customer_id không có trong Customers")
        if _number(loc.get("latitude")) is None or _number(loc.get("longitude")) is None:
            errors.append(f"{loc.get('location_id')}: thiếu hoặc sai tọa độ")
    for pallet in pallets:
        pid = pallet.get("pallet_id")
        oid = str(pallet.get("order_id") or "")
        if oid not in order_ids: errors.append(f"{pid}: order_id không tồn tại")
        if str(pallet.get("sku_id") or "") not in product_ids: errors.append(f"{pid}: sku_id không có trong Products")
        values = {k: _number(pallet.get(k)) for k in ["length_cm", "width_cm", "height_cm", "weight_kg", "volume_m3"]}
        if any(values[k] is None or values[k] <= 0 for k in ["length_cm", "width_cm", "height_cm", "weight_kg"]):
            errors.append(f"{pid}: kích thước và khối lượng pallet phải là số dương")
            continue
        weights[oid] = weights.get(oid, 0) + int(values["weight_kg"])
        volumes[oid] = volumes.get(oid, 0) + float(values["volume_m3"] or 0)
        counts[oid] = counts.get(oid, 0) + 1
    for order in orders:
        oid = str(order.get("order_id") or "")
        cid = str(order.get("customer_id") or "")
        if not oid or not cid: errors.append(f"{oid or 'Lệnh'}: thiếu mã lệnh hoặc mã khách hàng")
        if cid not in customer_ids: errors.append(f"{oid}: customer_id không có trong Customers")
        if str(order.get("drop_location_id") or "") not in location_ids: errors.append(f"{oid}: drop_location_id không có trong Locations")
        ready, due = _time(order.get("ready_at")), _time(order.get("due_at"))
        if ready is None or due is None: errors.append(f"{oid}: ready_at/due_at không phải thời gian hợp lệ")
        elif due < ready: errors.append(f"{oid}: hạn giao sớm hơn thời điểm hàng sẵn sàng")
        service, weight, volume = _number(order.get("service_min"), int), _number(order.get("total_weight_kg")), _number(order.get("total_volume_m3"))
        if service is None or weight is None or volume is None:
            errors.append(f"{oid}: service_min, total_weight_kg, total_volume_m3 phải là số"); continue
        if service < 0 or weight < 0 or volume < 0: errors.append(f"{oid}: thời gian phục vụ, khối lượng và thể tích không được âm")
        if counts.get(oid, 0) == 0: errors.append(f"{oid}: lệnh chưa có dòng pallet")
        if abs(weights.get(oid, 0) - int(weight)) > 0: errors.append(f"{oid}: khối lượng lệnh không khớp tổng pallet")
        if abs(volumes.get(oid, 0) - float(volume)) > 0.01: errors.append(f"{oid}: thể tích lệnh không khớp tổng pallet")
    return errors[:100]


@app.post("/api/imports/preview")
async def import_preview(file: UploadFile = File(...), user: User = Depends(shared_actor)):
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")): raise HTTPException(415,"Chỉ nhận workbook .xlsx hoặc .xlsm")
    payload=await file.read()
    if len(payload)>15*1024*1024: raise HTTPException(413,"Workbook phải nhỏ hơn hoặc bằng 15 MB")
    with tempfile.TemporaryDirectory(prefix="fleetmix-import-") as temp_dir:
        temp_path=__import__("pathlib").Path(temp_dir)/"upload.xlsx"
        temp_path.write_bytes(payload)
        try: rows=load_workbook_rows(temp_path)
        except Exception as exc: raise HTTPException(422,f"Không đọc được workbook: {exc}")
    order_rows=rows["orders"]; pallet_rows=rows["pallets"]; location_rows=rows["locations"];errors=_validate_import_rows(rows)
    return {"filename":file.filename,"valid":not errors,"errors":errors,"counts":{"orders":len(order_rows),"pallets":len(pallet_rows),
            "locations":len(location_rows),"customers":len(rows.get("customers",[])),"products":len(rows.get("products",[]))},
            "scenario_id":rows["scenario"][0].get("scenario_id") if rows["scenario"] else None,
            "next_step":"Upload the same workbook to /api/imports/commit after reviewing this preview"}


@app.post("/api/imports/commit")
async def import_commit(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(shared_actor)):
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")): raise HTTPException(415,"Chỉ nhận workbook .xlsx hoặc .xlsm")
    payload=await file.read()
    if len(payload)>15*1024*1024: raise HTTPException(413,"Workbook phải nhỏ hơn hoặc bằng 15 MB")
    with tempfile.TemporaryDirectory(prefix="fleetmix-import-") as temp_dir:
        temp_path=__import__("pathlib").Path(temp_dir)/"upload.xlsx"
        temp_path.write_bytes(payload)
        try: rows=load_workbook_rows(temp_path)
        except Exception as exc: raise HTTPException(422,f"Không đọc được workbook: {exc}")
    errors=_validate_import_rows(rows)
    if errors: raise HTTPException(422,detail={"errors":errors})
    scenario=_scenario(db,user)
    if not rows["scenario"] or rows["scenario"][0]["scenario_id"]!=scenario.id: raise HTTPException(409,"Mã kịch bản trong workbook không khớp kịch bản đang mở")
    existing_customers = {x.id: x for x in db.scalars(select(Customer).where(Customer.organization_id == user.organization_id)).all()}
    for row in rows.get("customers", []):
        obj = existing_customers.get(row["customer_id"])
        if obj:
            obj.legal_name=row["legal_name"]; obj.display_name=row["display_name"]; obj.customer_segment=row.get("customer_segment") or ""
            obj.sales_channel=row.get("sales_channel") or ""; obj.payment_terms=row.get("payment_terms") or ""; obj.service_level=row.get("service_level") or ""
            obj.status=str(row.get("status") or "ACTIVE").upper(); obj.account_owner=row.get("account_owner") or ""
        else:
            db.add(Customer(id=row["customer_id"],organization_id=user.organization_id,legal_name=row["legal_name"],display_name=row["display_name"],
                customer_segment=row.get("customer_segment") or "",sales_channel=row.get("sales_channel") or "",payment_terms=row.get("payment_terms") or "",
                service_level=row.get("service_level") or "",status=str(row.get("status") or "ACTIVE").upper(),account_owner=row.get("account_owner") or "",is_synthetic=True))
    existing_products = {x.id: x for x in db.scalars(select(Product).where(Product.organization_id == user.organization_id)).all()}
    for row in rows.get("products", []):
        obj = existing_products.get(row["sku_id"])
        if obj:
            obj.name=row["sku_name"]; obj.category=row.get("category") or ""; obj.base_uom=row.get("base_uom") or ""
            obj.handling_code=str(row.get("handling_code") or "GENERAL").upper(); obj.stackable_default=bool(row.get("stackable_default", True))
            obj.rotation_rule=str(row.get("rotation_rule") or "BASE_ROTATION_ALLOWED"); obj.status=str(row.get("status") or "ACTIVE").upper()
        else:
            db.add(Product(id=row["sku_id"],organization_id=user.organization_id,name=row["sku_name"],category=row.get("category") or "",
                base_uom=row.get("base_uom") or "",handling_code=str(row.get("handling_code") or "GENERAL").upper(),
                stackable_default=bool(row.get("stackable_default", True)),rotation_rule=str(row.get("rotation_rule") or "BASE_ROTATION_ALLOWED"),
                status=str(row.get("status") or "ACTIVE").upper(),is_synthetic=True))
    locs={x.id:x for x in db.scalars(select(Location).where(Location.organization_id==user.organization_id,Location.scenario_id==scenario.id)).all()}
    for row in rows["locations"]:
        if row["location_id"] in locs:
            obj=locs[row["location_id"]]; obj.customer_id=row.get("customer_id") or None; obj.name=row["location_name"];obj.zone=row["district_or_zone"];obj.address=row["address_text"]
            obj.latitude=float(row["latitude"]);obj.longitude=float(row["longitude"])
            obj.open_from=_clock(row.get("open_from"),obj.open_from or "00:00");obj.open_until=_clock(row.get("open_until"),obj.open_until or "23:59")
            if row.get("service_min_default") not in (None,""): obj.service_min_default=int(row["service_min_default"])
        else:
            obj=Location(id=row["location_id"],organization_id=user.organization_id,scenario_id=scenario.id,customer_id=row.get("customer_id") or None,name=row["location_name"],zone=row["district_or_zone"],
                address=row["address_text"],latitude=float(row["latitude"]),longitude=float(row["longitude"]),open_from=_clock(row.get("open_from"),"00:00"),
                open_until=_clock(row.get("open_until"),"23:59"),service_min_default=int(row["service_min_default"]),location_type=row["location_type"],is_synthetic=True);db.add(obj)
    db.flush(); existing={x.id:x for x in db.scalars(select(Order).where(Order.organization_id==user.organization_id,Order.scenario_id==scenario.id)).all()}
    for row in rows["orders"]:
        if row["drop_location_id"] not in locs and row["drop_location_id"] not in {x["location_id"] for x in rows["locations"]}: raise HTTPException(422,f"Lệnh {row['order_id']} có điểm giao không tồn tại")
        oid=row["order_id"]; obj=existing.get(oid)
        if obj:
            obj.customer_id=row["customer_id"];obj.order_type=row["order_type"];obj.drop_location_id=row["drop_location_id"];obj.ready_at=_dt(row["ready_at"])
            obj.due_at=_dt(row["due_at"]);obj.service_min=int(row["service_min"]);obj.priority=str(row["priority"]).upper();obj.status=str(row["status"]).upper()
            obj.total_weight_kg=int(row["total_weight_kg"]);obj.total_volume_m3=float(row["total_volume_m3"]);obj.minimum_vehicle_class=row["minimum_vehicle_class"];obj.notes=str(row.get("notes") or "")
            for old in db.scalars(select(Pallet).where(Pallet.order_id==oid, Pallet.organization_id==user.organization_id)).all(): db.delete(old)
        else:
            obj=Order(id=oid,organization_id=user.organization_id,scenario_id=scenario.id,external_id=oid,customer_id=row["customer_id"],order_type=row["order_type"],
                drop_location_id=row["drop_location_id"],ready_at=_dt(row["ready_at"]),due_at=_dt(row["due_at"]),service_min=int(row["service_min"]),priority=str(row["priority"]).upper(),
                status=str(row["status"]).upper(),split_allowed=bool(row["split_allowed"]),total_weight_kg=int(row["total_weight_kg"]),total_volume_m3=float(row["total_volume_m3"]),
                minimum_vehicle_class=row["minimum_vehicle_class"],notes=str(row.get("notes") or ""),is_synthetic=True);db.add(obj)
    db.flush()
    for row in rows["pallets"]:
        db.add(Pallet(id=row["pallet_id"],organization_id=user.organization_id,scenario_id=scenario.id,order_id=row["order_id"],sku_id=row["sku_id"],description=row["description"],
            weight_kg=int(row["weight_kg"]),length_cm=int(row["length_cm"]),width_cm=int(row["width_cm"]),height_cm=int(row["height_cm"]),volume_m3=float(row["volume_m3"]),
            stackable=bool(row["stackable"]),max_stack=int(row["max_stack"]),rotation_rule=row["rotation_rule"],handling_code=row["handling_code"],drop_location_id=row["drop_location_id"],is_synthetic=True))
    audit(db,user,"WORKBOOK_IMPORTED","Scenario",scenario.id,{"orders":len(rows["orders"]),"pallets":len(rows["pallets"]),
        "customers":len(rows.get("customers",[])),"products":len(rows.get("products",[])),"source":"uploaded workbook"});db.commit()
    return {"scenario_id":scenario.id,"orders_upserted":len(rows["orders"]),"pallets_replaced":len(rows["pallets"]),
        "customers_upserted":len(rows.get("customers",[])),"products_upserted":len(rows.get("products",[])),"status":"COMMITTED"}


@app.get("/api/audit")
def audit_log(db: Session=Depends(get_db),user: User=Depends(shared_actor)):
    rows=db.scalars(select(AuditEvent).where(AuditEvent.organization_id==user.organization_id).order_by(AuditEvent.created_at.desc()).limit(100)).all()
    return {"events":[{"id":x.id,"action":x.action,"entity_type":x.entity_type,"entity_id":x.entity_id,"details":json.loads(x.details_json),"created_at":x.created_at.isoformat()} for x in rows]}


@app.post("/api/ai/quote-extract")
def quote_extract(body: dict, db: Session=Depends(get_db), user: User=Depends(shared_actor)):
    text=str(body.get("text", ""))[:10000]
    if len(text.strip())<3: raise HTTPException(422,"Cần nhập nội dung báo giá")
    def num(pattern, scale=1):
        m=re.search(pattern,text,re.I)
        if not m:return None
        raw=next((group for group in m.groups() if group), m.group(0))
        if scale == 1: return round(float(raw.replace(",", "").replace(".", "")))
        return round(float(raw.replace(",", "."))*scale, 4)
    parsed={"rate_per_km_vnd":num(r"(?:([\d.,]+)\s*(?:₫|đ|vnd)\s*(?:/km|per\s*km|mỗi\s*km)|(?:km|kilomet|/km)[^\d]{0,15}([\d.,]+))")}
    parsed["minimum_fare_vnd"]=num(r"(?:minimum|min fare|tối thiểu|giá sàn)[^\d]{0,20}([\d.,]+)")
    parsed["callout_fee_vnd"]=num(r"(?:call.?out|dispatch|điều xe)[^\d]{0,20}([\d.,]+)")
    parsed["stop_fee_vnd"]=num(r"(?:stop|điểm dừng|mỗi điểm)[^\d]{0,20}([\d.,]+)")
    parsed["vat_rate_assumption"]=num(r"(?:vat|thuế)[^\d]{0,8}(\d+(?:\.\d+)?)",.01)
    parsed["return_trip_rule"]="ROUND_TRIP" if re.search(r"round.?trip|khứ hồi|hai chiều",text,re.I) else "ONE_WAY"
    confidence=sum(v is not None for k,v in parsed.items() if k!="return_trip_rule")/4
    audit(db,user,"QUOTE_TERMS_EXTRACTED","CarrierQuote","unsaved-draft",{"source":"LOCAL_RULES","confidence":round(confidence,2)})
    db.commit()
    return {"source":"LOCAL_RULES","ai_model_used":False,"confidence":round(confidence,2),"needs_human_review":True,"fields":parsed,
            "note":"Extracted fields are suggestions only. Verify source, units, currency, validity and tax before saving a quote."}
