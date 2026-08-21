# Copyright (c) 2026, Admin and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class AgencyComplaint(Document):
	def validate(self):
		if self.applicant:
			app_name = frappe.db.get_value("Applicant", self.applicant, "full_name")
			self.full_name = app_name or self.applicant

		if self.resolution_outcome and not self.resolved_at:
			if self.resolution_outcome in ("Resolved", "Returned / Free Replacement Required", "Escalated", "Dismissed"):
				self.resolved_at = now_datetime()
				if self.resolution_outcome == "Resolved":
					self.status = "Resolved"
				elif self.resolution_outcome == "Returned / Free Replacement Required":
					self.status = "Returned / Free Replacement Required"
				elif self.resolution_outcome == "Escalated":
					self.status = "Escalated to MoL / Embassy"
				elif self.resolution_outcome == "Dismissed":
					self.status = "Dismissed / Closed"

	def on_update(self):
		# Notify assigned officer if assigned
		if self.assigned_officer:
			self._notify_welfare_officer()

	def _notify_welfare_officer(self):
		from applicant_processing.applicant_processing.utils.push_api import notify_user_task

		subject = f"URGENT Complaint Assigned: {self.name} ({self.complaint_category})"
		message = (
			f"You have been assigned to Foreign Agency Complaint {self.name} for Worker {self.full_name}. "
			f"Severity: {self.severity}. Category: {self.complaint_category}."
		)

		notify_user_task(
			user=self.assigned_officer,
			subject=subject,
			description=message,
			reference_doctype="Agency Complaint",
			reference_name=self.name,
			event_type="agency_complaint_assigned",
			payload={
				"complaint": self.name,
				"applicant": self.applicant,
				"contractor": self.contractor,
				"severity": self.severity,
				"status": self.status
			}
		)
