# Copyright (c) 2026, Admin and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

# Fields to mirror from Applicant
APPLICANT_FIELDS = [
	"first_name", "middle_name", "last_name",
	"date_of_birth", "gender", "nationality",
	"email", "phone_number",
	"passport_number", "passport_expiry", "national_id",
	"highest_education", "institution", "graduation_year",
]


class CVRecord(Document):
	def before_insert(self):
		self._populate_from_applicant()

	def on_update(self):
		# Re-sync whenever the applicant link changes
		self._populate_from_applicant()

	def _populate_from_applicant(self):
		if not self.applicant:
			return
		applicant = frappe.get_doc("Applicant", self.applicant)
		for field in APPLICANT_FIELDS:
			setattr(self, field, getattr(applicant, field, None))
