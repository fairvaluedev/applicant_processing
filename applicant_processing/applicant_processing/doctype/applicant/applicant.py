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
    "phone_number": "Phone Number",
    "nationality": "Nationality",
    "gender": "Gender",
    "religion": "Religion",
    "marital_status": "Marital Status",
    "children": "Children (Count)",
}

# Required to move from Draft to Registered
REGISTRATION_REQUIRED_FIELDS = {
    "date_of_birth": "Date of Birth",
    "passport_number": "Passport Number",
    "highest_education": "Highest Education Level",
    "labour_id": "Labour ID",
    "contact_person_name": "Contact Person Name",
    "contact_person_phone": "Contact Person Phone",
    "coc_status": "COC Status",
    "exam_date": "Exam Date",
    "medical_status": "Medical Status",
    "medical_expiry_date": "Medical Request Expiration Date",
}


class Applicant(Document):
    def validate(self):
        # 1. Set full name
        self._set_full_name()
        # 2. Mandatory data to go to draft state (always required)
        self._check_missing(DRAFT_REQUIRED_FIELDS)
        # 3. Calculate computed fields (Exam remaining days, Medical remaining days)
        self._calculate_computed_days()
        # 4. Calculate lifecycle step and progress percentage
        self._calculate_state_progress()
        # 5. Record cancelling user and timestamp if cancelled
        if self.applicant_state == "Cancelled":
            if not self.cancelled_by:
                self.cancelled_by = frappe.session.user
            if not self.cancelled_at:
                self.cancelled_at = frappe.utils.now_datetime()
        # 6. Flexible data hygiene & formatting
        self._validate_pragmatic_data()
        # 7. Recompute financial totals directly from income_expense_logs
        self._recalculate_totals()

    def _set_full_name(self):
        parts = [self.first_name, self.middle_name, self.last_name]
        self.full_name = " ".join([p.strip() for p in parts if p and p.strip()]).strip()

    def _calculate_computed_days(self):
        """Computes remaining days for COC Exam and Medical validity."""
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


@frappe.whitelist()
def generate_cv(applicant_name):
    """
    Generates a PDF CV for the applicant using the system CV template.
    Blocking condition: applicant must be at least Registered.
    Advances applicant state to CV Generated if currently Registered.
    """
    import os
    import frappe.utils
    from frappe.utils.pdf import get_pdf
    from frappe.utils.file_manager import save_file

    applicant = frappe.get_doc("Applicant", applicant_name)

    if not applicant._has_reached("Registered"):
        frappe.throw(
            f"Cannot generate CV — applicant must be at least 'Registered'. "
            f"Current state: '{applicant.applicant_state}'"
        )

    # Build template context
    full_name = " ".join(filter(None, [
        applicant.first_name,
        getattr(applicant, "middle_name", None),
        applicant.last_name
    ]))

    generated_date = frappe.utils.now_datetime().strftime("%d %b %Y, %H:%M")

    context = {
        "applicant_name":    applicant_name,
        "cv_name":           "(pending)",
        "full_name":         full_name,
        "applicant_state":   applicant.applicant_state,
        "generated_date":    generated_date,
        "nationality":       applicant.nationality or "",
        "gender":            applicant.gender or "",
        "date_of_birth":     str(applicant.date_of_birth) if applicant.date_of_birth else "",
        "email":             applicant.email or "",
        "phone_number":      applicant.phone_number or "",
        "alternate_phone":   applicant.alternate_phone or "",
        "address_line_1":    applicant.address_line_1 or "",
        "city":              applicant.city or "",
        "country":           applicant.country or "",
        "passport_number":   applicant.passport_number or "",
        "passport_expiry":   str(applicant.passport_expiry) if applicant.passport_expiry else "",
        "national_id":       applicant.national_id or "",
        "highest_education": applicant.highest_education or "",
        "institution":       applicant.institution or "",
        "graduation_year":   applicant.graduation_year or "",
        "current_employer":  applicant.current_employer or "",
        "years_of_experience": applicant.years_of_experience or "",
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

    # Create CV Record
    cv_record = frappe.get_doc({
        "doctype":        "CV Record",
        "applicant":      applicant_name,
        "template":       "cv_template.html",
        "generated_by":   frappe.session.user,
        "generated_date": frappe.utils.now_datetime(),
        "status":         "Final",
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

    # Advance applicant state (only if they haven't passed this phase)
    if applicant.applicant_state == "Registered":
        applicant.applicant_state = "CV Generated"
        applicant.save(ignore_permissions=True)

    return {
        "cv_record": cv_record.name,
        "file_url":  saved_file.file_url,
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
def restore_applicant(applicant_name):
    """
    Restores a cancelled applicant back to their active lifecycle stage.
    """
    applicant = frappe.get_doc("Applicant", applicant_name)
    if applicant.applicant_state != "Cancelled":
        frappe.throw("Applicant is not in Cancelled state.")

    # Reset cancellation audit fields
    applicant.applicant_state = "Registered"  # Temporary baseline for recalculation
    applicant.cancel_remarks = None
    applicant.cancelled_at = None
    applicant.cancelled_by = None
    applicant.save(ignore_permissions=True)

    # Automatically compute true stage from downstream documents
    new_state = recalculate_applicant_state(applicant_name)
    return f"Applicant {applicant_name} restored to state '{new_state}'."


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

    # 4. Check Processing (Step 6) - when employees are assigned to LMS/Wakala/Injaz clearances or clearances are underway/completed
    elif dsr_names and (
        frappe.db.sql("""
            SELECT name FROM `tabLMS Clearance` WHERE dsr IN %(dsrs)s AND employee IS NOT NULL AND employee != ''
            UNION
            SELECT name FROM `tabWakala Clearance` WHERE dsr IN %(dsrs)s AND employee IS NOT NULL AND employee != ''
            UNION
            SELECT name FROM `tabInjaz Clearance` WHERE dsr IN %(dsrs)s AND employee IS NOT NULL AND employee != ''
            UNION
            SELECT name FROM `tabLMS Clearance` WHERE dsr IN %(dsrs)s AND status IN ('In Progress', 'Completed')
            UNION
            SELECT name FROM `tabWakala Clearance` WHERE dsr IN %(dsrs)s AND status IN ('In Progress', 'Completed')
            UNION
            SELECT name FROM `tabInjaz Clearance` WHERE dsr IN %(dsrs)s AND status IN ('In Progress', 'Completed')
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
        app.applicant_state = target_state
        app.save(ignore_permissions=True)

    return target_state