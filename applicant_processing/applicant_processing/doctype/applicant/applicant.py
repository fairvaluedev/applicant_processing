# Copyright (c) 2026, Admin and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

# Canonical state order for easier comparison
STATE_ORDER = [
    "Draft",
    "Registered",
    "CV Generated",
    "Contract Requested",
    "Dossier Submitted",
]

# Required to save an Applicant (Draft state floor)
DRAFT_REQUIRED_FIELDS = {
    "first_name": "First Name",
    "last_name": "Last Name",
    "phone_number": "Phone Number",
    "nationality": "Nationality",
}

# Required to move from Draft to Registered
REGISTRATION_REQUIRED_FIELDS = {
    "date_of_birth": "Date of Birth",
    "passport_number": "Passport Number",
}


class Applicant(Document):
    def validate(self):
        # 1. Mandatory data to go to draft state (always required)
        self._check_missing(DRAFT_REQUIRED_FIELDS)
        # 2. Sync fee rows to income/expense log on each save
        self._sync_income_expense_logs()
        # 3. Recompute financial totals
        self._recalculate_totals()

    def _check_missing(self, field_map):
        missing = [label for field, label in field_map.items() if not self.get(field)]
        if missing:
            frappe.throw("Missing required field(s): " + ", ".join(missing))

    def _has_reached(self, target_state):
        """True if this applicant's current state is at or beyond target_state."""
        # Handle cases where state might be unexpectedly None or not in list
        if self.applicant_state not in STATE_ORDER:
            return False
        return STATE_ORDER.index(self.applicant_state) >= STATE_ORDER.index(target_state)

    def _sync_income_expense_logs(self):
        """
        Keeps the Income Expense Log child table in sync with the Fees table.

        Strategy (Option B — log immediately on row creation):
        - Every fee row produces exactly one auto-generated log entry
          (identified by source_fee_row == fee row name).
        - On save we compare the current fee rows against existing auto entries:
            * New fee rows → append a new log entry.
            * Modified fee rows (amount/direction/type) → update the existing log entry.
            * Deleted fee rows → remove the orphaned log entry.
        - Manual entries (source_doctype == "Manual" or source_fee_row is blank)
          are never touched.
        """
        import frappe.utils

        # Build a dict of current fee rows keyed by their child-table row name.
        # New (unsaved) rows will have a blank name; we handle those below.
        current_fees = {}
        for fee in (self.fees or []):
            if fee.name:
                current_fees[fee.name] = fee

        # Build a dict of existing AUTO log entries keyed by source_fee_row
        auto_logs = {}
        for log in (self.income_expense_logs or []):
            if log.source_fee_row:
                auto_logs[log.source_fee_row] = log

        # ── 1. Update or create entries for every current fee row ──
        for fee_row_name, fee in current_fees.items():
            description = f"{fee.fee_type} – auto"
            date_val = fee.payment_date or frappe.utils.today()
            txn_type = fee.direction  # "Income" or "Expense"

            if fee_row_name in auto_logs:
                # Update existing log entry if anything changed
                log = auto_logs[fee_row_name]
                log.transaction_type = txn_type
                log.amount = fee.amount or 0
                log.date = date_val
                log.description = description
                log.source_doctype = "Applicant Fee"
            else:
                # Append a new auto log entry
                self.append("income_expense_logs", {
                    "transaction_type": txn_type,
                    "amount": fee.amount or 0,
                    "date": date_val,
                    "description": description,
                    "source_doctype": "Applicant Fee",
                    "source_fee_row": fee_row_name,
                })

        # ── 2. Remove log entries whose fee row no longer exists ──
        self.income_expense_logs = [
            log for log in (self.income_expense_logs or [])
            if not log.source_fee_row or log.source_fee_row in current_fees
        ]

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

    # Mark as Registered
    applicant.applicant_state = "Registered"
    applicant.save(ignore_permissions=True)

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
        "enable-local-file-access": None,
    }
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