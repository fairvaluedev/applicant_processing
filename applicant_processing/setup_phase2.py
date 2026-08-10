import frappe

def create_phase2_doctypes():
    frappe.init(site="applicant-processing.localhost")
    frappe.connect()
    
    if not frappe.db.exists("DocType", "Document Parse Request"):
        parse_request = frappe.get_doc({
            "doctype": "DocType",
            "name": "Document Parse Request",
            "module": "Applicant Processing",
            "custom": 0,
            "naming_rule": "Expression",
            "autoname": "PARSE-.#####",
            "fields": [
                {"fieldname": "applicant_document", "label": "Applicant Document", "fieldtype": "Link", "options": "Applicant Document", "reqd": 1, "in_list_view": 1},
                {"fieldname": "parser_status", "label": "Parser Status", "fieldtype": "Select", "options": "Pending\nProcessing\nCompleted\nFailed", "default": "Pending", "in_list_view": 1},
                {"fieldname": "extracted_data", "label": "Extracted Data", "fieldtype": "Code", "options": "JSON"},
                {"fieldname": "error_log", "label": "Error Log", "fieldtype": "Text"}
            ],
            "permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}]
        })
        parse_request.insert(ignore_permissions=True)
        print("Created Document Parse Request")
    
    frappe.db.commit()

create_phase2_doctypes()
