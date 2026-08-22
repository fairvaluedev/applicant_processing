# Copyright (c) 2026, Admin and contributors
# For license information, please see license.txt

import io
import json
import csv
import frappe
from frappe.utils import getdate, today, now_datetime, formatdate, flt


def get_unpaid_commission_data(contractor, limit=30, from_date=None, to_date=None, applicant_ids=None):
    """
    Fetches departed applicants for a specific foreign recruitment agency whose
    commission has not been marked as Paid.
    """
    if not contractor or not frappe.db.exists("Contractor", contractor):
        frappe.throw(f"Contractor / Agency '{contractor}' not found.", frappe.DoesNotExistError)

    contractor_doc = frappe.get_doc("Contractor", contractor)
    default_rate = flt(getattr(contractor_doc, "default_commission_amount", 1000.0) or 1000.0)
    currency = getattr(contractor_doc, "default_commission_currency", "SAR") or "SAR"

    conditions = [
        """(
            app.locked_contractor = %(contractor)s
            OR dos.contractor_name = %(contractor)s
            OR dsr.contractor_name = %(contractor)s
        )""",
        """(
            app.applicant_state = 'Departed'
            OR dep.status = 'Departed'
            OR dsr.departure_status = 'Departed'
        )""",
        """(
            app.commission_status IS NULL
            OR app.commission_status = ''
            OR app.commission_status = 'Unpaid'
        )"""
    ]
    values = {"contractor": contractor}

    if applicant_ids:
        if isinstance(applicant_ids, str):
            try:
                applicant_ids = json.loads(applicant_ids)
            except Exception:
                applicant_ids = [a.strip() for a in applicant_ids.split(",") if a.strip()]
        if applicant_ids:
            conditions.append("app.name IN %(applicant_ids)s")
            values["applicant_ids"] = tuple(applicant_ids)

    if from_date:
        conditions.append("DATE(COALESCE(dep.departure_time, dep.modified, app.modified)) >= %(from_date)s")
        values["from_date"] = str(getdate(from_date))

    if to_date:
        conditions.append("DATE(COALESCE(dep.departure_time, dep.modified, app.modified)) <= %(to_date)s")
        values["to_date"] = str(getdate(to_date))

    where_clause = " AND ".join(conditions)

    limit_clause = ""
    if limit and str(limit).lower() not in ("all", "0", "none"):
        try:
            limit_int = int(limit)
            if limit_int > 0:
                limit_clause = f"LIMIT {limit_int}"
        except Exception:
            pass

    sql = f"""
        SELECT DISTINCT
            app.name,
            app.full_name,
            app.first_name,
            app.last_name,
            app.passport_number,
            app.destination_country,
            app.job_applied,
            app.phone_number,
            app.applicant_state,
            app.commission_status,
            app.commission_amount,
            COALESCE(dep.departure_time, dep.modified, app.modified) AS departure_date,
            dos.sponsor_name,
            dos.visa_number
        FROM `tabApplicant` app
        LEFT JOIN `tabApplicant Dossier` dos ON dos.applicant = app.name
        LEFT JOIN `tabDSR` dsr ON dsr.applicant_dossier = dos.name
        LEFT JOIN `tabDSR Departure` dep ON dep.dsr = dsr.name
        WHERE {where_clause}
        ORDER BY departure_date DESC, app.creation DESC
        {limit_clause}
    """

    raw_candidates = frappe.db.sql(sql, values, as_dict=True)

    candidates = []
    total_amount = 0.0

    for idx, c in enumerate(raw_candidates, 1):
        rate = flt(c.get("commission_amount")) if c.get("commission_amount") else default_rate
        total_amount += rate

        dep_dt = c.get("departure_date")
        dep_str = ""
        if dep_dt:
            try:
                dep_str = formatdate(dep_dt, "yyyy-mm-dd")
            except Exception:
                dep_str = str(dep_dt)[:10]

        candidates.append({
            "idx": idx,
            "name": c.get("name"),
            "full_name": c.get("full_name") or f"{c.get('first_name', '')} {c.get('last_name', '')}".strip() or "Candidate",
            "passport_number": c.get("passport_number") or "-",
            "destination_country": c.get("destination_country") or contractor_doc.country or "Saudi Arabia",
            "job_applied": c.get("job_applied") or "General Domestic Worker",
            "phone_number": c.get("phone_number") or "-",
            "sponsor_name": c.get("sponsor_name") or "-",
            "visa_number": c.get("visa_number") or "-",
            "departure_date": dep_str,
            "commission_rate": rate,
            "commission_currency": currency,
            "commission_status": "Unpaid"
        })

    summary = {
        "contractor": contractor,
        "company_name": contractor_doc.company_name,
        "country": contractor_doc.country,
        "contact_person": contractor_doc.contact_person or "-",
        "phone": contractor_doc.phone or contractor_doc.whatsapp or "-",
        "email": contractor_doc.email or "-",
        "default_rate": default_rate,
        "currency": currency,
        "total_count": len(candidates),
        "total_amount": total_amount,
        "generated_on": formatdate(today(), "yyyy-mm-dd"),
        "batch_label": f"Last {len(candidates)}" if limit and str(limit).lower() != "all" else f"All ({len(candidates)})"
    }

    return summary, candidates


def build_commission_excel(summary, candidates):
    """
    Generates a professionally styled Excel workbook (.xlsx) using openpyxl,
    with fallback to UTF-8 CSV if openpyxl is not installed.
    """
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Unpaid Commission Statement"
        ws.views.sheetView[0].showGridLines = True

        # Palettes
        NAVY_FILL = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        LIGHT_FILL = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
        ALT_FILL = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        HEADER_FILL = PatternFill(start_color="0F766E", end_color="0F766E", fill_type="solid")
        ACCENT_FILL = PatternFill(start_color="E0F2FE", end_color="E0F2FE", fill_type="solid")

        FONT_TITLE = Font(name="Calibri", size=16, bold=True, color="FFFFFF")
        FONT_HEADER = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        FONT_BOLD = Font(name="Calibri", size=11, bold=True, color="0F172A")
        FONT_REGULAR = Font(name="Calibri", size=10, color="1E293B")
        FONT_MUTED = Font(name="Calibri", size=10, color="64748B")
        FONT_TOTAL = Font(name="Calibri", size=12, bold=True, color="0F766E")

        THIN_BORDER = Border(
            left=Side(style="thin", color="CBD5E1"),
            right=Side(style="thin", color="CBD5E1"),
            top=Side(style="thin", color="CBD5E1"),
            bottom=Side(style="thin", color="CBD5E1")
        )

        # Row 1-2: Header Banner
        ws.merge_cells("A1:K2")
        title_cell = ws["A1"]
        title_cell.value = f"AGENCY COMMISSION BILLING STATEMENT — {summary['company_name'].upper()}"
        title_cell.font = FONT_TITLE
        title_cell.fill = NAVY_FILL
        title_cell.alignment = Alignment(horizontal="center", vertical="center")

        # Rows 4-6: Agency Metadata Card
        ws["A4"] = "Partner Agency:"
        ws["B4"] = summary["company_name"]
        ws["D4"] = "Corridor / Country:"
        ws["E4"] = summary["country"]
        ws["G4"] = "Statement Date:"
        ws["H4"] = summary["generated_on"]

        ws["A5"] = "Contact Person:"
        ws["B5"] = summary["contact_person"]
        ws["D5"] = "Contact Phone:"
        ws["E5"] = summary["phone"]
        ws["G5"] = "Batch Scope:"
        ws["H5"] = summary["batch_label"]

        ws["A6"] = "Default Rate / Candidate:"
        ws["B6"] = f"{summary['default_rate']:,.2f} {summary['currency']}"
        ws["D6"] = "Unpaid Candidates:"
        ws["E6"] = summary["total_count"]
        ws["G6"] = "Total Outstanding:"
        ws["H6"] = f"{summary['total_amount']:,.2f} {summary['currency']}"

        for r in range(4, 7):
            for c in ["A", "D", "G"]:
                ws[f"{c}{r}"].font = FONT_BOLD
                ws[f"{c}{r}"].fill = ACCENT_FILL
            for c in ["B", "E", "H"]:
                ws[f"{c}{r}"].font = FONT_REGULAR

        # Row 8: Table Header
        headers = [
            "Item #", "Applicant ID", "Candidate Name", "Passport No",
            "Destination", "Job Position", "Departure Date",
            "Employer / Sponsor", "Visa Number", "Commission Amount", "Payment Status"
        ]

        start_row = 8
        for col_num, h_text in enumerate(headers, 1):
            cell = ws.cell(row=start_row, column=col_num)
            cell.value = h_text
            cell.font = FONT_HEADER
            cell.fill = HEADER_FILL
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = THIN_BORDER

        # Data Rows
        cur_row = start_row + 1
        for cand in candidates:
            fill_style = ALT_FILL if cur_row % 2 == 0 else LIGHT_FILL
            row_vals = [
                cand["idx"],
                cand["name"],
                cand["full_name"],
                cand["passport_number"],
                cand["destination_country"],
                cand["job_applied"],
                cand["departure_date"],
                cand["sponsor_name"],
                cand["visa_number"],
                cand["commission_rate"],
                cand["commission_status"]
            ]

            for col_idx, val in enumerate(row_vals, 1):
                c_cell = ws.cell(row=cur_row, column=col_idx)
                c_cell.value = val
                c_cell.font = FONT_REGULAR
                c_cell.fill = fill_style
                c_cell.border = THIN_BORDER

                if col_idx in (1, 2, 4, 7, 9, 11):
                    c_cell.alignment = Alignment(horizontal="center")
                elif col_idx == 10:
                    c_cell.alignment = Alignment(horizontal="right")
                    c_cell.number_format = "#,##0.00"

            cur_row += 1

        # Total Row
        total_row = cur_row
        ws.merge_cells(start_row=total_row, start_column=1, end_row=total_row, end_column=9)
        t_label = ws.cell(row=total_row, column=1)
        t_label.value = f"TOTAL OUTSTANDING COMMISSION PAYABLE ({summary['total_count']} CANDIDATES):"
        t_label.font = FONT_BOLD
        t_label.fill = ACCENT_FILL
        t_label.alignment = Alignment(horizontal="right", vertical="center")

        t_val = ws.cell(row=total_row, column=10)
        t_val.value = summary["total_amount"]
        t_val.font = FONT_TOTAL
        t_val.fill = ACCENT_FILL
        t_val.alignment = Alignment(horizontal="right", vertical="center")
        t_val.number_format = f"#,##0.00 \"{summary['currency']}\""

        t_stat = ws.cell(row=total_row, column=11)
        t_stat.value = "UNPAID"
        t_stat.font = FONT_BOLD
        t_stat.fill = ACCENT_FILL
        t_stat.alignment = Alignment(horizontal="center", vertical="center")

        for col_idx in range(1, 12):
            ws.cell(row=total_row, column=col_idx).border = THIN_BORDER

        # Auto-fit Column Widths
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                if cell.row in (1, 2):  # skip header banner
                    continue
                v_str = str(cell.value or "")
                max_len = max(max_len, len(v_str))
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"

    except Exception:
        # Robust CSV Fallback
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([f"AGENCY COMMISSION BILLING STATEMENT - {summary['company_name']}"])
        writer.writerow(["Statement Date", summary["generated_on"], "Country", summary["country"]])
        writer.writerow(["Default Rate", f"{summary['default_rate']} {summary['currency']}", "Total Candidates", summary["total_count"], "Total Amount", f"{summary['total_amount']} {summary['currency']}"])
        writer.writerow([])
        writer.writerow(["Item #", "Applicant ID", "Candidate Name", "Passport No", "Destination", "Position", "Departure Date", "Sponsor", "Visa No", f"Commission ({summary['currency']})", "Status"])

        for cand in candidates:
            writer.writerow([
                cand["idx"], cand["name"], cand["full_name"], cand["passport_number"],
                cand["destination_country"], cand["job_applied"], cand["departure_date"],
                cand["sponsor_name"], cand["visa_number"], cand["commission_rate"], cand["commission_status"]
            ])

        writer.writerow([])
        writer.writerow(["TOTAL", "", "", "", "", "", "", "", "", summary["total_amount"], "UNPAID"])

        return buf.getvalue().encode("utf-8-sig"), "text/csv", "csv"


def build_commission_pdf(summary, candidates):
    """
    Renders an executive PDF Billing Statement with company header, candidate table,
    currency calculation, and payment authorization block.
    """
    from frappe.utils.pdf import get_pdf

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{
                size: A4 portrait;
                margin: 12mm 15mm 15mm 15mm;
            }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                font-size: 11px;
                color: #0f172a;
                line-height: 1.4;
                margin: 0;
            }}
            .header-table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 18px;
                border-bottom: 2px solid #0f766e;
                padding-bottom: 12px;
            }}
            .brand-title {{
                font-size: 18px;
                font-weight: 800;
                color: #0f766e;
                letter-spacing: -0.02em;
                margin: 0 0 4px 0;
            }}
            .brand-subtitle {{
                font-size: 11px;
                color: #64748b;
                margin: 0;
            }}
            .statement-badge {{
                background: #0f766e;
                color: #ffffff;
                padding: 6px 12px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 700;
                text-align: right;
                display: inline-block;
            }}
            .kpi-container {{
                display: table;
                width: 100%;
                margin-bottom: 18px;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                background: #f8fafc;
            }}
            .kpi-col {{
                display: table-cell;
                padding: 10px 14px;
                border-right: 1px solid #e2e8f0;
                vertical-align: top;
            }}
            .kpi-col:last-child {{
                border-right: none;
                background: #f0fdf4;
            }}
            .kpi-label {{
                font-size: 9px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                color: #64748b;
                margin-bottom: 3px;
            }}
            .kpi-val {{
                font-size: 13px;
                font-weight: 800;
                color: #0f172a;
            }}
            .kpi-total-val {{
                font-size: 15px;
                font-weight: 800;
                color: #047857;
            }}
            table.data-table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 16px;
            }}
            table.data-table th {{
                background: #1e293b;
                color: #ffffff;
                font-size: 9px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.04em;
                padding: 7px 6px;
                border: 1px solid #1e293b;
                text-align: left;
            }}
            table.data-table td {{
                padding: 6px 6px;
                font-size: 10px;
                border: 1px solid #e2e8f0;
            }}
            table.data-table tr:nth-child(even) {{
                background: #f8fafc;
            }}
            .text-center {{ text-align: center; }}
            .text-right {{ text-align: right; }}
            .font-bold {{ font-weight: 700; }}
            .badge-unpaid {{
                background: #fef2f2;
                color: #b91c1c;
                padding: 2px 6px;
                border-radius: 4px;
                font-weight: 700;
                font-size: 9px;
                display: inline-block;
            }}
            .total-box {{
                background: #f0fdf4;
                border: 1px solid #86efac;
                padding: 10px 14px;
                border-radius: 6px;
                margin-bottom: 20px;
                display: flex;
                justify-content: space-between;
            }}
            .footer-sign {{
                margin-top: 30px;
                width: 100%;
                display: table;
            }}
            .sign-box {{
                display: table-cell;
                width: 48%;
                border-top: 1px solid #94a3b8;
                padding-top: 6px;
                font-size: 10px;
                color: #475569;
            }}
        </style>
    </head>
    <body>
        <table class="header-table">
            <tr>
                <td style="vertical-align: middle;">
                    <div class="brand-title">AGENCY RECRUITMENT COMMISSION STATEMENT</div>
                    <div class="brand-subtitle">Automated Deployment & Commission Billing Engine</div>
                </td>
                <td style="text-align: right; vertical-align: middle;">
                    <div class="statement-badge">INVOICE STATEMENT</div>
                    <div style="font-size: 10px; color: #64748b; margin-top: 4px;">Date: {summary['generated_on']}</div>
                </td>
            </tr>
        </table>

        <div class="kpi-container">
            <div class="kpi-col" style="width: 32%;">
                <div class="kpi-label">Partner Agency (Debtor)</div>
                <div class="kpi-val">{summary['company_name']}</div>
                <div style="font-size: 9px; color: #64748b;">{summary['country']} | Attn: {summary['contact_person']}</div>
            </div>
            <div class="kpi-col" style="width: 22%;">
                <div class="kpi-label">Rate / Candidate</div>
                <div class="kpi-val">{summary['default_rate']:,.2f} {summary['currency']}</div>
                <div style="font-size: 9px; color: #64748b;">Batch: {summary['batch_label']}</div>
            </div>
            <div class="kpi-col" style="width: 20%;">
                <div class="kpi-label">Departed Workers</div>
                <div class="kpi-val">{summary['total_count']} Candidates</div>
                <div style="font-size: 9px; color: #b91c1c; font-weight: 700;">Payment: UNPAID</div>
            </div>
            <div class="kpi-col" style="width: 26%;">
                <div class="kpi-label">Total Commission Payable</div>
                <div class="kpi-total-val">{summary['total_amount']:,.2f} {summary['currency']}</div>
                <div style="font-size: 9px; color: #047857;">Due upon statement receipt</div>
            </div>
        </div>

        <table class="data-table">
            <thead>
                <tr>
                    <th style="width: 5%;" class="text-center">#</th>
                    <th style="width: 14%;">Candidate ID</th>
                    <th style="width: 20%;">Full Name</th>
                    <th style="width: 12%;">Passport No</th>
                    <th style="width: 12%;">Job Position</th>
                    <th style="width: 11%;" class="text-center">Departed</th>
                    <th style="width: 14%;">Sponsor / Visa</th>
                    <th style="width: 12%;" class="text-right">Commission</th>
                </tr>
            </thead>
            <tbody>
    """

    for cand in candidates:
        html += f"""
                <tr>
                    <td class="text-center font-bold">{cand['idx']}</td>
                    <td class="font-bold">{cand['name']}</td>
                    <td>{cand['full_name']}</td>
                    <td>{cand['passport_number']}</td>
                    <td>{cand['job_applied']}</td>
                    <td class="text-center">{cand['departure_date']}</td>
                    <td>{cand['sponsor_name']}</td>
                    <td class="text-right font-bold">{cand['commission_rate']:,.2f} {cand['commission_currency']}</td>
                </tr>
        """

    html += f"""
                <tr style="background: #e0f2fe; font-weight: 800;">
                    <td colspan="7" class="text-right" style="padding: 8px;">TOTAL OUTSTANDING COMMISSION ({summary['total_count']} CANDIDATES):</td>
                    <td class="text-right" style="padding: 8px; color: #047857; font-size: 11px;">{summary['total_amount']:,.2f} {summary['currency']}</td>
                </tr>
            </tbody>
        </table>

        <div style="font-size: 9px; color: #64748b; margin-top: 10px; line-height: 1.4;">
            <b>Notice:</b> This statement covers deployed workers who have departed origin airport under <b>{summary['company_name']}</b> quota. Commission is calculated based on the agreed rate of {summary['default_rate']:,.2f} {summary['currency']} per deployed candidate.
        </div>

        <table class="footer-sign">
            <tr>
                <td class="sign-box">
                    <b>Prepared By:</b> Finance & Accounts Department<br>
                    Applicant Processing System
                </td>
                <td style="width: 4%;"></td>
                <td class="sign-box" style="text-align: right;">
                    <b>Approved By (Agency Representative):</b><br>
                    {summary['company_name']}
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    pdf_bytes = get_pdf(html, options={"page-size": "A4", "orientation": "Portrait", "margin-top": "12mm", "margin-bottom": "12mm"})
    return pdf_bytes, "application/pdf", "pdf"


# ─────────────────────────────────────────────────────────────────────────────
# Whitelisted RPC Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_unpaid_commission_summary(contractor):
    """
    Returns quick stats and candidate count for the contractor commission dialog.
    """
    summary, candidates = get_unpaid_commission_data(contractor, limit="all")
    return {
        "summary": summary,
        "sample_candidates": candidates[:10]
    }


@frappe.whitelist()
def get_unpaid_commission_candidates_list(contractor, limit=30, from_date=None, to_date=None):
    """
    Returns paginated / batch candidates list for table preview in Desk.
    """
    summary, candidates = get_unpaid_commission_data(contractor, limit=limit, from_date=from_date, to_date=to_date)
    return {
        "summary": summary,
        "candidates": candidates
    }


@frappe.whitelist()
def export_unpaid_commission_report(contractor, export_format="excel", limit=30, from_date=None, to_date=None, applicant_ids=None):
    """
    Generates and downloads the Excel (.xlsx) or PDF (.pdf) billing report.
    Directly streams file binary back to browser.
    """
    summary, candidates = get_unpaid_commission_data(
        contractor=contractor,
        limit=limit,
        from_date=from_date,
        to_date=to_date,
        applicant_ids=applicant_ids
    )

    clean_name = contractor.replace(" ", "_").replace("/", "-")
    batch_tag = f"Last_{len(candidates)}" if limit and str(limit).lower() != "all" else "All"
    date_tag = today().replace("-", "")

    if str(export_format).lower() in ("pdf", "invoice"):
        content, mime_type, ext = build_commission_pdf(summary, candidates)
        filename = f"Commission_Statement_{clean_name}_{batch_tag}_{date_tag}.pdf"
    else:
        content, mime_type, ext = build_commission_excel(summary, candidates)
        filename = f"Commission_Statement_{clean_name}_{batch_tag}_{date_tag}.{ext}"

    frappe.response["type"] = "binary"
    frappe.response["filename"] = filename
    frappe.response["filecontent"] = content


@frappe.whitelist()
def mark_commissions_as_paid(contractor, applicant_ids=None, reference=None, payment_date=None, limit=30):
    """
    Marks the exported batch (or specified applicant_ids) as Paid in Applicant records
    and auto-posts an Income Expense Log entry for financial audit reconciliation.
    """
    if not applicant_ids:
        # Fetch matching unpaid candidate names up to limit
        _, candidates = get_unpaid_commission_data(contractor, limit=limit)
        applicant_ids = [c["name"] for c in candidates]
    elif isinstance(applicant_ids, str):
        try:
            applicant_ids = json.loads(applicant_ids)
        except Exception:
            applicant_ids = [a.strip() for a in applicant_ids.split(",") if a.strip()]

    if not applicant_ids:
        return {"status": "warning", "message": "No eligible unpaid candidates found to mark as Paid."}

    pay_date = payment_date or today()
    ref_str = reference or f"BATCH-PAY-{today()}"

    contractor_doc = frappe.get_doc("Contractor", contractor)
    default_rate = flt(getattr(contractor_doc, "default_commission_amount", 1000.0) or 1000.0)
    currency = getattr(contractor_doc, "default_commission_currency", "SAR") or "SAR"

    updated_count = 0
    total_paid_amount = 0.0

    for app_id in applicant_ids:
        if frappe.db.exists("Applicant", app_id):
            app = frappe.get_doc("Applicant", app_id)
            rate = flt(app.commission_amount) if app.commission_amount else default_rate

            app.commission_status = "Paid"
            app.commission_amount = rate
            app.commission_paid_date = pay_date
            app.commission_batch_ref = ref_str

            # Add an accounting log entry if not already present
            existing_income = any(
                row.transaction_type == "Income" and ref_str in (row.description or "")
                for row in (app.income_expense_logs or [])
            )

            if not existing_income:
                app.append("income_expense_logs", {
                    "transaction_type": "Income",
                    "amount": rate,
                    "date": pay_date,
                    "description": f"Agency Commission Received: {contractor} (Ref: {ref_str})",
                    "source_doctype": "Contractor Commission Batch"
                })

            app.save(ignore_permissions=True)
            updated_count += 1
            total_paid_amount += rate

    frappe.db.commit()

    return {
        "status": "success",
        "updated_count": updated_count,
        "total_amount": total_paid_amount,
        "currency": currency,
        "reference": ref_str,
        "message": f"Successfully marked {updated_count} candidates as Paid ({total_paid_amount:,.2f} {currency}). Reference: {ref_str}"
    }
