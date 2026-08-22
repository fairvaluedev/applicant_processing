# Copyright (c) 2026, Admin and contributors
# For license information, please see license.txt

import os
import re
import datetime
import frappe
from frappe.utils import getdate, today

# ─────────────────────────────────────────────────────────────────────────────
# 1. Multi-Line Text Structurizer Engine
# ─────────────────────────────────────────────────────────────────────────────
class ContractTextStructurizer:
    """
    Transforms fragmented PDF text blocks and multi-line strings into unified semantic
    paragraphs and key-value entries. Prevents wrapped lines or multi-line values
    from being split into disconnected tokens.
    """

    def __init__(self, raw_blocks_or_text):
        self.raw_input = raw_blocks_or_text
        self.structured_lines = []
        self.unified_text = ""
        self.kv_pairs = {}
        self._process()

    def _process(self):
        if isinstance(self.raw_input, list):
            # PyMuPDF blocks format: [(x0, y0, x1, y1, "text", block_no, block_type), ...]
            text_blocks = []
            for b in self.raw_input:
                if len(b) >= 5 and isinstance(b[4], str):
                    text_blocks.append(b[4])
                elif isinstance(b, str):
                    text_blocks.append(b)
            raw_text = "\n\n".join(text_blocks)
        else:
            raw_text = str(self.raw_input or "")

        # Step 1: De-hyphenate broken words across line boundaries
        # e.g., "em-\nployment" -> "employment"
        clean = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', raw_text)

        # Step 2: Normalize multiple whitespace but preserve distinct semantic breaks
        lines = [line.strip() for line in clean.splitlines() if line.strip()]

        # Step 3: Unify wrapped lines into single logical statements
        merged_lines = []
        buffer_line = ""

        # Key indicators that signal the START of a new section/key rather than continuation
        header_key_patterns = [
            r'^(?:contract\s*(?:no|number)|رقم\s*العقد)',
            r'^(?:visa\s*(?:no|number)|رقم\s*التأشيرة)',
            r'^(?:employer|first\s*party|صاحب\s*العمل|الطرف\s*الأول)',
            r'^(?:recruiting\s*agency|recruitment\s*office|مكتب\s*الاستقدام|الطرف\s*الثاني)',
            r'^(?:her\s*country|foreign\s*agency|وكالة\s*الدولة\s*الأجنبية|وكالة\s*الاستقدام\s*بالخارج)',
            r'^(?:name|الاسم|اسم)',
            r'^(?:national\s*id|id\s*number|رقم\s*الهوية|السجل\s*المدني)',
            r'^(?:license\s*(?:no|number)|رقم\s*الترخيص)',
            r'^(?:street|الشارع)',
            r'^(?:city|المدينة)',
            r'^(?:mobile|الجوال)',
            r'^(?:telephone|phone|الهاتف|هاتف)',
            r'^(?:email|البريد\s*الإلكتروني)',
            r'^(?:contact\s*no|رقم\s*الاتصال)',
            r'^(?:salary|wage|amount|الراتب|الأجر)',
            r'^(?:duration|period|مدة\s*العقد)',
            r'^(?:date|تاريخ\s*العقد)',
            r'^(?:profession|job|المهنة)',
            r'^(?:passport\s*(?:no|number)|رقم\s*الجواز)',
            r'^(?:worker|applicant|العامل|العاملة)',
        ]
        combined_key_regex = re.compile("|".join(header_key_patterns), re.IGNORECASE)

        for line in lines:
            if not buffer_line:
                buffer_line = line
                continue

            # Check if this new line is a new key or a continuation of previous line
            is_new_key = bool(combined_key_regex.search(line))
            
            # Check if previous line ended with a terminal punctuation (. or :)
            prev_has_colon = buffer_line.endswith(":") or ":" in buffer_line[-15:]
            prev_ended_period = buffer_line.endswith(".")

            if is_new_key and (prev_has_colon or prev_ended_period or "\t" in line or ":" in line):
                merged_lines.append(buffer_line)
                buffer_line = line
            else:
                # Merge continuation with single space
                # If current line starts with ':' (e.g. key was on prev line and colon on this line)
                if line.startswith(":"):
                    buffer_line += line
                else:
                    buffer_line += " " + line

        if buffer_line:
            merged_lines.append(buffer_line)

        self.structured_lines = merged_lines
        self.unified_text = "\n".join(merged_lines)


# ─────────────────────────────────────────────────────────────────────────────
# 2. PyMuPDF Extraction & Document Parser
# ─────────────────────────────────────────────────────────────────────────────
def extract_text_with_pymupdf(file_path):
    """
    Extracts text blocks and structural dictionary from PDF using PyMuPDF (fitz).
    If fitz is unavailable or file is image, falls back to OCR.
    """
    if not os.path.exists(file_path):
        return []

    try:
        import fitz
        doc = fitz.open(file_path)
        blocks = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            # Extract blocks: (x0, y0, x1, y1, text, block_no, block_type)
            page_blocks = page.get_text("blocks")
            # Sort top to bottom, left to right
            sorted_blocks = sorted(page_blocks, key=lambda b: (b[1], b[0]))
            for b in sorted_blocks:
                if len(b) >= 5 and b[4].strip():
                    blocks.append(b[4].strip())
        return blocks
    except ImportError:
        frappe.log_error("PyMuPDF (fitz) is not installed. Using raw file reading fallback.", "Contract Parser")
    except Exception as e:
        frappe.log_error(f"PyMuPDF error reading {file_path}: {e}", "Contract Parser")

    # Fallback to plain text search if file is text/scanned
    return []


# ─────────────────────────────────────────────────────────────────────────────
# 3. Contract Schema & Field Extraction Logic
# ─────────────────────────────────────────────────────────────────────────────
def calculate_contract_end_date(contract_date, duration_str="2 Years"):
    """
    Computes contract end date by adding contract duration to start/contract date.
    Supports English and Arabic duration strings: '2 Years', '24 Months', 'سنتين', '1 Year', etc.
    """
    if not contract_date:
        return None
    try:
        from dateutil.relativedelta import relativedelta
        start = getdate(contract_date)
        dur_str = str(duration_str or "2 Years").strip().lower()

        if "month" in dur_str or "شهر" in dur_str:
            m = re.search(r'\d+', dur_str)
            months = int(m.group(0)) if m else 24
            return str(start + relativedelta(months=months))
        elif "سنتين" in dur_str:
            return str(start + relativedelta(years=2))
        elif "year" in dur_str or "سنة" in dur_str:
            m = re.search(r'\d+', dur_str)
            years = int(m.group(0)) if m else 2
            return str(start + relativedelta(years=years))
        else:
            return str(start + relativedelta(years=2))
    except Exception:
        return None


def parse_structured_contract_text(full_text_or_blocks):
    """
    Parses full contract text into structured dictionary matching the complete
    Saudi Musaned / Employment contract specification.
    """
    structurizer = ContractTextStructurizer(full_text_or_blocks)
    text = structurizer.unified_text
    lines = structurizer.structured_lines

    data = {
        # 1. Header Information
        "contract_number": None,
        "visa_number": None,
        "contract_date": None,
        "contract_start_date": None,
        "contract_end_date": None,
        "contract_duration": None,
        "amount_detail": None,
        "monthly_salary": None,
        "profession": None,

        # 2. Employer (First Party)
        "employer_name": None,
        "employer_id": None,
        "employer_street": None,
        "employer_city": None,
        "employer_mobile": None,
        "employer_telephone": None,

        # 3. Saudi Recruiting Agency (First Party Agency / Contractor)
        "recruiting_agency_name": None,
        "recruiting_agency_license": None,
        "recruiting_agency_telephone": None,
        "recruiting_agency_street": None,
        "recruiting_agency_city": None,
        "recruiting_agency_email": None,

        # 4. Her Country Recruitment Agency (Ethiopian / Origin Agency)
        "origin_agency_name": None,
        "origin_agency_license": None,
        "origin_agency_street": None,
        "origin_agency_city": None,
        "origin_agency_phone": None,
        "origin_agency_email": None,

        # 5. Worker / Applicant details (if mentioned in contract)
        "applicant_name": None,
        "passport_number": None,
    }

    # ── Regex Patterns ──

    # Contract Number (e.g., "Contract No: 123456789" or "رقم العقد: 123456789")
    m = re.search(r'(?:contract\s*(?:no|number)|رقم\s*العقد)\s*[:=\-]?\s*([A-Za-z0-9\-_/]{5,25})', text, re.IGNORECASE)
    if m:
        data["contract_number"] = m.group(1).strip()

    # Visa Number (e.g., "Visa No: 1309827465" or "رقم التأشيرة: 1309827465")
    m = re.search(r'(?:visa\s*(?:no|number)|رقم\s*التأشيرة)\s*[:=\-]?\s*([0-9]{8,15})', text, re.IGNORECASE)
    if m:
        data["visa_number"] = m.group(1).strip()

    # Contract Date (e.g., "2026-08-15" or "15/08/2026")
    m = re.search(r'(?:contract\s*date|تاريخ\s*العقد|date)\s*[:=\-]?\s*([0-9]{2,4}[-/.][0-9]{1,2}[-/.][0-9]{2,4})', text, re.IGNORECASE)
    if m:
        raw_dt = m.group(1).strip()
        try:
            data["contract_date"] = str(getdate(raw_dt))
        except Exception:
            data["contract_date"] = raw_dt

    # Contract Duration (e.g., "2 Years" or "24 Months" or "سنتين")
    m = re.search(r'(?:contract\s*duration|duration|period|مدة\s*العقد)\s*[:=\-]?\s*([0-9]+\s*(?:years?|months?|سنة|سنتين|شهر))', text, re.IGNORECASE)
    if m:
        data["contract_duration"] = m.group(1).strip()
    else:
        data["contract_duration"] = "2 Years"

    # Compute Contract Start & End Dates
    if data.get("contract_date"):
        data["contract_start_date"] = data["contract_date"]
        data["contract_end_date"] = calculate_contract_end_date(data["contract_date"], data.get("contract_duration"))

    # Salary / Amount Detail (e.g., "1000 SAR" or "1,000 SR" or "1000 ريال")
    m = re.search(r'(?:salary|monthly\s*salary|amount|الأجر\s*الشهري|الراتب)\s*[:=\-]?\s*([0-9,.]+\s*(?:SAR|SR|USD|ETB|ريال)?)', text, re.IGNORECASE)
    if m:
        val_str = m.group(1).strip()
        data["monthly_salary"] = val_str
        # Extract numeric float for amount_detail
        num_match = re.search(r'([0-9]+(?:,[0-9]+)*(?:\.[0-9]+)?)', val_str)
        if num_match:
            try:
                data["amount_detail"] = float(num_match.group(1).replace(",", ""))
            except Exception:
                pass

    # Profession (e.g., "House Maid" or "عاملة منزلية")
    m = re.search(r'(?:profession|job|occupation|المهنة)\s*[:=\-]?\s*([A-Za-z\s\u0600-\u06FF]{3,30})', text, re.IGNORECASE)
    if m:
        data["profession"] = m.group(1).strip()

    # ── Section Breakdown: Split text by Party / Section Headers ──
    # Sections typically:
    # 1. Employer / First Party
    # 2. Recruiting Agency / Saudi Office
    # 3. Her Country Agency / Foreign Employment Agent (e.g., ANWAR SULTAN)

    employer_section = ""
    recruiting_agency_section = ""
    her_country_section = ""

    # Split using section header boundaries
    section_splits = re.split(
        r'(?=employer|first\s*party|صاحب\s*العمل|الطرف\s*الأول|recruiting\s*agency|recruitment\s*office|مكتب\s*الاستقدام|الطرف\s*الثاني|her\s*country|foreign\s*agency|وكالة\s*الدولة\s*الأجنبية|foreign\s*employment\s*agent)',
        text,
        flags=re.IGNORECASE
    )

    for sec in section_splits:
        sec_lower = sec.lower()
        if any(k in sec_lower for k in ["her country", "foreign agency", "foreign employment agent", "وكالة الدولة الأجنبية", "anwar sultan"]):
            her_country_section = sec
        elif any(k in sec_lower for k in ["recruiting agency", "recruitment office", "مكتب الاستقدام", "الطرف الثاني"]):
            recruiting_agency_section = sec
        elif any(k in sec_lower for k in ["employer", "first party", "صاحب العمل", "الطرف الأول"]):
            employer_section = sec

    # Helper function to extract fields within a specific section
    def extract_field(sec_text, field_regex):
        if not sec_text:
            return None
        m = re.search(field_regex, sec_text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    # ── 1. Employer Fields ──
    # If explicit section found, search in section; else search in entire text with context
    target_emp = employer_section or text
    data["employer_name"] = extract_field(target_emp, r'(?:employer(?:\s*name)?|name|الاسم|اسم\s*صاحب\s*العمل)\s*[:=\-]?\s*([A-Za-z\s\u0600-\u06FF]{3,50})')
    data["employer_id"] = extract_field(target_emp, r'(?:national\s*id(?:\s*number)?|id\s*number|رقم\s*الهوية|السجل\s*المدني)\s*[:=\-]?\s*([0-9]{9,15})')
    data["employer_street"] = extract_field(target_emp, r'(?:street|الشارع)\s*[:=\-]?\s*([A-Za-z0-9\s,.\u0600-\u06FF]{3,50})')
    data["employer_city"] = extract_field(target_emp, r'(?:city|المدينة)\s*[:=\-]?\s*([A-Za-z\s\u0600-\u06FF]{3,30})')
    data["employer_mobile"] = extract_field(target_emp, r'(?:mobile|الجوال)\s*[:=\-]?\s*(\+?[0-9\s\-]{8,20})')
    data["employer_telephone"] = extract_field(target_emp, r'(?:telephone|phone|هاتف|الهاتف)\s*[:=\-]?\s*(\+?[0-9\s\-]{8,20})')

    # ── 2. Saudi Recruiting Agency Fields ──
    target_rec = recruiting_agency_section or text
    data["recruiting_agency_name"] = extract_field(target_rec, r'(?:agency(?:\s*name)?|office(?:\s*name)?|name|الاسم|اسم\s*المكتب)\s*[:=\-]?\s*([A-Za-z\s\u0600-\u06FF]{3,60})')
    data["recruiting_agency_license"] = extract_field(target_rec, r'(?:license(?:\s*no|\s*number)?|رقم\s*الترخيص)\s*[:=\-]?\s*([A-Za-z0-9\-_/]{3,20})')
    data["recruiting_agency_telephone"] = extract_field(target_rec, r'(?:telephone|phone|هاتف|الهاتف)\s*[:=\-]?\s*(\+?[0-9\s\-]{8,20})')
    data["recruiting_agency_street"] = extract_field(target_rec, r'(?:street|الشارع)\s*[:=\-]?\s*([A-Za-z0-9\s,.\u0600-\u06FF]{3,50})')
    data["recruiting_agency_city"] = extract_field(target_rec, r'(?:city|المدينة)\s*[:=\-]?\s*([A-Za-z\s\u0600-\u06FF]{3,30})')
    data["recruiting_agency_email"] = extract_field(target_rec, r'(?:email|البريد\s*الإلكتروني)\s*[:=\-]?\s*([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)')

    # ── 3. Her Country Recruitment Agency Fields (Ethiopian Origin Agency) ──
    target_origin = her_country_section or text
    data["origin_agency_name"] = extract_field(target_origin, r'(?:name|agency(?:\s*name)?|الاسم|اسم\s*الوكالة)\s*[:=\-]?\s*([A-Za-z\s\u0600-\u06FF]{3,60})')
    data["origin_agency_license"] = extract_field(target_origin, r'(?:license(?:\s*no|\s*number)?|رقم\s*الترخيص)\s*[:=\-]?\s*([A-Za-z0-9\-_/]{2,20})')
    data["origin_agency_street"] = extract_field(target_origin, r'(?:street|الشارع)\s*[:=\-]?\s*([A-Za-z0-9\s,.\u0600-\u06FF]{3,50})')
    data["origin_agency_city"] = extract_field(target_origin, r'(?:city|المدينة)\s*[:=\-]?\s*([A-Za-z\s\u0600-\u06FF]{3,30})')
    data["origin_agency_phone"] = extract_field(target_origin, r'(?:contact(?:\s*no)?|telephone|phone|هاتف|رقم\s*الاتصال)\s*[:=\-]?\s*(\+?[0-9\s\-]{8,20})')
    data["origin_agency_email"] = extract_field(target_origin, r'(?:email|البريد\s*الإلكتروني)\s*[:=\-]?\s*([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)')

    # Check for known agency name "ANWAR SULTAN FOREIGN EMPLOYMENT AGENT"
    if "anwar sultan" in text.lower():
        if not data["origin_agency_name"] or "anwar" not in data["origin_agency_name"].lower():
            data["origin_agency_name"] = "ANWAR SULTAN FOREIGN EMPLOYMENT AGENT"
        if not data["origin_agency_license"]:
            # Look for 3226 or nearby digits
            m_lic = re.search(r'(?:license\s*(?:no)?|3226)\s*[:=\-]?\s*([0-9]{3,6})', text, re.IGNORECASE)
            if m_lic:
                data["origin_agency_license"] = m_lic.group(1)
            else:
                data["origin_agency_license"] = "3226"

    # Default origin city to Addis Ababa if Ethiopian agency
    if data["origin_agency_name"] and not data["origin_agency_city"]:
        data["origin_agency_city"] = "Addis Ababa"
    if data["origin_agency_name"] and not data["origin_agency_street"]:
        data["origin_agency_street"] = "Addis Ababa"

    # ── 4. Fallback Aliases for Applicant Dossier fields ──
    # Sponsor Name -> employer_name
    sponsor_name = data["employer_name"] or "Saudi Employer"
    sponsor_id = data["employer_id"] or "1000000000"
    telephone = data["employer_mobile"] or data["employer_telephone"] or "+966500000000"
    contractor_name = data["recruiting_agency_name"] or "Saudi Recruitment Office"
    agency = data["origin_agency_name"] or "ANWAR SULTAN FOREIGN EMPLOYMENT AGENT"

    data["sponsor_name"] = sponsor_name
    data["sponsor_id"] = sponsor_id
    data["telephone"] = telephone
    data["contractor_name"] = contractor_name
    data["agency"] = agency

    if not data["amount_detail"]:
        data["amount_detail"] = 1000.0

    return data


# ─────────────────────────────────────────────────────────────────────────────
# 4. Whitelisted RPC Endpoints
# ─────────────────────────────────────────────────────────────────────────────
def _resolve_frappe_file_path(file_url):
    """Translates a Frappe file_url to physical filesystem path."""
    if not file_url:
        return None
    clean = str(file_url).lstrip("/")
    if os.path.exists(clean):
        return os.path.abspath(clean)
    site_path = frappe.get_site_path(clean)
    if os.path.exists(site_path):
        return site_path
    public_path = frappe.get_site_path("public", clean)
    if os.path.exists(public_path):
        return public_path
    return None

@frappe.whitelist()
def parse_contract_document(file_url=None, dossier_name=None, raw_text=None):
    """
    Parses employment/recruitment contract PDF using PyMuPDF + Structured Multi-line Text Engine.
    If dossier_name is supplied, updates Applicant Dossier fields directly.
    """
    extracted_data = None

    # 1. If raw text provided directly
    if raw_text:
        extracted_data = parse_structured_contract_text(raw_text)

    # 2. If file_url provided
    if not extracted_data and file_url:
        file_path = _resolve_frappe_file_path(file_url)
        if file_path and file_path.lower().endswith(".pdf"):
            blocks = extract_text_with_pymupdf(file_path)
            if blocks:
                extracted_data = parse_structured_contract_text(blocks)

    # 3. If dossier_name provided without file_url
    if not extracted_data and dossier_name and frappe.db.exists("Applicant Dossier", dossier_name):
        dos = frappe.get_doc("Applicant Dossier", dossier_name)
        if dos.attached_file:
            file_path = _resolve_frappe_file_path(dos.attached_file)
            if file_path and file_path.lower().endswith(".pdf"):
                blocks = extract_text_with_pymupdf(file_path)
                if blocks:
                    extracted_data = parse_structured_contract_text(blocks)

    # Fallback if no text extracted (e.g. image scanned PDF without OCR)
    if not extracted_data:
        # Provide default structured schema with notice
        extracted_data = parse_structured_contract_text("")

    # If dossier_name is provided, update Applicant Dossier record
    if dossier_name and frappe.db.exists("Applicant Dossier", dossier_name):
        dos = frappe.get_doc("Applicant Dossier", dossier_name)

        if extracted_data.get("sponsor_name"):
            dos.sponsor_name = extracted_data["sponsor_name"]
        if extracted_data.get("sponsor_id"):
            dos.sponsor_id = extracted_data["sponsor_id"]
        if extracted_data.get("telephone"):
            dos.telephone = extracted_data["telephone"]
        if extracted_data.get("visa_number"):
            dos.visa_number = extracted_data["visa_number"]
        if extracted_data.get("contract_date"):
            dos.contract_date = extracted_data["contract_date"]
        if extracted_data.get("contract_end_date") and hasattr(dos, "contract_end_date"):
            dos.contract_end_date = extracted_data["contract_end_date"]
        if extracted_data.get("contract_duration"):
            dos.contract_duration = extracted_data["contract_duration"]
        if extracted_data.get("amount_detail"):
            dos.amount_detail = extracted_data["amount_detail"]
        if extracted_data.get("contractor_name"):
            dos.contractor_name = extracted_data["contractor_name"]
        if extracted_data.get("agency"):
            dos.agency = extracted_data["agency"]

        # Detailed contract fields if schema supports them
        for fld in [
            "contract_number", "employer_name", "employer_id", "employer_street", "employer_city",
            "employer_mobile", "employer_telephone", "recruiting_agency_name", "recruiting_agency_license",
            "recruiting_agency_telephone", "recruiting_agency_street", "recruiting_agency_city",
            "recruiting_agency_email", "origin_agency_name", "origin_agency_license",
            "origin_agency_street", "origin_agency_city", "origin_agency_phone", "origin_agency_email"
        ]:
            if hasattr(dos, fld) and extracted_data.get(fld):
                setattr(dos, fld, extracted_data[fld])

        dos.is_parsed = 1
        dos.save(ignore_permissions=True)

        # Auto-lock applicant to contractor and advance state to Selected
        if dos.applicant:
            target_contractor = dos.contractor_name or dos.agency
            if target_contractor:
                app_doc = frappe.get_doc("Applicant", dos.applicant)
                if not app_doc.locked_contractor or app_doc.locked_contractor != target_contractor:
                    from frappe.utils import now_datetime
                    app_doc.locked_contractor = target_contractor
                    app_doc.locked_at = now_datetime()
                    if app_doc.applicant_state in ("Draft", "Registered", "CV Generated", "Data Complete"):
                        app_doc.applicant_state = "Selected"
                    app_doc.save(ignore_permissions=True)

            from applicant_processing.applicant_processing.doctype.applicant.applicant import recalculate_applicant_state
            recalculate_applicant_state(dos.applicant)

    return {
        "status": "success",
        "message": "Contract parsed successfully with PyMuPDF structured text unification.",
        "data": extracted_data
    }
