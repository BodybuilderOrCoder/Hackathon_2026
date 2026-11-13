import uuid
from datetime import datetime, time
from pathlib import Path

from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import (Availability, Carrier, CarrierQuote, Customer, DistanceMatrix, FleetVehicle, Location,
                      Order, Organization, Pallet, Product, Scenario, User, VehicleClass)
from ..security import hash_password

ORG_ID = "ORG-AP-001"


def _rows(book, name):
    ws = book[name]
    rows = ws.iter_rows(values_only=True)
    headers = [str(v) if v is not None else "" for v in next(rows)]
    return [dict(zip(headers, row)) for row in rows if any(v is not None for v in row)]


def _dt(value, fallback=None):
    if isinstance(value, datetime): return value
    if value is None: return fallback or datetime.utcnow()
    return datetime.fromisoformat(str(value))


def _clock(value, fallback="00:00"):
    return value.strftime("%H:%M") if isinstance(value, (datetime, time)) else str(value or fallback)[:5]


def load_workbook_rows(path: Path) -> dict[str, list[dict]]:
    if not path.exists(): raise FileNotFoundError(f"Seed workbook does not exist: {path}")
    wb = load_workbook(path, data_only=True, read_only=True)
    names = {"organization": "Organization", "scenario": "Scenario", "customers": "Customers", "products": "Products",
             "employees": "Employees", "orders": "Orders", "pallets": "Pallets", "locations": "Locations",
             "fleet": "Fleet", "classes": "Vehicle Classes", "carriers": "Carriers",
             "quotes": "Carrier Rates", "availability": "Availability", "distances": "Distance Matrix"}
    result = {key: _rows(wb, sheet) if sheet in wb.sheetnames else [] for key, sheet in names.items()}
    wb.close()
    return result


def seed_database(db: Session, password: str | None = None, path: Path | None = None) -> None:
    if db.scalar(select(Scenario).limit(1)): return
    settings = get_settings()
    rows = load_workbook_rows(path or settings.seed_path)
    scenario = rows["scenario"][0]
    organization = rows["organization"][0] if rows["organization"] else {}
    organization_id = str(organization.get("organization_id") or ORG_ID)
    org = Organization(id=organization_id, name=organization.get("legal_name") or "An Phúc Logistics Reference",
                       display_name=organization.get("display_name") or "An Phúc Distribution",
                       business_unit=organization.get("business_unit") or "Trung tâm Vận hành Logistics",
                       timezone=organization.get("timezone") or scenario.get("timezone") or "Asia/Ho_Chi_Minh",
                       is_synthetic=bool(organization.get("is_synthetic", True)))
    db.add(org)
    db.add(Scenario(id=scenario["scenario_id"], organization_id=organization_id, name=scenario["scenario_name"],
                    operation_date=_dt(scenario["operation_date"]), depot_id=scenario["depot_id"],
                    currency=scenario.get("currency") or "VND", timezone=scenario.get("timezone") or "Asia/Ho_Chi_Minh",
                    data_provenance=scenario.get("data_provenance") or "SYNTHETIC_SAMPLE",
                    planning_start=_dt(scenario["planning_start"]), planning_end=_dt(scenario["planning_end"])))
    db.flush()
    for row in rows["customers"]:
        db.add(Customer(id=row["customer_id"], organization_id=organization_id, legal_name=row["legal_name"],
                        display_name=row["display_name"], customer_segment=row.get("customer_segment") or "",
                        sales_channel=row.get("sales_channel") or "", payment_terms=row.get("payment_terms") or "",
                        service_level=row.get("service_level") or "", status=str(row.get("status") or "ACTIVE").upper(),
                        account_owner=row.get("account_owner") or "", is_synthetic=bool(row.get("is_synthetic", True))))
    for row in rows["products"]:
        db.add(Product(id=row["sku_id"], organization_id=organization_id, name=row["sku_name"], category=row.get("category") or "",
                       base_uom=row.get("base_uom") or "", handling_code=str(row.get("handling_code") or "GENERAL").upper(),
                       stackable_default=bool(row.get("stackable_default", True)), rotation_rule=str(row.get("rotation_rule") or "BASE_ROTATION_ALLOWED"),
                       status=str(row.get("status") or "ACTIVE").upper(), is_synthetic=bool(row.get("is_synthetic", True))))
    db.flush()
    for row in rows["classes"]:
        db.add(VehicleClass(id=row["vehicle_class"], organization_id=ORG_ID, class_rank=int(row["class_rank"]),
                            vehicle_type=row["vehicle_type"], capacity_kg=int(row["capacity_kg"]),
                            usable_volume_m3=float(row["usable_volume_m3"]), inner_length_cm=int(row["inner_length_cm"]),
                            inner_width_cm=int(row["inner_width_cm"]), inner_height_cm=int(row["inner_height_cm"]),
                            is_synthetic=bool(row.get("is_synthetic", True))))
    db.flush()
    for row in rows["locations"]:
        db.add(Location(id=row["location_id"], organization_id=organization_id, scenario_id=scenario["scenario_id"],
                        customer_id=row.get("customer_id") or None,
                        name=row["location_name"], zone=row["district_or_zone"], address=row["address_text"],
                        latitude=float(row["latitude"]), longitude=float(row["longitude"]), open_from=_clock(row["open_from"]),
                        open_until=_clock(row["open_until"]), service_min_default=int(row["service_min_default"]),
                        location_type=row["location_type"], is_synthetic=bool(row.get("is_synthetic", True))))
    for row in rows["fleet"]:
        db.add(FleetVehicle(id=row["vehicle_id"], organization_id=organization_id, scenario_id=scenario["scenario_id"],
                            fleet_type=row["fleet_type"], vehicle_class_id=row["vehicle_class"], plate_number=row["plate_number"],
                            capacity_kg=int(row["capacity_kg"]), usable_volume_m3=float(row["usable_volume_m3"]),
                            inner_length_cm=int(row["inner_length_cm"]), inner_width_cm=int(row["inner_width_cm"]),
                            inner_height_cm=int(row["inner_height_cm"]), fixed_cost_vnd=int(row["fixed_cost_vnd"]),
                            cost_per_km_vnd=int(row["cost_per_km_vnd"]), available_from=_dt(row["available_from"]),
                            available_until=_dt(row["available_until"]), start_depot_id=row["start_depot_id"],
                            status=str(row["status"]).upper(), is_synthetic=bool(row.get("is_synthetic", True))))
    for row in rows["carriers"]:
        db.add(Carrier(id=row["carrier_id"], organization_id=organization_id, name=row["carrier_name"], base_area=row["base_area"],
                       service_area=row["service_area"], source_type=row.get("source_type") or "SYNTHETIC",
                       is_synthetic=bool(row.get("is_synthetic", True))))
    db.flush()
    for row in rows["quotes"]:
        db.add(CarrierQuote(id=row["quote_id"], organization_id=organization_id, scenario_id=scenario["scenario_id"],
                            carrier_id=row["carrier_id"], vehicle_class_id=row["vehicle_class"], capacity_kg=int(row["capacity_kg"]),
                            usable_volume_m3=float(row["usable_volume_m3"]), inner_length_cm=int(row["inner_length_cm"]),
                            inner_width_cm=int(row["inner_width_cm"]), inner_height_cm=int(row["inner_height_cm"]),
                            rate_per_km_vnd=int(row["rate_per_km_vnd"]), callout_fee_vnd=int(row["callout_fee_vnd"]),
                            minimum_fare_vnd=int(row["minimum_fare_vnd"]), waiting_free_min=int(row["waiting_free_min"]),
                            waiting_fee_per_hour_vnd=int(row["waiting_fee_per_hour_vnd"]), stop_fee_vnd=int(row["stop_fee_vnd"]),
                            return_trip_rule=row["return_trip_rule"], vat_rate_assumption=float(row["vat_rate_assumption"]),
                            valid_from=_dt(row["valid_from"]), valid_until=_dt(row["valid_until"]),
                            status=str(row["quote_status"]).upper(), is_synthetic=bool(row.get("is_synthetic", True))))
    db.flush()
    for row in rows["availability"]:
        available = row.get("vehicles_available", 0)
        if isinstance(available, datetime): available = (available - datetime(1899, 12, 30)).days
        db.add(Availability(id=row["availability_id"], organization_id=organization_id, scenario_id=row["scenario_id"],
                            carrier_id=row["carrier_id"], vehicle_class_id=row["vehicle_class"],
                            window_start=_dt(row["window_start"]), window_end=_dt(row["window_end"]),
                            vehicles_available=max(0, int(available or 0)), confirmation_status=str(row["confirmation_status"]).upper(),
                            confirmed_at=_dt(row["confirmed_at"]) if row.get("confirmed_at") else None,
                            is_synthetic=bool(row.get("is_synthetic", True))))
    for row in rows["orders"]:
        order = Order(id=row["order_id"], organization_id=organization_id, scenario_id=row["scenario_id"], external_id=row["order_id"],
                      customer_id=row["customer_id"], order_type=row["order_type"], drop_location_id=row["drop_location_id"],
                      ready_at=_dt(row["ready_at"]), due_at=_dt(row["due_at"]), service_min=int(row["service_min"]),
                      priority=str(row["priority"]).upper(), status=str(row["status"]).upper(), split_allowed=bool(row["split_allowed"]),
                      total_weight_kg=int(row["total_weight_kg"]), total_volume_m3=float(row["total_volume_m3"]),
                      minimum_vehicle_class=row["minimum_vehicle_class"], notes=str(row.get("notes") or ""), is_synthetic=True)
        db.add(order)
    db.flush()
    for row in rows["pallets"]:
        db.add(Pallet(id=row["pallet_id"], organization_id=organization_id, scenario_id=row["scenario_id"], order_id=row["order_id"],
                      sku_id=row["sku_id"], description=row["description"], weight_kg=int(row["weight_kg"]),
                      length_cm=int(row["length_cm"]), width_cm=int(row["width_cm"]), height_cm=int(row["height_cm"]),
                      volume_m3=float(row["volume_m3"]), stackable=bool(row["stackable"]), max_stack=int(row["max_stack"]),
                      rotation_rule=str(row["rotation_rule"]), handling_code=str(row["handling_code"]),
                      drop_location_id=row["drop_location_id"], is_synthetic=True))
    db.flush()
    # Matrix workbook can include one-way pairs; optimizer reads direct distances and falls back symmetrically.
    for row in rows["distances"]:
        db.add(DistanceMatrix(organization_id=organization_id, scenario_id=row["scenario_id"],
                              from_location_id=row["from_location_id"], to_location_id=row["to_location_id"],
                              distance_km=float(row["distance_km"]), drive_time_min=int(row["drive_time_min"]),
                              source=str(row["source"]), matrix_version=str(row["matrix_version"]), is_synthetic=True))
    demo_password = password or settings.fleetmix_demo_password
    employee_rows = rows["employees"] or [
        {"user_id": "USR-LOG-0001", "full_name": "Nguyễn Thị Minh Anh", "email": "minh.anh@anphuc-logistics.example", "employee_code": "EMP-LOG-0001", "position": "Chuyên viên điều vận"},
        {"user_id": "USR-LOG-0002", "full_name": "Trần Quốc Bảo", "email": "quoc.bao@anphuc-logistics.example", "employee_code": "EMP-LOG-0002", "position": "Chuyên viên kế hoạch vận tải"},
        {"user_id": "USR-LOG-0003", "full_name": "Lê Hoàng Phúc", "email": "hoang.phuc@anphuc-logistics.example", "employee_code": "EMP-LOG-0003", "position": "Chuyên viên mua dịch vụ vận tải"},
        {"user_id": "USR-LOG-0004", "full_name": "Phạm Ngọc Hân", "email": "ngoc.han@anphuc-logistics.example", "employee_code": "EMP-LOG-0004", "position": "Chuyên viên kiểm soát cước"},
    ]
    for row in employee_rows:
        db.add(User(id=row["user_id"], organization_id=organization_id, full_name=row["full_name"],
                    employee_code=row["employee_code"], position=row.get("position") or "Nhân viên logistics",
                    department=str(row.get("department") or "LOGISTICS"), phone=str(row.get("phone") or ""),
                    email=row["email"], role="LOGISTICS_STAFF", password_hash=hash_password(demo_password),
                    active=bool(row.get("active", True))))
    db.commit()
