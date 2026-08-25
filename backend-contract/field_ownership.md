# Frontend-Backend Field Ownership & Schema Reference

> **Authoritative Notice**: This document defines field-level read/write ownership and resolves known naming and relational mismatches between frontend code and the deployed Frappe backend.

---

## 1. Resolved Schema & Relational Mismatches

| Frontend Assumption / Deprecated | Actual Deployed Backend Field / Architecture | Reason & Correction |
| :--- | :--- | :--- |
| `applicant.medical_expiry` | **`applicant.medical_expiry_date`** (Date) | The actual DocType field is `medical_expiry_date`. |
| `applicant_dossier.job_title` | **`applicant_dossier.profession`** (Data) | Dossier uses `profession`. The Applicant DocType uses `job_applied`. |
| `lms_clearance.applicant` | **Linked via `DSR` &rarr; `Applicant Dossier` &rarr; `applicant`** | Clearances attach to a **DSR** (`lms_clearance.dsr`), which references `applicant_dossier`, which references `applicant`. To query clearances by applicant, filter by `dsr.applicant_dossier.applicant` or use backend join endpoints. |
| `stream_lms_employee` / `stream_injaz_employee` | **`tabEmployee` / `tabUser` assignment via Frappe `_assign` / workflow** | Stream assignments are handled via Frappe standard assignments or custom role queue endpoints. |
| `applicant.status` | **`applicant.applicant_state`** (Select) | The lifecycle state field is `applicant_state`. |
| `cv_record.cv_pdf` | **`cv_record.file_attachment`** (Data/Attach) & **`cv_record.r2_url`** | The PDF attachment URL is stored in `file_attachment` and Cloudflare R2 URL in `r2_url`. |

---

## 2. DocType Field Ownership Tables

### A. `Applicant`

| Fieldname | Type | Ownership | Description / Notes |
| :--- | :--- | :--- | :--- |
| `name` | Data (ID) | **BACKEND ONLY** | Autoname `APP-.#####` (e.g. `APP-00001`). Generated on insert. |
| `applicant_type` | Select | **FRONTEND CREATE / UPDATE** | Options: `Standard`, `Muayena` (Default: `Standard`). |
| `destination_country` | Link (`Country`) | **FRONTEND CREATE / UPDATE** | Default: `Saudi Arabia`. |
| `first_name` | Data | **FRONTEND CREATE / UPDATE** | Required. |
| `middle_name` | Data | **FRONTEND CREATE / UPDATE** | Optional. |
| `last_name` | Data | **FRONTEND CREATE / UPDATE** | Required. |
| `full_name` | Data | **BACKEND ONLY** | Computed automatically on save: `first_name middle_name last_name`. |
| `gender` | Select | **FRONTEND CREATE / UPDATE** | Options: `Female`, `Male`. |
| `date_of_birth` | Date | **FRONTEND CREATE / UPDATE** | Required. Format: `YYYY-MM-DD`. |
| `age` | Int | **BACKEND ONLY** | Calculated automatically from `date_of_birth`. |
| `place_of_birth` | Data | **FRONTEND CREATE / UPDATE** | City / Region of birth. |
| `leaving_town` | Data | **FRONTEND CREATE / UPDATE** | Origin town in Ethiopia. |
| `height` | Data | **FRONTEND CREATE / UPDATE** | e.g. `160 cm`. |
| `weight` | Data | **FRONTEND CREATE / UPDATE** | e.g. `55 kg`. |
| `complexion` | Select | **FRONTEND CREATE / UPDATE** | Options: `FAIR`, `MEDIUM`, `DARK`. |
| `nationality` | Select / Data | **FRONTEND CREATE / UPDATE** | Default: `Ethiopia`. |
| `religion` | Select | **FRONTEND CREATE / UPDATE** | Options: `Muslim`, `Non-Muslim`, `Christian`, etc. |
| `marital_status` | Select | **FRONTEND CREATE / UPDATE** | Options: `Single`, `Married`, `Divorced`, `Widowed`. |
| `children` | Int | **FRONTEND CREATE / UPDATE** | Number of children. |
| `passport_number` | Data | **FRONTEND CREATE / UPDATE** | e.g. `EP1234567`. |
| `passport_issue_date`| Date | **FRONTEND CREATE / UPDATE** | Format: `YYYY-MM-DD`. |
| `passport_expiry` | Date | **FRONTEND CREATE / UPDATE** | Format: `YYYY-MM-DD`. |
| `place_of_issue` | Data | **FRONTEND CREATE / UPDATE** | Default: `ADDIS ABABA`. |
| `photo_passport` | Attach Image | **FRONTEND CREATE / UPDATE** | URL / Data URI for passport portrait image. |
| `photo_full_body` | Attach Image | **FRONTEND CREATE / UPDATE** | URL / Data URI for full length photo. |
| `passport_scan` | Attach Image | **FRONTEND CREATE / UPDATE** | URL / Data URI for scanned passport page. |
| `job_applied` | Select | **FRONTEND CREATE / UPDATE** | Default: `House Maid`. |
| `monthly_salary` | Data | **FRONTEND CREATE / UPDATE** | Default: `1,000 SR`. |
| `english_level` | Select | **FRONTEND CREATE / UPDATE** | Options: `None`, `Basic`, `Fair`, `Fluent`. |
| `arabic_level` | Select | **FRONTEND CREATE / UPDATE** | Options: `None`, `Basic`, `Fair`, `Fluent`. |
| `skill_*` | Select / Data | **FRONTEND CREATE / UPDATE** | Skill checkboxes/ratings (`skill_cooking`, `skill_cleaning`, etc.). |
| `phone_number` | Data | **FRONTEND CREATE / UPDATE** | Primary contact phone. |
| `email` | Data | **FRONTEND CREATE / UPDATE** | Email address. |
| `medical_status` | Select | **FRONTEND CREATE / UPDATE** | Options: `Pending`, `FIT`, `UNFIT`, `Expired`. |
| `medical_issue_date` | Date | **FRONTEND CREATE / UPDATE** | Issue date of GAMCA/medical certificate. |
| `medical_expiry_date`| Date | **FRONTEND CREATE / UPDATE** | Expiry date of medical certificate. |
| `medical_remaining_days`| Int | **BACKEND ONLY** | Calculated daily by background worker. |
| `coc_status` | Select | **FRONTEND CREATE / UPDATE** | Options: `Pending`, `Passed`, `Failed`. |
| `applicant_state` | Select | **BACKEND ONLY / ACTION DRIVEN**| **NEVER set arbitrary strings.** Progresses via state machine (`register_applicant`, `generate_cv`, contract parse, clearance approvals). |
| `state_step` | Int | **BACKEND ONLY** | Step index (1 to 12) reflecting `applicant_state`. |
| `state_progress` | Percent | **BACKEND ONLY** | Progress bar percentage (0% to 100%). |
| `locked_contractor`| Link (`Contractor`) | **BACKEND ONLY / ACTION DRIVEN**| Set when contract is parsed or contractor is locked. |
| `locked_at` | Datetime | **BACKEND ONLY** | Timestamp when locked to contractor. |

---

### B. `Applicant Dossier`

| Fieldname | Type | Ownership | Description |
| :--- | :--- | :--- | :--- |
| `name` | Data (ID) | **BACKEND ONLY** | Autoname `DOSSIER-.#####`. |
| `applicant` | Link (`Applicant`) | **FRONTEND CREATE** | Required link to Applicant. |
| `contract_request` | Link (`Contract Request`)| **FRONTEND CREATE (OPTIONAL)**| Optional link to Contract Request. |
| `attached_file` | Attach | **FRONTEND CREATE / UPDATE** | Uploaded contract PDF file URL. |
| `is_parsed` | Check | **BACKEND ONLY** | 1 when successfully parsed by PyMuPDF engine. |
| `contract_number` | Data | **BACKEND ONLY / PARSER POPULATED** | e.g. `2005450415`. |
| `visa_number` | Data | **BACKEND ONLY / PARSER POPULATED** | e.g. `1908334046`. |
| `sponsor_name` | Data | **BACKEND ONLY / PARSER POPULATED** | Employer full name. |
| `sponsor_id` | Data | **BACKEND ONLY / PARSER POPULATED** | Employer National ID. |
| `telephone` | Data | **BACKEND ONLY / PARSER POPULATED** | Sponsor phone / mobile. |
| `contractor_name` | Data | **BACKEND ONLY / PARSER POPULATED** | Saudi Recruiting Agency name. |
| `agency` | Data | **BACKEND ONLY / PARSER POPULATED** | Ethiopian Origin Agency name. |
| `amount_detail` | Currency | **BACKEND ONLY / PARSER POPULATED** | Contract monthly salary amount. |
| `contract_duration`| Data | **BACKEND ONLY / PARSER POPULATED** | Duration (e.g. `2 Years`). |
| `contract_date` | Date | **BACKEND ONLY / PARSER POPULATED** | Agreement issue date. |
| `contract_end_date`| Date | **BACKEND ONLY / PARSER POPULATED** | Calculated agreement expiry date. |

---

### C. `CV Record`

| Fieldname | Type | Ownership | Description |
| :--- | :--- | :--- | :--- |
| `name` | Data (ID) | **BACKEND ONLY** | Autoname `CV-.#####`. |
| `applicant` | Link (`Applicant`) | **BACKEND ONLY** | Set during `generate_cv` execution. |
| `file_attachment` | Attach / Data | **BACKEND ONLY** | PDF URL or Cloudflare R2 CDN URL. |
| `r2_url` | Data | **BACKEND ONLY** | Public Cloudflare R2 CDN URL. |
| `status` | Select | **BACKEND ONLY** | Options: `Draft`, `Final`, `Shared`, `Archived`. |
| `generated_by` | Link (`User`) | **BACKEND ONLY** | User who generated the CV. |
| `generated_date` | Datetime | **BACKEND ONLY** | Timestamp of generation. |

---

### D. Clearances & Operations (`DSR`, `LMS Clearance`, `Wakala Clearance`, `Injaz Clearance`, etc.)

All clearance records are linked hierarchically:

$$\text{Applicant} \xleftarrow{\text{applicant}} \text{Applicant Dossier} \xleftarrow{\text{applicant\_dossier}} \text{DSR} \xleftarrow{\text{dsr}} \begin{cases} \text{LMS Clearance} \\ \text{Wakala Clearance} \\ \text{Injaz Clearance} \\ \text{DSR Stamp} \\ \text{DSR Ticket} \\ \text{DSR Departure} \end{cases}$$

| DocType | Key Fields | Ownership | Notes |
| :--- | :--- | :--- | :--- |
| `DSR` | `name`, `applicant_dossier`, `status` | **FRONTEND CREATE / BACKEND MANAGED** | Daily Status Report master record connecting clearances to Dossier. |
| `LMS Clearance` | `dsr`, `status`, `submission_date`, `approval_date`, `reference_number` | **FRONTEND UPDATE** | Labor Market clearance. Setting status to `Approved` advances applicant state to `LMS Approved`. |
| `Wakala Clearance` | `dsr`, `status`, `wakala_number`, `approval_date` | **FRONTEND UPDATE** | Wakala power of attorney clearance. |
| `Injaz Clearance` | `dsr`, `status`, `injaz_number`, `approval_date` | **FRONTEND UPDATE** | Injaz electronic visa clearance. |
| `DSR Stamp` | `dsr`, `status`, `embassy_submission_date`, `stamped_date` | **FRONTEND UPDATE** | Embassy passport visa stamping. |
| `DSR Ticket` | `dsr`, `status`, `flight_number`, `departure_date`, `arrival_date`, `ticket_cost` | **FRONTEND UPDATE** | Flight booking and ticketing. |
| `DSR Departure` | `dsr`, `status`, `actual_departure_date`, `notes` | **FRONTEND UPDATE** | Final airport dispatch and departure confirmation. |
