"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity, AlertCircle, ArrowLeftRight, BadgeCheck, Boxes, Building2, CalendarDays,
  Check, CheckCircle2, ChevronRight, CircleHelp, ClipboardCheck, ClipboardList, Clock3, CloudUpload,
  FileSpreadsheet, LayoutDashboard, LoaderCircle, MapPin, Package,
  Plus, RefreshCw, Route, Search, ShieldCheck, Truck, UserRound, Users, Wallet, X,
} from "lucide-react";

type Pallet = { id: string; sku_id: string; sku_name: string; base_uom: string; description: string; weight_kg: number; length_cm: number; width_cm: number; height_cm: number; volume_m3: number; stackable: boolean; rotation_rule: string; handling_code: string };
type Order = { id: string; external_id: string; customer_id: string; customer_name: string; location_id: string; location_name: string; zone: string; latitude: number; longitude: number; address: string; ready_at: string; due_at: string; service_min: number; priority: string; status: string; total_weight_kg: number; total_volume_m3: number; minimum_vehicle_class: string; notes: string; pallets: Pallet[] };
type Vehicle = { id: string; name: string; plate_number: string; fleet_type: string; class_id: string; class_rank: number; capacity_kg: number; usable_volume_m3: number; inner_length_cm: number; inner_width_cm: number; inner_height_cm: number; status: string; available_from: string; available_until: string };
type Stop = { sequence: number; order_id: string; external_id: string; location_id: string; location_name: string; latitude: number; longitude: number; arrival?: string; eta: string; wait_min?: number; due_at: string; weight_kg: number; volume_m3: number; priority: string; pallet_count: number };
type Placement = { pallet_id: string; x_cm: number; y_cm: number; length_cm: number; width_cm: number; rotated: boolean };
type RoutePlan = { route_key: string; vehicle_id: string; vehicle_name: string; kind: string; plate_number?: string | null; unit_no?: number | null; trip_no?: number; carrier_id?: string; carrier_name?: string; quote_id?: string; state: string; status: string; departure?: string; return_at?: string; stops: Stop[]; distance_km: number; duration_min: number; waiting_min?: number; cost_vnd: number; load: { feasible: boolean; weight_kg: number; volume_m3: number; errors: string[]; packing: { status: string; placements: Placement[]; reason: string } }; vehicle: { class_id?: string; capacity_kg: number; usable_volume_m3: number; inner_length_cm: number; inner_width_cm: number; inner_height_cm: number } };
type Plan = { plan_id: string; plan_status: string; routes: RoutePlan[]; unassigned: { order_id: string; reason: string }[]; summary: { orders_total: number; assigned: number; unassigned: number; vehicles_used: number; trips?: number; distance_km: number; cost_vnd: number }; optimality?: string; synthetic_data?: boolean };
type Dashboard = { organization: { id: string; name: string; display_name: string; business_unit: string }; scenario: { id: string; name: string; operation_date: string; provenance: string; depot_name: string; depot_latitude: number; depot_longitude: number }; metrics: { orders_total: number; orders_ready: number; vehicles_available: number; vehicles_total: number; plan_status: string; cost_vnd: number; assigned: number; unassigned: number }; synthetic_data: boolean; ai_status: string };
type Quote = { id: string; carrier_name: string; class_id: string; capacity_kg: number; usable_volume_m3: number; rate_per_km_vnd: number; callout_fee_vnd: number; minimum_fare_vnd: number; stop_fee_vnd: number; return_trip_rule: string; vat_rate_assumption: number; status: string; synthetic: boolean };
type Availability = { id: string; carrier_name: string; class_id: string; vehicles_available: number; status: string; window_start: string; window_end: string };
type Customer = { id: string; legal_name: string; display_name: string; customer_segment: string; sales_channel: string; payment_terms: string; service_level: string; status: string };
type Product = { id: string; name: string; category: string; base_uom: string; handling_code: string; stackable_default: boolean; rotation_rule: string; status: string };
type Employee = { id: string; employee_code: string; name: string; email: string; department: string; position: string; active: boolean };
type Audit = { id: number; action: string; entity_type: string; entity_id: string; details: Record<string, unknown>; created_at: string };
type ImportPreview = { filename: string; valid: boolean; errors: string[]; counts: Record<string, number>; scenario_id: string | null };

const PLANNABLE = new Set(["READY", "VALIDATED", "PENDING"]);
const navItems = [
  { id: "dispatch", label: "Điều vận", icon: LayoutDashboard, group: "VẬN HÀNH" },
  { id: "orders", label: "Lệnh giao hàng & pallet", icon: Package, group: "VẬN HÀNH" },
  { id: "carriers", label: "Nhà cung cấp & biểu giá", icon: Truck, group: "MUA DỊCH VỤ VẬN TẢI" },
  { id: "approval", label: "Kế hoạch vận tải", icon: ClipboardCheck, group: "KIỂM SOÁT NGHIỆP VỤ" },
  { id: "masters", label: "Khách hàng & SKU", icon: Boxes, group: "DANH MỤC CHỦ" },
  { id: "team", label: "Nhân viên logistics", icon: Users, group: "DANH MỤC CHỦ" },
];
const statusLabel = (value: string) => {
  const labels: Record<string, string> = { READY: "Sẵn sàng điều vận", VALIDATED: "Đã kiểm tra", PENDING: "Chờ xử lý", ACTIVE: "Đang hoạt động", INACTIVE: "Ngừng hoạt động", DRAFT: "Bản nháp", APPROVED: "Đã duyệt", REJECTED: "Trả lại để điều chỉnh", PLANNED: "Đề xuất", COMPLETED: "Hoàn tất", CONFIRMED: "Đã xác nhận", DEMO_VALID: "Hiệu lực mô phỏng", PASS_2D_FLOOR_ONLY: "Đạt kiểm tra sàn 2D", FAIL_FLOOR: "Không vừa mặt sàn", FAIL_HEIGHT: "Vượt chiều cao thùng", NOT_CHECKED: "Chưa kiểm tra", NOT_FEASIBLE: "Không khả thi", NOT_PLANNED: "Chưa lập phương án", AVAILABLE: "Sẵn sàng", MAINTENANCE: "Bảo dưỡng" };
  return labels[value] ?? value.replaceAll("_", " ");
};
const routeStateLabel = (state: string) => state === "ACTIVE" ? "ĐANG CHẠY" : state === "COMPLETED" ? "HOÀN TẤT" : "ĐỀ XUẤT";
const reasonLabel = (value: string) => {
  const labels: Record<string, string> = {
    MINIMUM_VEHICLE_CLASS_UNAVAILABLE: "Không có xe đạt hạng tối thiểu",
    WEIGHT_OR_VOLUME_LIMIT: "Vượt tải trọng/thể tích của mọi xe phù hợp",
    PALLET_FLOOR_INFEASIBLE: "Pallet không xếp vừa sàn xe phù hợp",
    DELIVERY_WINDOW_UNREACHABLE: "Không kịp hạn giao hoặc giờ nhận hàng",
    TIME_WINDOW_OR_ROUTE_CAPACITY: "Hết năng lực xe trong khung giờ",
    NOT_IN_PLAN: "Chưa có trong phương án (đơn mới)",
  };
  return labels[value] ?? value.replaceAll("_", " ");
};
const auditLabel = (value: string) => {
  const labels: Record<string, string> = { OPTIMIZATION_QUEUED: "Lập phương án", PLAN_APPROVE: "Xác nhận kế hoạch", PLAN_REJECT: "Trả lại kế hoạch", ROUTE_STATE_CHANGED: "Cập nhật trạng thái tuyến", BOOKING_DRAFTS_PREPARED: "Lập nháp yêu cầu xe", ORDER_MANUALLY_ASSIGNED: "Xếp đơn thủ công", WORKBOOK_IMPORTED: "Nhập workbook", EMPLOYEE_CREATED: "Thêm nhân viên", QUOTE_TERMS_EXTRACTED: "Đọc báo giá" };
  return labels[value] ?? value;
};
const masterLabel = (value: string) => {
  const labels: Record<string, string> = { RETAIL_CHAIN: "Chuỗi bán lẻ", DISTRIBUTOR: "Nhà phân phối", FOOD_SERVICE: "Dịch vụ thực phẩm", MODERN_TRADE: "Bán lẻ hiện đại", GENERAL_TRADE: "Kênh truyền thống", B2B: "Giao dịch doanh nghiệp", NET30: "Công nợ 30 ngày", NET15: "Công nợ 15 ngày", "SLA-AM": "Giao buổi sáng", "SLA-PM": "Giao buổi chiều", "SLA-STD": "Khung giờ tiêu chuẩn", BEVERAGE: "Đồ uống", DAIRY: "Sữa & chế phẩm", GROCERY: "Thực phẩm khô", HOUSEHOLD: "Hàng gia dụng", PAPER_GOODS: "Giấy & vệ sinh", SNACKS: "Bánh kẹo", PERSONAL_CARE: "Chăm sóc cá nhân", CASE: "Thùng (CASE)", GENERAL: "Hàng khô thông thường", INTERNAL: "Đội xe nội bộ", CONTRACTED: "Thuê ngoài", ONE_WAY: "Một chiều", ROUND_TRIP: "Tính cả chiều về" };
  return labels[value] ?? value.replaceAll("_", " ");
};
const operationalExplanation = (value: string) => {
  if (value.includes("2D floor fit only")) return "Mô phỏng chỉ kiểm tra kích thước sàn 2D; chưa xác nhận xếp chồng, cân bằng tải trục hoặc chằng buộc hàng.";
  if (value.includes("feasible, constraint-checked heuristic")) return "Phương án khả thi đã kiểm tra ràng buộc (hàng sẵn sàng, giờ nhận hàng, hạn giao, tải và sàn xe); thuật toán heuristic chưa bảo đảm chi phí tối ưu toàn cục.";
  return value;
};
const routeTitle = (route: RoutePlan) => route.kind === "CARRIER" ? (route.carrier_name ?? route.vehicle_name) : `${route.vehicle_id}${route.trip_no ? ` · chuyến ${route.trip_no}` : ""}`;
const routeSubtitle = (route: RoutePlan) => {
  const cls = route.vehicle.class_id ? `${route.vehicle.class_id} · ` : "";
  if (route.kind === "CARRIER") return `${cls}Thuê ngoài${route.unit_no ? ` · xe #${route.unit_no}` : ""}`;
  return `${cls}Nội bộ${route.plate_number ? ` · ${route.plate_number}` : ""}`;
};

function errorMessage(payload: unknown, status: number) {
  const detail = (payload as { detail?: unknown })?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => (d as { msg?: string }).msg ?? JSON.stringify(d)).join("; ");
  if (detail && typeof detail === "object") {
    const d = detail as { message?: string; errors?: string[] };
    if (d.message) return d.message;
    if (d.errors?.length) return `Workbook có ${d.errors.length} lỗi: ${d.errors.slice(0, 3).join("; ")}`;
  }
  return status === 503 ? "Không kết nối được API FleetMix. Hãy khởi động API và worker." : `Yêu cầu thất bại (${status})`;
}

async function api<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, cache: "no-store", headers: { ...(init?.headers ?? {}) } });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(errorMessage(payload, response.status));
  return payload as T;
}
const jsonInit = (method: string, body: unknown): RequestInit => ({ method, headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
const money = (value: number) => new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 }).format(value) + " ₫";
const compact = (value: number) => new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 1 }).format(value);
const dateLabel = (value: string) => new Intl.DateTimeFormat("vi-VN", { weekday: "long", day: "2-digit", month: "long", year: "numeric" }).format(new Date(value));
const hoursLabel = (minutes: number) => minutes >= 60 ? `${Math.floor(minutes / 60)} giờ ${minutes % 60 ? `${minutes % 60} phút` : ""}`.trim() : `${minutes} phút`;
const isMac = () => typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);

export function DispatchBoard() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [fleet, setFleet] = useState<Vehicle[]>([]);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [availability, setAvailability] = useState<Availability[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [auditEvents, setAuditEvents] = useState<Audit[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [tab, setTab] = useState("dispatch");
  const [selectedRoute, setSelectedRoute] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [draggedOrder, setDraggedOrder] = useState<string | null>(null);
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);
  const [quoteText, setQuoteText] = useState("");
  const [quoteResult, setQuoteResult] = useState<Record<string, unknown> | null>(null);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importPreview, setImportPreview] = useState<ImportPreview | null>(null);
  const [employeeForm, setEmployeeForm] = useState({ employee_code: "", name: "", email: "", position: "Nhân viên logistics" });
  const [shortcut, setShortcut] = useState("Ctrl K");
  const searchRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    const [d, o, f, p, q, e, a, customerMaster, productMaster] = await Promise.all([
      api<Dashboard>("/api/backend/dashboard"), api<{ orders: Order[] }>("/api/backend/orders"), api<{ vehicles: Vehicle[] }>("/api/backend/fleet"),
      api<{ plan: Plan | null }>("/api/backend/plans/latest"), api<{ quotes: Quote[]; availability: Availability[] }>("/api/backend/quotes"), api<{ employees: Employee[] }>("/api/backend/employees"), api<{ events: Audit[] }>("/api/backend/audit"),
      api<{ customers: Customer[] }>("/api/backend/customers"), api<{ products: Product[] }>("/api/backend/products"),
    ]);
    setDashboard(d); setOrders(o.orders); setFleet(f.vehicles); setPlan(p.plan); setQuotes(q.quotes); setAvailability(q.availability ?? []); setEmployees(e.employees); setAuditEvents(a.events); setCustomers(customerMaster.customers); setProducts(productMaster.products);
    setSelectedRoute((current) => p.plan?.routes.some((r) => r.route_key === current) ? current : p.plan?.routes[0]?.route_key ?? null);
    setLoaded(true);
  }, []);

  useEffect(() => {
    let active = true;
    refresh().catch((e) => { if (active) setError(e instanceof Error ? e.message : "Không tải được dữ liệu điều vận"); });
    return () => { active = false; };
  }, [refresh]);

  // Success notices fade out; errors stay until dismissed.
  useEffect(() => {
    if (!notice || busy) return;
    const timer = setTimeout(() => setNotice(""), 7000);
    return () => clearTimeout(timer);
  }, [notice, busy]);

  useEffect(() => { window.scrollTo({ top: 0 }); }, [tab]);

  useEffect(() => {
    setShortcut(isMac() ? "⌘ K" : "Ctrl K");
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault(); setTab("dispatch"); setTimeout(() => searchRef.current?.focus(), 0);
      }
      if (event.key === "Escape") { setSelectedOrderId(null); setDraggedOrder(null); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const selected = plan?.routes.find((r) => r.route_key === selectedRoute) ?? plan?.routes[0] ?? null;
  const routeByOrder = useMemo(() => {
    const map = new Map<string, RoutePlan>();
    plan?.routes.forEach((r) => r.stops.forEach((s) => map.set(s.order_id, r)));
    return map;
  }, [plan]);
  const unassignedReasons = useMemo(() => new Map(plan?.unassigned.map((u) => [u.order_id, u.reason]) ?? []), [plan]);
  // Orders still waiting for a vehicle: plannable and not on any route of the current plan (includes orders imported after planning).
  const unassigned = useMemo(() => orders.filter((o) => PLANNABLE.has(o.status) && !routeByOrder.has(o.id)), [orders, routeByOrder]);
  const matchesQuery = useCallback((o: Order) => `${o.external_id} ${o.customer_id} ${o.customer_name} ${o.location_name} ${o.zone}`.toLowerCase().includes(query.trim().toLowerCase()), [query]);
  const visibleUnassigned = useMemo(() => unassigned.filter(matchesQuery), [unassigned, matchesQuery]);
  const filteredOrders = useMemo(() => orders.filter(matchesQuery), [orders, matchesQuery]);
  const idleVehicles = useMemo(() => fleet.filter((v) => !plan?.routes.some((r) => r.vehicle_id === v.id)), [fleet, plan]);
  const routePallets = useMemo(() => selected ? selected.stops.flatMap((stop) => {
    const order = orders.find((o) => o.id === stop.order_id);
    return (order?.pallets ?? []).map((pallet) => ({ ...pallet, stop: stop.sequence, drop: stop.location_name }));
  }) : [], [selected, orders]);
  const planEditable = plan?.plan_status === "DRAFT";
  const pendingOrder = draggedOrder ?? selectedOrderId;
  const lockedRoutes = plan?.routes.filter((r) => r.state !== "PLANNED").length ?? 0;

  async function runOptimize() {
    if (plan && (plan.plan_status === "APPROVED" || lockedRoutes > 0)) {
      const message = plan.plan_status === "APPROVED"
        ? "Kế hoạch hiện tại đã được xác nhận. Lập phương án mới sẽ tạo bản nháp thay thế và cần xác nhận lại. Tiếp tục?"
        : `Phương án mới giữ nguyên ${lockedRoutes} tuyến đã xuất phát/hoàn tất và thay các tuyến còn lại. Tiếp tục?`;
      if (!window.confirm(message)) return;
    }
    setBusy("optimize"); setError(""); setNotice("Đang lập tuyến và kiểm tra tải theo pallet…");
    try {
      const job = await api<{ id: string }>("/api/backend/optimization-runs", jsonInit("POST", { objective: "BALANCED", include_carriers: true, time_limit_seconds: 8 }));
      for (let attempt = 0; attempt < 50; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 600));
        const status = await api<{ status: string; error?: string }>(`/api/backend/optimization-runs/${job.id}`);
        if (status.status === "SUCCEEDED") { await refresh(); setSelectedOrderId(null); setNotice("Đã hoàn tất phương án. Kiểm tra các đơn chưa xếp và bố trí pallet trước khi xác nhận."); return; }
        if (status.status === "FAILED") throw new Error(status.error || "Bộ tối ưu không hoàn tất");
      }
      throw new Error("Bộ tối ưu chưa phản hồi sau 30 giây. Kiểm tra tiến trình worker (npm run dev:worker) rồi thử lại.");
    } catch (e) { setError(e instanceof Error ? e.message : "Không thể tối ưu"); setNotice(""); }
    finally { setBusy(""); }
  }

  async function assign(orderId: string, route: RoutePlan) {
    setDraggedOrder(null);
    if (!plan) return;
    if (!planEditable) { setError("Kế hoạch đã chốt; lập lại phương án để chỉnh sửa tuyến."); return; }
    if (route.state !== "PLANNED") { setError("Tuyến đã xuất phát hoặc hoàn tất; chọn tuyến khác."); return; }
    setBusy(`assign-${route.route_key}`); setError("");
    try {
      await api(`/api/backend/plans/${plan.plan_id}/assign`, jsonInit("POST", { order_id: orderId, route_key: route.route_key }));
      await refresh(); setSelectedRoute(route.route_key); setSelectedOrderId(null);
      setNotice("Đã thêm đơn vào tuyến sau khi kiểm tra tải trọng, sàn xe và khung giờ giao.");
    } catch (e) { setError(e instanceof Error ? e.message : "Không thể xếp đơn vào tuyến"); }
    finally { setBusy(""); }
  }

  async function setRouteState(route: RoutePlan, state: "ACTIVE" | "COMPLETED") {
    if (!plan) return; setBusy(`route-${route.route_key}`); setError("");
    try { await api(`/api/backend/plans/${plan.plan_id}/routes/${encodeURIComponent(route.route_key)}/state`, jsonInit("PATCH", { state })); await refresh(); setNotice(state === "ACTIVE" ? "Tuyến được đánh dấu đang thực hiện; lần lập lại phương án sẽ giữ nguyên tuyến này." : "Đã ghi nhận hoàn tất tuyến."); }
    catch (e) { setError(e instanceof Error ? e.message : "Không cập nhật được tuyến"); } finally { setBusy(""); }
  }

  async function approve(decision: "APPROVE" | "REJECT") {
    if (!plan) return;
    if (decision === "APPROVE" && unassigned.length > 0 && !window.confirm(`Còn ${unassigned.length} đơn chưa xếp tuyến. Vẫn xác nhận kế hoạch?`)) return;
    if (decision === "REJECT" && !window.confirm("Trả lại phương án này để điều chỉnh? Bạn sẽ cần lập lại phương án.")) return;
    setBusy("approval"); setError("");
    try { await api(`/api/backend/plans/${plan.plan_id}/approval`, jsonInit("POST", { decision, comment: "Nhân viên logistics xác nhận phương án trên bảng điều phối" })); await refresh(); setNotice(decision === "APPROVE" ? `Kế hoạch đã được xác nhận. Có thể cho tuyến xuất phát${plan.routes.some((r) => r.kind === "CARRIER") ? " và lập bản nháp yêu cầu nhà xe" : ""}.` :"Đã trả lại kế hoạch; điều chỉnh dữ liệu rồi lập lại phương án."); }
    catch (e) { setError(e instanceof Error ? e.message : "Không lưu được quyết định"); } finally { setBusy(""); }
  }

  async function createBookingDrafts() {
    if (!plan) return; setBusy("booking"); setError("");
    try {
      const result = await api<{ booking_drafts_created: number; booking_drafts_existing?: number }>(`/api/backend/plans/${plan.plan_id}/booking-drafts`, { method: "POST" });
      await refresh();
      const existing = result.booking_drafts_existing ?? 0;
      setNotice(result.booking_drafts_created > 0
        ? `Đã tạo ${result.booking_drafts_created} bản nháp yêu cầu xe thuê ngoài (chưa gửi ra ngoài).`
        : existing > 0 ? `Các tuyến thuê ngoài đã có ${existing} bản nháp; không tạo thêm.` : "Kế hoạch không có tuyến thuê ngoài nên không cần bản nháp yêu cầu xe.");
    }
    catch (e) { setError(e instanceof Error ? e.message : "Không tạo được bản nháp"); } finally { setBusy(""); }
  }

  async function extractQuote(event: React.FormEvent) {
    event.preventDefault(); setBusy("quote-ai"); setError("");
    try { setQuoteResult(await api<Record<string, unknown>>("/api/ai/quote-extract", jsonInit("POST", { text: quoteText }))); }
    catch (e) { setError(e instanceof Error ? e.message : "Không đọc được báo giá"); } finally { setBusy(""); }
  }

  async function previewImport() {
    if (!importFile) return; setBusy("import"); setError("");
    const data = new FormData(); data.append("file", importFile);
    try { setImportPreview(await api<ImportPreview>("/api/backend/imports/preview", { method: "POST", body: data })); }
    catch (e) { setError(e instanceof Error ? e.message : "Không kiểm tra được workbook"); } finally { setBusy(""); }
  }

  async function commitImport() {
    if (!importFile) return; setBusy("import"); setError(""); const data = new FormData(); data.append("file", importFile);
    try {
      await api("/api/backend/imports/commit", { method: "POST", body: data }); await refresh();
      setNotice(plan ? "Đã cập nhật dữ liệu. Phương án hiện tại chưa phản ánh thay đổi — hãy lập lại phương án vận tải." : "Đã cập nhật đơn, pallet và điểm giao trong kịch bản đang mở.");
      setImportPreview(null); setImportFile(null);
    }
    catch (e) { setError(e instanceof Error ? e.message : "Không nhập được workbook"); } finally { setBusy(""); }
  }

  async function addEmployee(event: React.FormEvent) {
    event.preventDefault(); setBusy("employee"); setError("");
    try { await api("/api/backend/employees", jsonInit("POST", employeeForm)); await refresh(); setEmployeeForm({ employee_code: "", name: "", email: "", position: "Nhân viên logistics" }); setNotice("Đã thêm hồ sơ nhân viên logistics."); }
    catch (e) { setError(e instanceof Error ? e.message : "Không tạo được nhân viên"); } finally { setBusy(""); }
  }

  const costNote = !plan ? "Chưa có phương án" : plan.plan_status === "APPROVED" ? "Đã xác nhận" : plan.plan_status === "REJECTED" ? "Đã trả lại" : "Chờ xác nhận";
  const trips = plan?.summary.trips ?? plan?.routes.length ?? 0;

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><Boxes size={20} /></div><div><strong>fleetmix<span>AI</span></strong><small>HỆ THỐNG VẬN HÀNH LOGISTICS</small></div></div>
      <div className="workspace"><div className="workspace-icon"><Building2 size={16} /></div><div><strong>{dashboard?.organization.display_name ?? "Đơn vị logistics"}</strong><small>{dashboard?.organization.business_unit ?? "Vận hành logistics"}</small></div></div>
      <nav className="navigation" aria-label="Điều hướng chính">{["VẬN HÀNH", "MUA DỊCH VỤ VẬN TẢI", "KIỂM SOÁT NGHIỆP VỤ", "DANH MỤC CHỦ"].map((group) => <div className="nav-group" key={group}><span className="nav-caption">{group}</span>{navItems.filter((item) => item.group === group).map((item) => { const Icon = item.icon; return <button key={item.id} title={item.label} aria-current={tab === item.id ? "page" : undefined} className={`nav-item ${tab === item.id ? "active" : ""}`} onClick={() => setTab(item.id)}><Icon size={17} /><span>{item.label}</span>{item.id === "dispatch" && loaded && unassigned.length > 0 && <b title="Đơn chờ xếp tuyến">{unassigned.length}</b>}{item.id === "orders" && <b title="Tổng lệnh trong ca">{dashboard?.metrics.orders_total ?? 0}</b>}</button>; })}</div>)}</nav>
      <div className="sidebar-bottom"><div className="health-dot"><i className={error.includes("API") ? "down" : ""} />{error.includes("API") ? "Mất kết nối API" : "Hệ thống hoạt động"}</div><div className="user-card"><div className="avatar">L</div><div className="user-meta"><strong>Nhân viên logistics</strong><small>Không cần đăng nhập</small></div></div></div>
    </aside>

    <main className="main-area">
      <header className="topbar"><div className="breadcrumbs"><span>Logistics</span><ChevronRight size={14} /><strong>{navItems.find((n) => n.id === tab)?.label}</strong></div><div className="topbar-right"><span className="date-chip"><CalendarDays size={15} />{dashboard ? dateLabel(dashboard.scenario.operation_date) : "Đang tải…"}</span><button className="icon-button" title="Làm mới dữ liệu" aria-label="Làm mới dữ liệu" onClick={() => refresh().then(() => setError("")).catch((e) => setError(e.message))}><RefreshCw size={16} /></button><div className="avatar avatar-sm">L</div></div></header>
      <div className="content-area">
        {dashboard?.synthetic_data && <div className="demo-ribbon"><AlertCircle size={15} /><span><strong>DỮ LIỆU THAM CHIẾU MÔ PHỎNG</strong> · Hồ sơ khách hàng, SKU, địa chỉ, đội xe, báo giá và cước được tạo mẫu; cần thay bằng dữ liệu chủ và chứng từ đã xác thực trước vận hành thực tế.</span></div>}
        <div className="toast-stack" aria-live="polite">
          {error && <div className="toast toast-error" role="alert"><AlertCircle size={16}/><span>{error}</span><button aria-label="Đóng thông báo" onClick={() => setError("")}><X size={14}/></button></div>}
          {notice && <div className="toast toast-success"><CheckCircle2 size={16}/><span>{notice}</span><button aria-label="Đóng thông báo" onClick={() => setNotice("")}><X size={14}/></button></div>}
        </div>
        {tab === "dispatch" && <>
          <div className="page-heading"><div><span className="eyebrow">BẢNG ĐIỀU HÀNH · KỊCH BẢN {dashboard?.scenario.id ?? "…"}</span><h1>Điều vận trong ngày</h1><p>{dashboard?.scenario.name ?? "Theo dõi lệnh giao hàng và phương tiện"}</p></div><div className="heading-actions"><button className="button button-quiet" onClick={() => setTab("orders")}><FileSpreadsheet size={16}/> Nhập dữ liệu</button><button className="button button-primary" onClick={runOptimize} disabled={busy === "optimize" || !loaded}>{busy === "optimize" ? <LoaderCircle className="spin" size={16}/> : <Activity size={16}/>} {busy === "optimize" ? "Đang tối ưu…" : plan ? "Lập lại phương án" : "Lập phương án vận tải"}</button></div></div>
          <div className="metric-grid"><Metric icon={ClipboardList} label="Đơn trong ca" value={dashboard?.metrics.orders_total ?? 0} note={`${unassigned.length} đơn đang chờ xếp`} tone="blue"/><Metric icon={Truck} label="Xe nội bộ sẵn sàng" value={`${dashboard?.metrics.vehicles_available ?? 0}/${dashboard?.metrics.vehicles_total ?? 0}`} note={`${fleet.filter((v) => v.status !== "AVAILABLE").length} xe ngừng khai thác`} tone="green"/><Metric icon={Route} label="Đơn đã xếp" value={`${plan?.summary.assigned ?? 0}/${plan ? plan.summary.assigned + unassigned.length : dashboard?.metrics.orders_total ?? 0}`} note={plan ? `${plan.summary.vehicles_used} xe · ${trips} chuyến` : "Chưa có phương án"} tone="purple"/><Metric icon={Wallet} label="Chi phí dự kiến" value={plan ? money(plan.summary.cost_vnd) : "—"} note={costNote} tone="amber"/></div>
          {plan && !planEditable && <div className="inline-hint"><CircleHelp size={14}/>{plan.plan_status === "APPROVED" ? "Kế hoạch đã xác nhận nên không thể kéo thả thêm đơn. Lập lại phương án nếu cần thay đổi." : "Kế hoạch đã bị trả lại. Lập lại phương án để có bản nháp mới."}</div>}
          <div className="dispatch-layout">
            <section className="panel order-panel"><div className="panel-heading"><div><h2>Đơn chưa xếp</h2><p>{unassigned.length} đơn{plan && planEditable ? " · kéo thả hoặc chọn rồi bấm vào tuyến" : plan ? "" : " · lập phương án để phân xe"}</p></div><button className="icon-button" aria-label="Tìm đơn" title={`Tìm đơn (${shortcut})`} onClick={() => searchRef.current?.focus()}><Search size={16}/></button></div><div className="search-box"><Search size={15}/><input ref={searchRef} aria-label="Tìm đơn chưa xếp" placeholder="Mã đơn, khách hàng, khu vực" value={query} onChange={(e) => setQuery(e.target.value)}/>{query ? <button className="clear-search" aria-label="Xoá tìm kiếm" onClick={() => setQuery("")}><X size={13}/></button> : <kbd>{shortcut}</kbd>}</div><div className="order-list">{visibleUnassigned.map((order) => <OrderCard key={order.id} order={order} reason={unassignedReasons.get(order.id) ?? (plan ? "NOT_IN_PLAN" : undefined)} canAssign={!!plan && planEditable} dragging={draggedOrder === order.id} selected={selectedOrderId === order.id} onSelect={() => setSelectedOrderId(selectedOrderId === order.id ? null : order.id)} onDragStart={() => setDraggedOrder(order.id)} onDragEnd={() => setDraggedOrder(null)}/>)}{loaded && unassigned.length === 0 && <Empty icon={CheckCircle2} title="Không còn đơn chờ xếp" detail="Tất cả đơn đã được phân vào tuyến."/>}{unassigned.length > 0 && visibleUnassigned.length === 0 && <Empty icon={Search} title="Không có đơn khớp tìm kiếm" detail="Thử mã đơn, tên khách hàng hoặc khu vực khác."/>}</div><div className="order-panel-footer"><span><span className="priority-dot priority-high"/>Ưu tiên cao</span><span><span className="priority-dot priority-normal"/>Thông thường</span></div></section>
            <section className="panel map-panel"><div className="panel-heading map-heading"><div><h2>Bản đồ điều vận</h2><p><span className="live-dot"/> Điểm giao tham chiếu · TP. Hồ Chí Minh</p></div><div className="map-tools"><span className="map-legend"><i className="legend-depot"/> Kho xuất</span><span className="map-legend"><i className="legend-stop"/> Điểm nhận</span></div></div><MapView orders={orders} selected={selected} depot={dashboard?.scenario.depot_name ?? "Kho xuất"} depotLatitude={dashboard?.scenario.depot_latitude ?? 10.801} depotLongitude={dashboard?.scenario.depot_longitude ?? 106.652}/><div className="map-footer"><span><MapPin size={14}/> {selected ? `${routeTitle(selected)} · ${selected.stops.length} điểm nhận${selected.departure ? ` · xuất ${selected.departure}, về ${selected.return_at}` : ""}` : "Lập phương án để hiển thị tuyến"}</span><span className="map-label">Sơ đồ tọa độ · Không phải dữ liệu dẫn đường</span></div></section>
            <section className="fleet-column"><div className="fleet-head"><div><h2>Đội xe & tuyến</h2><p>{plan ? `${plan.summary.vehicles_used} xe · ${trips} chuyến` : "Chưa lập phương án"}</p></div></div>{pendingOrder && plan && planEditable && <div className="assign-banner"><span>Chọn tuyến để xếp <strong>{orders.find((o) => o.id === pendingOrder)?.external_id}</strong></span><button aria-label="Huỷ chọn đơn" onClick={() => { setSelectedOrderId(null); setDraggedOrder(null); }}><X size={13}/></button></div>}<div className="fleet-list">{plan?.routes.map((route, index) => { const droppable = !!pendingOrder && planEditable && route.state === "PLANNED"; return <RouteCard key={route.route_key} route={route} index={index} selected={selected?.route_key === route.route_key} droppable={droppable} onClick={() => droppable && selectedOrderId ? assign(selectedOrderId, route) : setSelectedRoute(route.route_key)} onDrop={() => { if (droppable && pendingOrder) assign(pendingOrder, route); else setDraggedOrder(null); }} busy={busy === `assign-${route.route_key}`}/>; })}{plan && idleVehicles.length > 0 && <div className="fleet-subhead">Xe nội bộ chưa phân tuyến</div>}{(plan ? idleVehicles : fleet).map((vehicle) => <VehicleCard key={vehicle.id} vehicle={vehicle}/>)}{plan?.routes.length === 0 && <Empty icon={Truck} title="Chưa có tuyến xe" detail="Không có đơn nào xếp được; xem nguyên nhân ở trang Kế hoạch vận tải."/>}</div><div className="fleet-actions"><button onClick={runOptimize} disabled={busy === "optimize" || !loaded}>{busy === "optimize" ? <LoaderCircle className="spin" size={15}/> : <Activity size={15}/>} {busy === "optimize" ? "Đang tính…" : plan ? "Lập lại phương án" : "Lập phương án"}</button></div></section>
          </div>
          <section className="panel pallet-panel"><div className="panel-heading pallet-heading"><div><div className="section-title-row"><Boxes size={18}/><h2>Bố trí pallet trên xe</h2><span className="panel-tag">MÔ PHỎNG 2D</span></div><p>{selected ? `${routeTitle(selected)} · ${routeSubtitle(selected)} · ${selected.vehicle.inner_length_cm} × ${selected.vehicle.inner_width_cm} cm · ${routePallets.length} pallet` : "Chọn một tuyến để kiểm tra cách xếp hàng"}</p></div>{selected && <div className="capacity-pills"><Capacity label="Tải trọng" used={selected.load.weight_kg} total={selected.vehicle.capacity_kg} unit="kg"/><Capacity label="Thể tích" used={selected.load.volume_m3} total={selected.vehicle.usable_volume_m3} unit="m³"/></div>}</div>{selected ? <PalletView route={selected} pallets={routePallets}/> : <Empty icon={Boxes} title="Chưa có bố trí pallet" detail="Bộ lập tuyến sẽ kiểm tra kích thước sàn trước khi đề xuất xe."/>}<div className="pallet-disclaimer"><CircleHelp size={14}/>{selected ? operationalExplanation(selected.load.packing.reason) : "Bản vẽ là mô phỏng sàn 2D; cần kiểm tra xếp chồng, cân bằng tải và chằng buộc trước khi xếp hàng thực tế."}</div></section>
          {plan && <PlanActionBar plan={plan} busy={busy} onApprove={approve} onBooking={createBookingDrafts} onReplan={runOptimize} note={plan.optimality ? operationalExplanation(plan.optimality) : "Kiểm tra tuyến, tải trọng và hạn giao trước khi xác nhận kế hoạch."}/>}
        </>}
        {tab === "orders" && <OrdersPage orders={filteredOrders} routeByOrder={routeByOrder} hasPlan={!!plan} query={query} setQuery={setQuery} file={importFile} setFile={setImportFile} preview={importPreview} setPreview={setImportPreview} previewImport={previewImport} commitImport={commitImport} busy={busy}/>}
        {tab === "masters" && <MastersPage customers={customers} products={products}/>}
        {tab === "carriers" && <CarriersPage quotes={quotes} availability={availability} quoteText={quoteText} setQuoteText={setQuoteText} onExtract={extractQuote} result={quoteResult} busy={busy}/>}
        {tab === "approval" && <><ApprovalPage plan={plan} unassignedCount={unassigned.length} unassigned={unassigned} reasons={unassignedReasons} onApprove={approve} onBooking={createBookingDrafts} onReplan={runOptimize} busy={busy} onRouteState={setRouteState}/><AuditTable events={auditEvents}/></>}
        {tab === "team" && <TeamPage employees={employees} form={employeeForm} setForm={setEmployeeForm} onSubmit={addEmployee} busy={busy}/>}
      </div>
    </main>
  </div>;
}

function Metric({ icon: Icon, label, value, note, tone }: { icon: typeof Truck; label: string; value: string | number; note: string; tone: string }) { return <div className="metric-card"><div className={`metric-icon ${tone}`}><Icon size={18}/></div><div className="metric-copy"><span>{label}</span><strong>{value}</strong><small>{note}</small></div></div>; }

function OrderCard({ order, reason, canAssign, dragging, selected, onSelect, onDragStart, onDragEnd }: { order: Order; reason?: string; canAssign: boolean; dragging: boolean; selected: boolean; onSelect: () => void; onDragStart: () => void; onDragEnd: () => void }) {
  const state = order.priority === "HIGH" ? "high" : "normal";
  return <article className={`order-card ${dragging ? "dragging" : ""} ${selected ? "chosen" : ""}`} draggable={canAssign} onDragStart={(e) => { e.dataTransfer.setData("text/plain", order.id); e.dataTransfer.effectAllowed = "move"; onDragStart(); }} onDragEnd={onDragEnd}>
    <div className="order-card-top"><div className="order-code"><span className={`priority-dot priority-${state}`} title={order.priority === "HIGH" ? "Ưu tiên cao" : "Thông thường"}/><strong>{order.external_id}</strong></div><span className="order-time" title={`Hàng sẵn sàng ${order.ready_at} · hạn giao ${order.due_at}`}><Clock3 size={12}/>Hạn {order.due_at}</span></div>
    <div className="order-customer">{order.customer_name} <small>{order.customer_id}</small></div>
    <div className="order-place"><MapPin size={13}/><span>{order.location_name}</span><small>{order.zone}</small></div>
    <div className="order-card-bottom"><span><Package size={12}/>{order.pallets.length} pallet</span><span>{compact(order.total_weight_kg)} kg</span><span>{compact(order.total_volume_m3)} m³</span></div>
    <div className="order-card-note">Xuất kho từ {order.ready_at} · hạng xe tối thiểu: {order.minimum_vehicle_class === "ANY_COMPATIBLE" ? "theo tải hàng" : order.minimum_vehicle_class}</div>
    {reason && <div className="order-card-reason"><AlertCircle size={12}/>{reasonLabel(reason)}</div>}
    {canAssign && <button type="button" className="order-select-button" aria-pressed={selected} onClick={onSelect}>{selected ? "Đã chọn · bấm vào tuyến bên phải" : "Chọn để xếp vào tuyến"}<ChevronRight size={12}/></button>}
  </article>;
}

function RouteCard({ route, index, selected, droppable, onClick, onDrop, busy }: { route: RoutePlan; index: number; selected: boolean; droppable: boolean; onClick: () => void; onDrop: () => void; busy: boolean }) {
  const kg = route.load.weight_kg / route.vehicle.capacity_kg * 100, volume = route.load.volume_m3 / route.vehicle.usable_volume_m3 * 100;
  return <button className={`route-card ${selected ? "selected" : ""} ${droppable ? "drop-ready" : ""}`} aria-pressed={selected} onClick={onClick} onDragOver={(e) => { if (droppable) e.preventDefault(); }} onDrop={(e) => { e.preventDefault(); onDrop(); }}>
    <div className="route-card-top"><div className={`route-icon route-${index % 4}`}><Truck size={16}/></div><div className="route-title"><strong>{routeTitle(route)}</strong><small>{routeSubtitle(route)}</small></div><span className={`route-state state-${route.state.toLowerCase()}`}>{routeStateLabel(route.state)}</span></div>
    {route.departure && <div className="route-times"><Clock3 size={12}/>Xuất {route.departure} · về {route.return_at}{route.waiting_min ? ` · chờ ${route.waiting_min} phút` : ""}</div>}
    <div className="route-route-line">Kho{route.stops.slice(0, 3).map((s) => ` → ${s.location_name}`).join("")}{route.stops.length > 3 ? ` → +${route.stops.length - 3} điểm` : ""}</div>
    <div className="capacity-line"><div className="capacity-label"><span>Tải trọng</span><strong>{compact(route.load.weight_kg)} / {compact(route.vehicle.capacity_kg)} kg</strong></div><div className="progress"><i style={{ width: `${Math.min(100, kg)}%` }}/></div></div>
    <div className="capacity-line"><div className="capacity-label"><span>Thể tích</span><strong>{compact(route.load.volume_m3)} / {compact(route.vehicle.usable_volume_m3)} m³</strong></div><div className="progress volume"><i style={{ width: `${Math.min(100, volume)}%` }}/></div></div>
    <div className="route-card-foot"><span><MapPin size={12}/>{route.stops.length} điểm</span><span><ArrowLeftRight size={12}/>{compact(route.distance_km)} km</span><strong>{money(route.cost_vnd)}</strong></div>
    {droppable && !busy && <span className="drop-hint">Thả hoặc bấm để xếp lệnh vào tuyến này</span>}
    {busy && <span className="drop-hint"><LoaderCircle className="spin" size={11}/> Đang kiểm tra tải và khung giờ…</span>}
  </button>;
}

function VehicleCard({ vehicle }: { vehicle: Vehicle }) { return <div className="vehicle-card"><div className="route-card-top"><div className="route-icon route-vehicle"><Truck size={16}/></div><div className="route-title"><strong>{vehicle.name}</strong><small>{vehicle.class_id} · {vehicle.plate_number}</small></div><span className={`availability ${vehicle.status.toLowerCase()}`}><i/>{statusLabel(vehicle.status)}</span></div><div className="capacity-label"><span>Tải trọng khai thác</span><strong>{compact(vehicle.capacity_kg)} kg</strong></div><div className="capacity-label"><span>Kích thước lọt lòng</span><strong>{vehicle.inner_length_cm}×{vehicle.inner_width_cm}×{vehicle.inner_height_cm} cm</strong></div><div className="capacity-label"><span>Ca khai thác</span><strong>{vehicle.available_from}–{vehicle.available_until}</strong></div></div>; }

function MapView({ orders, selected, depot, depotLatitude, depotLongitude }: { orders: Order[]; selected: RoutePlan | null; depot: string; depotLatitude: number; depotLongitude: number }) {
  const points = orders.filter((o) => Number.isFinite(o.latitude) && Number.isFinite(o.longitude) && (o.latitude !== 0 || o.longitude !== 0));
  const all = [{ latitude: depotLatitude, longitude: depotLongitude }, ...points];
  const minLat = Math.min(...all.map((p) => p.latitude)), maxLat = Math.max(...all.map((p) => p.latitude)), minLng = Math.min(...all.map((p) => p.longitude)), maxLng = Math.max(...all.map((p) => p.longitude));
  const coord = (lat: number, lng: number) => ({ x: 55 + (lng - minLng) / (maxLng - minLng || .01) * 690, y: 40 + (maxLat - lat) / (maxLat - minLat || .01) * 330 });
  const depotPt = coord(depotLatitude, depotLongitude); const stops = selected?.stops ?? []; const routePts = [depotPt, ...stops.map((s) => coord(s.latitude, s.longitude)), depotPt];
  const label = depot.length > 34 ? `${depot.slice(0, 33)}…` : depot;
  const labelWidth = Math.max(70, label.length * 6.2 + 16);
  const labelX = Math.min(Math.max(depotPt.x - labelWidth / 2, 4), 796 - labelWidth);
  // Several orders can share a drop location; draw each location once.
  const locations = [...new Map(points.map((o) => [o.location_id, o])).values()];
  return <div className="map-canvas"><svg viewBox="0 0 800 430" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Sơ đồ vị trí kho xuất, điểm nhận và tuyến điều vận"><defs><pattern id="grid" width="38" height="38" patternUnits="userSpaceOnUse"><path d="M 38 0 L 0 0 0 38" fill="none" stroke="#e8edf2" strokeWidth="1"/></pattern><filter id="shadow" x="-50%" y="-50%" width="200%" height="200%"><feDropShadow dx="0" dy="2" stdDeviation="3" floodOpacity=".12"/></filter><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0 10 5 0 10z" fill="#e8793c"/></marker></defs><rect width="800" height="430" fill="url(#grid)"/>
    {stops.length > 0 && <polyline points={routePts.map((p) => `${p.x},${p.y}`).join(" ")} className="map-route-line" markerMid="url(#arrow)"/>}
    {locations.map((order) => { const p = coord(order.latitude, order.longitude); const stop = stops.find((s) => s.location_id === order.location_id); const names = points.filter((o) => o.location_id === order.location_id).map((o) => o.external_id).join(", "); return <g key={order.location_id} transform={`translate(${p.x} ${p.y})`} className={`map-point ${stop ? "map-point-active" : ""}`}><title>{`${order.location_name} · ${order.zone}\n${names}${stop ? `\nĐiểm ${stop.sequence} · ETA ${stop.eta}` : ""}`}</title><circle r={stop ? 10 : 6}/>{stop && <text y="4" textAnchor="middle" className="map-point-number">{stop.sequence}</text>}</g>; })}
    <g className="depot-marker" transform={`translate(${depotPt.x} ${depotPt.y})`} filter="url(#shadow)"><title>{depot}</title><circle r="14"/><path d="M-6 1 0-5 6 1v7h-4V4h-4v4h-4z"/></g>
    <g transform={`translate(${labelX} ${depotPt.y + 18})`}><rect width={labelWidth} height="22" rx="5" className="map-label-box"/><text x="8" y="15" className="map-label-text">{label}</text></g>
  </svg><div className="map-scale"><span>SƠ ĐỒ TỌA ĐỘ</span><span>tọa độ tham chiếu</span></div></div>;
}

function PalletView({ route, pallets }: { route: RoutePlan; pallets: (Pallet & { stop: number; drop: string })[] }) {
  const maxL = route.vehicle.inner_length_cm, maxW = route.vehicle.inner_width_cm, maxH = route.vehicle.inner_height_cm;
  const colors = ["#d6e8f7", "#d8efdf", "#fff0d2", "#e9def9", "#f9dce2", "#d8eff0"];
  return <div className="pallet-view"><div className="truck-drawing"><div className="drawing-label">NHÌN TỪ TRÊN · HƯỚNG CỬA XE →</div><div className="floor-shell"><div className="floor-inner">{route.load.packing.placements.map((p) => { const pallet = pallets.find((x) => x.id === p.pallet_id); if (!pallet) return null; return <div key={p.pallet_id} className="pallet-block" title={`${pallet.id} · ${pallet.sku_name} (${pallet.sku_id}) · ${pallet.weight_kg} kg · giao điểm ${pallet.stop}`} style={{ left: `${p.x_cm / maxL * 100}%`, top: `${p.y_cm / maxW * 100}%`, width: `${p.length_cm / maxL * 100}%`, height: `${p.width_cm / maxW * 100}%`, background: colors[(pallet.stop - 1) % colors.length] }}><strong>{pallet.id.slice(-3)}</strong><small>{p.length_cm}×{p.width_cm}</small><i>{pallet.stop}</i></div>; })}{route.load.packing.placements.length === 0 && <div className="floor-empty">Không có sơ đồ sàn khả thi cho tuyến này</div>}</div></div><div className="floor-dimensions"><span>{maxL} cm chiều dài hữu dụng</span><span>{maxW} cm chiều rộng</span></div></div><div className="side-drawing"><div className="drawing-label">NHÌN NGANG · CHIỀU CAO XE {maxH} cm</div><div className="side-shell"><div className="side-inner">{route.load.packing.placements.map((p) => { const pallet = pallets.find((x) => x.id === p.pallet_id); if (!pallet) return null; return <div key={p.pallet_id} className="side-pallet" style={{ left: `${p.x_cm / maxL * 100}%`, width: `${p.length_cm / maxL * 100}%`, height: `${pallet.height_cm / maxH * 100}%`, background: colors[(pallet.stop - 1) % colors.length] }} title={`${pallet.id} · cao ${pallet.height_cm} cm`}><span>{pallet.id.slice(-3)}</span></div>; })}</div></div><div className="floor-dimensions"><span>Không giả định xếp chồng</span><span>Không kiểm tra tải trục</span></div></div><div className="pallet-legend"><div className="pallet-legend-title">Thứ tự giao hàng</div>{route.stops.map((stop) => <span key={stop.order_id}><i style={{ background: colors[(stop.sequence - 1) % colors.length] }}/>{stop.sequence}. {stop.location_name} · {stop.eta}</span>)}</div></div>;
}

function Capacity({ label, used, total, unit }: { label: string; used: number; total: number; unit: string }) { return <div className="capacity-pill"><span>{label}</span><strong>{compact(used)} <small>/ {compact(total)} {unit}</small></strong></div>; }
function Empty({ icon: Icon, title, detail }: { icon: typeof Package; title: string; detail: string }) { return <div className="empty-state"><Icon size={26}/><strong>{title}</strong><span>{detail}</span></div>; }

function PlanActionBar({ plan, busy, onApprove, onBooking, onReplan, note }: { plan: Plan; busy: string; onApprove: (d: "APPROVE" | "REJECT") => void; onBooking: () => void; onReplan: () => void; note: string }) {
  const carrierRoutes = plan.routes.filter((r) => r.kind === "CARRIER").length;
  return <div className="plan-action-bar"><div><div className="approval-status"><span className={`status-dot ${plan.plan_status.toLowerCase()}`}/>{plan.plan_status === "APPROVED" ? "Kế hoạch đã xác nhận" : plan.plan_status === "REJECTED" ? "Kế hoạch đã trả lại — cần lập lại phương án" : "Kế hoạch chờ xác nhận"}</div><p>{note}</p></div><div className="heading-actions">
    {plan.plan_status === "DRAFT" && <><button className="button button-quiet" onClick={() => onApprove("REJECT")} disabled={busy === "approval"}>Trả lại để điều chỉnh</button><button className="button button-primary" onClick={() => onApprove("APPROVE")} disabled={busy === "approval"}>{busy === "approval" ? <LoaderCircle className="spin" size={16}/> : <ShieldCheck size={16}/>} Xác nhận kế hoạch</button></>}
    {plan.plan_status === "APPROVED" && carrierRoutes > 0 && <button className="button button-primary" onClick={onBooking} disabled={busy === "booking"}>{busy === "booking" ? <LoaderCircle className="spin" size={16}/> : <ClipboardCheck size={16}/>} Lập nháp yêu cầu xe ({carrierRoutes})</button>}
    {plan.plan_status === "REJECTED" && <button className="button button-primary" onClick={onReplan} disabled={busy === "optimize"}><Activity size={16}/> Lập lại phương án</button>}
  </div></div>;
}

function OrdersPage({ orders, routeByOrder, hasPlan, query, setQuery, file, setFile, preview, setPreview, previewImport, commitImport, busy }: { orders: Order[]; routeByOrder: Map<string, RoutePlan>; hasPlan: boolean; query: string; setQuery: (s: string) => void; file: File | null; setFile: (f: File | null) => void; preview: ImportPreview | null; setPreview: (v: ImportPreview | null) => void; previewImport: () => void; commitImport: () => void; busy: string }) {
  const counts = preview?.counts; const errors = preview?.errors;
  const pick = (e: React.ChangeEvent<HTMLInputElement>) => { setFile(e.target.files?.[0] ?? null); setPreview(null); e.target.value = ""; };
  return <><div className="page-heading"><div><span className="eyebrow">CHỨNG TỪ GIAO HÀNG · ĐƠN VỊ XẾP HÀNG</span><h1>Lệnh giao hàng & pallet</h1><p>Kiểm soát khách hàng, điểm nhận, SKU, tải trọng và hạn giao theo từng lệnh.</p></div></div>
    <section className="panel import-panel"><div className="panel-heading"><div><h2>Nhập dữ liệu vận hành</h2><p>Bước 1: chọn workbook · Bước 2: kiểm tra · Bước 3: xác nhận ghi vào kịch bản.</p></div><FileSpreadsheet size={20}/></div><div className="import-toolbar"><label className="file-drop"><CloudUpload size={20}/><div><strong>{file?.name ?? "Chọn workbook Excel"}</strong><small>{file ? `${(file.size / 1024).toFixed(1)} KB` : "Tệp .xlsx / .xlsm · tối đa 15 MB"}</small></div><span className="button button-quiet">Duyệt tệp</span><input type="file" accept=".xlsx,.xlsm" onChange={pick}/></label><button className="button button-primary" onClick={previewImport} disabled={!file || busy === "import"}>{busy === "import" ? <LoaderCircle className="spin" size={16}/> : <Search size={16}/>} Kiểm tra workbook</button></div>
      {preview && <div className={`preview-result ${preview.valid ? "valid" : "invalid"}`}><div className="preview-title">{preview.valid ? <CheckCircle2 size={17}/> : <AlertCircle size={17}/>}<strong>{preview.valid ? "Kiểm tra đạt — sẵn sàng xác nhận nhập" : `Workbook có ${errors?.length ?? 0} lỗi cần xử lý`}</strong><span>{counts?.customers ?? 0} khách hàng · {counts?.products ?? 0} SKU · {counts?.orders ?? 0} lệnh · {counts?.pallets ?? 0} pallet · {counts?.locations ?? 0} điểm nhận{preview.scenario_id ? ` · kịch bản ${preview.scenario_id}` : ""}</span></div>{errors?.length ? <ul>{errors.slice(0, 12).map((e) => <li key={e}>{e}</li>)}{errors.length > 12 && <li>… và {errors.length - 12} lỗi khác</li>}</ul> : <p>Kiểm tra cấu trúc và đối chiếu cơ bản đạt. Xác nhận để cập nhật dữ liệu cho kịch bản hiện tại.{hasPlan ? " Sau khi nhập, hãy lập lại phương án vận tải." : ""}</p>}{preview.valid && <button className="button button-primary" onClick={commitImport} disabled={busy === "import"}><Check size={15}/> Xác nhận nhập workbook</button>}</div>}
      <div className="import-warning"><AlertCircle size={14}/> Mã kịch bản phải khớp phiên đang mở. Pallet của lệnh trùng mã sẽ được thay bằng dữ liệu từ workbook.</div></section>
    <section className="panel table-panel"><div className="panel-heading"><div><h2>Sổ lệnh giao hàng</h2><p>{orders.length} lệnh{query ? " khớp tìm kiếm" : " trong kịch bản hiện tại"}</p></div><div className="search-box table-search"><Search size={15}/><input aria-label="Tìm lệnh giao hàng" placeholder="Tìm mã lệnh, khách hàng, điểm nhận…" value={query} onChange={(e) => setQuery(e.target.value)}/>{query && <button className="clear-search" aria-label="Xoá tìm kiếm" onClick={() => setQuery("")}><X size={13}/></button>}</div></div><div className="table-wrap"><table><thead><tr><th>MÃ LỆNH GIAO</th><th>KHÁCH HÀNG</th><th>ĐIỂM NHẬN</th><th>SẴN SÀNG / HẠN GIAO</th><th>PALLET</th><th>TẢI HÀNG</th><th>HẠNG XE TỐI THIỂU</th><th>PHÂN TUYẾN</th></tr></thead><tbody>{orders.map((o) => { const route = routeByOrder.get(o.id); const stop = route?.stops.find((s) => s.order_id === o.id); return <tr key={o.id}><td><strong>{o.external_id}</strong><small>{statusLabel(o.status)}</small></td><td><strong>{o.customer_name}</strong><small>{o.customer_id}</small></td><td><strong>{o.location_name}</strong><small>{o.zone}</small></td><td>{o.ready_at} → {o.due_at}<small>xuất kho → hạn giao</small></td><td>{o.pallets.length}</td><td>{compact(o.total_weight_kg)} kg<small>{compact(o.total_volume_m3)} m³</small></td><td>{o.minimum_vehicle_class === "ANY_COMPATIBLE" ? "Theo tải hàng" : o.minimum_vehicle_class}</td><td>{route ? <><span className={`table-status state-${route.state.toLowerCase()}`}>{routeTitle(route)}</span><small>ETA {stop?.eta}</small></> : <span className="table-status pending">{hasPlan ? "Chưa xếp" : "Chưa lập phương án"}</span>}</td></tr>; })}{orders.length === 0 && <tr><td colSpan={8}>Không có lệnh phù hợp.</td></tr>}</tbody></table></div></section></>;
}

function MastersPage({ customers, products }: { customers: Customer[]; products: Product[] }) {
  return <><div className="page-heading"><div><span className="eyebrow">DANH MỤC CHỦ · MASTER DATA</span><h1>Khách hàng & hàng hóa</h1><p>Danh mục tham chiếu được liên kết với lệnh giao hàng, điểm nhận và đơn vị xếp hàng.</p></div><span className="module-chip"><Building2 size={15}/>{customers.length} khách hàng · {products.length} mã SKU</span></div><section className="panel table-panel"><div className="panel-heading"><div><h2>Danh mục khách hàng</h2><p>Phân khúc, kênh giao dịch, điều khoản thanh toán và mức dịch vụ.</p></div><Users size={20}/></div><div className="table-wrap"><table><thead><tr><th>MÃ KHÁCH HÀNG</th><th>TÊN GIAO DỊCH</th><th>PHÂN KHÚC</th><th>KÊNH</th><th>ĐIỀU KHOẢN</th><th>MỨC DỊCH VỤ</th><th>TRẠNG THÁI HỒ SƠ</th></tr></thead><tbody>{customers.map((c) => <tr key={c.id}><td><strong>{c.id}</strong></td><td><strong>{c.display_name}</strong><small>{c.legal_name}</small></td><td>{masterLabel(c.customer_segment)}</td><td>{masterLabel(c.sales_channel)}</td><td>{masterLabel(c.payment_terms)}</td><td>{masterLabel(c.service_level)}</td><td><span className={`table-status ${c.status === "ACTIVE" ? "ready" : "pending"}`}>{statusLabel(c.status)}</span></td></tr>)}</tbody></table></div></section><section className="panel table-panel"><div className="panel-heading"><div><h2>Danh mục hàng hóa (SKU)</h2><p>Quy cách đơn vị tính và yêu cầu xử lý/xếp dỡ mặc định.</p></div><Package size={20}/></div><div className="table-wrap"><table><thead><tr><th>MÃ SKU</th><th>TÊN HÀNG / QUY CÁCH</th><th>NHÓM HÀNG</th><th>ĐƠN VỊ TÍNH</th><th>MÃ XỬ LÝ</th><th>XẾP CHỒNG</th><th>TRẠNG THÁI</th></tr></thead><tbody>{products.map((p) => <tr key={p.id}><td><strong>{p.id}</strong></td><td>{p.name}</td><td>{masterLabel(p.category)}</td><td>{masterLabel(p.base_uom)}</td><td>{masterLabel(p.handling_code)}</td><td>{p.stackable_default ? "Cho phép theo mặc định" : "Không xếp chồng"}</td><td><span className={`table-status ${p.status === "ACTIVE" ? "ready" : "pending"}`}>{statusLabel(p.status)}</span></td></tr>)}</tbody></table></div></section></>;
}

const quoteFieldLabels: Record<string, string> = { rate_per_km_vnd: "Đơn giá mỗi km", minimum_fare_vnd: "Cước tối thiểu", callout_fee_vnd: "Phí điều xe", stop_fee_vnd: "Phụ phí điểm dừng", vat_rate_assumption: "VAT", return_trip_rule: "Tính chiều về", currency: "Tiền tệ", vehicle_class_hint: "Gợi ý hạng xe", validity_hint: "Hiệu lực", assumptions: "Giả định" };
function quoteFieldValue(key: string, value: unknown) {
  if (value === null || value === undefined || (Array.isArray(value) && value.length === 0)) return "Chưa nhận diện";
  if (key.endsWith("_vnd") && typeof value === "number") return money(value);
  if (key === "vat_rate_assumption" && typeof value === "number") return `${compact(value * 100)}%`;
  if (key === "return_trip_rule") return masterLabel(String(value));
  return Array.isArray(value) ? value.join("; ") : typeof value === "object" ? JSON.stringify(value) : String(value);
}

function CarriersPage({ quotes, availability, quoteText, setQuoteText, onExtract, result, busy }: { quotes: Quote[]; availability: Availability[]; quoteText: string; setQuoteText: (s: string) => void; onExtract: (e: React.FormEvent) => void; result: Record<string, unknown> | null; busy: string }) {
  const fields = result?.fields as Record<string, unknown> | undefined;
  const confirmed = availability.filter((a) => a.status === "CONFIRMED").reduce((sum, a) => sum + a.vehicles_available, 0);
  return <><div className="page-heading"><div><span className="eyebrow">QUẢN LÝ NHÀ CUNG CẤP · BIỂU GIÁ</span><h1>Nhà cung cấp vận tải & biểu giá</h1><p>So sánh báo giá, xác nhận năng lực nhà xe trước khi đưa vào phương án.</p></div><span className="module-chip"><Truck size={15}/> {quotes.length} biểu cước · {confirmed} xe thuê đã xác nhận</span></div>
    <section className="panel table-panel"><div className="panel-heading"><div><h2>Năng lực nhà xe trong ca</h2><p>Chỉ năng lực đã xác nhận được đưa vào bộ lập tuyến; năng lực chờ xác nhận bị loại trừ.</p></div><ClipboardCheck size={20}/></div><div className="table-wrap"><table><thead><tr><th>ĐƠN VỊ VẬN TẢI</th><th>LOẠI XE</th><th>SỐ XE</th><th>KHUNG GIỜ</th><th>XÁC NHẬN</th></tr></thead><tbody>{availability.map((a) => <tr key={a.id}><td><strong>{a.carrier_name}</strong><small>{a.id}</small></td><td>{a.class_id}</td><td>{a.vehicles_available}</td><td>{a.window_start}–{a.window_end}</td><td><span className={`table-status ${a.status === "CONFIRMED" ? "ready" : "pending"}`}>{a.status === "CONFIRMED" ? "Đã xác nhận" : "Chờ xác nhận · không dùng"}</span></td></tr>)}{availability.length === 0 && <tr><td colSpan={5}>Chưa có khai báo năng lực nhà xe.</td></tr>}</tbody></table></div></section>
    <section className="panel table-panel"><div className="panel-heading"><div><h2>Biểu giá nhà cung cấp</h2><p>Biểu giá mô phỏng; chưa có hiệu lực thanh toán hoặc lệnh vận tải thực tế. Giá chưa gồm VAT.</p></div><Wallet size={20}/></div><div className="table-wrap"><table><thead><tr><th>ĐƠN VỊ VẬN TẢI</th><th>LOẠI XE</th><th>SỨC CHỨA</th><th>ĐƠN GIÁ KM</th><th>PHÍ ĐIỀU XE</th><th>PHỤ PHÍ ĐIỂM</th><th>GIÁ TỐI THIỂU</th><th>CHIỀU VỀ · VAT</th><th>TRẠNG THÁI</th></tr></thead><tbody>{quotes.map((q) => <tr key={q.id}><td><strong>{q.carrier_name}</strong><small>{q.id}</small></td><td>{q.class_id}</td><td>{compact(q.capacity_kg)} kg<small>{compact(q.usable_volume_m3)} m³</small></td><td>{money(q.rate_per_km_vnd)}</td><td>{money(q.callout_fee_vnd)}</td><td>{money(q.stop_fee_vnd)}</td><td>{money(q.minimum_fare_vnd)}</td><td>{masterLabel(q.return_trip_rule)}<small>VAT {compact(q.vat_rate_assumption * 100)}%</small></td><td><span className="table-status ready">{statusLabel(q.status)}</span></td></tr>)}</tbody></table></div></section>
    <section className="panel quote-ai-panel"><div className="panel-heading"><div><div className="section-title-row"><Activity size={18}/><h2>Trợ lý đọc báo giá</h2><span className="panel-tag">AI CÓ KIỂM SOÁT</span></div><p>Dán nội dung báo giá; các trường trích xuất luôn cần nhân viên kiểm tra lại và không tự lưu vào biểu giá.</p></div></div><form onSubmit={onExtract} className="quote-form"><textarea aria-label="Nội dung báo giá" value={quoteText} onChange={(e) => setQuoteText(e.target.value)} placeholder="Ví dụ: xe tải 1.5 tấn, đơn giá 15.500đ/km, phí điều xe 100.000đ, tối thiểu 360.000đ, điểm dừng thêm 20.000đ, VAT 10%, tính một chiều…" required minLength={3} maxLength={10000}/><div className="quote-form-footer"><span>Chế độ trích xuất phụ thuộc cấu hình AI Gateway; nếu chưa cấu hình, bộ quy tắc cục bộ sẽ trả kết quả.</span><button className="button button-primary" disabled={busy === "quote-ai" || quoteText.trim().length < 3}>{busy === "quote-ai" ? <LoaderCircle className="spin" size={15}/> : <Search size={15}/>} Trích xuất điều khoản</button></div></form>{fields && <div className="extraction-result"><div className="preview-title"><BadgeCheck size={17}/><strong>Kết quả trích xuất · {result?.source === "AI_GATEWAY" ? "AI Gateway" : "Bộ quy tắc cục bộ"}</strong><span>{typeof result?.confidence === "number" ? `Độ phủ ${Math.round((result.confidence as number) * 100)}% · ` : ""}Cần kiểm tra thủ công</span></div><div className="extraction-grid">{Object.entries(fields).map(([k, v]) => <div key={k}><small>{quoteFieldLabels[k] ?? k.replaceAll("_", " ")}</small><strong className={v === null ? "muted" : ""}>{quoteFieldValue(k, v)}</strong></div>)}</div><p>Kết quả chỉ là gợi ý. Kiểm tra nguồn, đơn vị, tiền tệ, hiệu lực và thuế trước khi cập nhật biểu giá.</p></div>}</section></>;
}

function ApprovalPage({ plan, unassignedCount, unassigned, reasons, onApprove, onBooking, onReplan, busy, onRouteState }: { plan: Plan | null; unassignedCount: number; unassigned: Order[]; reasons: Map<string, string>; onApprove: (d: "APPROVE" | "REJECT") => void; onBooking: () => void; onReplan: () => void; busy: string; onRouteState: (r: RoutePlan, s: "ACTIVE" | "COMPLETED") => void }) {
  const approved = plan?.plan_status === "APPROVED";
  return <><div className="page-heading"><div><span className="eyebrow">KIỂM SOÁT KẾ HOẠCH · NHẬT KÝ NGHIỆP VỤ</span><h1>Kế hoạch vận tải</h1><p>Rà soát phương án, ghi nhận trạng thái tuyến và quyết định vận hành.</p></div>{plan && <span className={`table-status ${plan.plan_status.toLowerCase()}`}>{statusLabel(plan.plan_status)}</span>}</div>
    {!plan ? <section className="panel"><Empty icon={ClipboardCheck} title="Chưa có kế hoạch" detail="Lập phương án vận tải ở màn hình Điều vận trước khi xác nhận nghiệp vụ."/></section> : <>
      <section className="approval-summary"><div><span>PHƯƠNG ÁN HIỆN TẠI</span><strong>{plan.plan_id.slice(0, 8).toUpperCase()}</strong><small>{plan.summary.assigned}/{plan.summary.assigned + unassignedCount} đơn đã xếp · {plan.summary.vehicles_used} xe · {plan.summary.trips ?? plan.routes.length} chuyến</small></div><div><span>CHI PHÍ ƯỚC TÍNH</span><strong>{money(plan.summary.cost_vnd)}</strong><small>{compact(plan.summary.distance_km)} km tổng tuyến · đã gồm VAT xe thuê</small></div><div><span>ĐƠN CHƯA XẾP</span><strong>{unassignedCount}</strong><small>{unassignedCount ? "Rà soát nguyên nhân trước khi xác nhận" : "Tất cả đơn đã có tuyến"}</small></div><div><span>NGUỒN DỮ LIỆU</span><strong>{plan.synthetic_data ? "MÔ PHỎNG" : "VẬN HÀNH"}</strong><small>Bộ lập tuyến: chèn lệnh theo chi phí tăng dần (heuristic)</small></div></section>
      <section className="panel table-panel"><div className="panel-heading"><div><h2>Danh sách tuyến</h2><p>{approved ? "Bấm “Xuất phát” khi xe rời kho; tuyến đang chạy được giữ nguyên khi lập lại phương án." : "Xác nhận kế hoạch trước khi cho tuyến xuất phát."}</p></div><Route size={20}/></div><div className="approval-routes">{plan.routes.map((r) => <div key={r.route_key} className="approval-route"><div className="route-icon route-vehicle"><Truck size={16}/></div><div className="approval-route-main"><strong>{routeTitle(r)} · {routeSubtitle(r)}</strong><small>{r.departure ? `Xuất ${r.departure} → ` : ""}{r.stops.map((s) => `${s.external_id} (${s.eta})`).join(" → ")}{r.return_at ? ` → về kho ${r.return_at}` : ""}</small><small>{compact(r.load.weight_kg)} kg / {compact(r.load.volume_m3)} m³ · {compact(r.distance_km)} km · {hoursLabel(r.duration_min)} · pallet: {statusLabel(r.load.packing.status)}</small></div><div className="approval-route-cost"><span>{money(r.cost_vnd)}</span><span className={`route-state state-${r.state.toLowerCase()}`}>{routeStateLabel(r.state)}</span></div><div className="approval-route-actions">{r.state === "PLANNED" && <button className="button button-quiet button-small" title={approved ? "" : "Cần xác nhận kế hoạch trước"} onClick={() => onRouteState(r, "ACTIVE")} disabled={!approved || busy === `route-${r.route_key}`}>Xuất phát</button>}{r.state === "ACTIVE" && <button className="button button-quiet button-small" onClick={() => onRouteState(r, "COMPLETED")} disabled={busy === `route-${r.route_key}`}>Hoàn tất</button>}{r.state === "COMPLETED" && <span className="done-label"><Check size={13}/> Đã xong</span>}</div></div>)}{plan.routes.length === 0 && <Empty icon={Truck} title="Không có tuyến" detail="Không đơn nào xếp được với đội xe hiện có."/>}</div></section>
      {unassigned.length > 0 && <section className="panel unassigned-panel"><h2><AlertCircle size={17}/> Đơn chưa xếp tuyến</h2>{unassigned.map((o) => <div key={o.id}><strong>{o.external_id}</strong><span>{o.customer_name} · hạn {o.due_at}</span><span>{reasonLabel(reasons.get(o.id) ?? "NOT_IN_PLAN")}</span></div>)}</section>}
      <PlanActionBar plan={plan} busy={busy} onApprove={onApprove} onBooking={onBooking} onReplan={onReplan} note="Ghi nhận xác nhận nghiệp vụ và giữ nhật ký người thao tác."/>
    </>}</>;
}

function TeamPage({ employees, form, setForm, onSubmit, busy }: { employees: Employee[]; form: { employee_code: string; name: string; email: string; position: string }; setForm: (f: { employee_code: string; name: string; email: string; position: string }) => void; onSubmit: (e: React.FormEvent) => void; busy: string }) {
  return <><div className="page-heading"><div><span className="eyebrow">DANH MỤC NHÂN SỰ</span><h1>Nhân viên logistics</h1><p>Danh bạ nhân sự của bộ phận logistics.</p></div><span className="module-chip"><Users size={15}/>{employees.length} nhân viên</span></div><div className="team-layout"><section className="panel table-panel"><div className="panel-heading"><div><h2>Danh bạ phòng logistics</h2><p>Thông tin liên hệ và chức danh nhân viên.</p></div><UserRound size={20}/></div><div className="table-wrap"><table><thead><tr><th>MÃ NHÂN VIÊN</th><th>HỌ TÊN</th><th>CHỨC DANH</th><th>EMAIL CÔNG VIỆC</th><th>PHÒNG BAN</th><th>TRẠNG THÁI</th></tr></thead><tbody>{employees.map((e) => <tr key={e.id}><td><strong>{e.employee_code || "—"}</strong></td><td>{e.name}</td><td>{e.position || "Nhân viên logistics"}</td><td>{e.email}</td><td>{e.department}</td><td><span className={`table-status ${e.active ? "ready" : "pending"}`}>{e.active ? "ĐANG LÀM VIỆC" : "NGỪNG HOẠT ĐỘNG"}</span></td></tr>)}</tbody></table></div></section><section className="panel employee-form-panel"><div className="panel-heading"><div><h2>Thêm hồ sơ nhân viên</h2><p>Thêm thông tin vào danh bạ phòng logistics.</p></div><Plus size={19}/></div><form onSubmit={onSubmit}><label>Mã nhân viên<input required value={form.employee_code} onChange={(e) => setForm({ ...form, employee_code: e.target.value })} placeholder="EMP-LOG-0005"/></label><label>Họ và tên<input required minLength={2} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Nguyễn Văn A"/></label><label>Email công việc<input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="ten@doanhnghiep.vn"/></label><label>Chức danh<input value={form.position} onChange={(e) => setForm({ ...form, position: e.target.value })}/></label><div className="employee-note"><Users size={14}/> Hệ thống dùng chung cho nhân viên logistics; không cần tài khoản đăng nhập.</div><button className="button button-primary" disabled={busy === "employee"}>{busy === "employee" ? <LoaderCircle className="spin" size={15}/> : <Plus size={15}/>} Thêm nhân viên</button></form></section></div></>;
}

function AuditTable({ events }: { events: Audit[] }) {
  return <section className="panel audit-panel"><div className="panel-heading"><div><h2>Nhật ký hoạt động</h2><p>Lưu thời điểm, người thao tác chung, loại thao tác và đối tượng để truy vết (100 sự kiện gần nhất).</p></div><Activity size={19}/></div><div className="table-wrap"><table><thead><tr><th>THỜI ĐIỂM</th><th>NGƯỜI THAO TÁC</th><th>HÀNH ĐỘNG</th><th>ĐỐI TƯỢNG</th></tr></thead><tbody>{events.map((event) => <tr key={event.id}><td>{new Date(/[zZ]|[+-]\d\d:\d\d$/.test(event.created_at) ? event.created_at : `${event.created_at}Z`).toLocaleString("vi-VN")}</td><td>{String(event.details.actor_name ?? event.details.employee_code ?? "Nhân viên")}</td><td><strong>{auditLabel(event.action)}</strong><small>{event.action}</small></td><td>{event.entity_type} · {event.entity_id.slice(0, 24)}</td></tr>)}{events.length === 0 && <tr><td colSpan={4}>Chưa có hoạt động được ghi nhận.</td></tr>}</tbody></table></div></section>;
}
