from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now_utc() -> datetime:
    return datetime.utcnow()


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    business_unit: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Ho_Chi_Minh", nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    employee_code: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    department: Mapped[str] = mapped_column(String(80), default="LOGISTICS", nullable=False)
    position: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    phone: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    role: Mapped[str] = mapped_column(String(32), index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)


class Scenario(Base):
    __tablename__ = "scenarios"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    operation_date: Mapped[datetime] = mapped_column(DateTime)
    depot_id: Mapped[str] = mapped_column(String(80))
    currency: Mapped[str] = mapped_column(String(3), default="VND")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Ho_Chi_Minh")
    data_provenance: Mapped[str] = mapped_column(String(40), default="SYNTHETIC_SAMPLE")
    planning_start: Mapped[datetime] = mapped_column(DateTime)
    planning_end: Mapped[datetime] = mapped_column(DateTime)


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    legal_name: Mapped[str] = mapped_column(String(180), nullable=False)
    display_name: Mapped[str] = mapped_column(String(140), nullable=False)
    customer_segment: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    sales_channel: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    payment_terms: Mapped[str] = mapped_column(String(24), default="", nullable=False)
    service_level: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="ACTIVE", index=True)
    account_owner: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Product(Base):
    __tablename__ = "products"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    category: Mapped[str] = mapped_column(String(48), default="", nullable=False)
    base_uom: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    handling_code: Mapped[str] = mapped_column(String(32), default="GENERAL", nullable=False)
    stackable_default: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rotation_rule: Mapped[str] = mapped_column(String(40), default="BASE_ROTATION_ALLOWED", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="ACTIVE", index=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Location(Base):
    __tablename__ = "locations"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    scenario_id: Mapped[str] = mapped_column(ForeignKey("scenarios.id"), index=True)
    customer_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(180))
    zone: Mapped[str] = mapped_column(String(120))
    address: Mapped[str] = mapped_column(String(255))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    open_from: Mapped[str] = mapped_column(String(8))
    open_until: Mapped[str] = mapped_column(String(8))
    service_min_default: Mapped[int] = mapped_column(Integer, default=15)
    location_type: Mapped[str] = mapped_column(String(24))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)


class VehicleClass(Base):
    __tablename__ = "vehicle_classes"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    class_rank: Mapped[int] = mapped_column(Integer)
    vehicle_type: Mapped[str] = mapped_column(String(32))
    capacity_kg: Mapped[int] = mapped_column(Integer)
    usable_volume_m3: Mapped[float] = mapped_column(Float)
    inner_length_cm: Mapped[int] = mapped_column(Integer)
    inner_width_cm: Mapped[int] = mapped_column(Integer)
    inner_height_cm: Mapped[int] = mapped_column(Integer)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)


class FleetVehicle(Base):
    __tablename__ = "fleet_vehicles"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    scenario_id: Mapped[str] = mapped_column(ForeignKey("scenarios.id"), index=True)
    fleet_type: Mapped[str] = mapped_column(String(24))
    vehicle_class_id: Mapped[str] = mapped_column(ForeignKey("vehicle_classes.id"), index=True)
    plate_number: Mapped[str] = mapped_column(String(48))
    capacity_kg: Mapped[int] = mapped_column(Integer)
    usable_volume_m3: Mapped[float] = mapped_column(Float)
    inner_length_cm: Mapped[int] = mapped_column(Integer)
    inner_width_cm: Mapped[int] = mapped_column(Integer)
    inner_height_cm: Mapped[int] = mapped_column(Integer)
    fixed_cost_vnd: Mapped[int] = mapped_column(Integer)
    cost_per_km_vnd: Mapped[int] = mapped_column(Integer)
    available_from: Mapped[datetime] = mapped_column(DateTime)
    available_until: Mapped[datetime] = mapped_column(DateTime)
    start_depot_id: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(24), index=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    vehicle_class: Mapped[VehicleClass] = relationship()


class Carrier(Base):
    __tablename__ = "carriers"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(180))
    base_area: Mapped[str] = mapped_column(String(120))
    service_area: Mapped[str] = mapped_column(String(180))
    source_type: Mapped[str] = mapped_column(String(32), default="SYNTHETIC")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)


class CarrierQuote(Base):
    __tablename__ = "carrier_quotes"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    scenario_id: Mapped[str] = mapped_column(ForeignKey("scenarios.id"), index=True)
    carrier_id: Mapped[str] = mapped_column(ForeignKey("carriers.id"), index=True)
    vehicle_class_id: Mapped[str] = mapped_column(ForeignKey("vehicle_classes.id"), index=True)
    capacity_kg: Mapped[int] = mapped_column(Integer)
    usable_volume_m3: Mapped[float] = mapped_column(Float)
    inner_length_cm: Mapped[int] = mapped_column(Integer)
    inner_width_cm: Mapped[int] = mapped_column(Integer)
    inner_height_cm: Mapped[int] = mapped_column(Integer)
    rate_per_km_vnd: Mapped[int] = mapped_column(Integer)
    callout_fee_vnd: Mapped[int] = mapped_column(Integer)
    minimum_fare_vnd: Mapped[int] = mapped_column(Integer)
    waiting_free_min: Mapped[int] = mapped_column(Integer)
    waiting_fee_per_hour_vnd: Mapped[int] = mapped_column(Integer)
    stop_fee_vnd: Mapped[int] = mapped_column(Integer)
    return_trip_rule: Mapped[str] = mapped_column(String(24))
    vat_rate_assumption: Mapped[float] = mapped_column(Float)
    valid_from: Mapped[datetime] = mapped_column(DateTime)
    valid_until: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(32), index=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    carrier: Mapped[Carrier] = relationship()
    vehicle_class: Mapped[VehicleClass] = relationship()


class Availability(Base):
    __tablename__ = "carrier_availability"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    scenario_id: Mapped[str] = mapped_column(ForeignKey("scenarios.id"), index=True)
    carrier_id: Mapped[str] = mapped_column(ForeignKey("carriers.id"), index=True)
    vehicle_class_id: Mapped[str] = mapped_column(ForeignKey("vehicle_classes.id"), index=True)
    window_start: Mapped[datetime] = mapped_column(DateTime)
    window_end: Mapped[datetime] = mapped_column(DateTime)
    vehicles_available: Mapped[int] = mapped_column(Integer)
    confirmation_status: Mapped[str] = mapped_column(String(24), index=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("organization_id", "scenario_id", "external_id", name="uq_order_tenant_scenario_external"),)
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    scenario_id: Mapped[str] = mapped_column(ForeignKey("scenarios.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(80))
    customer_id: Mapped[str] = mapped_column(String(80))
    order_type: Mapped[str] = mapped_column(String(32))
    drop_location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"), index=True)
    ready_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    due_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    service_min: Mapped[int] = mapped_column(Integer)
    priority: Mapped[str] = mapped_column(String(16), default="NORMAL")
    status: Mapped[str] = mapped_column(String(24), default="READY", index=True)
    split_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    total_weight_kg: Mapped[int] = mapped_column(Integer)
    total_volume_m3: Mapped[float] = mapped_column(Float)
    minimum_vehicle_class: Mapped[str] = mapped_column(String(64), default="ANY_COMPATIBLE")
    notes: Mapped[str] = mapped_column(Text, default="")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    pallets: Mapped[list["Pallet"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class Pallet(Base):
    __tablename__ = "pallets"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    scenario_id: Mapped[str] = mapped_column(ForeignKey("scenarios.id"), index=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    sku_id: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(180))
    weight_kg: Mapped[int] = mapped_column(Integer)
    length_cm: Mapped[int] = mapped_column(Integer)
    width_cm: Mapped[int] = mapped_column(Integer)
    height_cm: Mapped[int] = mapped_column(Integer)
    volume_m3: Mapped[float] = mapped_column(Float)
    stackable: Mapped[bool] = mapped_column(Boolean, default=False)
    max_stack: Mapped[int] = mapped_column(Integer, default=1)
    rotation_rule: Mapped[str] = mapped_column(String(40))
    handling_code: Mapped[str] = mapped_column(String(32))
    drop_location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    order: Mapped[Order] = relationship(back_populates="pallets")


class DistanceMatrix(Base):
    __tablename__ = "distance_matrix"
    __table_args__ = (UniqueConstraint("organization_id", "scenario_id", "from_location_id", "to_location_id", name="uq_matrix_pair"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    scenario_id: Mapped[str] = mapped_column(ForeignKey("scenarios.id"), index=True)
    from_location_id: Mapped[str] = mapped_column(String(80))
    to_location_id: Mapped[str] = mapped_column(String(80))
    distance_km: Mapped[float] = mapped_column(Float)
    drive_time_min: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(80))
    matrix_version: Mapped[str] = mapped_column(String(80))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)


class OptimizationRun(Base):
    __tablename__ = "optimization_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    scenario_id: Mapped[str] = mapped_column(ForeignKey("scenarios.id"), index=True)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(24), default="QUEUED", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    input_snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Plan(Base):
    __tablename__ = "plans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    scenario_id: Mapped[str] = mapped_column(ForeignKey("scenarios.id"), index=True)
    optimization_run_id: Mapped[str] = mapped_column(ForeignKey("optimization_runs.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(24), default="DRAFT", index=True)
    objective: Mapped[str] = mapped_column(String(24), default="BALANCED")
    total_cost_vnd: Mapped[int] = mapped_column(Integer, default=0)
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(24))
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)


class BookingDraft(Base):
    __tablename__ = "booking_drafts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id"), index=True)
    route_key: Mapped[str] = mapped_column(String(80))
    carrier_id: Mapped[str | None] = mapped_column(ForeignKey("carriers.id"), nullable=True)
    quote_id: Mapped[str | None] = mapped_column(ForeignKey("carrier_quotes.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="DRAFT")
    request_json: Mapped[str] = mapped_column(Text, default="{}")
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str] = mapped_column(String(80))
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, index=True)


Index("ix_plan_tenant_created", Plan.organization_id, Plan.created_at)
