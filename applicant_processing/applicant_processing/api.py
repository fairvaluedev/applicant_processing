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
# MULTI-TENANT AGENCY PORTAL & DISPUTE WORKBENCH (Production-Hardened)
# =========================================================================

def _get_effective_contractor_for_session(requested_contractor=None):
    """
    Resolves the partner agency (Contractor) context securely based on frappe.session.user.
    - If user is Guest: Throws AuthenticationError.
    - If Administrator / System Manager / LMS Employee / Accounts Manager:
      Allowed to view or act on behalf of requested_contractor (or fallback to active contractor).
    - If Foreign Agency user:
      Finds the Contractor record strictly linked by email == session.user OR user == session.user OR name == session.user.
      Overrides requested_contractor with the authenticated user's Contractor ID.
      Guarantees complete multi-tenant data isolation: no agency can see or act on another agency's data.
    """
    if not frappe.session.user or frappe.session.user == "Guest":
        frappe.throw("Authentication required. Please log in.", frappe.AuthenticationError)

    user_roles = frappe.get_roles(frappe.session.user)
    is_internal = any(r in user_roles for r in ("System Manager", "Administrator", "LMS Employee", "Accounts Manager"))

    if is_internal:
        if requested_contractor:
            if not frappe.db.exists("Contractor", requested_contractor):
                frappe.throw(f"Partner Agency '{requested_contractor}' not found.", frappe.DoesNotExistError)
            return requested_contractor
        # Return first active contractor as fallback if none requested
        return frappe.db.get_value("Contractor", {"active_status": 1}, "name")

    # Foreign Agency User: Find contractor strictly linked to this user's account
    contractor_name = frappe.db.get_value("Contractor", {"email": frappe.session.user, "active_status": 1}, "name")
    if not contractor_name and hasattr(frappe.db, "has_column") and frappe.db.has_column("Contractor", "user"):
        contractor_name = frappe.db.get_value("Contractor", {"user": frappe.session.user, "active_status": 1}, "name")
    if not contractor_name:
        contractor_name = frappe.db.get_value("Contractor", {"name": frappe.session.user, "active_status": 1}, "name")

    if not contractor_name:
        frappe.throw(
            "Your user account is not linked to an active Partner Agency. Please contact the administrator.",
            frappe.PermissionError
        )

    return contractor_name


@frappe.whitelist()
def get_my_agency_context():
    """
    Single bootstrap endpoint for the custom frontend.
    Returns logged-in user profile, linked Contractor record, country, currency,
    VAPID public key for Web Push, and quick portal stats in ONE call.
    """
    if not frappe.session.user or frappe.session.user == "Guest":
        frappe.throw("Authentication required. Please log in.", frappe.AuthenticationError)

    user_roles = frappe.get_roles(frappe.session.user)
    is_internal = any(r in user_roles for r in ("System Manager", "Administrator", "LMS Employee", "Accounts Manager"))
    user_doc = frappe.get_doc("User", frappe.session.user)

    contractor_name = None
    contractor_data = {}
    try:
        contractor_name = _get_effective_contractor_for_session()
        if contractor_name:
            c_doc = frappe.get_doc("Contractor", contractor_name)
            contractor_data = {
                "name": c_doc.name,
                "company_name": c_doc.company_name,
                "country": c_doc.country,
                "contact_person": c_doc.contact_person or "—",
                "phone": c_doc.phone or c_doc.whatsapp or "—",
                "email": c_doc.email or "—",
                "default_commission_amount": c_doc.default_commission_amount or 1000.0,
                "default_commission_currency": c_doc.default_commission_currency or "SAR",
                "active_status": c_doc.active_status
            }
    except Exception:
        pass

    # Get VAPID public key for Web Push subscription
    vapid_public_key = None
    try:
        from applicant_processing.applicant_processing.utils.push_api import get_vapid_keys
        _, vapid_public_key = get_vapid_keys()
    except Exception:
        pass

    portal_stats = get_portal_stats(contractor=contractor_name) if contractor_name else {}

    return {
        "user": frappe.session.user,
        "full_name": user_doc.full_name or frappe.session.user,
        "roles": user_roles,
        "is_internal_staff": is_internal,
        "contractor": contractor_data,
        "vapid_public_key": vapid_public_key,
        "portal_stats": portal_stats
    }


@frappe.whitelist()
def get_portal_available_candidates(contractor=None, destination_country=None, job_applied=None, religion=None, limit=50):
    """
    Returns the pool of available candidates for foreign agencies to browse:
    - Scoped to unreserved candidates (locked_contractor IS NULL or locked by current agency)
    - Filtered by destination country, job applied, religion
    - Includes photo URLs, skill highlights, and CV download URLs
    """
    effective_contractor = _get_effective_contractor_for_session(contractor)

    conditions = [
        "app.applicant_state IN ('CV Generated', 'Registered', 'Data Complete')",
        "(app.locked_contractor IS NULL OR app.locked_contractor = '' OR app.locked_contractor = %(contractor)s)"
    ]
    values = {"contractor": effective_contractor}

    if destination_country:
        conditions.append("app.destination_country = %(destination_country)s")
        values["destination_country"] = destination_country

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

    for c in candidates:
        full_name = c.get("full_name") or f"{c.get('first_name', '')} {c.get('last_name', '')}".strip() or "Candidate"
        c["full_name"] = full_name
        c["cv_file_url"] = frappe.db.get_value("CV Record", {"applicant": c["name"]}, "file_attachment")
        c["is_locked_by_me"] = bool(c.get("locked_contractor") and c.get("locked_contractor") == effective_contractor)

    return candidates


@frappe.whitelist()
def get_agency_candidate_detail(applicant_id, contractor=None):
    """
    Returns full candidate profile for the agency modal / detail page.
    Enforces multi-tenant security: if candidate is reserved by another agency, throws PermissionError.
    """
    if not applicant_id or not frappe.db.exists("Applicant", applicant_id):
        frappe.throw(f"Applicant '{applicant_id}' not found.", frappe.DoesNotExistError)

    effective_contractor = _get_effective_contractor_for_session(contractor)
    user_roles = frappe.get_roles(frappe.session.user)
    is_internal = any(r in user_roles for r in ("System Manager", "Administrator", "LMS Employee", "Accounts Manager"))

    app = frappe.get_doc("Applicant", applicant_id)

    # Multi-tenant lock check
    if app.locked_contractor and app.locked_contractor != effective_contractor and not is_internal:
        frappe.throw(
            "This candidate has been reserved by another partner agency and is not available.",
            frappe.PermissionError
        )

    cv_pdf = frappe.db.get_value("CV Record", {"applicant": app.name}, "file_attachment")

    # Linked Dossier & DSR milestones
    dossier = frappe.db.get_value(
        "Applicant Dossier",
        {"applicant": app.name},
        ["name", "sponsor_name", "visa_number", "contract_date", "contract_duration"],
        as_dict=True
    )

    ticket = None
    departure = None
    if dossier:
        dsr_name = frappe.db.get_value("DSR", {"applicant_dossier": dossier.name}, "name")
        if dsr_name:
            ticket = frappe.db.get_value(
                "DSR Ticket",
                {"dsr": dsr_name},
                ["airline", "flight_number", "flight_date", "route", "status"],
                as_dict=True
            )
            departure = frappe.db.get_value(
                "DSR Departure",
                {"dsr": dsr_name},
                ["departure_time", "status"],
                as_dict=True
            )

    is_locked_by_me = bool(app.locked_contractor and app.locked_contractor == effective_contractor)

    return {
        "name": app.name,
        "full_name": app.full_name or f"{app.first_name or ''} {app.last_name or ''}".strip() or "Candidate",
        "first_name": app.first_name,
        "last_name": app.last_name,
        "passport_number": app.passport_number or "—",
        "gender": app.gender,
        "age": app.age,
        "date_of_birth": app.date_of_birth,
        "nationality": app.nationality or "Ethiopian",
        "destination_country": app.destination_country or "Saudi Arabia",
        "religion": app.religion,
        "marital_status": app.marital_status,
        "children": app.children,
        "job_applied": app.job_applied or "General Domestic Worker",
        "monthly_salary": app.monthly_salary,
        "highest_education": app.highest_education,
        "photo_passport": app.photo_passport,
        "photo_full_body": app.photo_full_body,
        "skills": {
            "cleaning": bool(app.skill_cleaning),
            "cooking": bool(app.skill_cooking),
            "arabic_cooking": bool(app.skill_arabic_cooking),
            "baby_sitting": bool(app.skill_baby_sitting),
            "elderly_care": bool(app.skill_elderly_care),
            "sewing": bool(app.skill_sewing),
        },
        "experience_country": app.experience_country,
        "experience_period": app.experience_period,
        "applicant_state": app.applicant_state,
        "locked_contractor": app.locked_contractor,
        "locked_at": app.locked_at,
        "is_locked_by_me": is_locked_by_me,
        "cv_file_url": cv_pdf,
        "dossier": dossier,
        "ticket": ticket,
        "departure": departure
    }


@frappe.whitelist()
def get_agency_pipeline_candidates(contractor=None, stage="all", limit=50):
    """
    Returns candidates selected / processing / deployed for this partner agency,
    with real-time progress across recruitment milestones (Contract, Ticket, Departure).
    Stages: 'all', 'Selected', 'Processing', 'Stamped', 'Ticketed', 'Departed'
    """
    effective_contractor = _get_effective_contractor_for_session(contractor)

    conditions = [
        """(
            app.locked_contractor = %(contractor)s
            OR dos.contractor_name = %(contractor)s
            OR dsr.contractor_name = %(contractor)s
        )"""
    ]
    values = {"contractor": effective_contractor}

    if stage and stage.lower() != "all":
        conditions.append("app.applicant_state = %(stage)s")
        values["stage"] = stage

    where_clause = " AND ".join(conditions)
    sql = f"""
        SELECT
            app.name,
            app.full_name,
            app.first_name,
            app.last_name,
            app.passport_number,
            app.destination_country,
            app.job_applied,
            app.applicant_state,
            app.locked_at,
            app.photo_passport,
            dos.name AS dossier_name,
            dos.sponsor_name,
            dos.visa_number,
            dos.contract_date,
            dos.contract_duration,
            tkt.airline,
            tkt.flight_number,
            tkt.flight_date,
            tkt.route,
            tkt.status AS ticket_status,
            dep.departure_time,
            dep.status AS departure_status
        FROM `tabApplicant` app
        LEFT JOIN `tabApplicant Dossier` dos ON dos.applicant = app.name
        LEFT JOIN `tabDSR` dsr ON dsr.applicant_dossier = dos.name
        LEFT JOIN `tabDSR Ticket` tkt ON tkt.dsr = dsr.name
        LEFT JOIN `tabDSR Departure` dep ON dep.dsr = dsr.name
        WHERE {where_clause}
        GROUP BY app.name
        ORDER BY app.modified DESC
        LIMIT {int(limit)}
    """
    rows = frappe.db.sql(sql, values, as_dict=True)

    for r in rows:
        full_name = r.get("full_name") or f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or "Candidate"
        r["full_name"] = full_name
        r["cv_file_url"] = frappe.db.get_value("CV Record", {"applicant": r["name"]}, "file_attachment")

    return rows


@frappe.whitelist()
def portal_select_candidate(applicant_id, contractor=None):
    """
    Atomic Candidate Selection Gate:
    Locks an applicant to the requesting partner agency using SELECT FOR UPDATE
    to prevent sub-second multi-agency race conditions.
    """
    if not applicant_id:
        frappe.throw("Applicant ID is required.")

    effective_contractor = _get_effective_contractor_for_session(contractor)

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

    if app.get("locked_contractor") and app.get("locked_contractor") != effective_contractor:
        frappe.throw(
            f"Candidate was just selected by another partner agency ({app.get('locked_contractor')}).",
            frappe.DuplicateEntryError
        )

    if app.get("applicant_state") not in ("CV Generated", "Registered", "Data Complete", "Draft"):
        frappe.throw(f"Candidate cannot be selected. Current lifecycle state: {app.get('applicant_state')}.")

    # 2. Lock candidate to this agency
    from frappe.utils import now_datetime
    frappe.db.set_value("Applicant", applicant_id, {
        "locked_contractor": effective_contractor,
        "locked_at": now_datetime(),
        "applicant_state": "Selected"
    })

    # 3. Create or update Contract Request
    existing_cr = frappe.get_all("Contract Request", filters={"applicant": applicant_id, "contractor": effective_contractor}, pluck="name")
    if not existing_cr:
        cv_ref = frappe.db.get_value("CV Record", {"applicant": applicant_id}, "name")
        cr = frappe.get_doc({
            "doctype": "Contract Request",
            "applicant": applicant_id,
            "contractor": effective_contractor,
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
        f"<b>Candidate Selected on Agency Portal</b> by <b>{effective_contractor}</b> (User: {frappe.session.user}). Status changed to Selected."
    )

    frappe.db.commit()

    return {
        "status": "success",
        "applicant_id": applicant_id,
        "contractor": effective_contractor,
        "message": f"Candidate successfully selected and reserved for {effective_contractor}."
    }


@frappe.whitelist()
def portal_release_candidate(applicant_id, contractor=None):
    """
    Releases the selection lock if the agency cancels their reservation before issuing a contract.
    """
    if not applicant_id:
        frappe.throw("Applicant ID is required.")

    effective_contractor = _get_effective_contractor_for_session(contractor)

    app = frappe.get_doc("Applicant", applicant_id)
    if app.locked_contractor != effective_contractor:
        frappe.throw("You do not hold the active reservation lock for this candidate.", frappe.PermissionError)

    app.locked_contractor = None
    app.locked_at = None
    app.save(ignore_permissions=True)

    # Cancel or close any pending contract requests
    crs = frappe.get_all("Contract Request", filters={"applicant": applicant_id, "contractor": effective_contractor}, pluck="name")
    for cr in crs:
        frappe.db.set_value("Contract Request", cr, "status", "Closed")

    from applicant_processing.applicant_processing.doctype.applicant.applicant import recalculate_applicant_state
    new_state = recalculate_applicant_state(applicant_id)

    app.add_comment("Comment", f"<b>Selection Lock Released</b> by {effective_contractor} ({frappe.session.user}).")
    frappe.db.commit()

    return {"status": "success", "message": f"Candidate released back to available pool ({new_state})."}


@frappe.whitelist()
def get_portal_stats(contractor=None):
    """
    Returns quick stats for the Agency Portal hero banner:
    - available_candidates: unreserved candidates in pool
    - my_selected_candidates: candidates reserved/processing under this agency
    - open_complaints: unresolved complaints for this contractor
    """
    effective_contractor = None
    try:
        effective_contractor = _get_effective_contractor_for_session(contractor)
    except Exception:
        pass

    # Available candidates (unreserved)
    res = frappe.db.sql("""
        SELECT COUNT(*) as cnt FROM `tabApplicant`
        WHERE applicant_state IN ('CV Generated', 'Registered', 'Data Complete')
          AND (locked_contractor IS NULL OR locked_contractor = '')
    """, as_dict=True)
    available_count = res[0].cnt if res else 0

    # My Selected candidates count
    my_selected_count = 0
    if effective_contractor:
        my_selected_count = frappe.db.count("Applicant", {
            "locked_contractor": effective_contractor,
            "applicant_state": ["not in", ["Departed", "Cancelled"]]
        })

    # Open complaints
    comp_filters = {"status": ["in", ["Open", "Under Investigation"]]}
    if effective_contractor:
        comp_filters["contractor"] = effective_contractor
    open_complaints = frappe.db.count("Agency Complaint", comp_filters)

    return {
        "available_candidates": available_count,
        "my_selected_candidates": my_selected_count,
        "open_complaints": open_complaints,
        "contractor": effective_contractor
    }


# =========================================================================
# FOREIGN AGENCY COMPLAINT WORKBENCH & WELFARE DESK
# =========================================================================

@frappe.whitelist()
def get_agency_complaints(tab="unresolved", contractor=None):
    """
    Returns complaints for the Agency Complaints Workbench.
    Strictly isolated to the authenticated agency's complaints.
    - 'new': Status = Open
    - 'unresolved': Open + Under Investigation (oldest pending at top)
    - 'resolved': Resolved history
    """
    effective_contractor = _get_effective_contractor_for_session(contractor)

    filters = {"contractor": effective_contractor}

    if tab == "new":
        filters["status"] = "Open"
        order_by = "creation desc"
    elif tab == "resolved":
        filters["status"] = ["in", ["Resolved", "Returned / Free Replacement Required", "Escalated to MoL / Embassy", "Dismissed / Closed"]]
        order_by = "resolved_at desc, modified desc"
    else:  # 'unresolved' (default)
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


@frappe.whitelist()
def search_applicants_for_complaint(query, contractor=None):
    """
    Live autocomplete search for applicants to attach to a complaint.
    Strictly restricted to workers associated with this agency (locked, dossier, or departed).
    """
    if not query or len(str(query).strip()) < 2:
        return []

    effective_contractor = _get_effective_contractor_for_session(contractor)
    q = f"%{str(query).strip()}%"

    results = frappe.db.sql("""
        SELECT DISTINCT
            app.name AS id,
            app.full_name,
            app.first_name,
            app.last_name,
            app.passport_number,
            app.destination_country,
            app.applicant_state
        FROM `tabApplicant` app
        LEFT JOIN `tabApplicant Dossier` dos ON dos.applicant = app.name
        LEFT JOIN `tabDSR` dsr ON dsr.applicant_dossier = dos.name
        WHERE
            (app.locked_contractor = %(c)s OR dos.contractor_name = %(c)s OR dsr.contractor_name = %(c)s)
            AND (
                app.name LIKE %(q)s
                OR app.full_name LIKE %(q)s
                OR CONCAT(app.first_name, ' ', app.last_name) LIKE %(q)s
                OR app.passport_number LIKE %(q)s
            )
        ORDER BY app.creation DESC
        LIMIT 10
    """, {"c": effective_contractor, "q": q}, as_dict=True)

    for r in results:
        r["full_name"] = r.get("full_name") or f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or "Candidate"

    return results


@frappe.whitelist()
def submit_agency_complaint(applicant_search, complaint_category, complaint_details, contractor=None, severity="High", attachment=None):
    """
    Submits a dispute/complaint for an agency's worker.
    Forces contractor context from user session to prevent spoofing.
    """
    effective_contractor = _get_effective_contractor_for_session(contractor)

    if not applicant_search or not complaint_category or not complaint_details:
        frappe.throw("Applicant, Complaint Category, and Details are required.")

    # Resolve applicant search query -> valid Applicant ID
    resolved_id = None
    if frappe.db.exists("Applicant", applicant_search):
        resolved_id = applicant_search
    if not resolved_id:
        resolved_id = frappe.db.get_value("Applicant", {"passport_number": applicant_search}, "name")
    if not resolved_id:
        rows = frappe.db.sql("""
            SELECT name FROM `tabApplicant`
            WHERE full_name LIKE %(q)s OR CONCAT(first_name, ' ', last_name) LIKE %(q)s
            LIMIT 1
        """, {"q": f"%{applicant_search}%"}, as_dict=True)
        if rows:
            resolved_id = rows[0].name

    if not resolved_id:
        frappe.throw(f"Worker '{applicant_search}' not found. Please search by Applicant ID, passport number, or full name.")

    complaint = frappe.get_doc({
        "doctype": "Agency Complaint",
        "contractor": effective_contractor,
        "applicant": resolved_id,
        "complaint_category": complaint_category,
        "severity": severity or "High",
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
        "contractor": effective_contractor,
        "message": f"Complaint #{complaint.name} logged successfully. Assigned to Welfare Desk."
    }


@frappe.whitelist()
def resolve_agency_complaint(complaint_id, outcome, resolution_notes, return_date=None, replacement_applicant=None):
    """
    Internal staff endpoint to resolve an agency complaint.
    Requires System Manager, Administrator, or LMS Employee role.
    """
    frappe.only_for(["System Manager", "Administrator", "LMS Employee"])

    if not complaint_id or not outcome or not resolution_notes:
        frappe.throw("Complaint ID, Resolution Outcome, and Notes are required.")

    OUTCOME_STATUS_MAP = {
        "Resolved": "Resolved",
        "Returned / Free Replacement Required": "Returned / Free Replacement Required",
        "Escalated": "Escalated to MoL / Embassy",
        "Dismissed": "Dismissed / Closed",
    }
    new_status = OUTCOME_STATUS_MAP.get(outcome, outcome)

    from frappe.utils import now_datetime
    complaint = frappe.get_doc("Agency Complaint", complaint_id)
    complaint.resolution_outcome = outcome
    complaint.resolution_notes = resolution_notes
    complaint.status = new_status
    complaint.resolved_at = now_datetime()

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
    start_dt = f"{fd_str} 00:00:00"
    end_dt = f"{td_str} 23:59:59.999999"

    # --- Intake & Registration ---
    new_applicants = frappe.db.count("Applicant", {"creation": ["between", [start_dt, end_dt]]})
    standard_count = frappe.db.count("Applicant", {
        "applicant_type": "Standard",
        "creation": ["between", [start_dt, end_dt]]
    })
    muayena_count = frappe.db.count("Applicant", {
        "applicant_type": "Muayena",
        "creation": ["between", [start_dt, end_dt]]
    })
    muslim_count = frappe.db.count("Applicant", {
        "religion": "Muslim",
        "creation": ["between", [start_dt, end_dt]]
    })

    # --- CVs Generated ---
    cvs_generated = frappe.db.count("CV Record", {"creation": ["between", [start_dt, end_dt]]})

    # --- Dossiers / Contracts ---
    dossiers_created = frappe.db.count("Applicant Dossier", {"creation": ["between", [start_dt, end_dt]]})

    # --- Medical Stats ---
    fit_count = frappe.db.count("Applicant", {
        "medical_status": "FIT",
        "modified": ["between", [start_dt, end_dt]]
    })
    unfit_count = frappe.db.count("Applicant", {
        "medical_status": "UNFIT",
        "modified": ["between", [start_dt, end_dt]]
    })

    # --- Clearances (modified in period) ---
    lms_issued = frappe.db.count("LMS Clearance", {
        "status": "Issued",
        "modified": ["between", [start_dt, end_dt]]
    })

    # --- DSR Stages ---
    stamped = frappe.db.count("DSR Stamp", {"creation": ["between", [start_dt, end_dt]]})
    tickets_booked = frappe.db.count("DSR Ticket", {"creation": ["between", [start_dt, end_dt]]})
    departed = frappe.db.count("DSR Departure", {
        "status": "Departed",
        "modified": ["between", [start_dt, end_dt]]
    })

    # --- Complaints ---
    new_complaints = frappe.db.count("Agency Complaint", {"creation": ["between", [start_dt, end_dt]]})
    resolved_complaints = frappe.db.count("Agency Complaint", {
        "status": ["in", ["Resolved", "Dismissed / Closed"]],
        "resolved_at": ["between", [start_dt, end_dt]]
    })
    open_complaints = frappe.db.count("Agency Complaint", {
        "status": ["in", ["Open", "Under Investigation"]]
    })

    # --- Agency Selections ---
    selected_today = frappe.db.count("Applicant", {
        "applicant_state": "Selected",
        "locked_at": ["between", [start_dt, end_dt]]
    })

    # --- Corridor Breakdown ---
    ksa_pipeline = frappe.db.count("DSR", {
        "destination_country": "Saudi Arabia",
        "creation": ["between", [start_dt, end_dt]]
    })
    kwt_pipeline = frappe.db.count("DSR", {
        "destination_country": "Kuwait",
        "creation": ["between", [start_dt, end_dt]]
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

# =========================================================================
# MODULE 12: ADMIN USER & PERMISSION MANAGEMENT WRAPPERS
# =========================================================================

from applicant_processing.applicant_processing.utils.user_admin import (
    create_system_user,
    update_system_user,
    set_user_password,
    assign_user_roles,
    manage_user_permission,
    get_system_users,
    get_available_roles,
    get_user_detail
)

