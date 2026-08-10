# Copyright (c) 2026, Admin and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

# Fields to mirror — sourced exclusively from the linked CV Record
CV_FIELDS = [
	"applicant",
	"first_name", "middle_name", "last_name",
	"date_of_birth", "gender", "nationality",
	"email", "phone_number",
	"passport_number", "passport_expiry", "national_id",
	"highest_education", "institution", "graduation_year",
]


class ContractRequest(Document):
	def validate(self):
		if not self.applicant:
			if self.cv_reference:
				self.applicant = frappe.db.get_value("CV Record", self.cv_reference, "applicant")
			else:
				frappe.throw("Applicant is required.")

		# Block if applicant is still in Draft
		state = frappe.db.get_value("Applicant", self.applicant, "applicant_state")
		if state == "Draft":
			frappe.throw(
				f"Cannot create a Contract Request — the applicant "
				f"is still in Draft state."
			)

		if not self.cv_reference:
			frappe.throw("CV Reference is required.")
		cv = frappe.get_doc("CV Record", self.cv_reference)
		# Ensure applicant matches CV
		if self.applicant != cv.applicant:
			frappe.throw("Applicant does not match the CV Record's Applicant.")
		
		for field in CV_FIELDS:
			if self.meta.has_field(field):
				setattr(self, field, getattr(cv, field, None))
