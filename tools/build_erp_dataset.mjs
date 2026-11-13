import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "E:/hackathon business/outputs/2026-11-12-fleetmix-data/FleetMix_AI_Operational_Sample_Data.xlsx";
const outputDir = "E:/hackathon business/outputs/01a1cbad-1a1e-7de1-899b-92bedce65edf";
const outputPath = `${outputDir}/FleetMix_ERP_Operational_Dataset.xlsx`;
const previewDir = path.join(os.tmpdir(), "fleetmix-erp-previews");
const company = {
  id: "ORG-AP-001",
  legalName: "Công ty Cổ phần Phân phối An Phúc",
  displayName: "An Phúc Distribution",
  unit: "Trung tâm Vận hành Logistics",
};
const operationDate = "2026-11-13";
const scenarioId = "OPS-HCM-20261113";
const depotId = "WH-AP-HCM-TANBINH-001";

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));

function colLetter(n) {
  let s = "";
  while (n > 0) {
    const r = (n - 1) % 26;
    s = String.fromCharCode(65 + r) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

function records(sheetName) {
  const values = workbook.worksheets.getItem(sheetName).getUsedRange().values;
  const headers = values[0].map((v) => String(v ?? ""));
  return values.slice(1).filter((row) => row.some((v) => v !== null && v !== undefined && v !== ""))
    .map((row) => Object.fromEntries(headers.map((header, i) => [header, row[i] ?? null])));
}

function writeTable(sheetName, headers, rows, tableName, widths = {}) {
  let sheet;
  try {
    sheet = workbook.worksheets.getItem(sheetName);
  } catch {
    sheet = workbook.worksheets.add(sheetName);
  }
  for (const table of [...sheet.tables.items]) table.delete();
  const used = sheet.getUsedRange();
  if (used) used.clear({ applyTo: "contents" });
  const values = [headers, ...rows.map((row) => headers.map((key) => row[key] ?? null))];
  const end = `${colLetter(headers.length)}${values.length}`;
  sheet.getRange(`A1:${end}`).values = values;
  const table = sheet.tables.add(`A1:${end}`, true, tableName);
  table.style = "TableStyleMedium2";
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
  sheet.getRange(`A1:${end}`).format.verticalAlignment = "center";
  for (const [column, width] of Object.entries(widths)) {
    sheet.getRange(`${column}1:${column}${values.length}`).format.columnWidth = width;
  }
  return sheet;
}

function setColumnFormat(sheetName, range, format) {
  workbook.worksheets.getItem(sheetName).getRange(range).format.numberFormat = format;
}

const originalOrders = records("Orders");
const originalPallets = records("Pallets");
const originalFleet = records("Fleet");
const originalClasses = records("Vehicle Classes");
const originalCarriers = records("Carriers");
const originalRates = records("Carrier Rates");
const originalAvailability = records("Availability");
const originalScenario = records("Scenario")[0];

const customers = [
  ["Công ty TNHH Thương mại Minh Phát", "Minh Phát Mart", "RETAIL_CHAIN", "MODERN_TRADE", "NET30", "SLA-AM"],
  ["Công ty Cổ phần Bán lẻ Thành Đạt", "Thành Đạt Retail", "RETAIL_CHAIN", "MODERN_TRADE", "NET30", "SLA-AM"],
  ["Công ty TNHH Phân phối Hưng Thịnh", "Hưng Thịnh Distribution", "DISTRIBUTOR", "GENERAL_TRADE", "NET15", "SLA-STD"],
  ["Công ty Cổ phần Thực phẩm Đại Nam", "Đại Nam Foods", "FOOD_SERVICE", "B2B", "NET30", "SLA-PM"],
  ["Công ty TNHH Thương mại Phương Nam", "Phương Nam Trading", "DISTRIBUTOR", "GENERAL_TRADE", "NET15", "SLA-AM"],
  ["Công ty Cổ phần Tiêu dùng Việt", "Viet Consumer", "RETAIL_CHAIN", "MODERN_TRADE", "NET30", "SLA-STD"],
  ["Công ty TNHH Bán lẻ Gia Hưng", "Gia Hưng Stores", "RETAIL_CHAIN", "MODERN_TRADE", "NET30", "SLA-PM"],
  ["Công ty TNHH Dịch vụ Thương mại Nam Việt", "Nam Việt Supply", "DISTRIBUTOR", "GENERAL_TRADE", "NET15", "SLA-STD"],
  ["Công ty Cổ phần Thương mại An Khang", "An Khang Market", "RETAIL_CHAIN", "MODERN_TRADE", "NET30", "SLA-AM"],
  ["Công ty TNHH Phân phối Hoàng Gia", "Hoàng Gia Distribution", "DISTRIBUTOR", "GENERAL_TRADE", "NET15", "SLA-PM"],
  ["Công ty Cổ phần Bán lẻ Phúc An", "Phúc An Retail", "RETAIL_CHAIN", "MODERN_TRADE", "NET30", "SLA-STD"],
  ["Công ty TNHH Thương mại Tân Bình", "Tân Bình Wholesale", "DISTRIBUTOR", "GENERAL_TRADE", "NET15", "SLA-AM"],
].map((x, i) => ({
  customer_id: `CUS-AP-${String(i + 1).padStart(4, "0")}`,
  legal_name: x[0], display_name: x[1], customer_segment: x[2], sales_channel: x[3],
  payment_terms: x[4], service_level: x[5], status: "ACTIVE", account_owner: ["Nguyễn Hoàng Nam", "Lê Thu Hà", "Trần Minh Đức"][i % 3],
  is_synthetic: true,
}));

const locationSeed = [
  ["Q.1", "P. Bến Nghé", 10.7769, 106.7009],
  ["Q.3", "P. Võ Thị Sáu", 10.7823, 106.6844],
  ["Q.4", "P. Khánh Hội", 10.7655, 106.7058],
  ["Q.7", "P. Tân Phú", 10.7329, 106.7179],
  ["Q.10", "P. 12", 10.7731, 106.6670],
  ["Bình Thạnh", "P. 25", 10.8017, 106.7096],
  ["Gò Vấp", "P. 10", 10.8393, 106.6651],
  ["TP. Thủ Đức", "P. Thảo Điền", 10.8495, 106.7537],
  ["Tân Phú", "P. Tây Thạnh", 10.7901, 106.6272],
  ["Phú Nhuận", "P. 9", 10.7993, 106.6790],
  ["Bình Tân", "P. Bình Trị Đông", 10.7551, 106.6070],
  ["Nhà Bè", "X. Phước Kiển", 10.6962, 106.7016],
];
const locationNames = [
  "Điểm nhận Minh Phát - Bến Nghé", "Điểm nhận Thành Đạt - Võ Thị Sáu", "Kho nhận Hưng Thịnh - Khánh Hội",
  "Điểm nhận Đại Nam - Tân Phú", "Điểm nhận Phương Nam - Quận 10", "Trung tâm nhận Việt Consumer - Bình Thạnh",
  "Điểm nhận Gia Hưng - Gò Vấp", "Kho nhận Nam Việt - Thảo Điền", "Điểm nhận An Khang - Tây Thạnh",
  "Điểm nhận Hoàng Gia - Phú Nhuận", "Kho nhận Phúc An - Bình Tân", "Điểm nhận Tân Bình Wholesale - Nhà Bè",
];
const locations = [{
  location_id: depotId, customer_id: null, location_name: "Trung tâm phân phối An Phúc - Tân Bình", district_or_zone: "Tân Bình",
  address_text: "Khu vực Tân Bình, TP. Hồ Chí Minh (địa chỉ tham chiếu mô phỏng)", latitude: 10.8010, longitude: 106.6520,
  open_from: "06:00", open_until: "22:00", service_min_default: 30, location_type: "DEPOT", is_synthetic: true,
  notes: "Kho xuất hàng trung tâm. Địa chỉ và tọa độ mô phỏng.",
}, ...customers.map((customer, i) => ({
  location_id: `LOC-AP-HCM-${String(i + 1).padStart(3, "0")}`, customer_id: customer.customer_id, location_name: locationNames[i],
  district_or_zone: locationSeed[i][0], address_text: `${locationSeed[i][1]}, ${locationSeed[i][0]}, TP. Hồ Chí Minh (địa chỉ tham chiếu mô phỏng)`,
  latitude: locationSeed[i][2], longitude: locationSeed[i][3], open_from: "08:00", open_until: "18:00",
  service_min_default: i % 4 === 0 ? 25 : 20, location_type: "CUSTOMER", is_synthetic: true,
  notes: "Điểm nhận hàng của khách hàng. Tọa độ tham chiếu mô phỏng.",
}))];

const productNames = [
  "Nước uống đóng chai 500 ml (24 chai/thùng)", "Sữa tiệt trùng 180 ml (48 hộp/thùng)",
  "Nước trái cây 1 L (12 chai/thùng)", "Nước giải khát có ga 330 ml (24 lon/thùng)",
  "Dầu ăn thực vật 1 L (12 chai/thùng)", "Nước rửa chén 750 ml (12 chai/thùng)",
  "Giấy vệ sinh cuộn lớn (12 cuộn/thùng)", "Khăn giấy hộp 180 tờ (24 hộp/thùng)",
  "Mì ăn liền 75 g (30 gói/thùng)", "Bánh quy bơ 300 g (12 hộp/thùng)",
  "Cà phê hòa tan 3 trong 1 (24 hộp/thùng)", "Bột giặt 3 kg (4 túi/thùng)",
  "Nước giặt 2.4 L (6 chai/thùng)", "Dầu gội 650 g (12 chai/thùng)",
  "Thực phẩm đóng hộp 400 g (24 lon/thùng)", "Ngũ cốc dinh dưỡng 500 g (12 hộp/thùng)",
  "Nước tương 500 ml (12 chai/thùng)", "Nước lau sàn 1 L (12 chai/thùng)",
];
const productCategories = ["BEVERAGE", "DAIRY", "BEVERAGE", "BEVERAGE", "GROCERY", "HOUSEHOLD", "PAPER_GOODS", "PAPER_GOODS", "GROCERY", "SNACKS", "BEVERAGE", "HOUSEHOLD", "HOUSEHOLD", "PERSONAL_CARE", "GROCERY", "GROCERY", "GROCERY", "HOUSEHOLD"];
const products = productNames.map((sku_name, i) => ({
  sku_id: `SKU-AP-${String(i + 1).padStart(4, "0")}`, sku_name, category: productCategories[i], base_uom: "CASE",
  handling_code: "GENERAL", stackable_default: ![6, 7, 13].includes(i),
  rotation_rule: "BASE_ROTATION_ALLOWED", status: "ACTIVE", is_synthetic: true,
}));

const employees = [
  ["USR-LOG-0001", "EMP-LOG-0001", "Nguyễn Thị Minh Anh", "minh.anh@anphuc-logistics.example", "Chuyên viên điều vận", "+84 000 000 0001"],
  ["USR-LOG-0002", "EMP-LOG-0002", "Trần Quốc Bảo", "quoc.bao@anphuc-logistics.example", "Chuyên viên kế hoạch vận tải", "+84 000 000 0002"],
  ["USR-LOG-0003", "EMP-LOG-0003", "Lê Hoàng Phúc", "hoang.phuc@anphuc-logistics.example", "Chuyên viên mua dịch vụ vận tải", "+84 000 000 0003"],
  ["USR-LOG-0004", "EMP-LOG-0004", "Phạm Ngọc Hân", "ngoc.han@anphuc-logistics.example", "Chuyên viên kiểm soát cước", "+84 000 000 0004"],
].map((x) => ({ user_id: x[0], employee_code: x[1], full_name: x[2], email: x[3], department: "LOGISTICS", position: x[4], phone: x[5], active: true, is_synthetic: true }));

const oldSkuMap = new Map(Array.from({ length: 18 }, (_, i) => [`SKU-DEMO-${String(i + 1).padStart(2, "0")}`, `SKU-AP-${String(i + 1).padStart(4, "0")}`]));
const newOrderIdByOld = new Map(originalOrders.map((row, i) => [row.order_id, `DO-HCM-${operationDate.replaceAll("-", "")}-${String(i + 1).padStart(4, "0")}`]));
const newLocationByCustomer = new Map(customers.map((customer, i) => [customer.customer_id, locations[i + 1].location_id]));
const palletRows = originalPallets.map((row, i) => {
  const order = originalOrders.find((x) => x.order_id === row.order_id);
  const customerIndex = Math.floor(originalOrders.indexOf(order) / 2);
  const skuId = oldSkuMap.get(row.sku_id) ?? "SKU-AP-0001";
  const productIndex = Number(skuId.slice(-4)) - 1;
  let length = Number(row.length_cm), width = Number(row.width_cm), height = Number(row.height_cm);
  if (i === 0) { length = 120; width = 100; height = 140; }
  const volume = Math.round(length * width * height / 1_000_000 * 1000) / 1000;
  return {
    pallet_id: `PLT-HCM-${operationDate.replaceAll("-", "")}-${String(i + 1).padStart(5, "0")}`,
    scenario_id: scenarioId, order_id: newOrderIdByOld.get(row.order_id), sku_id: skuId,
    description: productNames[productIndex], weight_kg: Number(row.weight_kg), length_cm: length, width_cm: width, height_cm: height,
    volume_m3: volume, stackable: row.stackable, max_stack: row.stackable ? Math.max(2, Number(row.max_stack ?? 2)) : 1,
    rotation_rule: row.rotation_rule, handling_code: i === 0 ? "GENERAL" : row.handling_code,
    drop_location_id: locations[customerIndex + 1].location_id, is_synthetic: true,
  };
});

const palletsByOrder = new Map();
for (const pallet of palletRows) {
  const list = palletsByOrder.get(pallet.order_id) ?? [];
  list.push(pallet);
  palletsByOrder.set(pallet.order_id, list);
}
const orderRows = originalOrders.map((row, i) => {
  const customer = customers[Math.floor(i / 2)];
  const orderId = newOrderIdByOld.get(row.order_id);
  const lines = palletsByOrder.get(orderId) ?? [];
  return {
    scenario_id: scenarioId, order_id: orderId, customer_id: customer.customer_id, order_type: "CUSTOMER_DELIVERY",
    drop_location_id: newLocationByCustomer.get(customer.customer_id), ready_at: row.ready_at, due_at: row.due_at,
    service_min: Number(row.service_min), priority: row.priority, status: "READY", split_allowed: Boolean(row.split_allowed),
    total_weight_kg: lines.reduce((sum, p) => sum + p.weight_kg, 0),
    total_volume_m3: Math.round(lines.reduce((sum, p) => sum + p.volume_m3, 0) * 1000) / 1000,
    minimum_vehicle_class: i === 0 ? "TRUCK-1T5" : (row.minimum_vehicle_class || "ANY_COMPATIBLE"),
    notes: row.priority === "HIGH"
      ? "Giao trong khung giờ đã xác nhận. Đối soát số kiện theo chứng từ bàn giao."
      : "Giao đủ số kiện theo lệnh giao hàng. Ghi nhận xác nhận bàn giao khi hoàn tất.",
    is_synthetic: true,
  };
});

const organizationRows = [{
  organization_id: company.id, legal_name: company.legalName, display_name: company.displayName,
  business_unit: company.unit, industry: "Phân phối hàng tiêu dùng và giao nhận B2B",
  head_office_area: "Tân Bình, TP. Hồ Chí Minh", default_currency: "VND", timezone: "Asia/Ho_Chi_Minh",
  data_provenance: "SYNTHETIC_SAMPLE", is_synthetic: true,
}];

const scenarioRow = {
  scenario_id: scenarioId, operation_date: originalScenario.operation_date,
  scenario_name: "Kế hoạch phân phối TP. Hồ Chí Minh - ca ngày", depot_id: depotId,
  service_area: "TP. Hồ Chí Minh và khu vực lân cận", currency: "VND", timezone: "Asia/Ho_Chi_Minh",
  planning_start: originalScenario.planning_start, planning_end: originalScenario.planning_end,
  data_provenance: "SYNTHETIC_SAMPLE",
  notes: "Kịch bản tham chiếu mô phỏng cho phân phối hàng tiêu dùng. Không đại diện dữ liệu của doanh nghiệp có thật.",
};

const vehicleClassNotes = {
  "VAN-800": "Van tải nhẹ, phù hợp giao hàng nội đô và điểm nhận hạn chế không gian.",
  "TRUCK-1T5": "Xe tải nhẹ 1,5 tấn, phù hợp giao hàng nội thành.",
  "TRUCK-2T": "Xe tải 2 tấn, phù hợp gom đơn cùng khu vực.",
  "TRUCK-2T5": "Xe tải 2,5 tấn, phù hợp tuyến nhiều điểm giao.",
  "TRUCK-3T5": "Xe tải 3,5 tấn, phù hợp lệnh giao có tải trọng lớn.",
  "TRUCK-5T": "Xe tải 5 tấn, phù hợp tuyến liên quận và hàng cồng kềnh.",
};
const classRows = originalClasses.map((row) => ({ ...row, notes: vehicleClassNotes[row.vehicle_class] ?? "Hạng xe tham chiếu theo tải trọng và kích thước thùng." }));

const fleetRows = originalFleet.map((row, i) => ({
  ...row, vehicle_id: `VH-AP-${String(i + 1).padStart(3, "0")}`,
  plate_number: `51D-${String(180 + i * 37).padStart(3, "0")}.XX`,
  start_depot_id: depotId, end_depot_id: depotId, fleet_type: "INTERNAL",
  status: i === originalFleet.length - 1 ? "MAINTENANCE" : "AVAILABLE",
  is_synthetic: true,
}));

const carrierNames = [
  "Công ty TNHH Vận tải Đông Nam", "Công ty Cổ phần Giao nhận An Khang",
  "Công ty TNHH Vận tải Phú Thành", "Công ty Cổ phần Logistics Tân Việt",
];
const carriers = originalCarriers.map((row, i) => ({
  ...row, carrier_id: `CAR-AP-${String(i + 1).padStart(4, "0")}`, carrier_name: carrierNames[i],
  base_area: "TP. Hồ Chí Minh", service_area: i % 2 === 0 ? "TP. Hồ Chí Minh - nội thành" : "TP. Hồ Chí Minh, Bình Dương và Đồng Nai",
  contact_ref: `dieuphoi@carrier-${String(i + 1).padStart(2, "0")}.example`, source_type: "SYNTHETIC_REFERENCE", is_synthetic: true,
}));
const newCarrierId = new Map(originalCarriers.map((row, i) => [row.carrier_id, carriers[i].carrier_id]));
const carrierRateRows = originalRates.map((row, i) => ({
  ...row, quote_id: `QTN-AP-2026-${String(i + 1).padStart(3, "0")}`,
  carrier_id: newCarrierId.get(row.carrier_id), quote_status: "ACTIVE", source_type: "SYNTHETIC_REFERENCE", is_synthetic: true,
}));
const availabilityCounts = [2, 1, 2, 1, 1, 2, 1, 2];
const availabilityRows = originalAvailability.map((row, i) => ({
  ...row, availability_id: `AVL-AP-HCM-261113-${String(i + 1).padStart(3, "0")}`,
  scenario_id: scenarioId, carrier_id: newCarrierId.get(row.carrier_id), vehicles_available: i === originalAvailability.length - 1 ? 0 : availabilityCounts[i % availabilityCounts.length],
  confirmation_status: i === originalAvailability.length - 1 ? "PENDING" : "CONFIRMED",
  confirmed_at: i === originalAvailability.length - 1 ? null : row.confirmed_at,
  source_note: i === originalAvailability.length - 1 ? "Chờ xác nhận của nhà cung cấp vận tải." : "Năng lực tham chiếu đã xác nhận cho khung giờ kế hoạch.",
  is_synthetic: true,
}));

function haversineKm(a, b) {
  const rad = (n) => n * Math.PI / 180;
  const dLat = rad(b.latitude - a.latitude), dLon = rad(b.longitude - a.longitude);
  const x = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.latitude)) * Math.cos(rad(b.latitude)) * Math.sin(dLon / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(x), Math.sqrt(1 - x));
}
const distanceRows = [];
for (const from of locations) for (const to of locations) {
  const km = from.location_id === to.location_id ? 0 : Math.max(1, Math.round(haversineKm(from, to) * 1.35 * 10) / 10);
  distanceRows.push({
    scenario_id: scenarioId, from_location_id: from.location_id, to_location_id: to.location_id,
    distance_km: km, drive_time_min: km === 0 ? 0 : Math.round(km / 19 * 60 + 5),
    source: "MODELLED_ROAD_DISTANCE", matrix_version: "REF-HCM-2026-01", is_synthetic: true,
  });
}

const scenarioHeaders = ["scenario_id", "operation_date", "scenario_name", "depot_id", "service_area", "currency", "timezone", "planning_start", "planning_end", "data_provenance", "notes"];
const orderHeaders = ["scenario_id", "order_id", "customer_id", "order_type", "drop_location_id", "ready_at", "due_at", "service_min", "priority", "status", "split_allowed", "total_weight_kg", "total_volume_m3", "minimum_vehicle_class", "notes", "is_synthetic"];
const palletHeaders = ["pallet_id", "scenario_id", "order_id", "sku_id", "description", "weight_kg", "length_cm", "width_cm", "height_cm", "volume_m3", "stackable", "max_stack", "rotation_rule", "handling_code", "drop_location_id", "is_synthetic"];
const locationHeaders = ["location_id", "customer_id", "location_name", "district_or_zone", "address_text", "latitude", "longitude", "open_from", "open_until", "service_min_default", "location_type", "is_synthetic", "notes"];

writeTable("Organization", ["organization_id", "legal_name", "display_name", "business_unit", "industry", "head_office_area", "default_currency", "timezone", "data_provenance", "is_synthetic"], organizationRows, "OrganizationMasterTable", { A: 21, B: 39, C: 30, D: 35, E: 43 });
writeTable("Scenario", scenarioHeaders, [scenarioRow], "ScenarioTable", { C: 48, E: 43, K: 82 });
writeTable("Customers", ["customer_id", "legal_name", "display_name", "customer_segment", "sales_channel", "payment_terms", "service_level", "status", "account_owner", "is_synthetic"], customers, "CustomerMasterTable", { A: 19, B: 42, C: 28, D: 22, E: 18, I: 23 });
writeTable("Products", ["sku_id", "sku_name", "category", "base_uom", "handling_code", "stackable_default", "rotation_rule", "status", "is_synthetic"], products, "ProductMasterTable", { A: 18, B: 51, C: 21, G: 29 });
writeTable("Employees", ["user_id", "employee_code", "full_name", "email", "department", "position", "phone", "active", "is_synthetic"], employees, "EmployeeMasterTable", { A: 18, B: 20, C: 25, D: 42, F: 34 });
writeTable("Orders", orderHeaders, orderRows, "OrdersTable", { B: 28, C: 18, E: 24, O: 75 });
writeTable("Pallets", palletHeaders, palletRows, "PalletsTable", { A: 30, C: 28, D: 18, E: 51, N: 18 });
writeTable("Locations", locationHeaders, locations, "LocationsTable", { A: 27, C: 45, E: 64, M: 64 });
writeTable("Fleet", Object.keys(fleetRows[0]), fleetRows, "FleetTable", { A: 18, D: 18, Q: 65 });
writeTable("Vehicle Classes", Object.keys(classRows[0]), classRows, "VehicleClassesTable", { A: 18, C: 18, J: 76 });
writeTable("Carriers", Object.keys(carriers[0]), carriers, "CarriersTable", { A: 19, B: 43, E: 45 });
writeTable("Carrier Rates", Object.keys(carrierRateRows[0]), carrierRateRows, "CarrierRatesTable", { A: 22, B: 19, C: 18 });
writeTable("Availability", Object.keys(availabilityRows[0]), availabilityRows, "AvailabilityTable", { A: 28, C: 19, J: 65 });
writeTable("Distance Matrix", Object.keys(distanceRows[0]), distanceRows, "DistanceMatrixTable", { B: 27, C: 27, F: 28, G: 20 });

setColumnFormat("Scenario", "B2", "yyyy-mm-dd");
setColumnFormat("Scenario", "H2:I2", "yyyy-mm-dd hh:mm");
setColumnFormat("Orders", "F2:G25", "yyyy-mm-dd hh:mm");
setColumnFormat("Orders", "L2:L25", "#,##0");
setColumnFormat("Orders", "M2:M25", "0.000");
setColumnFormat("Pallets", "F2:I54", "#,##0");
setColumnFormat("Pallets", "J2:J54", "0.000");
setColumnFormat("Locations", "F2:G14", "0.000000");
setColumnFormat("Fleet", "E2:E7", "#,##0");
setColumnFormat("Fleet", "F2:F7", "0.0");
setColumnFormat("Carrier Rates", "D2:D11", "#,##0");
setColumnFormat("Carrier Rates", "E2:E11", "0.0");
setColumnFormat("Carrier Rates", "L2:N11", "#,##0");
setColumnFormat("Carrier Rates", "O2:O11", "0.0%");
setColumnFormat("Availability", "E2:F9", "yyyy-mm-dd hh:mm");
setColumnFormat("Availability", "G2:G9", "0");
setColumnFormat("Availability", "I2:I9", "yyyy-mm-dd hh:mm");
setColumnFormat("Distance Matrix", "D2:D170", "0.0");
setColumnFormat("Distance Matrix", "E2:E170", "0");

const descriptions = {
  Organization: { organization_id: "Mã pháp nhân hoặc đơn vị vận hành trong tenant.", legal_name: "Tên pháp lý của doanh nghiệp tham chiếu.", display_name: "Tên hiển thị trong giao diện.", business_unit: "Đơn vị nghiệp vụ sử dụng hệ thống.", industry: "Lĩnh vực hoạt động.", head_office_area: "Khu vực trụ sở hoặc trung tâm vận hành.", default_currency: "Mã tiền tệ ISO 4217.", timezone: "Múi giờ nghiệp vụ IANA.", data_provenance: "Nguồn và mức độ xác thực dữ liệu.", is_synthetic: "TRUE khi bản ghi được tạo mô phỏng." },
  Scenario: { scenario_id: "Mã phiên kế hoạch vận tải.", operation_date: "Ngày điều vận theo giờ địa phương.", scenario_name: "Tên ca hoặc phạm vi kế hoạch.", depot_id: "Khóa địa điểm kho xuất phát.", service_area: "Phạm vi phục vụ của kế hoạch.", currency: "Mã tiền tệ của cước.", timezone: "Múi giờ dùng cho khung giờ giao.", planning_start: "Thời điểm bắt đầu điều vận.", planning_end: "Thời điểm kết thúc điều vận.", data_provenance: "Nguồn và mức độ xác thực dữ liệu.", notes: "Ghi chú vận hành và giới hạn dữ liệu." },
  Customers: { customer_id: "Mã khách hàng duy nhất.", legal_name: "Tên pháp lý của khách hàng mô phỏng.", display_name: "Tên giao dịch hiển thị trên màn hình.", customer_segment: "Phân khúc khách hàng.", sales_channel: "Kênh phân phối hoặc giao nhận.", payment_terms: "Điều khoản thanh toán tham chiếu.", service_level: "Mã cam kết thời gian phục vụ.", status: "Trạng thái hồ sơ khách hàng.", account_owner: "Nhân sự phụ trách tài khoản.", is_synthetic: "TRUE khi bản ghi được tạo mô phỏng." },
  Products: { sku_id: "Mã SKU duy nhất trong danh mục hàng hóa.", sku_name: "Tên hàng hóa và quy cách đóng gói.", category: "Nhóm hàng hóa.", base_uom: "Đơn vị tính cơ sở theo mã UOM.", handling_code: "Mã yêu cầu bảo quản và xếp dỡ.", stackable_default: "Quy tắc xếp chồng mặc định của SKU.", rotation_rule: "Quy tắc xoay pallet trên sàn xe.", status: "Trạng thái sử dụng của SKU.", is_synthetic: "TRUE khi bản ghi được tạo mô phỏng." },
  Employees: { user_id: "Khóa tài khoản nhân viên nội bộ.", employee_code: "Mã nhân sự dùng trong nhật ký thao tác.", full_name: "Họ và tên nhân viên.", email: "Email đăng nhập công việc trong môi trường mô phỏng.", department: "Mã phòng ban.", position: "Chức danh nghiệp vụ.", phone: "Số liên hệ mô phỏng; không phải thông tin liên lạc thật.", active: "TRUE khi tài khoản đang hoạt động.", is_synthetic: "TRUE khi bản ghi được tạo mô phỏng." },
  Orders: { scenario_id: "Khóa ngoại tới Scenario.", order_id: "Mã lệnh giao hàng duy nhất theo doanh nghiệp và ngày vận hành.", customer_id: "Khóa ngoại tới Customers.customer_id.", order_type: "Loại nghiệp vụ giao hàng.", drop_location_id: "Khóa ngoại tới địa điểm nhận trong Locations.", ready_at: "Thời điểm hàng sẵn sàng xuất kho.", due_at: "Hạn giao theo cam kết dịch vụ.", service_min: "Thời gian phục vụ tại điểm giao, phút.", priority: "Mức ưu tiên nghiệp vụ.", status: "Trạng thái xử lý lệnh giao.", split_allowed: "Cho phép chia lệnh giao qua nhiều xe.", total_weight_kg: "Tổng khối lượng hàng, kg; đối soát với Pallets.", total_volume_m3: "Tổng thể tích, m³; đối soát với Pallets.", minimum_vehicle_class: "Hạng xe thấp nhất được phép phân công.", notes: "Hướng dẫn giao nhận cho điều vận.", is_synthetic: "TRUE khi bản ghi được tạo mô phỏng." },
  Pallets: { pallet_id: "Mã đơn vị xếp hàng duy nhất (handling unit).", scenario_id: "Khóa ngoại tới Scenario.", order_id: "Khóa ngoại tới Orders.order_id.", sku_id: "Khóa ngoại tới Products.sku_id.", description: "Tên hàng hóa và quy cách đóng gói.", weight_kg: "Khối lượng gộp của pallet, kg.", length_cm: "Chiều dài pallet, cm.", width_cm: "Chiều rộng pallet, cm.", height_cm: "Chiều cao pallet, cm.", volume_m3: "Thể tích pallet, m³.", stackable: "Pallet có thể xếp chồng hay không.", max_stack: "Số lớp xếp tối đa theo dữ liệu tham chiếu.", rotation_rule: "Quy tắc xoay pallet khi kiểm tra mặt sàn.", handling_code: "Mã xử lý hàng hóa.", drop_location_id: "Khóa ngoại tới điểm nhận.", is_synthetic: "TRUE khi bản ghi được tạo mô phỏng." },
  Locations: { location_id: "Mã kho hoặc địa điểm giao nhận duy nhất.", customer_id: "Khách hàng sở hữu điểm nhận; để trống với kho.", location_name: "Tên kho hoặc điểm nhận hàng.", district_or_zone: "Quận, huyện hoặc khu vực điều vận.", address_text: "Địa chỉ tham chiếu; dữ liệu này được mô phỏng.", latitude: "Vĩ độ tọa độ tham chiếu.", longitude: "Kinh độ tọa độ tham chiếu.", open_from: "Giờ bắt đầu tiếp nhận hàng.", open_until: "Giờ kết thúc tiếp nhận hàng.", service_min_default: "Thời gian phục vụ mặc định tại điểm, phút.", location_type: "Loại địa điểm: kho hoặc khách hàng.", is_synthetic: "TRUE khi bản ghi được tạo mô phỏng.", notes: "Ghi chú vận hành và độ tin cậy địa chỉ." },
  Fleet: { vehicle_id: "Mã tài sản phương tiện nội bộ.", fleet_type: "Phân loại xe nhà hoặc xe thuê.", vehicle_class: "Khóa ngoại tới Vehicle Classes.vehicle_class.", plate_number: "Biển số được che một phần trong bộ dữ liệu mô phỏng.", capacity_kg: "Tải trọng khai thác tham chiếu, kg.", usable_volume_m3: "Thể tích khai thác, m³.", inner_length_cm: "Chiều dài lọt lòng thùng xe, cm.", inner_width_cm: "Chiều rộng lọt lòng thùng xe, cm.", inner_height_cm: "Chiều cao lọt lòng thùng xe, cm.", fixed_cost_vnd: "Chi phí cố định mỗi chuyến, VND.", cost_per_km_vnd: "Chi phí vận hành mỗi km, VND.", available_from: "Thời điểm xe bắt đầu khả dụng.", available_until: "Thời điểm xe kết thúc khả dụng.", start_depot_id: "Kho xuất phát của xe.", end_depot_id: "Kho kết thúc chuyến.", status: "Trạng thái khai thác của phương tiện.", temperature_control: "Yêu cầu kiểm soát nhiệt độ.", is_synthetic: "TRUE khi bản ghi được tạo mô phỏng." },
  "Vehicle Classes": { vehicle_class: "Mã hạng xe theo năng lực khai thác.", class_rank: "Thứ tự tương thích từ xe nhỏ tới xe lớn.", vehicle_type: "Loại thân xe.", capacity_kg: "Tải trọng tham chiếu, kg.", usable_volume_m3: "Thể tích khai thác, m³.", inner_length_cm: "Chiều dài lọt lòng, cm.", inner_width_cm: "Chiều rộng lọt lòng, cm.", inner_height_cm: "Chiều cao lọt lòng, cm.", is_synthetic: "TRUE khi bản ghi được tạo mô phỏng.", notes: "Mô tả phạm vi sử dụng hạng xe." },
  Carriers: { carrier_id: "Mã nhà cung cấp dịch vụ vận tải.", carrier_name: "Tên nhà cung cấp vận tải mô phỏng.", base_area: "Khu vực khai thác chính.", service_area: "Phạm vi phục vụ được khai báo.", contact_ref: "Email tham chiếu trên tên miền .example.", source_type: "Nguồn của danh mục nhà cung cấp.", is_synthetic: "TRUE khi bản ghi được tạo mô phỏng." },
  "Carrier Rates": { quote_id: "Mã biểu giá hoặc báo giá duy nhất.", carrier_id: "Khóa ngoại tới Carriers.carrier_id.", vehicle_class: "Hạng xe áp dụng.", capacity_kg: "Tải trọng tham chiếu của hạng xe, kg.", usable_volume_m3: "Thể tích khai thác, m³.", inner_length_cm: "Chiều dài lọt lòng thùng xe, cm.", inner_width_cm: "Chiều rộng lọt lòng thùng xe, cm.", inner_height_cm: "Chiều cao lọt lòng thùng xe, cm.", rate_per_km_vnd: "Đơn giá vận chuyển mỗi km, VND.", callout_fee_vnd: "Phí điều xe hoặc phí khởi tạo chuyến, VND.", minimum_fare_vnd: "Cước tối thiểu mỗi chuyến, VND.", waiting_free_min: "Số phút chờ miễn phí.", waiting_fee_per_hour_vnd: "Phí chờ mỗi giờ, VND.", stop_fee_vnd: "Phụ phí mỗi điểm dừng, VND.", return_trip_rule: "Quy tắc tính chiều về.", vat_rate_assumption: "Thuế suất VAT giả định.", valid_from: "Ngày bắt đầu hiệu lực biểu giá.", valid_until: "Ngày kết thúc hiệu lực biểu giá.", quote_status: "Trạng thái hiệu lực của biểu giá.", source_type: "Nguồn tham chiếu của biểu giá.", is_synthetic: "TRUE khi bản ghi được tạo mô phỏng." },
  Availability: { availability_id: "Mã xác nhận năng lực nhà xe.", scenario_id: "Khóa ngoại tới Scenario.", carrier_id: "Nhà cung cấp vận tải.", vehicle_class: "Hạng xe đã khai báo năng lực.", window_start: "Thời điểm bắt đầu năng lực.", window_end: "Thời điểm kết thúc năng lực.", vehicles_available: "Số xe có thể nhận chuyến trong khung giờ.", confirmation_status: "CONFIRMED hoặc PENDING.", confirmed_at: "Thời điểm xác nhận của nhà cung cấp.", source_note: "Ghi chú nguồn xác nhận năng lực.", is_synthetic: "TRUE khi bản ghi được tạo mô phỏng." },
  "Distance Matrix": { scenario_id: "Khóa ngoại tới Scenario.", from_location_id: "Mã điểm xuất phát.", to_location_id: "Mã điểm đến.", distance_km: "Khoảng cách tham chiếu, km.", drive_time_min: "Thời gian di chuyển tham chiếu, phút.", source: "Nguồn hoặc phương pháp ước lượng tuyến.", matrix_version: "Phiên bản ma trận khoảng cách.", is_synthetic: "TRUE khi bản ghi được tạo mô phỏng." },
};
const sheetByTitle = {
  "Organization": "Organizations", "Scenario": "Scenarios", "Customers": "Customers", "Products": "Products", "Employees": "Employees",
  "Orders": "Orders", "Pallets": "Handling units", "Locations": "Locations", "Fleet": "Fleet vehicles", "Vehicle Classes": "Vehicle classes",
  "Carriers": "Transport suppliers", "Carrier Rates": "Carrier tariffs", "Availability": "Supplier capacity", "Distance Matrix": "Distance matrix",
};
const dataDictionaryRows = [];
for (const [sheetName, fieldDescriptions] of Object.entries(descriptions)) {
  const sheet = workbook.worksheets.getItem(sheetName);
  const headers = sheet.getUsedRange().values[0].map((v) => String(v ?? ""));
  const sample = sheet.getUsedRange().values[1] ?? [];
  for (const field of headers) {
    const unit = field.endsWith("_kg") ? "kg" : field.endsWith("_m3") ? "m³" : field.endsWith("_cm") ? "cm" :
      field.endsWith("_vnd") ? "VND" : field.endsWith("_min") ? "phút" : ["latitude", "longitude"].includes(field) ? "decimal degrees" :
      ["ready_at", "due_at", "planning_start", "planning_end", "operation_date", "available_from", "available_until", "window_start", "window_end", "valid_from", "valid_until", "confirmed_at"].includes(field) ? "Date-time" :
      ["is_synthetic", "stackable", "stackable_default", "split_allowed", "active"].includes(field) ? "Boolean" : "Text / code";
    const keyLike = field.endsWith("_id") || ["vehicle_class", "sku_id", "customer_id", "carrier_id", "order_id", "location_id"].includes(field);
    const example = sample[headers.indexOf(field)];
    dataDictionaryRows.push({
      sheet_name: sheetName, business_entity: sheetByTitle[sheetName] ?? sheetName, field_name: field,
      meaning: fieldDescriptions[field] ?? `Trường dữ liệu ${field.replaceAll("_", " ")} theo cấu trúc tích hợp FleetMix.`,
      type_or_unit: unit, required_or_source: keyLike ? "Mã/khóa tham chiếu" : "Dữ liệu mô phỏng",
      example_or_rule: example instanceof Date ? example.toISOString().slice(0, 16).replace("T", " ") : example === null || example === undefined ? "Có thể để trống theo nghiệp vụ" : String(example),
    });
  }
}
writeTable("Data Dictionary", ["sheet_name", "business_entity", "field_name", "meaning", "type_or_unit", "required_or_source", "example_or_rule"], dataDictionaryRows, "DataDictionaryTable", { A: 22, B: 25, C: 30, D: 78, E: 20, F: 24, G: 50 });

const startSheet = workbook.worksheets.getItem("Start Here");
const startUsed = startSheet.getUsedRange();
if (startUsed) startUsed.clear({ applyTo: "contents" });
const startRows = Array.from({ length: 40 }, () => [null, null, null]);
const put = (row, values) => { startRows[row - 1] = [...values, ...Array(Math.max(0, 3 - values.length)).fill(null)].slice(0, 3); };
put(1, ["FleetMix AI | Bộ dữ liệu ERP vận tải"]);
put(3, ["DỮ LIỆU THAM CHIẾU MÔ PHỎNG", "Doanh nghiệp, nhân sự, khách hàng, hàng hóa, địa chỉ, biển số, báo giá và năng lực nhà xe đều được tạo mô phỏng. Không dùng cho giao nhận, điều xe hoặc thanh toán thật."]);
put(5, ["Doanh nghiệp", company.legalName]);
put(6, ["Mã đơn vị", company.id]);
put(7, ["Kịch bản", scenarioId]);
put(8, ["Ngày vận hành", originalScenario.operation_date]);
put(9, ["Khu vực", "TP. Hồ Chí Minh và khu vực lân cận"]);
put(10, ["Tiền tệ / múi giờ", "VND / Asia/Ho_Chi_Minh"]);
put(11, ["Nguồn", "Dữ liệu mô phỏng theo cấu trúc vận hành doanh nghiệp"]);
put(13, ["Danh mục dữ liệu", "Số bản ghi"]);
[
  ["Khách hàng", customers.length], ["Lệnh giao hàng", orderRows.length], ["Pallet / đơn vị xếp hàng", palletRows.length],
  ["Mã hàng hóa SKU", products.length], ["Kho và điểm nhận", locations.length], ["Phương tiện nội bộ", fleetRows.length],
  ["Hạng xe", classRows.length], ["Nhà cung cấp vận tải", carriers.length], ["Biểu giá vận tải", carrierRateRows.length],
  ["Nhân viên logistics", employees.length],
].forEach((row, i) => put(14 + i, row));
put(25, ["Thứ tự nạp dữ liệu", "Sheet", "Nghiệp vụ"]);
[
  [1, "Organization / Scenario", "Khai báo pháp nhân và ca vận hành."],
  [2, "Customers / Products", "Nạp danh mục khách hàng, điểm nhận và SKU."],
  [3, "Employees", "Nạp tài khoản nhân viên logistics dùng chung chức năng."],
  [4, "Locations / Fleet / Vehicle Classes", "Khai báo kho, điểm giao và năng lực xe."],
  [5, "Carriers / Carrier Rates / Availability", "Nạp nhà cung cấp, biểu giá và số xe đã xác nhận."],
  [6, "Orders / Pallets", "Nạp lệnh giao và từng đơn vị xếp hàng; tổng tải phải khớp."],
  [7, "Distance Matrix", "Ma trận tham chiếu mô phỏng cho lập tuyến."],
].forEach((row, i) => put(26 + i, row));
put(34, ["Chuẩn dữ liệu trước khi vận hành thật", "Thay mã và hồ sơ mô phỏng bằng master data đã được chủ dữ liệu phê duyệt."]);
put(35, ["Đơn hàng và pallet", "Đối soát SKU, đơn vị tính, gross weight, kích thước và hạn giao với chứng từ WMS/ERP."]);
put(36, ["Phương tiện và nhà cung cấp", "Xác nhận biển số, đăng kiểm, tải trọng, kích thước thùng, hợp đồng và biểu phí."]);
put(37, ["Địa chỉ và tuyến đường", "Thay tọa độ, khoảng cách và thời gian mô phỏng bằng dữ liệu địa chỉ và bản đồ đã kiểm chứng."]);
put(38, ["Nguồn dữ liệu", "Mọi dòng trong workbook có is_synthetic = TRUE."]);
put(40, ["Kiểm tra xếp hàng", "Mô phỏng sàn pallet 2D chỉ hỗ trợ rà soát kích thước. Chưa chứng nhận xếp chồng, tải trục hoặc chằng buộc."]);
startSheet.getRange("A1:C40").values = startRows;
startSheet.showGridLines = false;
startSheet.getRange("A1:Z40").format = { fill: "#FFFFFF", font: { name: "Arial", size: 10, color: "#203648", bold: false, italic: false } };
startSheet.getRange("A1:C40").format.font = { name: "Arial", size: 10, color: "#203648" };
startSheet.getRange("A1:C1").format.font = { name: "Arial", size: 14, bold: true, color: "#203648" };
for (const range of ["A13:B13", "A25:C25", "A34:C34"]) {
  startSheet.getRange(range).format = { fill: "#17364D", font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" } };
}
startSheet.getRange("A5:A11").format = { fill: "#EAF1F5", font: { name: "Arial", size: 10, bold: true, color: "#203648" } };
startSheet.getRange("A3:B3").format = { fill: "#FCE4D6", font: { name: "Arial", size: 10, bold: true, color: "#9C3D20" }, wrapText: true };
startSheet.getRange("B3:B3").format.rowHeight = 46;
startSheet.getRange("A34:C38").format.wrapText = true;
startSheet.getRange("A40:B40").format = { fill: "#FFF2CC", font: { name: "Arial", size: 9, italic: true, color: "#765A19" }, wrapText: true };
startSheet.getRange("A40:C40").format.rowHeight = 40;
startSheet.getRange("A1:A40").format.columnWidth = 34;
startSheet.getRange("B1:B40").format.columnWidth = 86;
startSheet.getRange("C1:C40").format.columnWidth = 74;
startSheet.getRange("B8").format.numberFormat = "yyyy-mm-dd";
startSheet.freezePanes.unfreeze();

workbook.recalculate();
await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(previewDir, { recursive: true });
for (const sheetName of ["Start Here", "Organization", "Scenario", "Customers", "Products", "Employees", "Orders", "Pallets", "Locations", "Fleet", "Vehicle Classes", "Carriers", "Carrier Rates", "Availability", "Distance Matrix", "Data Dictionary"]) {
  const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 0.6, format: "png" });
  await fs.writeFile(path.join(previewDir, `${sheetName.replaceAll(" ", "_")}.png`), new Uint8Array(await preview.arrayBuffer()));
}
const summary = await workbook.inspect({ kind: "workbook,sheet,table", maxChars: 3500, tableMaxRows: 2, tableMaxCols: 10, tableMaxCellChars: 60 });
console.log(summary.ndjson);
console.log(JSON.stringify({
  outputPath, rows: { customers: customers.length, products: products.length, employees: employees.length, orders: orderRows.length,
    pallets: palletRows.length, locations: locations.length, distancePairs: distanceRows.length, dictionaryFields: dataDictionaryRows.length },
  reconciled: orderRows.every((order) => {
    const lines = palletsByOrder.get(order.order_id) ?? [];
    return order.total_weight_kg === lines.reduce((sum, p) => sum + p.weight_kg, 0) && Math.abs(order.total_volume_m3 - lines.reduce((sum, p) => sum + p.volume_m3, 0)) < 0.001;
  }),
}));
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
