import frappe

@frappe.whitelist()
def get_complaints_desk_data():
    contractors = frappe.get_all(
        "Contractor",
        filters={"active_status": 1},
        fields=["name", "company_name", "country"],
        order_by="company_name asc"
    )
    return {"contractors": contractors}
