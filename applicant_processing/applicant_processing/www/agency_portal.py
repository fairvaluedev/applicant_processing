import frappe

def get_context(context):
    context.no_cache = 1
    context.no_breadcrumbs = 1
    context.title = "Partner Agency Portal | FairValue APS"
    context.countries = frappe.get_all("Country", fields=["name"], order_by="name asc")
    context.contractors = frappe.get_all(
        "Contractor",
        filters={"active_status": 1},
        fields=["name", "company_name", "country", "contact_person", "whatsapp"],
        order_by="company_name asc"
    )
