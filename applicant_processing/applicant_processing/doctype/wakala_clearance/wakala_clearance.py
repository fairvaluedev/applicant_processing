# Copyright (c) 2026, Admin and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class WakalaClearance(Document):
	def validate(self):
		if self.dsr:
			dsr_doc = frappe.get_doc("DSR", self.dsr)
			self.full_name = getattr(dsr_doc, "full_name", None) or f"{dsr_doc.first_name or ''} {dsr_doc.last_name or ''}".strip()
		elif not self.full_name:
			self.full_name = f"{self.first_name or ''} {self.last_name or ''}".strip()

	def on_update(self):
		if self.dsr:
			frappe.db.set_value("DSR", self.dsr, "wakala_status", self.status, update_modified=False)

		# Notify assigned Wakala employee if set
		if self.employee:
			self._notify_assigned_employee()

		self._recalculate_applicant()

	def on_trash(self):
		self._recalculate_applicant()

	def _recalculate_applicant(self):
		if self.dsr:
			dossier = frappe.db.get_value("DSR", self.dsr, "applicant_dossier")
			applicant = frappe.db.get_value("Applicant Dossier", dossier, "applicant") if dossier else None
			if applicant:
				from applicant_processing.applicant_processing.doctype.applicant.applicant import recalculate_applicant_state
				recalculate_applicant_state(applicant)

	def _notify_assigned_employee(self):
		from applicant_processing.applicant_processing.utils.push_api import notify_user_task

		full_name = f"{self.first_name or ''} {self.last_name or ''}".strip() or self.name
		subject = f"Wakala Clearance Task Assigned: {self.name}"
		message = (
			f"You have been assigned to Wakala Clearance task {self.name} "
			f"for Applicant {full_name}. Current status: {self.status}."
		)

		notify_user_task(
			user=self.employee,
			subject=subject,
			description=message,
			reference_doctype="Wakala Clearance",
			reference_name=self.name,
			event_type="wakala_clearance_assigned",
			payload={
				"clearance": self.name,
				"dsr": self.dsr,
				"applicant_name": full_name,
				"status": self.status,
				"assigned_to": self.employee
			}
		)
