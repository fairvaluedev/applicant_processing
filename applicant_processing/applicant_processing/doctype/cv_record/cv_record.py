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

@frappe.whitelist()
def share_cv(cv_name, contractors, channel):
	import json
	if isinstance(contractors, str):
		contractors = json.loads(contractors)
		
	cv = frappe.get_doc("CV Record", cv_name)
	
	if cv.status not in ["Final", "Shared"]:
		frappe.throw("CV must be in Final state before sharing.")
		
	added = 0
	for contractor in contractors:
		cv.append("share_log", {
			"contractor": contractor,
			"channel": channel,
			"shared_by": frappe.session.user,
			"shared_date": frappe.utils.now_datetime(),
			"status": "Sent"
		})
		added += 1
		
	if added > 0:
		cv.status = "Shared"
		cv.sharing_status = "Fully Shared"
		cv.save(ignore_permissions=True)
		
	return f"CV successfully shared with {added} contractor(s) via {channel}."
