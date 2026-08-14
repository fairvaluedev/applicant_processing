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


@frappe.whitelist()
def get_accounting_summary():
    """
    Returns a financial summary for the Accounting Dashboard across ALL parts:
    - Applicant Fees & Direct Logs
    - CV Record
    - LMS Clearance
    - Wakala Clearance
    - Injaz Clearance
    - DSR Stamp
    - DSR Ticket
    - DSR Departure
    - Applicant Dossier & DSR
    """

    # Helper subquery for joining all parent doctypes to get their Applicant link
    base_sql = """
        FROM `tabIncome Expense Log` iel
        LEFT JOIN `tabCV Record` cvr ON iel.parenttype = 'CV Record' AND iel.parent = cvr.name
        LEFT JOIN `tabApplicant Dossier` dos ON iel.parenttype = 'Applicant Dossier' AND iel.parent = dos.name
        LEFT JOIN `tabDSR` dsr ON iel.parenttype = 'DSR' AND iel.parent = dsr.name
        LEFT JOIN `tabApplicant Dossier` dsr_dos ON dsr.applicant_dossier = dsr_dos.name

        LEFT JOIN `tabLMS Clearance` lms ON iel.parenttype = 'LMS Clearance' AND iel.parent = lms.name
        LEFT JOIN `tabDSR` lms_dsr ON lms.dsr = lms_dsr.name
        LEFT JOIN `tabApplicant Dossier` lms_dos ON lms_dsr.applicant_dossier = lms_dos.name

        LEFT JOIN `tabWakala Clearance` wak ON iel.parenttype = 'Wakala Clearance' AND iel.parent = wak.name
        LEFT JOIN `tabDSR` wak_dsr ON wak.dsr = wak_dsr.name
        LEFT JOIN `tabApplicant Dossier` wak_dos ON wak_dsr.applicant_dossier = wak_dos.name

        LEFT JOIN `tabInjaz Clearance` inj ON iel.parenttype = 'Injaz Clearance' AND iel.parent = inj.name
        LEFT JOIN `tabDSR` inj_dsr ON inj.dsr = inj_dsr.name
        LEFT JOIN `tabApplicant Dossier` inj_dos ON inj_dsr.applicant_dossier = inj_dos.name

        LEFT JOIN `tabDSR Stamp` stp ON iel.parenttype = 'DSR Stamp' AND iel.parent = stp.name
        LEFT JOIN `tabDSR` stp_dsr ON stp.dsr = stp_dsr.name
        LEFT JOIN `tabApplicant Dossier` stp_dos ON stp_dsr.applicant_dossier = stp_dos.name

        LEFT JOIN `tabDSR Ticket` tkt ON iel.parenttype = 'DSR Ticket' AND iel.parent = tkt.name
        LEFT JOIN `tabDSR` tkt_dsr ON tkt.dsr = tkt_dsr.name
        LEFT JOIN `tabApplicant Dossier` tkt_dos ON tkt_dsr.applicant_dossier = tkt_dos.name

        LEFT JOIN `tabDSR Departure` dep ON iel.parenttype = 'DSR Departure' AND iel.parent = dep.name
        LEFT JOIN `tabDSR` dep_dsr ON dep.dsr = dep_dsr.name
        LEFT JOIN `tabApplicant Dossier` dep_dos ON dep_dsr.applicant_dossier = dep_dos.name
    """

    # ── 1. Overall totals across ALL parts ──
    totals = frappe.db.sql(f"""
        SELECT
            SUM(CASE WHEN iel.transaction_type = 'Income'  THEN iel.amount ELSE 0 END) AS total_income,
            SUM(CASE WHEN iel.transaction_type = 'Expense' THEN iel.amount ELSE 0 END) AS total_expense,
            COUNT(*) AS transaction_count
        {base_sql}
    """, as_dict=True)

    total_income  = float(totals[0].total_income  or 0)
    total_expense = float(totals[0].total_expense or 0)
    transaction_count = int(totals[0].transaction_count or 0)

    # ── 2. Breakdown by Stage / Part (DocType) ──
    by_stage_rows = frappe.db.sql(f"""
        SELECT
            iel.parenttype AS stage,
            SUM(CASE WHEN iel.transaction_type = 'Income'  THEN iel.amount ELSE 0 END) AS income,
            SUM(CASE WHEN iel.transaction_type = 'Expense' THEN iel.amount ELSE 0 END) AS expense,
            SUM(CASE WHEN iel.transaction_type = 'Income'  THEN iel.amount
                     WHEN iel.transaction_type = 'Expense' THEN -iel.amount ELSE 0 END) AS net,
            COUNT(*) AS count
        {base_sql}
        GROUP BY iel.parenttype
        ORDER BY SUM(iel.amount) DESC
    """, as_dict=True)

    by_stage = [
        {
            "stage": r.stage,
            "income": float(r.income or 0),
            "expense": float(r.expense or 0),
            "net": float(r.net or 0),
            "count": int(r.count or 0)
        }
        for r in by_stage_rows
    ]

    # ── 3. Breakdown by fee type (from Applicant Fee rows) ──
    by_fee_type_rows = frappe.db.sql("""
        SELECT
            af.fee_type,
            af.direction,
            SUM(af.amount) AS total
        FROM `tabApplicant Fee` af
        WHERE af.parenttype = 'Applicant'
        GROUP BY af.fee_type, af.direction
        ORDER BY total DESC
    """, as_dict=True)

    by_fee_type = {}
    for row in by_fee_type_rows:
        key = f"{row.fee_type} ({row.direction})"
        by_fee_type[key] = float(row.total or 0)

    # ── 4. Per-applicant summary across ALL stage parts (top 20) ──
    per_applicant = frappe.db.sql(f"""
        SELECT
            COALESCE(
                CASE WHEN iel.parenttype = 'Applicant' THEN iel.parent END,
                cvr.applicant,
                dos.applicant,
                dsr_dos.applicant,
                lms_dos.applicant,
                wak_dos.applicant,
                inj_dos.applicant,
                stp_dos.applicant,
                tkt_dos.applicant,
                dep_dos.applicant,
                'Unlinked / General'
            ) AS applicant,
            SUM(CASE WHEN iel.transaction_type = 'Income'  THEN iel.amount ELSE 0 END) AS income,
            SUM(CASE WHEN iel.transaction_type = 'Expense' THEN iel.amount ELSE 0 END) AS expense,
            SUM(CASE WHEN iel.transaction_type = 'Income'  THEN iel.amount
                     WHEN iel.transaction_type = 'Expense' THEN -iel.amount ELSE 0 END) AS net
        {base_sql}
        GROUP BY applicant
        ORDER BY SUM(iel.amount) DESC
        LIMIT 20
    """, as_dict=True)

    # ── 5. 25 most recent transactions across ALL parts ──
    recent = frappe.db.sql(f"""
        SELECT
            iel.name,
            COALESCE(
                CASE WHEN iel.parenttype = 'Applicant' THEN iel.parent END,
                cvr.applicant,
                dos.applicant,
                dsr_dos.applicant,
                lms_dos.applicant,
                wak_dos.applicant,
                inj_dos.applicant,
                stp_dos.applicant,
                tkt_dos.applicant,
                dep_dos.applicant,
                'Unlinked'
            ) AS applicant,
            iel.parenttype AS stage,
            iel.parent AS stage_doc,
            iel.transaction_type,
            iel.amount,
            iel.date,
            iel.description,
            iel.source_doctype
        {base_sql}
        ORDER BY iel.date DESC, iel.creation DESC
        LIMIT 25
    """, as_dict=True)

    # Attach Applicant Full Names
    app_ids = list({
        r["applicant"] for r in per_applicant if r.get("applicant") and r["applicant"] != "Unlinked / General"
    } | {
        r["applicant"] for r in recent if r.get("applicant") and r["applicant"] != "Unlinked"
    })

    app_name_map = {}
    if app_ids:
        app_rows = frappe.get_all(
            "Applicant",
            filters={"name": ["in", app_ids]},
            fields=["name", "full_name", "first_name", "last_name"]
        )
        for a in app_rows:
            app_name_map[a["name"]] = a.get("full_name") or f"{a.get('first_name') or ''} {a.get('last_name') or ''}".strip()

    for r in per_applicant:
        r["applicant_name"] = app_name_map.get(r.get("applicant")) or r.get("applicant")

    for r in recent:
        r["applicant_name"] = app_name_map.get(r.get("applicant")) or r.get("applicant")

    return {
        "total_income":       total_income,
        "total_expense":      total_expense,
        "net_balance":        total_income - total_expense,
        "transaction_count":  transaction_count,
        "by_stage":           by_stage,
        "by_fee_type":        by_fee_type,
        "per_applicant":      per_applicant,
        "recent_transactions": recent,
    }


@frappe.whitelist()
def sync_all_full_names():
    """
    Backfills and synchronizes full_name across all records:
    Applicant -> CV Record -> Contract Request -> Dossier -> DSR -> Clearances.
    """
    updated_counts = {}

    # 1. Applicant
    applicants = frappe.get_all("Applicant", fields=["name", "first_name", "middle_name", "last_name", "full_name"])
    app_map = {}
    app_count = 0
    for app in applicants:
        parts = [app.get("first_name"), app.get("middle_name"), app.get("last_name")]
        fn = " ".join([p.strip() for p in parts if p and p.strip()]).strip()
        app_map[app.name] = fn
        if app.get("full_name") != fn:
            frappe.db.set_value("Applicant", app.name, "full_name", fn, update_modified=False)
            app_count += 1
    updated_counts["Applicant"] = app_count

    # 2. CV Record
    cvs = frappe.get_all("CV Record", fields=["name", "applicant", "full_name", "first_name", "middle_name", "last_name"])
    cv_count = 0
    for cv in cvs:
        fn = app_map.get(cv.get("applicant")) or " ".join([p.strip() for p in [cv.get("first_name"), cv.get("middle_name"), cv.get("last_name")] if p and p.strip()]).strip()
        if fn and cv.get("full_name") != fn:
            frappe.db.set_value("CV Record", cv.name, "full_name", fn, update_modified=False)
            cv_count += 1
    updated_counts["CV Record"] = cv_count

    # 3. Contract Request
    crs = frappe.get_all("Contract Request", fields=["name", "applicant", "full_name"])
    cr_count = 0
    for cr in crs:
        fn = app_map.get(cr.get("applicant"))
        if fn and cr.get("full_name") != fn:
            frappe.db.set_value("Contract Request", cr.name, "full_name", fn, update_modified=False)
            cr_count += 1
    updated_counts["Contract Request"] = cr_count

    # 4. Applicant Dossier
    dos_map = {}
    dossiers = frappe.get_all("Applicant Dossier", fields=["name", "applicant", "first_name", "last_name", "full_name"])
    dos_count = 0
    for dos in dossiers:
        fn = app_map.get(dos.get("applicant")) or f"{dos.get('first_name') or ''} {dos.get('last_name') or ''}".strip()
        dos_map[dos.name] = fn
        if fn and dos.get("full_name") != fn:
            frappe.db.set_value("Applicant Dossier", dos.name, "full_name", fn, update_modified=False)
            dos_count += 1
    updated_counts["Applicant Dossier"] = dos_count

    # 5. DSR
    dsr_map = {}
    dsrs = frappe.get_all("DSR", fields=["name", "applicant_dossier", "first_name", "last_name", "full_name"])
    dsr_count = 0
    for dsr in dsrs:
        fn = dos_map.get(dsr.get("applicant_dossier")) or f"{dsr.get('first_name') or ''} {dsr.get('last_name') or ''}".strip()
        dsr_map[dsr.name] = fn
        if fn and dsr.get("full_name") != fn:
            frappe.db.set_value("DSR", dsr.name, "full_name", fn, update_modified=False)
            dsr_count += 1
    updated_counts["DSR"] = dsr_count

    # 6. Clearance DocTypes
    clearance_doctypes = [
        "LMS Clearance", "Wakala Clearance", "Injaz Clearance",
        "DSR Stamp", "DSR Ticket", "DSR Departure"
    ]
    for dt in clearance_doctypes:
        records = frappe.get_all(dt, fields=["name", "dsr", "first_name", "last_name", "full_name"])
        dt_count = 0
        for rec in records:
            fn = dsr_map.get(rec.get("dsr")) or f"{rec.get('first_name') or ''} {rec.get('last_name') or ''}".strip()
            if fn and rec.get("full_name") != fn:
                frappe.db.set_value(dt, rec.name, "full_name", fn, update_modified=False)
                dt_count += 1
        updated_counts[dt] = dt_count

    frappe.db.commit()
    return {
        "status": "success",
        "message": "Full names synchronized across all records successfully.",
        "updated": updated_counts
    }


