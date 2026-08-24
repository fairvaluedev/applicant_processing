# Copyright (c) 2026, Admin and contributors
# For license information, please see license.txt

import os
import re
import unicodedata
import datetime
import frappe
from frappe.utils import getdate, today


# ─────────────────────────────────────────────────────────────────────────────
# 1. Unicode & Arabic Normalization Helpers
# ─────────────────────────────────────────────────────────────────────────────
ARABIC_PRESENTATION_MAP = {
    '\ufe80': '\u0621', '\ufe81': '\u0622', '\ufe82': '\u0622', '\ufe83': '\u0623',
    '\ufe84': '\u0623', '\ufe85': '\u0624', '\ufe86': '\u0624', '\ufe87': '\u0625',
    '\ufe88': '\u0625', '\ufe89': '\u0626', '\ufe8a': '\u0626', '\ufe8b': '\u0626',
    '\ufe8c': '\u0626', '\ufe8d': '\u0627', '\ufe8e': '\u0627', '\ufe8f': '\u0628',
    '\ufe90': '\u0628', '\ufe91': '\u0628', '\ufe92': '\u0628', '\ufe93': '\u0629',
    '\ufe94': '\u0629', '\ufe95': '\u062a', '\ufe96': '\u062a', '\ufe97': '\u062a',
    '\ufe98': '\u062a', '\ufe99': '\u062b', '\ufe9a': '\u062b', '\ufe9b': '\u062b',
    '\ufe9c': '\u062b', '\ufe9d': '\u062c', '\ufe9e': '\u062c', '\ufe9f': '\u062c',
    '\ufea0': '\u062c', '\ufea1': '\u062d', '\ufea2': '\u062d', '\ufea3': '\u062d',
    '\ufea4': '\u062d', '\ufea5': '\u062e', '\ufea6': '\u062e', '\ufea7': '\u062e',
    '\ufea8': '\u062e', '\ufea9': '\u062f', '\ufeaa': '\u062f', '\ufeab': '\u0630',
    '\ufeac': '\u0630', '\ufead': '\u0631', '\ufeae': '\u0631', '\ufeaf': '\u0632',
    '\ufeb0': '\u0632', '\ufeb1': '\u0633', '\ufeb2': '\u0633', '\ufeb3': '\u0633',
    '\ufeb4': '\u0633', '\ufeb5': '\u0634', '\ufeb6': '\u0634', '\ufeb7': '\u0634',
    '\ufeb8': '\u0634', '\ufeb9': '\u0635', '\ufeba': '\u0635', '\ufebb': '\u0635',
    '\ufebc': '\u0635', '\ufebd': '\u0636', '\ufebe': '\u0636', '\ufebf': '\u0636',
    '\ufec0': '\u0636', '\ufec1': '\u0637', '\ufec2': '\u0637', '\ufec3': '\u0637',
    '\ufec4': '\u0637', '\ufec5': '\u0638', '\ufec6': '\u0638', '\ufec7': '\u0638',
    '\ufec8': '\u0638', '\ufec9': '\u0639', '\ufeca': '\u0639', '\ufecb': '\u0639',
    '\ufecc': '\u0639', '\ufecd': '\u063a', '\ufece': '\u063a', '\ufecf': '\u063a',
    '\ufed0': '\u063a', '\ufed1': '\u0641', '\ufed2': '\u0641', '\ufed3': '\u0641',
    '\ufed4': '\u0641', '\ufed5': '\u0642', '\ufed6': '\u0642', '\ufed7': '\u0642',
    '\ufed8': '\u0642', '\ufed9': '\u0643', '\ufeda': '\u0643', '\ufedb': '\u0643',
    '\ufedc': '\u0643', '\ufedd': '\u0644', '\ufede': '\u0644', '\ufedf': '\u0644',
    '\ufee0': '\u0644', '\ufee1': '\u0645', '\ufee2': '\u0645', '\ufee3': '\u0645',
    '\ufee4': '\u0645', '\ufee5': '\u0646', '\ufee6': '\u0646', '\ufee7': '\u0646',
    '\ufee8': '\u0646', '\ufee9': '\u0647', '\ufeea': '\u0647', '\ufeeb': '\u0647',
    '\ufeec': '\u0647', '\ufeed': '\u0648', '\ufeee': '\u0648', '\ufeef': '\u0649',
    '\ufef0': '\u0649', '\ufef1': '\u064a', '\ufef2': '\u064a', '\ufef3': '\u064a',
    '\ufef4': '\u064a', '\ufef5': '\u0644\u0622', '\ufef6': '\u0644\u0622',
    '\ufef7': '\u0644\u0623', '\ufef8': '\u0644\u0623', '\ufef9': '\u0644\u0625',
    '\ufefa': '\u0644\u0625', '\ufefb': '\u0644\u0627', '\ufefc': '\u0644\u0627',
}

def normalize_text(text):
    """
    Cleans raw text extracted from PDF:
    - Normalizes Unicode (NFKC)
    - Replaces Arabic presentation forms with base Arabic
    - Strips bidi / direction markers
    - Cleans whitespace
    """
    if not text:
        return ""

    chars = []
    for ch in str(text):
        chars.append(ARABIC_PRESENTATION_MAP.get(ch, ch))
    normalized = "".join(chars)

    normalized = unicodedata.normalize("NFKC", normalized)
    normalized = re.sub(r'[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff\u200b\u00ad]', '', normalized)
    normalized = re.sub(r'[\xa0\u2000-\u200a\u202f\u205f\u3000]', ' ', normalized)
    return normalized


# ─────────────────────────────────────────────────────────────────────────────
# 2. Multi-Line Text Structurizer Engine
# ─────────────────────────────────────────────────────────────────────────────
class ContractTextStructurizer:
    """
    Parses and organizes raw PDF text blocks, multi-line strings, and tables into
    structured semantic lines, section blocks, and key-value maps.
    Handles standard bilateral Saudi Musaned employment contract layouts.
    """

    def __init__(self, raw_blocks_or_text):
        self.raw_input = raw_blocks_or_text
        self.clean_lines = []
        self.unified_text = ""
        self.sections = {
            "header": "",
            "employer": "",
            "recruiting_agency": "",
            "worker": "",
            "origin_agency": "",
            "financial": "",
        }
        self._process()

    def _process(self):
        raw_lines = []
        if isinstance(self.raw_input, list):
            for b in self.raw_input:
                if isinstance(b, (list, tuple)) and len(b) >= 5 and isinstance(b[4], str):
                    raw_lines.extend(b[4].splitlines())
                elif isinstance(b, str):
                    raw_lines.extend(b.splitlines())
        else:
            raw_lines = str(self.raw_input or "").splitlines()

        clean_lines = []
        for line in raw_lines:
            cleaned = normalize_text(line).strip()
            if cleaned:
                clean_lines.append(cleaned)

        self.clean_lines = clean_lines
        self.unified_text = "\n".join(clean_lines)
        self._partition_sections()

    def _partition_sections(self):
        """Splits the full text into semantic contract sections."""
        current_section = "header"
        section_lines = {k: [] for k in self.sections}

        for line in self.clean_lines:
            lower = line.lower()

            # 1. Section A: Employer (First Party)
            if any(k in lower for k in [
                "a. employer", "ا. صاحب العمل", "صاحب العمل:", "بيانات صاحب العمل",
                "first party", "الطرف الأول"
            ]) and not any(k in lower for k in ["hereinafter called", "represented in", "اسم صاحب", "هاتف", "signature of", "توقيع"]):
                current_section = "employer"
            # 2. Section: Saudi Recruiting Agency (Second Party)
            elif any(k in lower for k in [
                "saudi recruiting agency", "وكالة الاستقدام السعودية", "مكتب الاستقدام السعودي",
                "represented in the kingdom of saudi arabia",
                "second party", "الطرف الثاني", "مكتب الاستقدام:"
            ]) and not any(k in lower for k in ["signature of", "توقيع"]):
                current_section = "recruiting_agency"
            # 3. Section B: Domestic Service Worker
            elif any(k in lower for k in [
                "b. domestic service worker", "ب. العامل المنزلي", "العامل المنزلي / العاملة المنزلية",
                "domestic service worker", "domestic worker", "بيانات العامل", "worker details"
            ]) and not any(k in lower for k in ["hereinafter called dsw", "represented in his", "signature of", "توقيع"]):
                current_section = "worker"
            # 4. Section: Foreign Origin Agency (Third Party / Ethiopia Agency)
            elif any(k in lower for k in [
                "dsw represented", "represented in his", "represented in her", "her country agency",
                "وكالة الاستقدام بالخارج", "وكالة الاستقدام:", "ethiopian recruitment agency",
                "وكالة تصدير العمالة", "foreign agency", "third party", "الطرف الثالث"
            ]) and not any(k in lower for k in ["signature of", "توقيع"]):
                current_section = "origin_agency"
            # 5. Financial / Wage Section
            elif any(k in lower for k in ["6. wage", "6. الأجر", "wage", "الأجور"]):
                current_section = "financial"

            section_lines[current_section].append(line)

        for k in self.sections:
            self.sections[k] = "\n".join(section_lines[k])


# ─────────────────────────────────────────────────────────────────────────────
# 3. PyMuPDF Extraction & Document Parser
# ─────────────────────────────────────────────────────────────────────────────
def extract_text_with_pymupdf(file_path):
    """
    Extracts text blocks from PDF using PyMuPDF (fitz/pymupdf).
    Sorts blocks in reading order (top-to-bottom, left-to-right).
    """
    if not file_path or not os.path.exists(file_path):
        return []

    try:
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz

        doc = fitz.open(file_path)
        blocks = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_blocks = page.get_text("blocks")
            sorted_blocks = sorted(page_blocks, key=lambda b: (round(b[1] / 10) * 10, b[0]))
            for b in sorted_blocks:
                if len(b) >= 5 and b[4].strip():
                    blocks.append(b[4].strip())
        return blocks
    except Exception as e:
        frappe.log_error(f"PyMuPDF error reading {file_path}: {e}", "Contract Parser")

    return []


# ─────────────────────────────────────────────────────────────────────────────
# 4. Helper Extraction Utilities
# ─────────────────────────────────────────────────────────────────────────────
GENERIC_TITLES = {
    "صاحب العمل", "الطرف الأول", "مكتب الاستقدام", "الطرف الثاني", "شركة الاستقدام",
    "الطرف الثالث", "وكالة الاستقدام بالخارج", "العامل", "العاملة", "العامل المنزلي",
    "بيانات العامل", "first party", "second party", "third party", "employer",
    "recruiting agency", "recruitment office", "foreign agency", "domestic worker",
    "domestic service worker", "saudi recruiting agency"
}

def clean_extracted_value(val):
    """Cleans an extracted field value: removes colon prefixes, bounding quotes, extra spaces, generic headers, and bilingual label remnants."""
    if val is None:
        return None
    val_str = str(val).strip()

    # If bilingual label remnant like " / اسم العاملة: Meseret Hailemariam Desta" or "ة: Meseret"
    if ":" in val_str:
        prefix, suffix = val_str.split(":", 1)
        if len(prefix) < 30 and (
            prefix.startswith("/") or prefix.startswith("|") or
            any(k in prefix.lower() for k in ["اسم", "name", "worker", "employer", "agency", "office", "الطرف", "صاحب", "مكتب", "وكالة", "ة", "رقم", "street", "الشارع", "city", "المدينة"])
        ):
            val_str = suffix.strip()

    val_str = re.sub(r'^[:=\-–—\s|/#]+', '', val_str)
    val_str = re.sub(r'[:=\-–—\s|/#]+$', '', val_str)
    val_str = re.sub(r'\s+', ' ', val_str).strip()
    if val_str.startswith("(") and val_str.endswith(")"):
        inner = val_str[1:-1].strip()
        if inner.lower() in GENERIC_TITLES:
            return None
    if val_str.lower() in GENERIC_TITLES:
        return None
    return val_str if val_str else None


def extract_field_from_text(text_or_lines, patterns, flags=re.IGNORECASE):
    """
    Extracts clean field value from text.
    Handles:
    - Same-line: 'Label: Value'
    - Multi-column same line: 'Label: Value   Label2: Value2'
    - Next-line: 'Label\nValue'
    """
    if not text_or_lines:
        return None

    if isinstance(text_or_lines, list):
        text = "\n".join(text_or_lines)
        lines = text_or_lines
    else:
        text = str(text_or_lines)
        lines = [line.strip() for line in text.splitlines() if line.strip()]

    # 1. Direct Regex Search (check all matches in text)
    for pat in patterns:
        for m in re.finditer(pat, text, flags | re.MULTILINE):
            val = m.group(1).strip()
            if "\n" in val:
                val = val.split("\n")[0].strip()
            val = re.split(r'\s{2,}|\t', val)[0].strip()
            cleaned = clean_extracted_value(val)
            if cleaned:
                return cleaned

    # 2. Line-by-line fallback (Label on line i, Value on line i+1)
    label_patterns = []
    for pat in patterns:
        prefix_match = re.match(r'^\(?\?:?([^()]+)\)?', pat)
        if prefix_match:
            label_patterns.append(prefix_match.group(1))

    for i, line in enumerate(lines):
        line_clean = line.strip()
        for l_pat in label_patterns:
            if re.search(rf'^{l_pat}[:=\-–#]?$', line_clean, flags=flags) and i + 1 < len(lines):
                next_val = lines[i + 1].strip()
                if next_val and not any(re.search(rf'^{lp}[:=\-–#]?$', next_val, flags=flags) for lp in label_patterns):
                    cleaned = clean_extracted_value(next_val)
                    if cleaned:
                        return cleaned

    return None


def normalize_date_string(date_str):
    """Converts various date formats (Gregorian DD/MM/YYYY, YYYY-MM-DD, etc.) to YYYY-MM-DD."""
    if not date_str:
        return None
    d = str(date_str).strip()

    m = re.search(r'([0-9]{1,4}[-/.][0-9]{1,2}[-/.][0-9]{1,4})', d)
    if not m:
        return None
    raw = m.group(1).replace("/", "-").replace(".", "-")
    parts = raw.split("-")

    try:
        if len(parts) == 3:
            if len(parts[0]) == 4:
                year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
            else:
                day, month, year = int(parts[0]), int(parts[1]), int(parts[2])

            dt = datetime.date(year, month, day)
            return str(dt)
    except Exception:
        pass

    try:
        return str(getdate(d))
    except Exception:
        return None


def calculate_contract_end_date(contract_date, duration_str="2 Years"):
    """
    Computes contract end date by adding contract duration to start date.
    Supports English & Arabic duration strings: '2 Years', '24 Months', 'سنتين', '1 Year', 'سنة'.
    """
    if not contract_date:
        return None
    try:
        from dateutil.relativedelta import relativedelta
        if isinstance(contract_date, str):
            parts = [int(p) for p in re.findall(r'\d+', contract_date)]
            if len(parts) >= 3:
                if parts[0] > 1000:
                    start = datetime.date(parts[0], parts[1], parts[2])
                else:
                    start = datetime.date(parts[2], parts[1], parts[0])
            else:
                start = getdate(contract_date)
        else:
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
        elif "2" in dur_str:
            return str(start + relativedelta(years=2))
        elif "1" in dur_str:
            return str(start + relativedelta(years=1))
        else:
            return str(start + relativedelta(years=2))
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 5. Core Contract Parsing Logic
# ─────────────────────────────────────────────────────────────────────────────
def parse_structured_contract_text(full_text_or_blocks):
    """
    Parses full contract text into structured dictionary matching the complete
    Saudi Musaned / Employment contract specification.
    Extracts all available data fields from Arabic and/or English sections.
    Does NOT inject fake placeholder names.
    """
    structurizer = ContractTextStructurizer(full_text_or_blocks)
    text = structurizer.unified_text
    sec = structurizer.sections

    data = {
        # 1. Header Information
        "contract_number": None,
        "visa_number": None,
        "contract_date": None,
        "contract_start_date": None,
        "contract_end_date": None,
        "contract_duration": "2 Years",
        "amount_detail": None,
        "monthly_salary": None,
        "profession": None,

        # 2. Employer (First Party / Sponsor)
        "sponsor_name": None,
        "sponsor_id": None,
        "telephone": None,
        "employer_name": None,
        "employer_id": None,
        "employer_mobile": None,
        "employer_telephone": None,
        "employer_street": None,
        "employer_city": None,

        # 3. Saudi Recruiting Agency (Second Party / Contractor)
        "contractor_name": None,
        "recruiting_agency_name": None,
        "recruiting_agency_license": None,
        "recruiting_agency_telephone": None,
        "recruiting_agency_street": None,
        "recruiting_agency_city": None,
        "recruiting_agency_email": None,

        # 4. Her Country Recruitment Agency (Ethiopian / Origin Agency)
        "agency": None,
        "origin_agency_name": None,
        "origin_agency_license": None,
        "origin_agency_phone": None,
        "origin_agency_street": None,
        "origin_agency_city": None,
        "origin_agency_email": None,

        # 5. Worker / Applicant details
        "applicant_name": None,
        "passport_number": None,
        "nationality": None,
    }

    # ── 1. Contract & Visa Header ──

    # Contract Number (e.g. CONTRACT # 2005450415 or CONTRACT No: CR-99887766 or رقم العقد 2005450415)
    data["contract_number"] = extract_field_from_text(
        text,
        [
            r'(?:CONTRACT\s*(?:#|NO\.?|NUMBER|ID|No:|#\s*)|رقم\s*عقد\s*خدمات\s*التوسط|رقم\s*عقد\s*التوسط|رقم\s*العقد|رقم\s*الاتفاقية|agreement\s*(?:no|number))\s*[:=\-–#]?\s*([A-Za-z0-9][A-Za-z0-9\-_/]{3,25})',
            r'رق[^\s]*\s*ا[^\s]*عقد\s*[:=\-–#]?\s*([A-Za-z0-9][A-Za-z0-9\-_/]{3,25})',
        ]
    )

    # Visa Number (e.g. VISA NUMBER # 1908334046 or رقم التأشيرة 1908334046)
    data["visa_number"] = extract_field_from_text(
        text,
        [
            r'VISA\s*(?:NUMBER|NO\.?|ID)?\s*#?\s*[:=\-–]?\s*([0-9]{8,15})',
            r'(?:رقم\s*التأشيرة|رقم\s*التاشيرة|رقم\s*تأشيرة\s*العمل|رقم\s*صادر\s*التأشيرة|رقم\s*الصادر)\s*[:=\-–#]?\s*([0-9]{8,15})',
            r'رق[^\s]*\s*ا[^\s]*تأشيرة\s*[:=\-–#]?\s*([0-9]{8,15})',
        ]
    )

    # Contract Date (e.g. corresponding to (13/08/2026) or بتاريخ (13/08/2026))
    raw_date = extract_field_from_text(
        text,
        [
            r'corresponding\s*to\s*\(?([0-9]{1,2}[-/.][0-9]{1,2}[-/.][0-9]{2,4})\)?',
            r'بتاريخ\s*\(?([0-9]{1,2}[-/.][0-9]{1,2}[-/.][0-9]{2,4})\)?',
            r'(?:تاريخ\s*إبرام\s*العقد|تاريخ\s*ابرام\s*العقد|تاريخ\s*العقد|تاريخ\s*توقيع\s*العقد|تاريخ\s*الاتفاقية|تاريخ\s*الإصدار|تاريخ\s*الاصدار)\s*[:=\-–]?\s*\(?([0-9]{1,4}[-/.][0-9]{1,2}[-/.][0-9]{1,4})\)?',
            r'(?:contract\s*date|agreement\s*date|date\s*of\s*agreement|issue\s*date|date)\s*[:=\-–]?\s*\(?([0-9]{1,4}[-/.][0-9]{1,2}[-/.][0-9]{1,4})\)?',
        ]
    )
    if raw_date:
        data["contract_date"] = normalize_date_string(raw_date)
        data["contract_start_date"] = data["contract_date"]

    # Contract Duration (e.g. مدة العقد سنتين or 2 Years / 24 Months)
    dur = extract_field_from_text(
        text,
        [
            r'مدة\s*العقد\s*(سنتين|سنة\s*واحدة|[0-9]+\s*(?:سنة|سنتين|أشهر|شهر|عام|أعوام))',
            r'(?:مدة\s*العقد|مدة\s*الاتفاقية|المدة)\s*[:=\-–]?\s*([0-9]+\s*(?:سنة|سنتين|أشهر|شهر|عام|أعوام|years?|months?)|سنتين|سنة\s*واحدة)',
            r'(?:contract\s*duration|duration|period|contract\s*period)\s*[:=\-–]?\s*([0-9]+\s*(?:years?|months?)|2\s*years|24\s*months)',
        ]
    )
    if dur:
        data["contract_duration"] = dur
    else:
        data["contract_duration"] = "2 Years"

    # Contract End Date
    if data["contract_date"]:
        data["contract_end_date"] = calculate_contract_end_date(data["contract_date"], data["contract_duration"])

    # Monthly Salary / Amount (e.g. fixed monthly wage of 1000 (Saudi Riyals) or أجر شهري ثابت قدره 1000)
    salary_match = re.search(r'fixed\s*monthly\s*wage\s*of\s*([0-9,.]+)\s*\(([^)]+)\)', text, re.IGNORECASE)
    if not salary_match:
        salary_match = re.search(r'أجر\s*شهري\s*ثابت\s*قدره\s*([0-9,.]+)\s*\(([^)]+)\)', text, re.IGNORECASE)

    if salary_match:
        data["amount_detail"] = float(salary_match.group(1).replace(",", ""))
        data["monthly_salary"] = f"{salary_match.group(1)} {salary_match.group(2)}"
    else:
        salary_str = extract_field_from_text(
            text,
            [
                r'(?:الراتب\s*الشهري|الراتب|الأجر\s*الشهري|الأجر|أجر\s*العامل|قيمة\s*العقد)\s*[:=\-–]?\s*([0-9,.]+\s*(?:ريال|SAR|SR|USD|ETB)?)',
                r'(?:monthly\s*salary|salary|basic\s*salary|wage|monthly\s*wage|amount)\s*[:=\-–]?\s*([0-9,.]+\s*(?:SAR|SR|USD|ETB|ريال)?)',
            ]
        )
        if salary_str:
            data["monthly_salary"] = salary_str
            num_m = re.search(r'([0-9]+(?:,[0-9]+)*(?:\.[0-9]+)?)', salary_str)
            if num_m:
                try:
                    data["amount_detail"] = float(num_m.group(1).replace(",", ""))
                except Exception:
                    pass

    # Profession (e.g. Position: House Maid or الوظيفة: عاملة منزلية or hired as House Maid)
    data["profession"] = extract_field_from_text(
        text,
        [
            r'(?:Position|الوظيفة)\s*[:=\-–]?\s*([^\r\n]+)',
            r'hired\s*as\s*([A-Za-z\s]+)',
            r'لعمل\s*(عاملة\s*منزلية|سائق\s*خاص|[^\r\n]+)',
            r'(?:المهنة|المسمى\s*الوظيفي)\s*[:=\-–]?\s*([^\r\n]+)',
            r'(?:profession|job|occupation)\s*[:=\-–]?\s*([^\r\n]+)',
        ]
    )

    # Nationality
    nat = extract_field_from_text(
        text,
        [
            r'CONTRACT\s*FOR\s*([A-Z]+)\s*DOMESTIC\s*WORKERS',
            r'من\s*(اثيوبيا|إثيوبيا|[^\s]+)\s*المغادرة\s*للمملكة',
            r'(?:الجنسية|جنسية\s*العامل)\s*[:=\-–]?\s*([^\r\n]+)',
            r'(?:nationality)\s*[:=\-–]?\s*([^\r\n]+)',
        ]
    )
    if nat:
        data["nationality"] = nat.title() if nat.isupper() else nat

    # ── 2. Employer (First Party / Sponsor) ──
    emp_text = sec["employer"] or text

    # Handle multi-line Name in Employer section (e.g. Name: ABDULLAH AMER MUGHABBIRI \n ALBARIQI)
    emp_name = None
    m_ename = re.search(
        r'(?:Name|الاسم|اسم\s*صاحب\s*العمل|اسم\s*الكفيل)\s*[:=\-–]?\s*([^\r\n]+(?:\n(?!(?:Name|الاسم|National|رقم|Address|العنوان|Contact|Mobile|Telephone|City|المدينة|Street|الشارع|Position))[^\r\n]+)?)',
        emp_text,
        re.IGNORECASE
    )
    if m_ename:
        raw_n = m_ename.group(1).replace("\n", " ").strip()
        emp_name = clean_extracted_value(raw_n)

    if not emp_name:
        emp_name = extract_field_from_text(
            emp_text,
            [
                r'(?:اسم\s*صاحب\s*العمل|اسم\s*الكفيل|اسم\s*المستقدم)\s*[:=\-–]?\s*([^\r\n]+)',
                r'(?:employer\s*name|sponsor\s*name|first\s*party\s*name)\s*[:=\-–]?\s*([^\r\n]+)',
                r'Name\s*[:=\-–]?\s*([^\r\n]+)',
                r'الاسم\s*[:=\-–]?\s*([^\r\n]+)',
            ]
        )
    data["employer_name"] = emp_name

    data["employer_id"] = extract_field_from_text(
        emp_text,
        [
            r'(?:National\s*ID\s*Number|رقم\s*الهوية\s*الوطنية)\s*[:=\-–]?\s*([0-9]{9,15})',
            r'(?:رقم\s*الهوية\s*الوطنية|رقم\s*الهوية|الهوية\s*الوطنية|السجل\s*المدني|رقم\s*الإقامة|رقم\s*بطاقة\s*الأحوال|رقم\s*هوية\s*صاحب\s*العمل)\s*[:=\-–]?\s*([0-9]{9,15})',
            r'(?:national\s*id(?:\s*number)?|national\s*id\s*no|id\s*number|id\s*no|iqama\s*(?:no|number))\s*[:=\-–]?\s*([0-9]{9,15})',
        ]
    )

    data["employer_mobile"] = extract_field_from_text(
        emp_text,
        [
            r'(?:Mobile|رقم\s*الجوال|الجوال)\s*[:=\-–]?\s*(\+?[0-9\s\-]{8,20})',
            r'(?:mobile\s*(?:no|number)?|cell\s*(?:no|number)?)\s*[:=\-–]?\s*(\+?[0-9\s\-]{8,20})',
        ]
    )

    data["employer_telephone"] = extract_field_from_text(
        emp_text,
        [
            r'(?:Telephone|رقم\s*الهاتف|الهاتف)\s*[:=\-–]?\s*(\+?[0-9\s\-]{7,20})',
            r'(?:telephone\s*(?:no|number)?|phone\s*(?:no|number)?)\s*[:=\-–]?\s*(\+?[0-9\s\-]{7,20})',
        ]
    )

    data["employer_city"] = extract_field_from_text(
        emp_text,
        [
            r'(?:City|المدينة)\s*[:=\-–]?\s*([^\r\n]+)',
            r'(?:city|residence\s*city|مدينة\s*الإقامة|مدينة\s*صاحب\s*العمل)\s*[:=\-–]?\s*([^\r\n]+)',
        ]
    )

    data["employer_street"] = extract_field_from_text(
        emp_text,
        [
            r'(?:Street|الشارع)\s*[:=\-–]?\s*([^\r\n]+)',
            r'(?:الحي\s*/\s*الشارع|الحي\s*والشارع|الحي|العنوان)\s*[:=\-–]?\s*([^\r\n]+)',
            r'(?:street|district|address)\s*[:=\-–]?\s*([^\r\n]+)',
        ]
    )

    # ── 3. Saudi Recruiting Agency (Second Party / Contractor) ──
    rec_text = sec["recruiting_agency"] or text

    # Handle multi-line Name in Saudi Recruiting Agency
    rec_name = None
    m_rname = re.search(
        r'(?:Name|الاسم|اسم\s*مكتب\s*الاستقدام|اسم\s*الشركة)\s*[:=\-–]?\s*([^\r\n]+(?:\n(?!(?:Name|الاسم|License|رقم|Address|العنوان|Contact|Telephone|Phone|City|المدينة|Street|الشارع|Email|البريد))[^\r\n]+)?)',
        rec_text,
        re.IGNORECASE
    )
    if m_rname:
        raw_rn = m_rname.group(1).replace("\n", " ").strip()
        rec_name = clean_extracted_value(raw_rn)

    if not rec_name:
        rec_name = extract_field_from_text(
            rec_text,
            [
                r'(?:Name|الاسم|اسم\s*مكتب\s*الاستقدام|اسم\s*المكتب|اسم\s*الشركة|اسم\s*جهة\s*الاستقدام|جهة\s*الاستقدام\s*المرخصة)\s*[:=\-–]?\s*([^\r\n]+)',
                r'(?:recruiting\s*agency\s*name|recruitment\s*office\s*name|office\s*name|contractor\s*name|agency\s*name|company\s*name)\s*[:=\-–]?\s*([^\r\n]+)',
            ]
        )
    data["recruiting_agency_name"] = rec_name

    data["recruiting_agency_license"] = extract_field_from_text(
        rec_text,
        [
            r'(?:License\s*no|رقم\s*الترخيص|ترخيص\s*رقم)\s*[:=\-–]?\s*([A-Za-z0-9\-_/]{2,25})',
            r'(?:license\s*(?:no|number)|license\s*#|commercial\s*reg)\s*[:=\-–]?\s*([A-Za-z0-9\-_/]{2,25})',
        ]
    )

    data["recruiting_agency_telephone"] = extract_field_from_text(
        rec_text,
        [
            r'(?:Telephone|رقم\s*الهاتف|الهاتف|رقم\s*الاتصال|الجوال)\s*[:=\-–]?\s*(\+?[0-9\s\-]{7,20})',
            r'(?:telephone\s*(?:no|number)?|phone\s*(?:no|number)?|contact\s*no)\s*[:=\-–]?\s*(\+?[0-9\s\-]{7,20})',
        ]
    )

    data["recruiting_agency_street"] = extract_field_from_text(
        rec_text,
        [
            r'(?:Street|الشارع)\s*[:=\-–]?\s*([^\r\n]+)',
            r'(?:الحي|العنوان|address)\s*[:=\-–]?\s*([^\r\n]+)',
        ]
    )

    data["recruiting_agency_city"] = extract_field_from_text(
        rec_text,
        [
            r'(?:City|المدينة)\s*[:=\-–]?\s*([^\r\n]+)',
        ]
    )

    data["recruiting_agency_email"] = extract_field_from_text(
        rec_text,
        [
            r'(?:Email|البريد\s*الإلكتروني|البريد\s*الالكتروني|الإيميل)\s*[:=\-–]?\s*([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)',
            r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)',
        ]
    )

    # ── 4. Origin Agency (Third Party / Ethiopian Agency) ──
    orig_text = sec["origin_agency"] or text

    # Handle multi-line Origin Agency Name (e.g. Name: ANWAR SULTAN FOREIGN \n EMPLOYMENT AGENT)
    orig_name = None
    m_oname = re.search(
        r'(?:Name|الاسم|اسم\s*الوكالة)\s*[:=\-–]?\s*([^\r\n]+(?:\n(?!(?:Name|الاسم|License|رقم|Address|العنوان|Contact|Phone|Telephone|City|المدينة|Street|الشارع|Email|البريد))[^\r\n]+)?)',
        orig_text,
        re.IGNORECASE
    )
    if m_oname:
        raw_on = m_oname.group(1).replace("\n", " ").strip()
        orig_name = clean_extracted_value(raw_on)

    if not orig_name:
        orig_name = extract_field_from_text(
            orig_text,
            [
                r'(?:Name|الاسم|اسم\s*الوكالة\s*بالخارج|اسم\s*الوكالة|اسم\s*المكتب\s*الأجنبي|وكالة\s*الدولة\s*الأجنبية)\s*[:=\-–]?\s*([^\r\n]+)',
                r'(?:foreign\s*agency\s*name|her\s*country\s*agency\s*name|origin\s*agency\s*name|foreign\s*agency|foreign\s*employment\s*agent)\s*[:=\-–]?\s*([^\r\n]+)',
            ]
        )
    data["origin_agency_name"] = orig_name

    data["origin_agency_license"] = extract_field_from_text(
        orig_text,
        [
            r'(?:License\s*No|رقم\s*الترخيص|ترخيص\s*رقم)\s*[:=\-–]?\s*([A-Za-z0-9\-_/]{2,25})',
            r'(?:license\s*(?:no|number)|license\s*#)\s*[:=\-–]?\s*([A-Za-z0-9\-_/]{2,25})',
        ]
    )

    data["origin_agency_phone"] = extract_field_from_text(
        orig_text,
        [
            r'(?:Contact\s*No|رقم\s*الاتصال|الهاتف|رقم\s*الهاتف|الجوال)\s*[:=\-–]?\s*(\+?[0-9\s\-]{7,20})',
            r'(?:contact\s*(?:no|number)?|phone\s*(?:no|number)?|telephone)\s*[:=\-–]?\s*(\+?[0-9\s\-]{7,20})',
        ]
    )

    data["origin_agency_street"] = extract_field_from_text(
        orig_text,
        [
            r'(?:Street|الشارع)\s*[:=\-–]?\s*([^\r\n]+)',
            r'(?:العنوان|الحي|address)\s*[:=\-–]?\s*([^\r\n]+)',
        ]
    )

    data["origin_agency_city"] = extract_field_from_text(
        orig_text,
        [
            r'(?:City|المدينة)\s*[:=\-–]?\s*([^\r\n]+)',
        ]
    )

    data["origin_agency_email"] = extract_field_from_text(
        orig_text,
        [
            r'(?:Email|البريد\s*الإلكتروني|البريد\s*الالكتروني|الإيميل)\s*[:=\-–]?\s*([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)',
            r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)',
        ]
    )

    # ── 5. Worker / Applicant Details ──
    work_text = sec["worker"] or text

    data["applicant_name"] = extract_field_from_text(
        work_text,
        [
            r'(?:Name|الاسم|اسم\s*العاملة\s*المنزلية|اسم\s*العامل\s*المنزلي|اسم\s*العاملة|اسم\s*العامل|اسم\s*المستقدمة|اسم\s*المستقدم)\s*[:=\-–]?\s*([^\r\n]+)',
            r'(?:worker\s*name|domestic\s*worker\s*name|applicant\s*name|name\s*of\s*worker|name\s*of\s*applicant)\s*[:=\-–]?\s*([^\r\n]+)',
            r'Worker\s*Name\s*[:=\-–]?\s*([^\r\n]+)',
            r'Applicant\s*Name\s*[:=\-–]?\s*([^\r\n]+)',
            r'Full\s*Name\s*[:=\-–]?\s*([^\r\n]+)',
        ]
    )

    data["passport_number"] = extract_field_from_text(
        work_text or text,
        [
            r'(?:Passport\s*No|رقم\s*جواز\s*السفر|رقم\s*الجواز|جواز\s*السفر)\s*[:=\-–]?\s*([A-Za-z0-9]{6,12})',
            r'(?:passport\s*(?:no|number)|passport\s*#)\s*[:=\-–]?\s*([A-Za-z0-9]{6,12})',
        ]
    )

    # ── 6. Dossier Direct Aliases (NO FAKE DEFAULTS) ──
    data["sponsor_name"] = data["employer_name"]
    data["sponsor_id"] = data["employer_id"]
    data["telephone"] = data["employer_mobile"] or data["employer_telephone"]
    data["contractor_name"] = data["recruiting_agency_name"]
    data["agency"] = data["origin_agency_name"]

    return data


# ─────────────────────────────────────────────────────────────────────────────
# 6. Whitelisted RPC Endpoints & File Resolver
# ─────────────────────────────────────────────────────────────────────────────
def _resolve_frappe_file_path(file_url):
    """Translates a Frappe file_url to physical filesystem path across OSes."""
    if not file_url:
        return None

    clean = str(file_url).lstrip("/").replace("\\", "/")
    
    # 1. Direct path exists
    if os.path.exists(clean):
        return os.path.abspath(clean)

    # 2. Extract base file name
    basename = os.path.basename(clean)

    # 3. Check public files
    pub_path = frappe.get_site_path("public", "files", basename)
    if os.path.exists(pub_path):
        return pub_path

    # 4. Check private files
    priv_path = frappe.get_site_path("private", "files", basename)
    if os.path.exists(priv_path):
        return priv_path

    # 5. Check direct get_site_path
    site_path = frappe.get_site_path(clean)
    if os.path.exists(site_path):
        return site_path

    # 6. Search within site files
    try:
        site_folder = frappe.get_site_path()
        for root, dirs, files in os.walk(site_folder):
            if basename in files:
                return os.path.join(root, basename)
    except Exception:
        pass

    return None


@frappe.whitelist()
def parse_contract_document(file_url=None, dossier_name=None, raw_text=None):
    """
    Parses employment/recruitment contract PDF using PyMuPDF + Structured Multi-line Text Engine.
    Updates Applicant Dossier fields cleanly with real extracted data.
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

    # 3. If dossier_name provided
    if not extracted_data and dossier_name and frappe.db.exists("Applicant Dossier", dossier_name):
        dos = frappe.get_doc("Applicant Dossier", dossier_name)
        if dos.attached_file:
            file_path = _resolve_frappe_file_path(dos.attached_file)
            if file_path and file_path.lower().endswith(".pdf"):
                blocks = extract_text_with_pymupdf(file_path)
                if blocks:
                    extracted_data = parse_structured_contract_text(blocks)

    if not extracted_data:
        extracted_data = parse_structured_contract_text("")

    # Update Dossier record if dossier_name is provided
    updated_fields = []
    if dossier_name and frappe.db.exists("Applicant Dossier", dossier_name):
        dos = frappe.get_doc("Applicant Dossier", dossier_name)

        field_mapping = [
            ("sponsor_name", "sponsor_name"),
            ("sponsor_id", "sponsor_id"),
            ("telephone", "telephone"),
            ("visa_number", "visa_number"),
            ("contract_number", "contract_number"),
            ("contract_date", "contract_date"),
            ("contract_end_date", "contract_end_date"),
            ("contract_duration", "contract_duration"),
            ("amount_detail", "amount_detail"),
            ("contractor_name", "contractor_name"),
            ("agency", "agency"),
            ("employer_street", "employer_street"),
            ("employer_city", "employer_city"),
            ("employer_mobile", "employer_mobile"),
            ("recruiting_agency_license", "recruiting_agency_license"),
            ("recruiting_agency_telephone", "recruiting_agency_telephone"),
            ("recruiting_agency_street", "recruiting_agency_street"),
            ("recruiting_agency_city", "recruiting_agency_city"),
            ("recruiting_agency_email", "recruiting_agency_email"),
            ("origin_agency_license", "origin_agency_license"),
            ("origin_agency_phone", "origin_agency_phone"),
            ("origin_agency_street", "origin_agency_street"),
            ("origin_agency_city", "origin_agency_city"),
            ("origin_agency_email", "origin_agency_email"),
        ]

        for ext_key, doc_field in field_mapping:
            val = extracted_data.get(ext_key)
            if val is not None and hasattr(dos, doc_field):
                setattr(dos, doc_field, val)
                updated_fields.append(doc_field)

        dos.is_parsed = 1
        dos.save(ignore_permissions=True)

        # Cross-update applicant locked contractor and state
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
        "message": f"Contract parsed successfully. Updated fields: {', '.join(updated_fields) if updated_fields else 'None'}",
        "data": extracted_data,
        "updated_fields": updated_fields
    }
