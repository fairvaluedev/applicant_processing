# Copyright (c) 2026, Admin and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ApplicantDossier(Document):
	def validate(self):
		self.auto_fetch_linked_cv_and_contract()

	def auto_fetch_linked_cv_and_contract(self):
		"""Auto-populates the latest CV Record and Contract Request for the selected Applicant."""
		if not self.applicant:
			return

		if not self.cv_record:
			latest_cv = frappe.db.get_value(
				"CV Record",
				{"applicant": self.applicant},
				"name",
				order_by="creation desc"
			)
			if latest_cv:
				self.cv_record = latest_cv

		if not self.contract_request:
			latest_cr = frappe.db.get_value(
				"Contract Request",
				{"applicant": self.applicant},
				"name",
				order_by="creation desc"
			)
			if latest_cr:
				self.contract_request = latest_cr

	def before_submit(self):
		missing = []
		if not self.sponsor_name: missing.append("Sponsor Name")
		if not self.amount_detail: missing.append("Amount Detail")
		if not self.contractor_name: missing.append("Contractor Name")
		if not self.agency: missing.append("Agency")
		
		if missing:
			frappe.throw(
				"Cannot submit Dossier. Please parse a file or fill in the missing fields: " 
				+ ", ".join(missing)
			)
		

@frappe.whitelist()
def parse_dossier_file(dossier_name):
	dossier = frappe.get_doc("Applicant Dossier", dossier_name)
	
	if not dossier.attached_file:
		frappe.throw("Please attach a file before parsing.")
		
	if dossier.is_parsed:
		frappe.throw("This dossier has already been parsed. Manual edits will not be overwritten.")
		
	# MOCK PARSER logic
	dossier.sponsor_name = "Mock Sponsor Ltd."
	dossier.amount_detail = 5000.00
	dossier.contractor_name = "Global Recruitment"
	dossier.agency = "Main Agency"
	dossier.is_parsed = 1
	
	dossier.save()
	
	return "File successfully parsed and additional fields populated."
