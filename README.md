# FleetMix AI Logistics Operations

FleetMix is an internal logistics operations MVP for dispatch staff. It covers the daily transport planning flow from order and pallet intake through fleet assignment, route review, human confirmation, carrier request drafts and an employee audit trail. All signed-in logistics employees share the same functional access, as requested; the employee directory records who performed each operation.

## Included modules

- Dispatch control tower with outstanding orders, a synthetic route map and internal fleet status.
- Orders and pallet records, workbook preview/validation/commit, manual route assignment and drag-and-drop in the board.
- Weight, volume, delivery window, vehicle class and conservative 2D floor-fit checks.
- Deterministic cheapest-insertion route planner with cost estimation. It returns a feasible heuristic result and does not claim a global optimum.
- Carrier quote and confirmed-availability catalog; pending capacity is excluded from planning.
- Separate plan confirmation, route start/completion states, replanning that preserves started/completed routes, and local carrier booking drafts after confirmation.
- Logistics employee directory, shared employee login, audit history, and a quote text extraction assistant.
- AI Gateway structured extraction is optional. Without `AI_GATEWAY_API_KEY` and `FLEETMIX_AI_MODEL`, a local rule parser is used. Extracted quote fields always require human review.

## Run locally on Windows

Open PowerShell in the project directory:

```powershell
python -m venv .venv
$env:DISABLE_SQLALCHEMY_CEXT = "1"
.\.venv\Scripts\python.exe -m pip install -r api\requirements.txt
npm install
Push-Location web
npm install --workspaces=false
Pop-Location
npm run dev
```

The SQLAlchemy source install disables optional C extensions to run on this Windows environment, where the native extension binaries are blocked by its Application Control policy. The application code and tests use SQLAlchemy's supported pure-Python implementation.

Open <http://127.0.0.1:3000>. The local API is at <http://127.0.0.1:8000/docs>.

## Tài khoản nhân viên tham chiếu

Workbook seed tạo bốn tài khoản nhân viên logistics mẫu. Mọi nhân viên dùng cùng chức năng; tài khoản chỉ phục vụ đăng nhập và lưu dấu vết giao dịch:

- `minh.anh@anphuc-logistics.example`
- `quoc.bao@anphuc-logistics.example`
- `hoang.phuc@anphuc-logistics.example`
- `ngoc.han@anphuc-logistics.example`
- Mật khẩu cục bộ ban đầu: `FleetMixDemo!2026`

Set `FLEETMIX_DEMO_PASSWORD` in the untracked project-root `.env` to change the local seed password. The production startup guard rejects the default signing key or demo password.

Optional API settings are in the project-root `.env.example`. Optional web settings belong in `web/.env.local`; copy `web/.env.example` there to configure the API URL or AI Gateway model. Do not commit either local environment file.

## Tests and build

```powershell
npm test
```

This runs API tests, TypeScript checks and a Next.js production build.

## Data and operational boundaries

The seed workbook at `outputs/01a1cbad-1a1e-7de1-899b-92bedce65edf/FleetMix_ERP_Operational_Dataset.xlsx` contains a synthetic company, employees, 12 customers, 18 SKU masters, 24 delivery orders, 53 pallet handling units, 13 locations, six internal vehicles, four transport suppliers, ten tariff rows and a modeled distance matrix. Naming follows stable enterprise prefixes (`ORG`, `CUS`, `SKU`, `DO`, `PLT`, `WH`/`LOC`, `VH`, `CAR`, `QTN`, `AVL`) and IDs link the master and transaction sheets.

All names and operating values are synthetic. Addresses and distances are modeled, vehicle plates are masked, and `.example` emails are reserved samples. Do not dispatch or pay from this dataset. The in-app map is a coordinate schematic, not navigation. Pallet placement verifies conservative 2D floor use only; it does not certify stacking, axle weight, load restraint, or vehicle roadworthiness. Carrier requests remain local drafts and are never transmitted. The app does not yet connect to an enterprise ERP, WMS, TMS, accounting, payment, HRIS, map/traffic or carrier booking system.

SQLite is the default database at `data/fleetmix_erp.db`; `DATABASE_URL` can select PostgreSQL for a deployment environment. Replacing the synthetic workbook with approved master and transaction data plus validated ERP, WMS, route, pricing and carrier interfaces is required before live business operations.
