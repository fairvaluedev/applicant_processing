import frappe

def get_context(context):
    context.no_cache = 1
    context.title = "Partner Agency Candidate Sourcing & Selection Portal"
    
    # Fetch available countries and job roles for filter dropdowns
    context.countries = frappe.get_all("Country", fields=["name"], order_by="name asc")
    
    # Get contractors list for agency selection filter / switcher
    context.contractors = frappe.get_all(
        "Contractor",
        filters={"active_status": 1},
        fields=["name", "company_name", "country", "contact_person"],
        order_by="company_name asc"
    )
