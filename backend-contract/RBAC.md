# Role-Based Access Control (RBAC) & Permissions Matrix

## 1. Production Roles

The backend defines the following core business roles in Frappe:

1. **`System Manager` / `Administrator`**: Full platform control across all settings, DocTypes, and API methods.
2. **`Agency Admin`**: Full operational visibility across applicants, dossiers, clearances, accounting, and reports.
3. **`Recruiter` / `Intake Officer`**: Permissions to register applicants, edit biodata, upload passport photos, and generate CVs.
4. **`Clearance Officer`**: Permissions to review dossiers, manage DSR records, update LMS/Wakala/Injaz/Embassy clearance statuses, and attach tickets.
5. **`Accounts Officer`**: Permissions to record applicant fees, view financial ledgers, and manage Income Expense logs.
6. **`Applicant Viewer` / `Auditor`**: Read-only access to applicant records and operational summaries.
7. **`Guest`**: Restricted to public web portal endpoints (e.g. `/api/method/applicant_processing.applicant_processing.api.get_portal_stats`).

---

## 2. DocType Permission Matrix

| DocType | System Manager | Agency Admin | Recruiter | Clearance Officer | Accounts Officer | Applicant Viewer |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`Applicant`** | CRUD | CRUD | CRUD | R, U | R | R |
| **`Applicant Dossier`** | CRUD | CRUD | R | CRUD | R | R |
| **`CV Record`** | CRUD | CRUD | CRUD | R | R | R |
| **`Contract Request`** | CRUD | CRUD | CRUD | R | R | R |
| **`Contractor`** | CRUD | CRUD | R | R, U | R | R |
| **`DSR`** | CRUD | CRUD | R | CRUD | R | R |
| **`LMS Clearance`** | CRUD | CRUD | -- | CRUD | -- | R |
| **`Wakala Clearance`**| CRUD | CRUD | -- | CRUD | -- | R |
| **`Injaz Clearance`** | CRUD | CRUD | -- | CRUD | -- | R |
| **`DSR Stamp`** | CRUD | CRUD | -- | CRUD | -- | R |
| **`DSR Ticket`** | CRUD | CRUD | -- | CRUD | R | R |
| **`DSR Departure`** | CRUD | CRUD | -- | CRUD | -- | R |
| **`Applicant Fee`** | CRUD | CRUD | -- | -- | CRUD | R |
| **`Income Expense Log`**| CRUD | CRUD | -- | -- | CRUD | R |
| **`Agency Complaint`** | CRUD | CRUD | CRUD | CRUD | -- | R |
| **`Cloudflare R2 Settings`**| CRUD | R | -- | -- | -- | -- |

*Legend: C = Create, R = Read, U = Update, D = Delete*

---

## 3. Role Permission vs. Per-Applicant Assignment

- **Role Permissions**: Govern the broad structural ability to create, read, or update specific DocTypes (e.g. `Clearance Officer` can update `LMS Clearance`).
- **Per-Applicant Assignment (`_assign`)**:
  - Affects **workflow queue routing** and **assigned task lists**.
  - Does NOT block users with appropriate global role permissions from viewing or editing records unless strict user permission rules are configured.
