# Copyright (c) 2026, Admin and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today, date_diff


class ApplicantDossier(Document):
	def validate(self):
		self.populate_from_contract_request()
		self._calculate_contract_elapsed_days()
		self._calculate_contract_end_date()

	def _calculate_contract_end_date(self):
		"""Calculates contract end date by adding contract duration to contract date."""
		if self.contract_date and not self.contract_end_date:
			from applicant_processing.applicant_processing.utils.contract_parser import calculate_contract_end_date
			self.contract_end_date = calculate_contract_end_date(self.contract_date, self.contract_duration or "2 Years")

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
			self.full_name = getattr(app, "full_name", None) or f"{app.first_name or ''} {app.last_name or ''}".strip()
			self.nationality = app.nationality
			self.passport_number = app.passport_number
			self.destination_country = getattr(app, "destination_country", None) or "Saudi Arabia"

		if cr.cv_reference:
			self.cv_status = frappe.db.get_value("CV Record", cr.cv_reference, "status")

	def _calculate_contract_elapsed_days(self):
		"""Calculates elapsed days since contract arrival."""
		ref_date = self.contract_date or self.creation
		if ref_date:
			try:
				self.contract_elapsed_days = max(0, date_diff(getdate(today()), getdate(ref_date)))
			except Exception:
				self.contract_elapsed_days = 0

	def after_insert(self):
		# Auto-create corresponding DSR if not exists
		self._auto_create_dsr()
		self._recalculate_applicant()

	def on_update(self):
		self._auto_create_dsr()
		self._recalculate_applicant()

	def on_trash(self):
		self._recalculate_applicant()

	def _auto_create_dsr(self):
		if not self.name:
			return
		if not frappe.db.exists("DSR", {"applicant_dossier": self.name}):
			try:
				dsr = frappe.get_doc({
					"doctype": "DSR",
					"applicant_dossier": self.name,
					"destination_country": self.destination_country or "Saudi Arabia",
					"first_name": self.first_name,
					"last_name": self.last_name,
					"full_name": self.full_name,
					"passport_number": self.passport_number,
					"sponsor_name": self.sponsor_name,
					"contractor_name": self.contractor_name,
					"agency": self.agency,
				})
				dsr.insert(ignore_permissions=True)
			except Exception as e:
				frappe.log_error(title=f"Failed to auto-create DSR for Dossier {self.name}", message=str(e))

	def _recalculate_applicant(self):
		applicant = self.applicant
		if not applicant and self.contract_request:
			applicant = frappe.db.get_value("Contract Request", self.contract_request, "applicant")
		if applicant:
			from applicant_processing.applicant_processing.doctype.applicant.applicant import recalculate_applicant_state
			recalculate_applicant_state(applicant)

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

	from applicant_processing.applicant_processing.utils.contract_parser import parse_contract_document
	res = parse_contract_document(file_url=dossier.attached_file, dossier_name=dossier_name)

	return res.get("message", "File successfully parsed and additional fields populated.")
