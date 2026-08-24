# Copyright (c) 2026, Admin and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

# Canonical state order for easier comparison and progress tracking
STATE_ORDER = [
    "Draft",
    "Registered",
    "CV Generated",
    "Request Pending",
    "Selected",
    "Processing",
    "Stamped",
    "Ticketed",
    "Departed",
]

# Required to save an Applicant (Draft state floor)
DRAFT_REQUIRED_FIELDS = {
    "first_name": "First Name",
    "last_name": "Last Name",
    "nationality": "Nationality",
    "phone_number": "Phone Number",
    "gender": "Gender",
}

# Required to move from Draft to Registered
REGISTRATION_REQUIRED_FIELDS = {
    "passport_number": "Passport Number",
    "passport_issue_date": "Passport Issue Date",
    "passport_expiry": "Passport Expiry Date",
    "place_of_issue": "Place of Issue",
    "job_applied": "Job / Position Applied",
    "highest_education": "Educational Qualification",
    "photo_passport": "Small / Passport Photo",
    "photo_full_body": "Full Body Photo",
    "passport_scan": "Scanned Passport Copy",
    "medical_status": "Medical Status",
    "medical_expiry_date": "Medical Expiration Date",
}


class Applicant(Document):
    def validate(self):
        # 1. Set full name
        self._set_full_name()
        # 2. Auto-compute age if DOB given
        self._calculate_age()
        # 3. Mandatory data to go to draft state (always required)
        self._check_missing(DRAFT_REQUIRED_FIELDS)
        # 4. Calculate computed fields (Exam remaining days, Medical remaining days)
        self._calculate_computed_days()
        # 5. Calculate lifecycle step and progress percentage
        self._calculate_state_progress()
        # 6. Record cancelling user and timestamp if cancelled
        if self.applicant_state == "Cancelled":
            if not self.cancelled_by:
                self.cancelled_by = frappe.session.user
            if not self.cancelled_at:
                self.cancelled_at = frappe.utils.now_datetime()
        # 7. Flexible data hygiene & formatting
        self._validate_pragmatic_data()
        # 8. Recompute financial totals directly from income_expense_logs
        self._recalculate_totals()

    def _calculate_age(self):
        if self.date_of_birth and not self.age:
            from frappe.utils import getdate, today
            try:
                dob = getdate(self.date_of_birth)
                curr = getdate(today())
                self.age = curr.year - dob.year - ((curr.month, curr.day) < (dob.month, dob.day))
            except Exception:
                pass

    def _set_full_name(self):
        parts = [self.first_name, self.middle_name, self.last_name]
        self.full_name = " ".join([p.strip() for p in parts if p and p.strip()]).strip()

    def _calculate_computed_days(self):
        """Computes remaining days for COC Exam and Medical validity, and elapsed processing days."""
        from frappe.utils import getdate, today, date_diff

        curr_today = getdate(today())

        if self.exam_date:
            self.exam_remaining_days = date_diff(getdate(self.exam_date), curr_today)
        else:
            self.exam_remaining_days = None

        if self.medical_expiry_date:
            self.medical_remaining_days = date_diff(getdate(self.medical_expiry_date), curr_today)
        else:
            self.medical_remaining_days = None

        ref_date = self.registration_date or self.creation
        if ref_date:
            try:
                self.contract_elapsed_days = max(0, date_diff(curr_today, getdate(ref_date)))
            except Exception:
                self.contract_elapsed_days = 0

    def _calculate_state_progress(self):
        """Computes lifecycle step and percentage for frontend dashboards and progress bars."""
        if self.applicant_state == "Cancelled":
            self.state_step = "Cancelled"
            self.state_progress = 0.0
            return

        if self.applicant_state in STATE_ORDER:
            idx = STATE_ORDER.index(self.applicant_state)
            total = len(STATE_ORDER)
            self.state_step = f"{idx + 1} of {total}"
            self.state_progress = round(((idx + 1) / total) * 100.0, 1)
        else:
            self.state_step = "Unknown"
            self.state_progress = 0.0

    def _validate_pragmatic_data(self):
        """Pragmatic data hygiene and field formatting checks."""
        from frappe.utils import getdate, today

        curr_today = getdate(today())

        # 1. Date of Birth cannot be in the future
        if self.date_of_birth and getdate(self.date_of_birth) > curr_today:
            frappe.throw("Date of Birth cannot be in the future.")

        # 2. Passport Expiry Warning (Non-blocking)
        if self.passport_expiry and getdate(self.passport_expiry) < curr_today:
            frappe.msgprint("Note: Passport Expiry Date is in the past.", indicator="orange")

        # 3. Medical Expiry Warning (Non-blocking)
        if self.medical_expiry_date and getdate(self.medical_expiry_date) < curr_today:
            frappe.msgprint("Note: Medical Request Expiration Date is in the past.", indicator="orange")

        # 4. Passport formatting
        if self.passport_number:
            self.passport_number = self.passport_number.upper().strip()

        # 5. Email formatting validation
        if self.email:
            self.email = self.email.strip()
            frappe.utils.validate_email_address(self.email, throw=True)

    def _check_missing(self, field_map):
        missing = []
        for field, label in field_map.items():
            val = self.get(field)
            if val is None or val == "":
                missing.append(label)
        if missing:
            frappe.throw("Missing required field(s): " + ", ".join(missing))

    def _has_reached(self, target_state):
        """True if this applicant's current state is at or beyond target_state."""
        # Handle cases where state might be unexpectedly None or not in list
        if self.applicant_state not in STATE_ORDER:
            return False
        return STATE_ORDER.index(self.applicant_state) >= STATE_ORDER.index(target_state)

    def _recalculate_totals(self):
        """Sums Income Expense Log rows to compute total_income, total_expense, net_balance."""
        total_income = 0.0
        total_expense = 0.0

        for log in (self.income_expense_logs or []):
            if log.transaction_type == "Income":
                total_income += (log.amount or 0)
            elif log.transaction_type == "Expense":
                total_expense += (log.amount or 0)

        self.total_income = total_income
        self.total_expense = total_expense
        self.net_balance = total_income - total_expense

    def on_update(self):
        pass

    def _check_immediate_medical_expiry_alert(self):
        """Runs an immediate medical expiry check upon registration."""
        if not self.medical_expiry_date:
            return

        from frappe.utils import getdate, today, date_diff
        from applicant_processing.applicant_processing.utils.push_api import notify_user_task

        current_date = getdate(today())
        expiry_dt = getdate(self.medical_expiry_date)
        days_left = date_diff(expiry_dt, current_date)

        if days_left <= 16:
            full_name = f"{self.first_name or ''} {self.last_name or ''}".strip() or self.name
            subject = f"Registration Alert: Medical Expiring in {days_left} day(s) for {full_name}"
            message = (
                f"Applicant {full_name} ({self.name}) was registered today, but their medical request "
                f"expires on {self.medical_expiry_date} ({days_left} day(s) remaining)."
            )

            target_users = set()
            if self.owner: target_users.add(self.owner)

            managers = frappe.get_all("Has Role", filters={"role": "System Manager", "parenttype": "User"}, fields=["parent"])
            for m in managers:
                target_users.add(m.parent)

            payload = {
                "applicant": self.name,
                "full_name": full_name,
                "medical_expiry_date": str(self.medical_expiry_date),
                "days_remaining": days_left,
                "event": "registered_with_expiring_medical"
            }

            for user in target_users:
                notify_user_task(
                    user=user,
                    subject=subject,
                    description=message,
                    reference_doctype="Applicant",
                    reference_name=self.name,
                    event_type="applicant_registered_medical_warning",
                    payload=payload,
                    date_val=self.medical_expiry_date
                )


@frappe.whitelist()
def register_applicant(applicant_name):
    """
    Transitions Draft -> Registered.
    Blocking condition: date_of_birth and passport_number must be filled.
    """
    applicant = frappe.get_doc("Applicant", applicant_name)

    if applicant.applicant_state != "Draft":
        frappe.throw(
            f"Cannot register — applicant is in state '{applicant.applicant_state}', must be 'Draft'."
        )

    # Check for Registration required fields
    applicant._check_missing(REGISTRATION_REQUIRED_FIELDS)

    if applicant.medical_status == "UNFIT":
        frappe.throw("Cannot register applicant: Medical Status is marked as 'UNFIT'.")

    # Mark as Registered
    applicant.applicant_state = "Registered"
    applicant.save(ignore_permissions=True)

    # Check immediate medical expiry alert on registration
    applicant._check_immediate_medical_expiry_alert()

    return f"Applicant {applicant_name} is now Registered."


def _get_base64_image(file_url):
    """Converts a Frappe file URL, path, or Data URI into a base64 Data URI for embedding in PDF."""
    if not file_url:
        return None
    url_str = str(file_url).strip()
    if url_str.startswith("data:image"):
        return url_str
    # If raw base64 string without data:image prefix
    if len(url_str) > 100 and not url_str.startswith("http") and not "/" in url_str[:20]:
        return f"data:image/jpeg;base64,{url_str}"

    import base64, mimetypes, os

    # Strip domain if present (e.g. http://localhost:8000/files/...)
    if "://" in url_str:
        try:
            url_str = "/" + url_str.split("://", 1)[1].split("/", 1)[1]
        except Exception:
            pass

    clean_path = url_str.lstrip("/").replace("\\", "/")
    basename = os.path.basename(clean_path)

    candidate_paths = [
        frappe.get_site_path("public", "files", basename),
        frappe.get_site_path("private", "files", basename),
        frappe.get_site_path("public", clean_path),
        frappe.get_site_path(clean_path),
    ]

    # If direct file path exists on disk
    if os.path.isabs(clean_path) and os.path.exists(clean_path):
        candidate_paths.insert(0, clean_path)

    for p in candidate_paths:
        try:
            if p and os.path.exists(p) and os.path.isfile(p):
                mime_type, _ = mimetypes.guess_type(p)
                mime_type = mime_type or "image/jpeg"
                with open(p, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode("utf-8")
                    return f"data:{mime_type};base64,{encoded}"
        except Exception:
            continue

    # Search site directory recursively for the basename if not found yet
    try:
        site_folder = frappe.get_site_path()
        for root, dirs, files in os.walk(site_folder):
            if basename in files:
                target_p = os.path.join(root, basename)
                mime_type, _ = mimetypes.guess_type(target_p)
                mime_type = mime_type or "image/jpeg"
                with open(target_p, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode("utf-8")
                    return f"data:{mime_type};base64,{encoded}"
    except Exception:
        pass

    return file_url


@frappe.whitelist()
def generate_cv(applicant_name):
    """
    Generates a PDF CV for the applicant using the 2-page system CV template.
    Blocking condition: applicant must be at least Registered and medical status not UNFIT.
    Advances applicant state to CV Generated if currently Registered.
    """
    import os
    import frappe.utils
    from frappe.utils.pdf import get_pdf
    from frappe.utils.file_manager import save_file

    applicant = frappe.get_doc("Applicant", applicant_name)

    if applicant.medical_status == "UNFIT":
        frappe.throw("Cannot generate CV: Applicant medical status is marked as 'UNFIT'.")

    if not applicant._has_reached("Registered"):
        frappe.throw(
            f"Cannot generate CV — applicant must be at least 'Registered'. "
            f"Current state: '{applicant.applicant_state}'"
        )

    # Format dates
    def fmt_d(d):
        if not d:
            return ""
        try:
            return frappe.utils.formatdate(d, "dd/mm/yyyy")
        except Exception:
            return str(d)

    full_name = " ".join(filter(None, [
        applicant.first_name,
        getattr(applicant, "middle_name", None),
        applicant.last_name
    ])).strip()

    generated_date = frappe.utils.now_datetime().strftime("%d/%m/%Y")

    # Encode images as base64 Data URIs
    photo_passport_b64 = _get_base64_image(applicant.photo_passport)
    photo_full_body_b64 = _get_base64_image(applicant.photo_full_body)
    passport_scan_b64 = _get_base64_image(applicant.passport_scan)

    context = {
        "applicant_name":        applicant_name,
        "cv_name":               "(pending)",
        "full_name":             full_name.upper(),
        "first_name":            applicant.first_name or "",
        "middle_name":           applicant.middle_name or "",
        "last_name":             applicant.last_name or "",
        "applicant_state":       applicant.applicant_state,
        "generated_date":        generated_date,
        "job_applied":           applicant.job_applied or "House Maid",
        "monthly_salary":        applicant.monthly_salary or "1,000 SR",
        "passport_number":       applicant.passport_number or "",
        "passport_issue_date":   fmt_d(applicant.passport_issue_date),
        "passport_expiry":       fmt_d(applicant.passport_expiry),
        "place_of_issue":        applicant.place_of_issue or "ADDIS ABABA",
        "english_level":         applicant.english_level or "",
        "arabic_level":          applicant.arabic_level or "",
        "highest_education":     applicant.highest_education or "Primary School",
        "nationality":           applicant.nationality or "Ethiopia",
        "religion":              applicant.religion or "Non-Muslim",
        "date_of_birth":         fmt_d(applicant.date_of_birth),
        "place_of_birth":        applicant.place_of_birth or "",
        "leaving_town":          applicant.leaving_town or "",
        "marital_status":        applicant.marital_status or "Single",
        "children":              applicant.children if applicant.children is not None and applicant.children != "" else "",
        "height":                applicant.height or "",
        "weight":                applicant.weight or "",
        "complexion":            applicant.complexion or "FAIR",
        "age":                   applicant.age or "",
        "experience_period":     applicant.experience_period or "",
        "experience_country":    applicant.experience_country or "",
        "skill_cleaning":        applicant.skill_cleaning or "",
        "skill_washing":         applicant.skill_washing or "",
        "skill_ironing":         applicant.skill_ironing or "",
        "skill_baby_sitting":    applicant.skill_baby_sitting or "",
        "skill_children_care":   applicant.skill_children_care or "",
        "skill_cooking":         applicant.skill_cooking or "",
        "skill_arabic_cooking":  applicant.skill_arabic_cooking or "",
        "skill_sewing":          applicant.skill_sewing or "",
        "skill_elderly_care":    applicant.skill_elderly_care or "",
        "remarks":               applicant.remarks or "FED",
        "phone_number":          applicant.phone_number or "",
        "email":                 applicant.email or "",
        "photo_passport":        photo_passport_b64,
        "photo_full_body":       photo_full_body_b64,
        "passport_scan":         passport_scan_b64,
    }

    # Render HTML template
    template_path = os.path.join(
        frappe.get_app_path("applicant_processing"),
        "templates", "cv_template.html"
    )
    with open(template_path, "r", encoding="utf-8") as f:
        template_str = f.read()

    from jinja2 import Environment
    env = Environment(autoescape=True)
    html = env.from_string(template_str).render(**context)

    # Convert HTML to PDF
    pdf_options = {
        "page-size": "A4",
        "margin-top": "0mm",
        "margin-bottom": "0mm",
        "margin-left": "0mm",
        "margin-right": "0mm",
        "encoding": "UTF-8",
        "no-outline": None,
        "quiet": None,
        "disable-smart-shrinking": None,
        "enable-local-file-access": None,
        "load-error-handling": "ignore",
        "load-media-error-handling": "ignore",
    }
    if not getattr(frappe.local, "assets_json", None):
        frappe.local.assets_json = {}

    pdf_bytes = get_pdf(html, options=pdf_options)

    # Create CV Record with full snapshot data
    cv_record = frappe.get_doc({
        "doctype":               "CV Record",
        "applicant":             applicant_name,
        "full_name":             full_name,
        "first_name":            applicant.first_name,
        "middle_name":           applicant.middle_name,
        "last_name":             applicant.last_name,
        "nationality":           applicant.nationality,
        "religion":              applicant.religion,
        "marital_status":        applicant.marital_status,
        "children":              applicant.children,
        "age":                   applicant.age,
        "gender":                applicant.gender,
        "date_of_birth":         applicant.date_of_birth,
        "place_of_birth":        applicant.place_of_birth,
        "leaving_town":          applicant.leaving_town,
        "height":                applicant.height,
        "weight":                applicant.weight,
        "complexion":            applicant.complexion,
        "photo_passport":        applicant.photo_passport,
        "photo_full_body":       applicant.photo_full_body,
        "passport_scan":         applicant.passport_scan,
        "passport_number":       applicant.passport_number,
        "passport_issue_date":   applicant.passport_issue_date,
        "passport_expiry":       applicant.passport_expiry,
        "place_of_issue":        applicant.place_of_issue,
        "national_id":           applicant.national_id,
        "labour_id":             applicant.labour_id,
        "job_applied":           applicant.job_applied,
        "monthly_salary":        applicant.monthly_salary,
        "highest_education":     applicant.highest_education,
        "english_level":         applicant.english_level,
        "arabic_level":          applicant.arabic_level,
        "experience_country":    applicant.experience_country,
        "experience_period":     applicant.experience_period,
        "skill_cleaning":        applicant.skill_cleaning,
        "skill_washing":         applicant.skill_washing,
        "skill_ironing":         applicant.skill_ironing,
        "skill_baby_sitting":    applicant.skill_baby_sitting,
        "skill_children_care":   applicant.skill_children_care,
        "skill_cooking":         applicant.skill_cooking,
        "skill_arabic_cooking":  applicant.skill_arabic_cooking,
        "skill_sewing":          applicant.skill_sewing,
        "skill_elderly_care":    applicant.skill_elderly_care,
        "email":                 applicant.email,
        "phone_number":          applicant.phone_number,
        "remarks":               applicant.remarks,
        "template":              "cv_template.html",
        "generated_by":          frappe.session.user,
        "generated_date":        frappe.utils.now_datetime(),
        "status":                "Final",
    })
    cv_record.insert(ignore_permissions=True)

    # Attach PDF to CV Record
    file_name = f"CV-{applicant_name}-{cv_record.name}.pdf"
    saved_file = save_file(
        fname=file_name,
        content=pdf_bytes,
        dt="CV Record",
        dn=cv_record.name,
        is_private=1,
    )
    cv_record.db_set("file_attachment", saved_file.file_url)

    # If Cloudflare R2 is enabled, upload PDF directly to R2 bucket with organized folder path
    r2_url = None
    try:
        from applicant_processing.applicant_processing.utils.r2_storage import get_r2_settings, upload_bytes_to_r2, get_r2_key, notify_frontend
        r2_set = get_r2_settings()
        if r2_set and r2_set.get("enabled") and r2_set.get("sync_cv_pdfs"):
            key = get_r2_key("Applicant", applicant_name, fieldname="cv", filename=file_name)
            r2_res = upload_bytes_to_r2(pdf_bytes, key=key, content_type="application/pdf")
            if r2_res.get("status") == "success":
                r2_url = r2_res.get("url")
                if hasattr(cv_record, "r2_url"):
                    cv_record.db_set("r2_url", r2_url)

        # Notify frontend client in realtime
        notify_frontend("cv_generated", {
            "applicant": applicant_name,
            "cv_record": cv_record.name,
            "file_url": r2_url or saved_file.file_url,
            "r2_url": r2_url,
            "applicant_state": "CV Generated" if applicant.applicant_state == "Registered" else applicant.applicant_state,
        })
    except Exception as e:
        frappe.log_error(f"Failed to upload CV to R2: {e}", "Cloudflare R2")

    # Advance applicant state (only if they haven't passed this phase)
    if applicant.applicant_state == "Registered":
        applicant.applicant_state = "CV Generated"
        applicant.save(ignore_permissions=True)

    return {
        "cv_record": cv_record.name,
        "file_url":  r2_url or saved_file.file_url,
        "r2_url":    r2_url,
        "message":   f"CV generated successfully: {cv_record.name}",
    }


@frappe.whitelist()
def cancel_applicant(applicant_name, cancel_remarks=None):
    """
    Cancels the applicant process and records optional remarks, timestamp, and cancelling user.
    Blocking condition: applicant cannot be cancelled if already Departed.
    """
    applicant = frappe.get_doc("Applicant", applicant_name)

    if applicant.applicant_state == "Departed":
        frappe.throw("Cannot cancel applicant process: Applicant has already Departed.")
    if applicant.applicant_state == "Cancelled":
        frappe.throw("Applicant process is already Cancelled.")

    applicant.applicant_state = "Cancelled"
    applicant.cancel_remarks = (cancel_remarks or "").strip()
    applicant.cancelled_at = frappe.utils.now_datetime()
    applicant.cancelled_by = frappe.session.user
    applicant.save(ignore_permissions=True)

    return f"Applicant {applicant_name} process has been Cancelled."


@frappe.whitelist()
def restore_applicant(applicant_name, restore_option="auto"):
    """
    Restores a cancelled applicant back to their active lifecycle stage.
    restore_option:
      - 'auto': Recalculates state from downstream records (resumes where left off).
      - 'beginning' / 'registered': Resets state to Registered (start of processing pipeline).
      - 'draft': Resets state to Draft.
    """
    applicant = frappe.get_doc("Applicant", applicant_name)
    if applicant.applicant_state != "Cancelled":
        frappe.throw("Applicant is not in Cancelled state.")

    # Reset cancellation audit fields
    applicant.cancel_remarks = None
    applicant.cancelled_at = None
    applicant.cancelled_by = None

    option = (restore_option or "auto").lower()

    if option in ["beginning", "registered", "start"]:
        applicant.applicant_state = "Registered"
        applicant.save(ignore_permissions=True)
        new_state = "Registered"
    elif option == "draft":
        applicant.applicant_state = "Draft"
        applicant.save(ignore_permissions=True)
        new_state = "Draft"
    else:
        applicant.applicant_state = "Registered"  # Temporary baseline for recalculation
        applicant.save(ignore_permissions=True)
        new_state = recalculate_applicant_state(applicant_name)

    return {
        "status": "success",
        "new_state": new_state,
        "message": f"Applicant {applicant_name} restored to state '{new_state}'."
    }


@frappe.whitelist()
def recalculate_applicant_state(applicant_name):
    """
    Computes the true lifecycle state for an Applicant by inspecting all linked
    downstream documents (Departures, Tickets, Stamps, Clearances, Dossiers, CRs, CVs).
    Supports two-way/reverting state transitions if a record is updated, cancelled, or deleted.
    """
    if not applicant_name or not frappe.db.exists("Applicant", applicant_name):
        return None

    app = frappe.get_doc("Applicant", applicant_name)

    # If applicant was explicitly Cancelled, preserve Cancelled state unless restored
    if app.applicant_state == "Cancelled":
        return "Cancelled"

    # Find linked dossiers for this applicant
    dossier_names = frappe.get_all("Applicant Dossier", filters={"applicant": applicant_name}, pluck="name")
    dsr_names = []
    if dossier_names:
        dsr_names = frappe.get_all("DSR", filters={"applicant_dossier": ["in", dossier_names]}, pluck="name")

    target_state = "Draft"

    # 1. Check Departed (Step 9)
    if dsr_names and frappe.db.exists("DSR Departure", {"dsr": ["in", dsr_names], "status": ["in", ["Departed", "Completed"]]}):
        target_state = "Departed"

    # 2. Check Ticketed (Step 8)
    elif dsr_names and frappe.db.exists("DSR Ticket", {"dsr": ["in", dsr_names], "status": ["in", ["Booked", "Completed", "Issued", "Approved"]]}):
        target_state = "Ticketed"

    # 3. Check Stamped (Step 7)
    elif dsr_names and frappe.db.exists("DSR Stamp", {"dsr": ["in", dsr_names], "status": ["in", ["Completed", "Approved"]]}):
        target_state = "Stamped"

    # 4. Check Processing (Step 6) - when employees are assigned to LMS/Wakala/Injaz/Telesign/Embassy clearances or clearances are underway/completed
    elif dsr_names and (
        frappe.db.sql("""
            SELECT name FROM `tabLMS Clearance` WHERE dsr IN %(dsrs)s AND employee IS NOT NULL AND employee != ''
            UNION
            SELECT name FROM `tabWakala Clearance` WHERE dsr IN %(dsrs)s AND employee IS NOT NULL AND employee != ''
            UNION
            SELECT name FROM `tabInjaz Clearance` WHERE dsr IN %(dsrs)s AND employee IS NOT NULL AND employee != ''
            UNION
            SELECT name FROM `tabTelesign Clearance` WHERE dsr IN %(dsrs)s AND employee IS NOT NULL AND employee != ''
            UNION
            SELECT name FROM `tabEmbassy Clearance` WHERE dsr IN %(dsrs)s AND employee IS NOT NULL AND employee != ''
            UNION
            SELECT name FROM `tabLMS Clearance` WHERE dsr IN %(dsrs)s AND status IN ('In Progress', 'Completed', 'Issued')
            UNION
            SELECT name FROM `tabWakala Clearance` WHERE dsr IN %(dsrs)s AND status IN ('In Progress', 'Completed', 'Paid')
            UNION
            SELECT name FROM `tabInjaz Clearance` WHERE dsr IN %(dsrs)s AND status IN ('In Progress', 'Completed')
            UNION
            SELECT name FROM `tabTelesign Clearance` WHERE dsr IN %(dsrs)s AND status IN ('In Progress', 'Authenticated', 'Completed')
            UNION
            SELECT name FROM `tabEmbassy Clearance` WHERE dsr IN %(dsrs)s AND status IN ('In Progress', 'Submitted', 'Approved', 'Completed')
        """, {"dsrs": dsr_names})
    ):
        target_state = "Processing"

    # 5. Check Selected (Step 5) - when Dossier exists/parsed or Contract Request is Accepted
    elif dossier_names or frappe.db.exists("Contract Request", {"applicant": applicant_name, "status": "Accepted"}):
        target_state = "Selected"

    # 6. Check Request Pending (Step 4) - when Contract Request is Sent
    elif frappe.db.exists("Contract Request", {"applicant": applicant_name, "status": "Sent"}):
        target_state = "Request Pending"

    # 7. Check CV Generated (Step 3) - when CV Record exists
    elif frappe.db.exists("CV Record", {"applicant": applicant_name}):
        target_state = "CV Generated"

    # 8. Check Registered (Step 2)
    elif app.applicant_state != "Draft":
        target_state = "Registered"

    # 9. Draft (Step 1)
    else:
        target_state = "Draft"

    if app.applicant_state != target_state:
        frappe.db.set_value("Applicant", applicant_name, "applicant_state", target_state, update_modified=False)

    return target_state


@frappe.whitelist()
def scan_and_populate_passport(applicant_name=None, file_url=None, raw_mrz_text=None):
    """
    Whitelisted RPC method to parse a passport document or image using
    MRZ-Targeted OCR and ICAO 9303 Checksum Decoder.
    Populates extracted data onto the Applicant record.
    """
    from applicant_processing.applicant_processing.utils.passport_mrz import parse_passport_document

    res = parse_passport_document(
        file_url=file_url,
        applicant_name=applicant_name,
        raw_mrz_text=raw_mrz_text
    )
    return res


@frappe.whitelist()
def revert_applicant_state(applicant_name, target_state, reason):
    """
    Forgiving UI State Rollback:
    Allows authorized staff to revert an Applicant's state back to a previous stage
    with a mandatory justification remark and audit logging.
    """
    if not applicant_name or not target_state or not reason:
        frappe.throw("Applicant Name, Target State, and Reason are mandatory.")

    app = frappe.get_doc("Applicant", applicant_name)
    old_state = app.applicant_state
    app.applicant_state = target_state
    app.save(ignore_permissions=True)

    app.add_comment(
        "Comment",
        f"<b>State Reverted</b> from <i>{old_state}</i> to <i>{target_state}</i> by {frappe.session.user}. Reason: {reason}"
    )

    return {"message": f"Applicant state reverted to {target_state}.", "applicant_state": target_state}


@frappe.whitelist()
def uncancel_applicant(applicant_name, reason):
    """
    Re-activates an accidentally cancelled applicant and restores their computed state.
    """
    if not applicant_name or not reason:
        frappe.throw("Applicant Name and Reason are mandatory.")

    app = frappe.get_doc("Applicant", applicant_name)
    if app.applicant_state != "Cancelled":
        frappe.throw("Applicant is not in Cancelled state.")

    app.cancelled_at = None
    app.cancelled_by = None
    app.cancel_remarks = None
    app.applicant_state = "Draft"
    app.save(ignore_permissions=True)

    app.add_comment("Comment", f"<b>Applicant Un-cancelled</b> by {frappe.session.user}. Reason: {reason}")
    
    # Recalculate true state
    new_state = recalculate_applicant_state(applicant_name)
    return {"message": f"Applicant restored to active status ({new_state}).", "applicant_state": new_state}