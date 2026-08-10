import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

def make_applicant_fields_optional():
    frappe.init(site="applicant-processing.localhost")
    frappe.connect()

    applicant_doctype = frappe.get_doc("DocType", "Applicant")
    
    # Remove mandatory requirement from all fields except perhaps first_name
    for field in applicant_doctype.fields:
        # Keep first_name mandatory just so it has a title, everything else optional
        if field.fieldname != "first_name":
            field.reqd = 0
            
    # Add an HTML field to indicate missing data at the top of the form
    # We will place it right after the Internal Information section or at the top
    html_field_exists = any(f.fieldname == "missing_data_indicator" for f in applicant_doctype.fields)
    
    if not html_field_exists:
        applicant_doctype.append("fields", {
            "fieldname": "missing_data_indicator",
            "label": "Missing Data Indicator",
            "fieldtype": "HTML",
            "insert_after": "personal_info_sec" # Put it at the top
        })

    applicant_doctype.save(ignore_permissions=True)
    frappe.db.commit()
    print("Applicant fields made optional and indicator added.")

make_applicant_fields_optional()
