# Backend → Frontend Integration Handoff & Technical Specification
**Project:** Applicant Processing & Travel Agency Management System  
**Target Environment:** `https://applicantprocessing-production.up.railway.app/`  
**Backend Engine:** Frappe Framework v15 (Python 3.10+ / MariaDB / REST & RPC API)  
**Date:** August 15, 2026  
**Audience:** Frontend Development Team (Next.js + TypeScript)  

---

# 1. Current Backend Reality Summary

This section compares our earlier UX/Figma concepts against what is **actually implemented** in the backend today.

### Major Discrepancy Matrix

| Feature / Concept | Earlier UX / Prototype Concept | Current Actual Backend Implementation | Status | Notes & Discrepancies |
| :--- | :--- | :--- | :---: | :--- |
| **Applicant Registration** | Single-form submission or multi-step wizard without strict stage separation | Two-stage progressive validation (Stage 1 Draft Floor vs Stage 2 Strict Registration) | **Changed** | Draft requires 8 fields. Registration strictly requires 11 KYC/Medical fields + Medical `FIT` validation. |
| **Registration State Action** | Client state toggle | Whitelisted RPC method `register_applicant` | **Same** | `POST /api/method/applicant_processing.applicant_processing.doctype.applicant.applicant.register_applicant` |
| **CV Generation** | Upload static PDF or simple form export | Server-side Jinja2 HTML $\rightarrow$ wkhtmltopdf 2-page bilateral recruitment CV | **Same** | `POST /api/method/applicant_processing.applicant_processing.doctype.applicant.applicant.generate_cv` |
| **Contractor & Dispatch** | Manual email sending or static contact list | Contractor doctype + Meta WhatsApp Cloud API PDF dispatch + WhatsApp Web URL generator | **New / Expanded** | Dispatches PDF binary directly to WhatsApp chat thread or generates deep-link. |
| **Contractor Document Approval** | `upload_contractor_doc` & `approve_contractor_doc` custom RPC endpoints | Managed via `Applicant Dossier` entity & `parse_dossier_file` RPC | **Changed** | Upload contract to `Applicant Dossier`, parse file, auto-create linked `DSR`. |
| **LMS Clearance** | Standalone custom stream wrapper endpoints (`update_lms_stream`) | Standard REST resource `LMS Clearance` (`LMS-.#####`) | **Changed** | Controlled via standard Frappe REST (`PUT /api/resource/LMS Clearance/{id}`). |
| **Wakala Clearance** | Custom stream wrapper (`update_wakala_stream`) | Standard REST resource `Wakala Clearance` (`WAK-.#####`) | **Changed** | Controlled via standard Frappe REST (`PUT /api/resource/Wakala Clearance/{id}`). |
| **Injaz Clearance** | Custom stream wrapper (`update_injaz_stream`) | Standard REST resource `Injaz Clearance` (`INJ-.#####`) | **Changed** | Controlled via standard Frappe REST (`PUT /api/resource/Injaz Clearance/{id}`). |
| **Employee Assignment** | Bulk RPC `assign_employee` | Field `employee` (Link to User) on `LMS`, `Wakala`, `Injaz` | **Changed** | Assigning `employee` field automatically sets Frappe `User Permission` and generates a `ToDo` + `Notification Log`. |
| **Pre-Departure Guardrails** | Independent visa stamping & flight ticketing | Strict validation `check_clearances_completed` | **New / Enforced** | `DSR Stamp`, `DSR Ticket`, and `DSR Departure` throw blocking errors if LMS, Wakala, or Injaz are incomplete! |
| **Pre-Departure Medical 2** | Generic departure logging | Pre-departure Medical 2 verification in `DSR Departure` | **New / Enforced** | `medical_2_result` (`Pass`/`Fail`). If `Fail`, departure is blocked and remarks are required. |
| **Financial Tracking** | Separate standalone accounting ledger | Embedded `Income Expense Log` child table across ALL pipeline DocTypes | **New / Expanded** | Dashboard RPC `get_accounting_summary` aggregates totals across all 9 stages in real time. |
| **Notifications** | Polling/WebSockets | `ToDo` task assignment + `Notification Log` (Desk bell icon) + Webhooks | **Changed** | Server handles ToDos, Bell notifications, and webhook dispatches asynchronously. |
| **Expiry Automation** | Frontend date difference calculations | Daily automated cron `check_medical_expirations` for $\le 16$ days | **New** | Automatically creates urgent ToDo tasks for officers when medical expiry is $\le 16$ days. |
| **Applicant States** | `Draft`, `Registered`, `CV Generated`, `Request Pending`, `Selected`, `Processing`, `Embassy/Stamped`, `Departed` | `Draft`, `Registered`, `CV Generated`, `Request Pending`, `Selected`, `Processing`, `Stamped`, `Ticketed`, `Departed`, `Cancelled` | **Changed** | Canonical 9-stage sequence + `Cancelled`. Separate `Stamped` and `Ticketed` stages. |

---

# 2. Current Backend Capability Inventory

| Entity / DocType Name | Purpose | Implementation Status | Main Relationships | Available Operations | Frontend Integration Status | Known Limitations |
| :--- | :--- | :---: | :--- | :--- | :---: | :--- |
| **`Applicant`** | Master applicant profile & lifecycle container | **Fully Implemented** | Has many `Income Expense Log`, `CV Record`, `Contract Request` | CRUD, `register_applicant`, `generate_cv`, `cancel_applicant`, `restore_applicant` | **Ready** | `medical_status == "UNFIT"` blocks registration. |
| **`CV Record`** | Archived 2-page snapshot & generated PDF link | **Fully Implemented** | Belongs to `Applicant` | Read, List | **Ready** | Generated server-side via `generate_cv`. |
| **`Contractor`** | Agency details for overseas contract requests | **Fully Implemented** | Has many `Contract Request` | CRUD, List | **Ready** | Keyed by `company_name`. |
| **`Contract Request`** | Contract request broadcast to contractor | **Fully Implemented** | Belongs to `Applicant`, `CV Record`, `Contractor` | CRUD, `send_contract_request`, `batch_send_contract_requests` | **Ready** | Integrates with Meta WhatsApp Cloud API. |
| **`Applicant Dossier`** | Saudi contract document upload & parsing container | **Fully Implemented** | Belongs to `Contract Request`, `Applicant` | CRUD, `parse_dossier_file` | **Ready** | Auto-creates linked `DSR`. |
| **`DSR`** | Daily Status Report master progress tracker | **Fully Implemented** | Belongs to `Applicant Dossier` | Read, List | **Ready** | Auto-creates 3 Clearance records on creation. |
| **`LMS Clearance`** | Labor Ministry clearance tracking | **Fully Implemented** | Belongs to `DSR`, Assigned to `User` | CRUD (Standard REST) | **Ready** | Setting `status="Issued"` requires `issued_on`. |
| **`Wakala Clearance`** | Power of Attorney clearance tracking | **Fully Implemented** | Belongs to `DSR`, Assigned to `User` | CRUD (Standard REST) | **Ready** | Statuses: `Pending`, `Completed`. |
| **`Injaz Clearance`** | Visa payment & biometrics clearance tracking | **Fully Implemented** | Belongs to `DSR`, Assigned to `User` | CRUD (Standard REST) | **Ready** | Statuses: `Pending`, `Completed`. |
| **`DSR Stamp`** | Embassy visa stamp details | **Fully Implemented** | Belongs to `DSR` | CRUD (Standard REST) | **Ready** | Requires all 3 clearances completed first. |
| **`DSR Ticket`** | Flight ticket booking details | **Fully Implemented** | Belongs to `DSR` | CRUD (Standard REST) | **Ready** | Requires all 3 clearances completed first. |
| **`DSR Departure`** | Final flight departure & Medical 2 check | **Fully Implemented** | Belongs to `DSR` | CRUD (Standard REST) | **Ready** | `medical_2_result="Fail"` blocks departure. |
| **`Income Expense Log`** | Universal child table for financial transactions | **Fully Implemented** | Embedded in all stage DocTypes | Create/Edit row on parent DocType | **Ready** | Auto-recalculates parent totals. |
| **`Notification Config`**| Webhook & Meta WhatsApp API configuration | **Fully Implemented** | System Single DocType | Read/Update (Admin) | **Ready** | Single instance. |

---

# 3. Current API Inventory

### 3.1. Core Authentication
* `POST /api/method/login` — Session cookie login (`usr`, `pwd`).
* `GET /api/method/frappe.auth.get_logged_user` — Returns logged-in user email.

### 3.2. Standard Resource CRUD (`/api/resource/{DocType}`)
All DocTypes support standard Frappe REST operations:
* `GET /api/resource/{DocType}` — List records (params: `fields`, `filters`, `order_by`, `limit_start`, `limit_page_length`).
* `GET /api/resource/{DocType}/{name}` — Get single record.
* `POST /api/resource/{DocType}` — Create record.
* `PUT /api/resource/{DocType}/{name}` — Update record.
* `DELETE /api/resource/{DocType}/{name}` — Delete record.

### 3.3. Whitelisted Custom RPC Methods (`/api/method/...`)

#### 1. Register Applicant
* **Method & Endpoint:** `POST /api/method/applicant_processing.applicant_processing.doctype.applicant.applicant.register_applicant`
* **Auth & Permission:** Required (`System Manager` or authorized user)
* **Request Body:** `{ "applicant_name": "APP-00001" }`
* **Response:** `{ "message": "Applicant APP-00001 is now Registered." }`
* **Errors:** Throws `417` if Stage 2 fields missing or if `medical_status == "UNFIT"`.

#### 2. Generate CV PDF
* **Method & Endpoint:** `POST /api/method/applicant_processing.applicant_processing.doctype.applicant.applicant.generate_cv`
* **Request Body:** `{ "applicant_name": "APP-00001" }`
* **Response:** `{ "message": { "cv_record": "CV-00001", "file_url": "/private/files/CV-APP-00001-CV-00001.pdf", "message": "CV generated successfully: CV-00001" } }`
* **Errors:** Throws `417` if state is before `Registered` or `medical_status == "UNFIT"`.

#### 3. Send Single Contract Request (WhatsApp API Integration)
* **Method & Endpoint:** `POST /api/method/applicant_processing.applicant_processing.doctype.contract_request.contract_request.send_contract_request`
* **Request Body:** `{ "contract_request_name": "CR-00001" }`
* **Response:** `{ "message": { "status": "success", "message": "Contract Request CR-00001 successfully sent...", "whatsapp_url": "https://api.whatsapp.com/send?phone=...", "whatsapp_api_sent": true, ... } }`

#### 4. Batch Send Contract Requests
* **Method & Endpoint:** `POST /api/method/applicant_processing.applicant_processing.doctype.contract_request.contract_request.batch_send_contract_requests`
* **Request Body:** `{ "cv_references": ["CV-00001", "CV-00002"], "contractor": "Al Qurashi Recruitment Office" }`
* **Response:** `{ "message": { "total": 2, "created_count": 1, "sent_count": 2, "failed_count": 0, "results": [...] } }`

#### 5. Parse Dossier Document File
* **Method & Endpoint:** `POST /api/method/applicant_processing.applicant_processing.doctype.applicant_dossier.applicant_dossier.parse_dossier_file`
* **Request Body:** `{ "dossier_name": "DOSSIER-00001" }`
* **Response:** `{ "message": "File successfully parsed and additional fields populated." }`

#### 6. Cancel Applicant Process
* **Method & Endpoint:** `POST /api/method/applicant_processing.applicant_processing.doctype.applicant.applicant.cancel_applicant`
* **Request Body:** `{ "applicant_name": "APP-00001", "cancel_remarks": "Family emergency" }`
* **Response:** `{ "message": "Applicant APP-00001 process has been Cancelled." }`

#### 7. Restore Cancelled Applicant
* **Method & Endpoint:** `POST /api/method/applicant_processing.applicant_processing.doctype.applicant.applicant.restore_applicant`
* **Request Body:** `{ "applicant_name": "APP-00001", "restore_option": "auto" }`
* **Response:** `{ "message": { "status": "success", "new_state": "Processing", "message": "Applicant APP-00001 restored..." } }`

#### 8. Accounting & Financial Summary Dashboard
* **Method & Endpoint:** `GET /api/method/applicant_processing.applicant_processing.api.get_accounting_summary`
* **Response:** `{ "message": { "total_income": 45000.0, "total_expense": 18500.0, "net_balance": 26500.0, "by_stage": [...], "per_applicant": [...], "recent_transactions": [...] } }`

---

# 4. NOT IMPLEMENTED / PARTIALLY IMPLEMENTED FEATURES

### ❌ NOT IMPLEMENTED
1. **Custom `request_pending` RPC:** Use `send_contract_request` or `batch_send_contract_requests`.
2. **RPC Endpoints `upload_contractor_doc` & `approve_contractor_doc`:** In the actual backend, contractor document upload and parsing are handled via `Applicant Dossier` and `parse_dossier_file`.
3. **Dedicated `assign_employee` RPC endpoint:** In the actual backend, assign employees by updating the `employee` field on `LMS Clearance`, `Wakala Clearance`, or `Injaz Clearance` via standard `PUT /api/resource/{DocType}/{id}`. The backend automatically handles User Permissions and ToDo generation!
4. **Dedicated `update_lms_stream`, `update_injaz_stream`, `update_wakala_stream` RPC endpoints:** Stream updates are done directly via standard REST `PUT /api/resource/{Clearance DocType}/{id}`.
5. **Real-time WebSockets / SSE:** Backend currently operates via REST API requests and standard polling.
6. **Dedicated `get_dashboard_analytics` RPC endpoint:** Use `get_accounting_summary` for financials. For pipeline counts, query `/api/resource/Applicant?fields=["applicant_state"]`.

### ⚠️ PARTIALLY IMPLEMENTED
1. **Dossier OCR File Parsing:** Currently operates on a robust built-in mock parser (`parse_dossier_file`). Integration hooks (`Document Parse Request`) exist for connecting external OCR microservices.

---

# 5. Changes from Earlier Frontend Design

| Previous Frontend Concept | Current Backend Reality | Frontend Action Required |
| :--- | :--- | :--- |
| Single bulk `assign_employee` RPC call | Edit `employee` field on `LMS Clearance`, `Wakala Clearance`, or `Injaz Clearance` | Send standard `PUT` request to clearance DocType with `"employee": "user@example.com"`. |
| Stream update RPCs (`update_lms_stream`) | Standard REST `PUT /api/resource/LMS Clearance/{id}` | Update clearance records using standard REST endpoints. |
| Single `Embassy/Stamped` state | Separate `Stamped` (step 7) and `Ticketed` (step 8) states | Update stepper UI to display `Stamped` and `Ticketed` as distinct steps. |
| Standalone `Expenses/Income` module | Embedded `Income Expense Log` child table | Render `income_expense_logs` table within Applicant and Clearance forms. |

---

# 6. Applicant Data Model — Current Version

### Classification Categories:

#### 1. Draft-Required Fields (Mandatory to Save Initial Record)
`first_name`, `last_name`, `gender`, `religion`, `marital_status`, `children`, `nationality`, `phone_number`, `city`, `country`.

#### 2. Registration-Required Fields (Mandatory to Call `register_applicant`)
`date_of_birth`, `passport_number`, `passport_issue_date`, `passport_expiry`, `place_of_issue`, `job_applied`, `highest_education`, `photo_passport`, `photo_full_body`, `passport_scan`, `medical_status`, `medical_expiry_date`.

#### 3. Optional Fields
`middle_name`, `alternate_phone`, `email`, `region`, `sub_region`, `address_line_1`, `national_id`, `labour_id`, `contact_person_name`, `contact_person_phone`, `coc_status`, `exam_date`, `english_level`, `arabic_level`, `experience_country`, `experience_period`, `remarks`, `medical_remarks`, skill checkboxes (`skill_cleaning`, `skill_cooking`, etc.).

#### 4. Computed / System Fields
`name` (`APP-.#####`), `full_name`, `age`, `exam_remaining_days`, `medical_remaining_days`, `applicant_state`, `state_step`, `state_progress`, `registration_date`, `total_income`, `total_expense`, `net_balance`, `cancel_remarks`, `cancelled_at`, `cancelled_by`.

---

# 7. Applicant Registration — Current Actual Flow

1. **Creation:** `POST /api/resource/Applicant` with Stage 1 Draft fields. Saves record in state `Draft`.
2. **Draft Modifications:** User can perform `PUT /api/resource/Applicant/APP-00001` at any time to add optional or registration fields.
3. **Registration Transition:** Frontend calls `POST /api/method/.../register_applicant` with `{ "applicant_name": "APP-00001" }`.
4. **Backend Enforcement:**
   - Validates all Stage 2 fields are non-empty.
   - Verifies `medical_status != "UNFIT"`.
   - Checks date of birth is not in the future.
   - Formats `passport_number` to uppercase.
   - Sets `applicant_state = "Registered"`.
   - Triggers immediate medical expiry watchdog check.

---

# 8. Current Applicant State Machine

### Canonical State Order (`STATE_ORDER`):
1. `Draft` (Step 1 of 9, 11.1%)
2. `Registered` (Step 2 of 9, 22.2%)
3. `CV Generated` (Step 3 of 9, 33.3%)
4. `Request Pending` (Step 4 of 9, 44.4%)
5. `Selected` (Step 5 of 9, 55.6%)
6. `Processing` (Step 6 of 9, 66.7%)
7. `Stamped` (Step 7 of 9, 77.8%)
8. `Ticketed` (Step 8 of 9, 88.9%)
9. `Departed` (Step 9 of 9, 100.0%)
10. `Cancelled` (Cancelled state, 0.0%)

### Transition Matrix
| Current State | Triggering Action | Allowed Roles | Endpoint / Mechanism | New State |
| :--- | :--- | :--- | :--- | :--- |
| `Draft` | Register Applicant | All Users | `POST /api/method/.../register_applicant` | `Registered` |
| `Registered` | Generate CV | All Users | `POST /api/method/.../generate_cv` | `CV Generated` |
| `CV Generated` | Send Contract Request | All Users | `POST /api/method/.../send_contract_request` | `Request Pending` |
| `Request Pending` | Parse Dossier / Accept CR | All Users | `POST /api/method/.../parse_dossier_file` | `Selected` |
| `Selected` | Update Clearance / Assign Employee | Clearance Officers | `PUT /api/resource/{Clearance DocType}` | `Processing` |
| `Processing` | Submit Visa Stamp | Operations | `POST /api/resource/DSR Stamp` | `Stamped` |
| `Stamped` | Book Flight Ticket | Operations | `POST /api/resource/DSR Ticket` | `Ticketed` |
| `Ticketed` | Medical 2 Pass & Depart | Operations | `POST /api/resource/DSR Departure` | `Departed` |
| *Any State* | Cancel Process | Managers | `POST /api/method/.../cancel_applicant` | `Cancelled` |
| `Cancelled` | Restore Applicant | Managers | `POST /api/method/.../restore_applicant` | Recalculated |

---

# 9. LMS / Wakala / Injaz Workstreams — Current Reality

* **Entities:** `LMS Clearance` (`LMS-.#####`), `Wakala Clearance` (`WAK-.#####`), `Injaz Clearance` (`INJ-.#####`).
* **Auto-Creation:** Auto-generated when a `DSR` is created for an `Applicant Dossier`.
* **Field Comparison:**
  - **LMS:** Statuses: `["Pending", "Issued", "Rejected"]`. Field `issued_on` required when status is `Issued`.
  - **Wakala:** Statuses: `["Pending", "Completed"]`.
  - **Injaz:** Statuses: `["Pending", "Completed"]`.
* **Clearance Guardrail:** Creating `DSR Stamp`, `DSR Ticket`, or `DSR Departure` records is **strictly blocked** until LMS, Wakala, and Injaz all reach `Issued`/`Completed`.

---

# 10. Employee Assignment — Current Reality

* **Assignment Model:** Edit the Link field `employee` (options: `User`) directly on `LMS Clearance`, `Wakala Clearance`, or `Injaz Clearance`.
* **Automatic Permissions:** When `employee` is assigned on `LMS Clearance`, the backend automatically:
  1. Creates Frappe `User Permission` for the assigned user on `LMS Clearance`.
  2. Creates `User Permission` on linked `DSR Ticket` and `DSR Departure`.
  3. Generates an in-app `ToDo` task assigned to that employee.
  4. Generates a top-right Desk bell icon alert (`Notification Log`).

---

# 11. Permissions — Current Reality

* `System Manager`: Full access across all DocTypes and RPC methods.
* `LMS Employee` / Stage Roles: Granted granular access to their assigned Clearance documents and linked Ticket/Departure records via dynamic Frappe `User Permissions`.
* **Authentication Errors:** `401 Unauthorized` (Invalid/missing token or session).
* **Permission Errors:** `403 Forbidden` (Insufficient role/permission).

---

# 12. Documents & Media Handling

* **Upload Endpoint:** `POST /api/method/upload_file` (Multipart form-data).
* **Parameters:** `file`, `doctype`, `docname`, `fieldname`, `is_private`.
* **Supported Attach Fields:**
  - `photo_passport` (Applicant 2x2 photo)
  - `photo_full_body` (Applicant full body photo)
  - `passport_scan` (Applicant passport copy)
  - `file_attachment` (Generated CV PDF / Dossier contract attachment)

---

# 13. Expiry Watchdog & Automation — Current Reality

* **Medical Expiration Watchdog:**
  - Daily scheduler task `check_medical_expirations` runs automatically.
  - Queries all active applicants with `medical_expiry_date` $\le 16$ days.
  - Generates urgent `ToDo` tasks and `Notification Log` alerts for:
    1. Applicant Owner (Registering Officer).
    2. Assigned LMS, Wakala, and Injaz employees.
    3. System Managers.
* **Frontend Date Badging:** Frontend should display reactive badges:
  - Green: $>30$ Days
  - Yellow: $10-30$ Days
  - Pulsing Red: $\le 16$ Days (Matches server alert threshold)

---

# 14. Expenses / Income — Current Reality

* **Child DocType:** `Income Expense Log` (`istable: 1`).
* **Fields:** `transaction_type` (`Income`/`Expense`), `amount` (`Currency`), `date` (`Date`), `description` (`Data`), `source_doctype` (`Data`).
* **Embed Locations:** Available as sub-table `income_expense_logs` in `Applicant`, `CV Record`, `Applicant Dossier`, `DSR`, `LMS Clearance`, `Wakala Clearance`, `Injaz Clearance`, `DSR Stamp`, `DSR Ticket`, `DSR Departure`.
* **Dashboard Summary:** `GET /api/method/applicant_processing.applicant_processing.api.get_accounting_summary`.

---

# 15. Real-Time & Concurrency Behavior

* **Protocol:** REST API over HTTP/HTTPS.
* **Polling:** Polling recommended for status updates.
* **Concurrency:** Frappe uses `modified` timestamp check. If User B updates a record while User A is viewing old data, User A's update returns a `409 Conflict` error (`TimestampMismatchError`).

---

# 16. Test & Demo Credentials / Data

* **Base URL:** `https://applicantprocessing-production.up.railway.app/`
* **Admin Login:** `usr: admin@example.com`
* **Sample Applicants Available:** `APP-00001`, `APP-00002`

---

# 17. Final Change Log

### Changed from Earlier Version
1. Clearance updates use standard Frappe REST `PUT` endpoints instead of custom `update_*_stream` endpoints.
2. Employee assignment is managed directly by writing `employee` user email to clearance documents.
3. State machine includes distinct `Stamped` (step 7) and `Ticketed` (step 8) stages.

### New Features
1. Meta WhatsApp Cloud API PDF dispatch & WhatsApp Web link generation in `Contract Request`.
2. Accounting summary RPC (`get_accounting_summary`).
3. Strict clearance guardrail checks (`check_clearances_completed`) for Stamping and Ticketing.
4. Pre-Departure Medical 2 verification.
5. Automated 16-day medical expiration alert watchdog.

### Not Implemented / Out of Scope
1. Custom RPC endpoints `upload_contractor_doc`, `approve_contractor_doc`, `assign_employee`.
2. WebSockets / SSE real-time push.
