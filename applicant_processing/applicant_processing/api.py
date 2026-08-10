import frappe
import json

@frappe.whitelist()
def create_parse_request(applicant_document_name):
    """
    Creates a new Document Parse Request for a given Applicant Document.
    """
    if not frappe.db.exists("Applicant Document", applicant_document_name):
        frappe.throw(f"Applicant Document {applicant_document_name} not found", frappe.DoesNotExistError)

    doc = frappe.get_doc("Applicant Document", applicant_document_name)
    
    # Check if a pending or processing request already exists
    existing = frappe.db.get_value("Document Parse Request", 
        {"applicant_document": applicant_document_name, "parser_status": ["in", ["Pending", "Processing"]]}, "name")
    
    if existing:
        return {"status": "exists", "parse_request": existing}

    parse_request = frappe.get_doc({
        "doctype": "Document Parse Request",
        "applicant_document": applicant_document_name,
        "parser_status": "Pending"
    })
    parse_request.insert(ignore_permissions=True)
    frappe.db.commit()
    
    # Update the Applicant Document status
    doc.db_set("status", "Processing")
    
    return {"status": "success", "parse_request": parse_request.name}

@frappe.whitelist()
def get_parse_status(parse_request_name):
    """
    Returns the status of a specific Document Parse Request.
    """
    if not frappe.db.exists("Document Parse Request", parse_request_name):
        frappe.throw(f"Parse Request {parse_request_name} not found", frappe.DoesNotExistError)
        
    doc = frappe.get_doc("Document Parse Request", parse_request_name)
    
    return {
        "status": doc.parser_status,
        "extracted_data": json.loads(doc.extracted_data) if doc.extracted_data else None,
        "error_log": doc.error_log
    }

@frappe.whitelist(allow_guest=True)
def update_extracted_data(parse_request_name, extracted_data=None, status="Completed", error_log=None):
    """
    Receives payload from the external parser and updates the Parse Request.
    (For external systems, you'd usually use token auth, but allow_guest=True for testing/simplicity initially, or use API keys)
    """
    # In production, enforce API key authentication instead of allow_guest
    # However, for external parser callbacks, token auth is best.
    if isinstance(extracted_data, str):
        try:
            extracted_data = json.loads(extracted_data)
        except Exception:
            pass
            
    if not frappe.db.exists("Document Parse Request", parse_request_name):
        frappe.throw(f"Parse Request {parse_request_name} not found", frappe.DoesNotExistError)
        
    doc = frappe.get_doc("Document Parse Request", parse_request_name)
    
    if status == "Completed":
        doc.extracted_data = json.dumps(extracted_data) if extracted_data else None
        doc.parser_status = "Completed"
    else:
        doc.parser_status = "Failed"
        doc.error_log = error_log
        
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    
    # Also update the related Applicant Document status
    app_doc = frappe.get_doc("Applicant Document", doc.applicant_document)
    if status == "Completed":
        app_doc.db_set("status", "Processed")
    else:
        app_doc.db_set("status", "Rejected") # Or we could just set it back to Uploaded, depending on error spec

    return {"status": "success"}

@frappe.whitelist()
def get_pending_documents(limit=10):
    """
    Returns a list of Applicant Documents that are ready to be parsed.
    """
    # Fetch Applicant Documents that are Uploaded and whose Document Type requires parsing
    docs = frappe.db.sql("""
        select ad.name, ad.file, ad.document_type
        from `tabApplicant Document` ad
        join `tabDocument Type` dt on ad.document_type = dt.name
        where ad.status = 'Uploaded' and dt.parser_required = 1
        limit %s
    """, (limit,), as_dict=True)
    
    return docs

