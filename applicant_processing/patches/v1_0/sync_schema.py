import frappe

def execute():
    """
    Ensures all updated DocTypes and schema columns (such as commission_status,
    contract_end_date, and contractor configurations) are cleanly reloaded into MariaDB.
    """
    doctypes_to_reload = [
        "Applicant",
        "Applicant Dossier",
        "Contractor",
        "DSR",
        "DSR Departure",
        "LMS Clearance",
        "Wakala Clearance",
        "Injaz Clearance",
        "Telesign Clearance",
        "Embassy Clearance",
        "Agency Complaint",
        "Income Expense Log",
        "Web Push Subscription",
        "Notification Config"
    ]

    for dt in doctypes_to_reload:
        try:
            frappe.reload_doc("Applicant Processing", "doctype", frappe.scrub(dt), force=True)
        except Exception as e:
            frappe.log_error(title=f"Patch reload failed for {dt}", message=str(e))

    frappe.db.commit()
