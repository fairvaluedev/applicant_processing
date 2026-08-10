import frappe

def execute():
    frappe.init(site="applicant-processing.localhost")
    frappe.connect()

    doctypes_to_delete = [
        "VSR",
        "Stamp",
        "Ticket",
        "Data Request",
        "Data Request Type",
        "Document Parse Request",
        "Applicant Document",
        "Employee Task"
    ]

    for dt in doctypes_to_delete:
        if frappe.db.exists("DocType", dt):
            print(f"Deleting DocType: {dt}")
            # delete all records first to avoid foreign key or linked doc issues
            records = frappe.get_all(dt, pluck="name")
            for record in records:
                frappe.delete_doc(dt, record, force=1, ignore_permissions=True)
            
            # delete the doctype itself
            frappe.delete_doc("DocType", dt, force=1, ignore_permissions=True)
        else:
            print(f"DocType {dt} does not exist.")

    frappe.db.commit()
    print("Done deleting doctypes.")

if __name__ == "__main__":
    execute()
