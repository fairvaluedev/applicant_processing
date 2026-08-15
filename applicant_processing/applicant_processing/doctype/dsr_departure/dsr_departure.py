# Copyright (c) 2026, Admin and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from applicant_processing.applicant_processing.doctype.dsr.dsr import check_clearances_completed


class DSRDeparture(Document):
	def validate(self):
		if self.dsr:
			check_clearances_completed(self.dsr)
			dsr_doc = frappe.get_doc("DSR", self.dsr)
			self.full_name = getattr(dsr_doc, "full_name", None) or f"{dsr_doc.first_name or ''} {dsr_doc.last_name or ''}".strip()
		elif not self.full_name:
			self.full_name = f"{self.first_name or ''} {self.last_name or ''}".strip()

		# Medical 2 validation
		if self.medical_2_result == "Fail":
			if not self.medical_2_remark:
				frappe.throw("Medical 2 Remark is required when Medical 2 result is Fail.")
			if self.status == "Departed":
				frappe.throw("Cannot deport / depart applicant: Medical 2 result is Fail.")

	def after_insert(self):
		self._sync_lms_employee_permission()

	def on_update(self):
		if self.dsr:
			frappe.db.set_value("DSR", self.dsr, "departure_status", self.status, update_modified=False)
		self._sync_lms_employee_permission()
		self._recalculate_applicant()

	def on_trash(self):
		if self.dsr:
			frappe.db.set_value("DSR", self.dsr, "departure_status", "Pending", update_modified=False)
		self._recalculate_applicant()

	def _sync_lms_employee_permission(self):
		"""Ensure assigned LMS employee has User Permission for this Departure document."""
		if not self.dsr:
			return
		lms_employee = frappe.db.get_value("LMS Clearance", {"dsr": self.dsr}, "employee")
		if lms_employee:
			from applicant_processing.applicant_processing.doctype.lms_clearance.lms_clearance import _create_user_permission_if_missing
			_create_user_permission_if_missing(lms_employee, "DSR Departure", self.name)

	def _recalculate_applicant(self):
		if self.dsr:
			dossier = frappe.db.get_value("DSR", self.dsr, "applicant_dossier")
			applicant = frappe.db.get_value("Applicant Dossier", dossier, "applicant") if dossier else None
			if applicant:
				from applicant_processing.applicant_processing.doctype.applicant.applicant import recalculate_applicant_state
				recalculate_applicant_state(applicant)
