# Backend Integration Contract & Authoritative Schema

> **Authoritative Statement**:
> **The deployed Frappe DocType schema and specifications in this package are authoritative over any older or external documentation.**

---

## 1. Package Contents

This folder provides a complete, machine-readable backend integration contract for the custom agency frontend:

```text
backend-contract/
├── openapi.yaml               # OpenAPI 3.1.0 specification (YAML)
├── openapi.json               # OpenAPI 3.1.0 specification (JSON)
├── field_ownership.md         # Field-level Read/Write matrix & corrected field names
├── lifecycle.md               # 12-state canonical state machine & transition rules
├── RBAC.md                    # Role-Based Access Control matrix
├── errors.md                  # Standard error envelopes, HTTP codes & TypeScript parser
├── README.md                  # This document
└── doctypes/                  # Authoritative JSON exports for all deployed DocTypes
    ├── Applicant.json
    ├── Applicant_Dossier.json
    ├── Applicant_Fee.json
    ├── CV_Record.json
    ├── CV_Share_Log.json
    ├── Contract_Request.json
    ├── Contract_Request_Recipient.json
    ├── Contractor.json
    ├── LMS_Clearance.json
    ├── Injaz_Clearance.json
    ├── Wakala_Clearance.json
    ├── Embassy_Clearance.json
    ├── Telesign_Clearance.json
    ├── DSR.json
    ├── DSR_Stamp.json
    ├── DSR_Ticket.json
    ├── DSR_Departure.json
    ├── Income_Expense_Log.json
    ├── Agency_Complaint.json
    ├── Cloudflare_R2_Settings.json
    ├── Notification_Config.json
    ├── Web_Push_Subscription.json
    ├── User.json
    └── Employee.json
```

---

## 2. Environment & Version Metadata

- **Backend App**: `applicant_processing`
- **Frappe Framework Version**: `Frappe v15.x`
- **Specification Version**: `1.2.0`
- **Export Timestamp**: `2026-08-25 12:30:00 UTC`
- **Cloud Storage Engine**: Cloudflare R2 Object Storage (`tracking-agency`)
- **Realtime WebSocket Protocol**: Frappe Socket.IO (`frappe.publish_realtime`)

---

## 3. Quick Reference for Common Frontend Questions

1. **Medical Expiry Field**:
   - Correct fieldname is **`medical_expiry_date`** (Date format `YYYY-MM-DD`).
2. **Applicant Dossier Profession Field**:
   - Correct fieldname is **`profession`** (Data).
3. **Clearance Linkage to Applicants**:
   - Clearances attach to a **`DSR`** (`lms_clearance.dsr`), which references `applicant_dossier`, which references `applicant`.
4. **Applicant State Field**:
   - **`applicant_state`** (Select). Never set directly; use API triggers (`register_applicant`, `generate_cv`, contract parsing, clearance approvals).
5. **Realtime Socket Events**:
   - Listen for `cv_generated` and `contract_parsed` on your frontend Socket.IO client.
