import json
import uuid

from sqlalchemy import select

from app.models import FleetVehicle, OptimizationRun, Order, Pallet, Plan, VehicleClass
from app.services.optimizer import optimize
from app.services.packing import pack_floor
from app.services.seed import ORG_ID, SHARED_ACTOR_ID


def test_operations_are_open_without_login(client):
    assert client.get("/api/auth/me").status_code == 404
    assert client.post("/api/auth/login", json={"email":"nobody@example.test","password":"unused"}).status_code == 404
    assert client.get("/api/dashboard").status_code == 200
    response=client.post("/api/employees",json={"employee_code":"LOG-TEST","name":"Test Operator","email":"operator@example.test","position":"Điều phối"})
    assert response.status_code==200,response.text
    assert response.json()["employee"]["department"]=="LOGISTICS"
    assert "password_hash" not in response.json()["employee"]
    assert len(client.get("/api/employees").json()["employees"])==5

def test_optimizer_persists_plan_and_approval_booking_gate(client,db_session):
    queued=client.post("/api/optimization-runs",json={"objective":"BALANCED","include_carriers":False,"time_limit_seconds":2})
    assert queued.status_code==202,queued.text
    job_id=queued.json()["id"]
    result=optimize(db_session,job_id,ORG_ID,SHARED_ACTOR_ID,{"objective":"BALANCED","include_carriers":False,"time_limit_seconds":2})
    ids=[s["order_id"] for r in result["routes"] for s in r["stops"]]+[x["order_id"] for x in result["unassigned"]]
    assert len(ids)==len(set(ids))==24
    assert all(r["load"]["feasible"] and r["load"]["packing"]["status"].startswith("PASS") for r in result["routes"])
    plan_id=result["plan_id"]
    premature=client.post(f"/api/plans/{plan_id}/booking-drafts")
    assert premature.status_code==409
    approved=client.post(f"/api/plans/{plan_id}/approval",json={"decision":"APPROVE","comment":"Reviewed by logistics employee"})
    assert approved.status_code==200 and approved.json()["status"]=="APPROVED"
    drafts=client.post(f"/api/plans/{plan_id}/booking-drafts")
    assert drafts.status_code==200 and drafts.json()["external_submission"] is False
    assert client.get("/api/plans/latest").json()["plan"]["plan_status"]=="APPROVED"


def test_quote_extraction_is_review_only(client):
    response=client.post("/api/ai/quote-extract",json={"text":"Xe tải 1.5 tấn giá 15.500đ/km, phí điều xe 100.000đ, tối thiểu 360.000đ, điểm dừng thêm 20.000đ, VAT 10%"})
    assert response.status_code==200,response.text
    data=response.json()
    assert data["ai_model_used"] is False
    assert data["needs_human_review"] is True
    assert data["fields"]["rate_per_km_vnd"]==15500
    assert data["fields"]["minimum_fare_vnd"]==360000


def test_manual_assignment_refuses_a_missed_time_window(client,db_session):
    import uuid
    from datetime import datetime, time
    from app.models import Scenario, User
    from app.services.packing import pack_floor
    scenario=db_session.scalar(select(Scenario).where(Scenario.organization_id==ORG_ID))
    chosen=None
    for vehicle in db_session.scalars(select(FleetVehicle).where(FleetVehicle.scenario_id==scenario.id,FleetVehicle.status=="AVAILABLE")).all():
        vc=db_session.get(VehicleClass,vehicle.vehicle_class_id)
        orders=db_session.scalars(select(Order).where(Order.scenario_id==scenario.id,Order.minimum_vehicle_class=="ANY_COMPATIBLE")).all()
        for order in orders:
            pallets=db_session.scalars(select(Pallet).where(Pallet.order_id==order.id)).all()
            packing=pack_floor([{"pallet_id":p.id,"length_cm":p.length_cm,"width_cm":p.width_cm,"height_cm":p.height_cm,"rotation_rule":p.rotation_rule} for p in pallets],vehicle.inner_length_cm,vehicle.inner_width_cm,vehicle.inner_height_cm)
            if packing["status"].startswith("PASS") and order.total_weight_kg<=vehicle.capacity_kg and order.total_volume_m3<=vehicle.usable_volume_m3:
                chosen=(vehicle,vc,order,packing);break
        if chosen:break
    assert chosen is not None
    vehicle,vc,order,packing=chosen
    order.ready_at=datetime.combine(order.ready_at.date(),time(7,0));order.due_at=order.ready_at;db_session.flush()
    run_id=str(uuid.uuid4())
    db_session.add(OptimizationRun(id=run_id,organization_id=ORG_ID,scenario_id=scenario.id,created_by_id=SHARED_ACTOR_ID,status="SUCCEEDED"))
    route_key=vehicle.id
    route={"route_key":route_key,"vehicle_id":vehicle.id,"vehicle_name":vehicle.plate_number,"kind":"INTERNAL","carrier_id":None,"carrier_name":None,
        "quote_id":None,"state":"PLANNED","status":"DRAFT","stops":[],"distance_km":0,"duration_min":0,"cost_vnd":vehicle.fixed_cost_vnd,
        "load":{"feasible":True,"weight_kg":0,"volume_m3":0,"errors":[],"packing":{"status":"PASS_2D_FLOOR_ONLY","placements":[],"reason":"test"}},
        "vehicle":{"capacity_kg":vehicle.capacity_kg,"usable_volume_m3":vehicle.usable_volume_m3,"inner_length_cm":vehicle.inner_length_cm,
            "inner_width_cm":vehicle.inner_width_cm,"inner_height_cm":vehicle.inner_height_cm,"class_id":vehicle.vehicle_class_id,"class_rank":vc.class_rank,
            "available_from":vehicle.available_from.strftime("%H:%M"),"available_until":vehicle.available_until.strftime("%H:%M")}}
    plan_id=str(uuid.uuid4())
    db_session.add(Plan(id=plan_id,organization_id=ORG_ID,scenario_id=scenario.id,optimization_run_id=run_id,version=1,status="DRAFT",objective="BALANCED",
        total_cost_vnd=vehicle.fixed_cost_vnd,result_json=json.dumps({"routes":[route],"unassigned":[{"order_id":order.id,"reason":"test"}],
        "summary":{"orders_total":1,"assigned":0,"unassigned":1,"vehicles_used":1,"distance_km":0,"cost_vnd":vehicle.fixed_cost_vnd}}),created_by_id=SHARED_ACTOR_ID))
    db_session.commit()
    response=client.post(f"/api/plans/{plan_id}/assign",json={"order_id":order.id,"route_key":route_key})
    assert response.status_code==422
    assert "time window" in response.json()["detail"]


def test_replan_preserves_started_routes(client,db_session):
    queued=client.post("/api/optimization-runs",json={"objective":"BALANCED","include_carriers":False,"time_limit_seconds":2})
    first=optimize(db_session,queued.json()["id"],ORG_ID,SHARED_ACTOR_ID,{"objective":"BALANCED","include_carriers":False,"time_limit_seconds":2})
    assert first["routes"]
    route=first["routes"][0]
    locked=client.patch(f"/api/plans/{first['plan_id']}/routes/{route['route_key']}/state",json={"state":"ACTIVE"})
    assert locked.status_code==200
    next_job=client.post("/api/optimization-runs",json={"objective":"BALANCED","include_carriers":False,"time_limit_seconds":2})
    job=db_session.get(OptimizationRun,next_job.json()["id"])
    config=json.loads(job.config_json)
    assert any(r["route_key"]==route["route_key"] for r in config["locked_routes"])
    second=optimize(db_session,job.id,ORG_ID,SHARED_ACTOR_ID,config)
    preserved=next(r for r in second["routes"] if r["route_key"]==route["route_key"])
    assert preserved["state"]=="ACTIVE"
    assigned=[s["order_id"] for r in second["routes"] for s in r["stops"]]
    assert len(assigned)==len(set(assigned))


def test_import_preview_then_commit_updates_active_scenario(client,db_session):
    from pathlib import Path
    workbook=Path(__file__).resolve().parents[2]/"outputs"/"01a1cbad-1a1e-7de1-899b-92bedce65edf"/"FleetMix_ERP_Operational_Dataset.xlsx"
    with workbook.open("rb") as stream:
        preview=client.post("/api/imports/preview",files={"file":(workbook.name,stream,"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert preview.status_code==200,preview.text
    assert preview.json()["valid"] is True
    with workbook.open("rb") as stream:
        committed=client.post("/api/imports/commit",files={"file":(workbook.name,stream,"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert committed.status_code==200,committed.text
    assert db_session.scalar(select(Order).where(Order.external_id=="DO-HCM-20261113-0001")).total_weight_kg==1369


def test_import_rejects_order_totals_that_do_not_match_pallets(client):
    from io import BytesIO
    from pathlib import Path
    from openpyxl import load_workbook
    workbook=Path(__file__).resolve().parents[2]/"outputs"/"01a1cbad-1a1e-7de1-899b-92bedce65edf"/"FleetMix_ERP_Operational_Dataset.xlsx"
    book=load_workbook(workbook)
    sheet=book["Orders"]
    columns={cell.value:index for index,cell in enumerate(sheet[1],start=1)}
    sheet.cell(2,columns["total_weight_kg"],1468)
    buffer=BytesIO();book.save(buffer);payload=buffer.getvalue()
    upload=("bad-totals.xlsx",payload,"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    preview=client.post("/api/imports/preview",files={"file":upload})
    assert preview.status_code==200 and preview.json()["valid"] is False
    assert any("weight does not match" in error for error in preview.json()["errors"])
    commit=client.post("/api/imports/commit",files={"file":upload})
    assert commit.status_code==422
