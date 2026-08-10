import frappe

def create_doctypes():
    frappe.init(site="applicant-processing.localhost")
    frappe.connect()
    
    # 1. Document Type
    if not frappe.db.exists("DocType", "Document Type"):
        doc_type = frappe.get_doc({
            "doctype": "DocType",
            "name": "Document Type",
            "module": "Applicant Processing",
            "custom": 0,
            "naming_rule": "By fieldname",
            "autoname": "field:document_type_name",
            "fields": [
                {"fieldname": "document_type_name", "label": "Name", "fieldtype": "Data", "reqd": 1, "unique": 1},
                {"fieldname": "description", "label": "Description", "fieldtype": "Small Text"},
                {"fieldname": "mandatory", "label": "Mandatory", "fieldtype": "Check", "default": "0"},
                {"fieldname": "allow_multiple", "label": "Allow Multiple", "fieldtype": "Check", "default": "0"},
                {"fieldname": "parser_required", "label": "Parser Required", "fieldtype": "Check", "default": "0"}
            ],
            "permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}]
        })
        doc_type.insert(ignore_permissions=True)
        print("Created Document Type")
        
    # 2. Applicant (Minimal)
    if not frappe.db.exists("DocType", "Applicant"):
        applicant = frappe.get_doc({
            "doctype": "DocType",
            "name": "Applicant",
            "module": "Applicant Processing",
            "custom": 0,
            "naming_rule": "Expression",
            "autoname": "APP-.#####",
            "fields": [
                {"fieldname": "full_name", "label": "Full Name", "fieldtype": "Data", "reqd": 1},
                {"fieldname": "applicant_state", "label": "Applicant State", "fieldtype": "Select", "options": "Draft\nRegistered\nWaiting For Data\nData Complete\nCV Generated\nContract Processing\nDocumentation\nInternal Processing\nCompleted\nTicket Issued\nDeparted", "default": "Draft"}
            ],
            "permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}]
        })
        applicant.insert(ignore_permissions=True)
        print("Created Applicant")
        
    # 3. Applicant Document
    if not frappe.db.exists("DocType", "Applicant Document"):
        app_doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "Applicant Document",
            "module": "Applicant Processing",
            "custom": 0,
            "naming_rule": "Expression",
            "autoname": "DOC-.#####",
            "fields": [
                {"fieldname": "applicant", "label": "Applicant", "fieldtype": "Link", "options": "Applicant", "reqd": 1},
                {"fieldname": "document_type", "label": "Document Type", "fieldtype": "Link", "options": "Document Type", "reqd": 1},
                {"fieldname": "file", "label": "File", "fieldtype": "Attach"},
                {"fieldname": "uploaded_by", "label": "Uploaded By", "fieldtype": "Link", "options": "User"},
                {"fieldname": "upload_date", "label": "Upload Date", "fieldtype": "Datetime"},
                {"fieldname": "status", "label": "Status", "fieldtype": "Select", "options": "Uploaded\nProcessing\nProcessed\nVerified\nRejected", "default": "Uploaded"}
            ],
            "permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}]
        })
        app_doc.insert(ignore_permissions=True)
        print("Created Applicant Document")
        
    frappe.db.commit()

create_doctypes()
