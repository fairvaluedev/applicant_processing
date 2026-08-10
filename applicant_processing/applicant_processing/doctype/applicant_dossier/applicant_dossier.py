# Copyright (c) 2026, Admin and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ApplicantDossier(Document):
	def validate(self):
		self.populate_from_contract_request()

	def populate_from_contract_request(self):
		"""Populates Applicant, CV Record, Contractor, and Statuses from the selected Contract Request."""
		if not self.contract_request:
			frappe.throw("Contract Request is required to create an Applicant Dossier.")

		cr = frappe.get_doc("Contract Request", self.contract_request)

		self.applicant = cr.applicant
		self.cv_record = cr.cv_reference
		self.contract_status = cr.status
		if cr.contractor:
			self.contractor_name = cr.contractor

		if cr.applicant:
			app = frappe.get_doc("Applicant", cr.applicant)
			self.first_name = app.first_name
			self.last_name = app.last_name
			self.nationality = app.nationality
			self.passport_number = app.passport_number

		if cr.cv_reference:
			self.cv_status = frappe.db.get_value("CV Record", cr.cv_reference, "status")

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
	if not dossier.contractor_name:
		dossier.contractor_name = "Global Recruitment"
	dossier.agency = "Main Agency"
	dossier.is_parsed = 1
	
	dossier.save()
	
	return "File successfully parsed and additional fields populated."
