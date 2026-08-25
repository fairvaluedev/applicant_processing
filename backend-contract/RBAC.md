# Role-Based Access Control (RBAC) & Permissions Matrix

## 1. Deployed Production Roles

The backend defines the following active roles:

1. **`System Manager` / `Administrator`**: Full platform control across all settings, DocTypes, and API methods.
2. **`Foreign Agency`**: External partner recruitment agencies (Musaned / Saudi agencies) accessing the agency portal to browse candidates, view generated CVs, and lock candidate reservations.
3. **`LMS Employee` / `LMS Officer`**: Staff managing Labor Market approvals and GAMCA/COC missing data requests.
4. **`Injaz Officer`**: Staff managing electronic visa applications and Injaz clearances.
5. **`Wakala Officer`**: Staff managing Musaned Power of Attorney and contract authentication clearances.
6. **`Accounts Manager` / `Accounts User`**: Staff managing financial transactions, applicant commission fees, and Income Expense logs.
7. **`Desk User`**: Standard internal agency employees.
8. **`Guest`**: Unauthenticated public endpoints.

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
