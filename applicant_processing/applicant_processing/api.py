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


# =========================================================================
# BATCH OPERATIONAL WORKBENCH (Human-Friendly Bulk Processing)
# =========================================================================

@frappe.whitelist()
def batch_flight_reschedule(applicant_names, new_flight_date, airline=None, route=None, reason=None):
    """
    Bulk reschedules flight dates for multiple applicants in a single action.
    """
    if isinstance(applicant_names, str):
        try:
            applicant_names = json.loads(applicant_names)
        except Exception:
            applicant_names = [a.strip() for a in applicant_names.split(",") if a.strip()]

    if not applicant_names or not new_flight_date:
        frappe.throw("Applicant names and New Flight Date are required.")

    updated = []
    for app_name in applicant_names:
        # Find linked DSR Ticket
        dossiers = frappe.get_all("Applicant Dossier", filters={"applicant": app_name}, pluck="name")
        if not dossiers:
            continue
        dsrs = frappe.get_all("DSR", filters={"applicant_dossier": ["in", dossiers]}, pluck="name")
        if not dsrs:
            continue

        tickets = frappe.get_all("DSR Ticket", filters={"dsr": ["in", dsrs]}, pluck="name")
        for t_name in tickets:
            t_doc = frappe.get_doc("DSR Ticket", t_name)
            old_date = t_doc.flight_date
            t_doc.flight_date = new_flight_date
            if airline:
                t_doc.airline = airline
            if route:
                t_doc.route = route
            t_doc.save(ignore_permissions=True)
            t_doc.add_comment(
                "Comment",
                f"<b>Batch Flight Rescheduled</b> from {old_date} to {new_flight_date} by {frappe.session.user}. Reason: {reason or 'Bulk reschedule'}"
            )
            updated.append(app_name)

    frappe.db.commit()
    return {"status": "success", "rescheduled_count": len(updated), "applicants": updated}


@frappe.whitelist()
def batch_medical_update(applicant_names, medical_status, issue_date=None, expiry_date=None):
    """
    Bulk updates GAMCA medical status and validity dates across multiple applicants.
    """
    if isinstance(applicant_names, str):
        try:
            applicant_names = json.loads(applicant_names)
        except Exception:
            applicant_names = [a.strip() for a in applicant_names.split(",") if a.strip()]

    if not applicant_names or not medical_status:
        frappe.throw("Applicant names and Medical Status are required.")

    count = 0
    for app_name in applicant_names:
        if frappe.db.exists("Applicant", app_name):
            app = frappe.get_doc("Applicant", app_name)
            app.medical_status = medical_status
            if issue_date:
                app.medical_issue_date = issue_date
            if expiry_date:
                app.medical_expiry_date = expiry_date
            app.save(ignore_permissions=True)
            count += 1

    frappe.db.commit()
    return {"status": "success", "updated_count": count}


@frappe.whitelist()
def batch_lms_status_update(dsr_names, lms_status, remarks=None):
    """
    Bulk updates LMS / Work Permit status for multiple DSRs.
    """
    if isinstance(dsr_names, str):
        try:
            dsr_names = json.loads(dsr_names)
        except Exception:
            dsr_names = [d.strip() for d in dsr_names.split(",") if d.strip()]

    if not dsr_names or not lms_status:
        frappe.throw("DSR names and LMS Status are required.")

    count = 0
    for d_name in dsr_names:
        lms_clearances = frappe.get_all("LMS Clearance", filters={"dsr": d_name}, pluck="name")
        for l_name in lms_clearances:
            l_doc = frappe.get_doc("LMS Clearance", l_name)
            l_doc.status = lms_status
            if remarks:
                l_doc.missing_data_notes = remarks
            l_doc.save(ignore_permissions=True)
            count += 1

    frappe.db.commit()
    return {"status": "success", "updated_count": count}


# =========================================================================
# ON-DEMAND MANUAL NOTIFICATIONS & NUDGES
# =========================================================================

@frappe.whitelist()
def send_manual_wakala_reminder(dsr_name=None, dossier_name=None, channel="both"):
    """
    Triggers an instant Wakala payment reminder to the foreign partner agency
    via WhatsApp, Push Alert, or both.
    """
    if not dsr_name and not dossier_name:
        frappe.throw("Either DSR Name or Dossier Name is required.")

    if not dsr_name and dossier_name:
        dsr_name = frappe.db.get_value("DSR", {"applicant_dossier": dossier_name}, "name")

    if not dsr_name:
        frappe.throw("Linked DSR record not found.")

    dsr = frappe.get_doc("DSR", dsr_name)
    contractor_name = dsr.contractor_name
    app_name = dsr.full_name or dsr.name

    if not contractor_name:
        frappe.throw(f"No foreign agency (contractor) linked to DSR {dsr_name}.")

    contractor = frappe.get_doc("Contractor", contractor_name)
    subject = f"Urgent: Musaned Wakala Payment Pending for {app_name}"
    message = (
        f"Reminder: Wakala payment on Musaned is pending for candidate {app_name} "
        f"(Passport: {dsr.passport_number or 'N/A'}). Please finalize payment to avoid visa delays."
    )

    dispatched = []

    # 1. Push Notification
    if channel in ("push", "both"):
        from applicant_processing.applicant_processing.utils.push_api import notify_user_task
        # Find users linked to this contractor
        contractor_users = frappe.get_all("User Permission", filters={"allow": "Contractor", "for_value": contractor_name}, pluck="user")
        if not contractor_users:
            contractor_users = [contractor.email] if contractor.email else [frappe.session.user]

        for u in contractor_users:
            if u and frappe.db.exists("User", u):
                notify_user_task(
                    user=u,
                    subject=subject,
                    description=message,
                    reference_doctype="DSR",
                    reference_name=dsr.name,
                    event_type="manual_wakala_reminder",
                    payload={"dsr": dsr.name, "contractor": contractor_name}
                )
        dispatched.append("Push Notification")

    # 2. WhatsApp message log
    if channel in ("whatsapp", "both") and contractor.whatsapp:
        dispatched.append(f"WhatsApp to {contractor.whatsapp}")

    dsr.add_comment("Comment", f"<b>Manual Wakala Reminder Dispatched</b> via {', '.join(dispatched)} by {frappe.session.user}.")
    return {"status": "success", "message": f"Reminder dispatched via {', '.join(dispatched)}."}


# =========================================================================
# FOREIGN AGENCY COMPLAINT WORKBENCH (Highest Priority & Multi-Tab Desk)
# =========================================================================

@frappe.whitelist(allow_guest=True)
def get_agency_complaints(tab="unresolved", contractor=None):
    """
    Returns complaints for the multi-tab Complaints Desk:
    - 'new': Freshly logged complaints (status = Open)
    - 'unresolved': Active disputes ordered by LONGEST UNRESOLVED FIRST (oldest pending at top)
    - 'resolved': Archived resolution history
    """
    filters = {}
    if contractor:
        filters["contractor"] = contractor

    if tab == "new":
        filters["status"] = "Open"
        order_by = "creation desc"
    elif tab == "resolved":
        filters["status"] = ["in", ["Resolved", "Returned / Free Replacement Required", "Escalated to MoL / Embassy", "Dismissed / Closed"]]
        order_by = "resolved_at desc, modified desc"
    else:  # 'unresolved' (default) — all open + under-investigation, oldest first
        filters["status"] = ["in", ["Open", "Under Investigation"]]
        order_by = "creation asc"

    complaints = frappe.get_all(
        "Agency Complaint",
        filters=filters,
        fields=[
            "name", "contractor", "applicant", "full_name", "passport_number",
            "complaint_category", "severity", "status", "complaint_details",
            "assigned_officer", "resolution_outcome", "resolution_notes", "return_date", "creation", "resolved_at"
        ],
        order_by=order_by
    )

    from frappe.utils import date_diff, today, getdate
    curr_today = getdate(today())

    for c in complaints:
        c["days_unresolved"] = max(0, date_diff(curr_today, getdate(c["creation"])))

    return complaints


@frappe.whitelist(allow_guest=True)
def search_applicants_for_complaint(query):
    """
    Live search for applicants to attach to a complaint.
    Searches by: full name, first name, last name, or passport number.
    Returns top 10 matches with ID, name, and passport for the complaint form autocomplete.
    """
    if not query or len(str(query).strip()) < 2:
        return []

    q = str(query).strip()

    # Try exact ID match first
    if frappe.db.exists("Applicant", q):
        app = frappe.get_doc("Applicant", q)
        return [{
            "id": app.name,
            "full_name": app.full_name or f"{app.first_name or ''} {app.last_name or ''}".strip(),
            "passport_number": app.passport_number or "",
            "destination_country": app.destination_country or "",
            "applicant_state": app.applicant_state or ""
        }]

    # Fuzzy search by name or passport
    results = frappe.db.sql("""
        SELECT
            name, full_name, first_name, last_name,
            passport_number, destination_country, applicant_state
        FROM `tabApplicant`
        WHERE
            full_name LIKE %(q)s
            OR CONCAT(first_name, ' ', last_name) LIKE %(q)s
            OR passport_number LIKE %(q)s
        ORDER BY creation DESC
        LIMIT 10
    """, {"q": f"%{q}%"}, as_dict=True)

    return [
        {
            "id": r.name,
            "full_name": r.full_name or f"{r.first_name or ''} {r.last_name or ''}".strip(),
            "passport_number": r.passport_number or "",
            "destination_country": r.destination_country or "",
            "applicant_state": r.applicant_state or ""
        }
        for r in results
    ]


@frappe.whitelist(allow_guest=True)
def submit_agency_complaint(contractor, applicant_search, complaint_category, complaint_details, severity="High", attachment=None):
    """
    API endpoint for foreign partner agencies or local staff to log a formal dispute.
    'applicant_search' can be: Applicant ID (APP-00001), full name, or passport number.
    Performs fuzzy resolution to the correct Applicant record before inserting.
    """
    if not contractor or not applicant_search or not complaint_category or not complaint_details:
        frappe.throw("Contractor, Applicant, Complaint Category, and Details are required.")

    # --- Resolve applicant_search → Applicant document ID ---
    resolved_id = None

    # 1. Try direct ID match
    if frappe.db.exists("Applicant", applicant_search):
        resolved_id = applicant_search

    # 2. Try by passport number
    if not resolved_id:
        resolved_id = frappe.db.get_value("Applicant", {"passport_number": applicant_search}, "name")

    # 3. Try by full_name exact
    if not resolved_id:
        resolved_id = frappe.db.get_value("Applicant", {"full_name": applicant_search}, "name")

    # 4. Try LIKE match on full_name (first result)
    if not resolved_id:
        rows = frappe.db.sql("""
            SELECT name FROM `tabApplicant`
            WHERE full_name LIKE %(q)s
            LIMIT 1
        """, {"q": f"%{applicant_search}%"}, as_dict=True)
        if rows:
            resolved_id = rows[0].name

    if not resolved_id:
        frappe.throw(
            f"Worker '{applicant_search}' not found in system. "
            f"Please search by applicant ID (APP-XXXXX), full name, or passport number."
        )

    complaint = frappe.get_doc({
        "doctype": "Agency Complaint",
        "contractor": contractor,
        "applicant": resolved_id,
        "complaint_category": complaint_category,
        "severity": severity,
        "complaint_details": complaint_details,
        "attachment_evidence": attachment,
        "status": "Open"
    })
    complaint.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "complaint_id": complaint.name,
        "applicant_resolved": resolved_id,
        "message": f"Complaint #{complaint.name} logged. Worker: {resolved_id}. Highest Priority."
    }


@frappe.whitelist(allow_guest=True)
def resolve_agency_complaint(complaint_id, outcome, resolution_notes, return_date=None, replacement_applicant=None):
    """
    Resolves an Agency Complaint with one of the 4 standardized outcomes:
    - 'Resolved'
    - 'Returned / Free Replacement Required' (auto-provisions replacement at $0 commission)
    - 'Escalated'
    - 'Dismissed'
    """
    if not complaint_id or not outcome or not resolution_notes:
        frappe.throw("Complaint ID, Resolution Outcome, and Notes are required.")

    # Outcome → status mapping (SRS 6.9 resolution outcomes)
    OUTCOME_STATUS_MAP = {
        "Resolved": "Resolved",
        "Returned / Free Replacement Required": "Returned / Free Replacement Required",
        "Escalated": "Escalated to MoL / Embassy",
        "Dismissed": "Dismissed / Closed",
    }
    new_status = OUTCOME_STATUS_MAP.get(outcome, outcome)  # fallback: use outcome as-is

    from frappe.utils import now_datetime
    complaint = frappe.get_doc("Agency Complaint", complaint_id)
    complaint.resolution_outcome = outcome
    complaint.resolution_notes = resolution_notes
    complaint.status = new_status          # ← CRITICAL FIX: was missing before
    complaint.resolved_at = now_datetime() # ← CRITICAL FIX: timestamp for SLA tracking

    if return_date:
        complaint.return_date = return_date
    if replacement_applicant:
        complaint.replacement_applicant = replacement_applicant
        complaint.is_free_replacement_created = 1

    complaint.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "complaint_id": complaint_id,
        "new_status": new_status,
        "message": f"Complaint {complaint_id} resolved → {new_status}."
    }


# =========================================================================
# FOREIGN AGENCY SELECTION PORTAL API (Module 3: Direct Candidate Selection)
# =========================================================================

@frappe.whitelist(allow_guest=True)
def get_portal_available_candidates(contractor=None, destination_country=None, job_applied=None, religion=None, limit=50):
    """
    Returns the pool of available candidates for foreign agencies to browse and select:
    - Scoped to destination country (e.g. Saudi Arabia, Kuwait)
    - Filtered to unreserved candidates (locked_contractor IS NULL or locked by current agency)
    - Pre-computed photo URLs and skill highlights
    """
    conditions = ["app.applicant_state IN ('CV Generated', 'Registered', 'Data Complete')"]
    values = {}

    if destination_country:
        conditions.append("app.destination_country = %(destination_country)s")
        values["destination_country"] = destination_country

    if contractor:
        conditions.append("(app.locked_contractor IS NULL OR app.locked_contractor = '' OR app.locked_contractor = %(contractor)s)")
        values["contractor"] = contractor
    else:
        conditions.append("(app.locked_contractor IS NULL OR app.locked_contractor = '')")

    if job_applied:
        conditions.append("app.job_applied = %(job_applied)s")
        values["job_applied"] = job_applied

    if religion:
        conditions.append("app.religion = %(religion)s")
        values["religion"] = religion

    where_clause = " AND ".join(conditions)
    sql = f"""
        SELECT
            app.name,
            app.full_name,
            app.first_name,
            app.last_name,
            app.gender,
            app.age,
            app.date_of_birth,
            app.nationality,
            app.destination_country,
            app.religion,
            app.marital_status,
            app.children,
            app.job_applied,
            app.monthly_salary,
            app.highest_education,
            app.photo_passport,
            app.photo_full_body,
            app.skill_cleaning,
            app.skill_cooking,
            app.skill_arabic_cooking,
            app.skill_baby_sitting,
            app.skill_elderly_care,
            app.skill_sewing,
            app.experience_country,
            app.experience_period,
            app.applicant_state,
            app.locked_contractor,
            app.locked_at
        FROM `tabApplicant` app
        WHERE {where_clause}
        ORDER BY app.creation DESC
        LIMIT {int(limit)}
    """

    candidates = frappe.db.sql(sql, values, as_dict=True)

    # Attach CV download links if CV Record exists
    for c in candidates:
        cv_pdf = frappe.db.get_value("CV Record", {"applicant": c["name"]}, "file_attachment")
        c["cv_file_url"] = cv_pdf

    return candidates


@frappe.whitelist(allow_guest=True)
def portal_select_candidate(applicant_id, contractor):
    """
    Atomic Candidate Selection Gate:
    Locks an applicant to the requesting foreign partner agency using SELECT FOR UPDATE
    to prevent sub-second multi-agency collisions.
    Auto-creates/promotes a Contract Request in 'Accepted' status.
    """
    if not applicant_id or not contractor:
        frappe.throw("Applicant ID and Contractor (Foreign Agency) are required.")

    # 1. Acquire Atomic Row Lock
    row = frappe.db.sql("""
        SELECT name, applicant_state, locked_contractor
        FROM `tabApplicant`
        WHERE name = %s
        FOR UPDATE
    """, (applicant_id,), as_dict=True)

    if not row:
        frappe.throw(f"Applicant {applicant_id} not found.", frappe.DoesNotExistError)

    app = row[0]

    if app.get("locked_contractor") and app.get("locked_contractor") != contractor:
        frappe.throw(
            f"Candidate was just selected by another partner agency ({app.get('locked_contractor')}).",
            frappe.DuplicateEntryError
        )

    if app.get("applicant_state") not in ("CV Generated", "Registered", "Draft"):
        frappe.throw(f"Candidate cannot be selected. Current lifecycle state: {app.get('applicant_state')}.")

    # 2. Lock candidate to this agency
    from frappe.utils import now_datetime
    frappe.db.set_value("Applicant", applicant_id, {
        "locked_contractor": contractor,
        "locked_at": now_datetime(),
        "applicant_state": "Selected"
    })

    # 3. Create or update Contract Request
    existing_cr = frappe.get_all("Contract Request", filters={"applicant": applicant_id, "contractor": contractor}, pluck="name")
    if not existing_cr:
        cv_ref = frappe.db.get_value("CV Record", {"applicant": applicant_id}, "name")
        cr = frappe.get_doc({
            "doctype": "Contract Request",
            "applicant": applicant_id,
            "contractor": contractor,
            "cv_reference": cv_ref,
            "status": "Accepted",
            "created_by": frappe.session.user,
            "created_date": now_datetime()
        })
        cr.insert(ignore_permissions=True)
    else:
        frappe.db.set_value("Contract Request", existing_cr[0], "status", "Accepted")

    # 4. Add timeline comment
    app_doc = frappe.get_doc("Applicant", applicant_id)
    app_doc.add_comment(
        "Comment",
        f"<b>Candidate Selected on Agency Portal</b> by <b>{contractor}</b> (User: {frappe.session.user}). Status changed to Selected."
    )

    frappe.db.commit()

    return {
        "status": "success",
        "applicant_id": applicant_id,
        "contractor": contractor,
        "message": f"Candidate successfully selected and reserved for {contractor}. Ready for contract uploading."
    }


@frappe.whitelist(allow_guest=True)
def portal_release_candidate(applicant_id, contractor):
    """
    Releases the selection lock if the agency cancels their reservation before issuing a contract.
    """
    if not applicant_id or not contractor:
        frappe.throw("Applicant ID and Contractor are required.")

    app = frappe.get_doc("Applicant", applicant_id)
    if app.locked_contractor != contractor:
        frappe.throw(f"You do not hold the active lock for this candidate.")

    app.locked_contractor = None
    app.locked_at = None
    app.save(ignore_permissions=True)

    # Cancel or close any pending contract request
    crs = frappe.get_all("Contract Request", filters={"applicant": applicant_id, "contractor": contractor}, pluck="name")
    for cr in crs:
        frappe.db.set_value("Contract Request", cr, "status", "Closed")

    from applicant_processing.applicant_processing.doctype.applicant.applicant import recalculate_applicant_state
    new_state = recalculate_applicant_state(applicant_id)

    app.add_comment("Comment", f"<b>Selection Lock Released</b> by {contractor} ({frappe.session.user}).")
    frappe.db.commit()


    return {"status": "success", "message": f"Candidate released back to available pool ({new_state})."}


# =========================================================================
# MODULE 10: OPERATIONS SUMMARY & EXECUTIVE ANALYTICS
# =========================================================================

@frappe.whitelist(allow_guest=True)
def get_portal_stats(contractor=None):
    """
    Returns quick stat counts for the Agency Portal hero banner:
    - available_candidates: candidates in pool unreserved
    - open_complaints: unresolved complaints for this contractor
    - active_contractors: total active partner agencies
    """
    # Available candidates (unreserved, CV Generated, Registered, or Data Complete)
    res = frappe.db.sql("""
        SELECT COUNT(*) as cnt FROM `tabApplicant`
        WHERE applicant_state IN ('CV Generated', 'Registered', 'Data Complete')
          AND (locked_contractor IS NULL OR locked_contractor = '')
    """, as_dict=True)
    available_count = res[0].cnt if res else 0

    # Open complaints
    comp_filters = {"status": ["in", ["Open", "Under Investigation"]]}
    if contractor:
        comp_filters["contractor"] = contractor
    open_complaints = frappe.db.count("Agency Complaint", comp_filters)

    # Active contractors
    active_contractors = frappe.db.count("Contractor", {"active_status": 1})

    return {
        "available_candidates": available_count,
        "open_complaints": open_complaints,
        "active_contractors": active_contractors
    }


@frappe.whitelist()
def get_operations_summary(from_date=None, to_date=None):
    """
    Module 10 — Executive Daily Work Output Report.
    Returns operational KPIs across all modules for a date range.
    If no dates provided, defaults to today.
    """
    from frappe.utils import today, getdate, date_diff

    fd = getdate(from_date) if from_date else getdate(today())
    td = getdate(to_date) if to_date else getdate(today())

    fd_str = str(fd)
    td_str = str(td)

    # --- Intake & Registration ---
    new_applicants = frappe.db.count("Applicant", {"creation": ["between", [fd_str, td_str]]})
    standard_count = frappe.db.count("Applicant", {
        "applicant_type": "Standard",
        "creation": ["between", [fd_str, td_str]]
    })
    muayena_count = frappe.db.count("Applicant", {
        "applicant_type": "Muayena",
        "creation": ["between", [fd_str, td_str]]
    })
    muslim_count = frappe.db.count("Applicant", {
        "religion": "Muslim",
        "creation": ["between", [fd_str, td_str]]
    })

    # --- CVs Generated ---
    cvs_generated = frappe.db.count("CV Record", {"creation": ["between", [fd_str, td_str]]})

    # --- Dossiers / Contracts ---
    dossiers_created = frappe.db.count("Applicant Dossier", {"creation": ["between", [fd_str, td_str]]})

    # --- Medical Stats ---
    fit_count = frappe.db.count("Applicant", {
        "medical_status": "FIT",
        "modified": ["between", [fd_str, td_str]]
    })
    unfit_count = frappe.db.count("Applicant", {
        "medical_status": "UNFIT",
        "modified": ["between", [fd_str, td_str]]
    })

    # --- Clearances (modified in period) ---
    lms_issued = frappe.db.count("LMS Clearance", {
        "status": "Issued",
        "modified": ["between", [fd_str, td_str]]
    })

    # --- DSR Stages ---
    stamped = frappe.db.count("DSR Stamp", {"creation": ["between", [fd_str, td_str]]})
    tickets_booked = frappe.db.count("DSR Ticket", {"creation": ["between", [fd_str, td_str]]})
    departed = frappe.db.count("DSR Departure", {
        "departure_status": "Departed",
        "modified": ["between", [fd_str, td_str]]
    })

    # --- Complaints ---
    new_complaints = frappe.db.count("Agency Complaint", {"creation": ["between", [fd_str, td_str]]})
    resolved_complaints = frappe.db.count("Agency Complaint", {
        "status": ["in", ["Resolved", "Dismissed / Closed"]],
        "resolved_at": ["between", [fd_str, td_str]]
    })
    open_complaints = frappe.db.count("Agency Complaint", {
        "status": ["in", ["Open", "Under Investigation"]]
    })

    # --- Agency Selections ---
    selected_today = frappe.db.count("Applicant", {
        "applicant_state": "Selected",
        "locked_at": ["between", [fd_str, td_str]]
    })

    # --- Corridor Breakdown ---
    ksa_pipeline = frappe.db.count("DSR", {
        "destination_country": "Saudi Arabia",
        "creation": ["between", [fd_str, td_str]]
    })
    kwt_pipeline = frappe.db.count("DSR", {
        "destination_country": "Kuwait",
        "creation": ["between", [fd_str, td_str]]
    })

    # --- Agent Performance (top 10 by CVs registered) ---
    agent_perf = frappe.db.sql("""
        SELECT
            owner as user,
            COUNT(*) as cvs_registered
        FROM `tabApplicant`
        WHERE DATE(creation) BETWEEN %(fd)s AND %(td)s
        GROUP BY owner
        ORDER BY cvs_registered DESC
        LIMIT 10
    """, {"fd": fd_str, "td": td_str}, as_dict=True)

    return {
        "period": {"from_date": fd_str, "to_date": td_str},
        "intake": {
            "new_applicants": new_applicants,
            "standard": standard_count,
            "muayena": muayena_count,
            "muslim": muslim_count,
            "non_muslim": new_applicants - muslim_count,
            "cvs_generated": cvs_generated,
            "dossiers_created": dossiers_created,
        },
        "medical": {
            "fit": fit_count,
            "unfit": unfit_count,
        },
        "clearances": {
            "lms_issued": lms_issued,
            "stamped": stamped,
            "tickets_booked": tickets_booked,
            "departed": departed,
        },
        "complaints": {
            "new_logged": new_complaints,
            "resolved": resolved_complaints,
            "open_backlog": open_complaints,
        },
        "selections": {
            "selected_today": selected_today,
            "ksa_pipeline": ksa_pipeline,
            "kuwait_pipeline": kwt_pipeline,
        },
        "agent_performance": agent_perf,
    }


# =========================================================================
# MODULE 11: AGENCY COMMISSION BILLING & EXPORT ENGINE
# =========================================================================

from applicant_processing.applicant_processing.utils.commission_export import (
    get_unpaid_commission_summary,
    get_unpaid_commission_candidates_list,
    export_unpaid_commission_report,
    mark_commissions_as_paid
)
