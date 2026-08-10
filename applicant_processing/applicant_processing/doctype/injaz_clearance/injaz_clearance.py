# Copyright (c) 2026, Admin and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class InjazClearance(Document):
	def on_update(self):
		if self.dsr:
			frappe.db.set_value("DSR", self.dsr, "injaz_status", self.status, update_modified=False)

		# Notify assigned Injaz employee if set
		if self.employee:
			self._notify_assigned_employee()

	def _notify_assigned_employee(self):
		from applicant_processing.applicant_processing.utils.push_api import notify_user_task

		full_name = f"{self.first_name or ''} {self.last_name or ''}".strip() or self.name
		subject = f"Injaz Clearance Task Assigned: {self.name}"
		message = (
			f"You have been assigned to Injaz Clearance task {self.name} "
			f"for Applicant {full_name}. Current status: {self.status}."
		)

		notify_user_task(
			user=self.employee,
			subject=subject,
			description=message,
			reference_doctype="Injaz Clearance",
			reference_name=self.name,
			event_type="injaz_clearance_assigned",
			payload={
				"clearance": self.name,
				"dsr": self.dsr,
				"applicant_name": full_name,
				"status": self.status,
				"assigned_to": self.employee
			}
		)
