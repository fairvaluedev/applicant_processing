# Copyright (c) 2026, Admin and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LMSClearance(Document):
	def validate(self):
		if self.dsr:
			dsr_doc = frappe.get_doc("DSR", self.dsr)
			self.full_name = getattr(dsr_doc, "full_name", None) or f"{dsr_doc.first_name or ''} {dsr_doc.last_name or ''}".strip()
		elif not self.full_name:
			self.full_name = f"{self.first_name or ''} {self.last_name or ''}".strip()

		# Issued status requires issued_on date
		if self.status == "Issued" and not self.issued_on:
			frappe.throw("Issued On date is required when status is Issued.")

	def on_update(self):
		if self.dsr:
			frappe.db.set_value("DSR", self.dsr, "lms_status", self.status, update_modified=False)

		# Sync employee permissions when employee is assigned
		if self.employee:
			self._sync_employee_permissions()
			self._notify_assigned_employee()

		self._recalculate_applicant()

	def on_trash(self):
		# Clean up any user permissions created for this LMS
		self._cleanup_employee_permissions()
		self._recalculate_applicant()

	def _recalculate_applicant(self):
		if self.dsr:
			dossier = frappe.db.get_value("DSR", self.dsr, "applicant_dossier")
			applicant = frappe.db.get_value("Applicant Dossier", dossier, "applicant") if dossier else None
			if applicant:
				from applicant_processing.applicant_processing.doctype.applicant.applicant import recalculate_applicant_state
				recalculate_applicant_state(applicant)

	def _sync_employee_permissions(self):
		"""
		Create User Permissions so the assigned employee can access:
		  - This LMS Clearance document
		  - The linked DSR Ticket (if exists)
		  - The linked DSR Departure (if exists)
		"""
		if not self.employee or not self.dsr:
			return

		# Clean up old permissions first (in case employee changed)
		self._cleanup_employee_permissions()

		user = self.employee

		# 1. Permission on this LMS Clearance
		_create_user_permission_if_missing(user, "LMS Clearance", self.name)

		# 2. Permission on linked DSR Ticket(s)
		tickets = frappe.get_all("DSR Ticket", filters={"dsr": self.dsr}, pluck="name")
		for ticket_name in tickets:
			_create_user_permission_if_missing(user, "DSR Ticket", ticket_name)

		# 3. Permission on linked DSR Departure(s)
		departures = frappe.get_all("DSR Departure", filters={"dsr": self.dsr}, pluck="name")
		for dep_name in departures:
			_create_user_permission_if_missing(user, "DSR Departure", dep_name)

	def _cleanup_employee_permissions(self):
		"""Remove User Permissions previously created by this LMS assignment."""
		if not self.dsr:
			return

		# Find old employee from DB (before current save)
		old_employee = frappe.db.get_value("LMS Clearance", self.name, "employee")
		if not old_employee:
			return

		# Remove permission for this LMS Clearance
		_remove_user_permission(old_employee, "LMS Clearance", self.name)

		# Remove permissions for linked Ticket/Departure
		tickets = frappe.get_all("DSR Ticket", filters={"dsr": self.dsr}, pluck="name")
		for ticket_name in tickets:
			_remove_user_permission(old_employee, "DSR Ticket", ticket_name)

		departures = frappe.get_all("DSR Departure", filters={"dsr": self.dsr}, pluck="name")
		for dep_name in departures:
			_remove_user_permission(old_employee, "DSR Departure", dep_name)

	def _notify_assigned_employee(self):
		from applicant_processing.applicant_processing.utils.push_api import notify_user_task

		full_name = f"{self.first_name or ''} {self.last_name or ''}".strip() or self.name
		subject = f"LMS Clearance Task Assigned: {self.name}"
		message = (
			f"You have been assigned to LMS Clearance task {self.name} "
			f"for Applicant {full_name}. Current status: {self.status}."
		)

		notify_user_task(
			user=self.employee,
			subject=subject,
			description=message,
			reference_doctype="LMS Clearance",
			reference_name=self.name,
			event_type="lms_clearance_assigned",
			payload={
				"clearance": self.name,
				"dsr": self.dsr,
				"applicant_name": full_name,
				"status": self.status,
				"assigned_to": self.employee
			}
		)


def _create_user_permission_if_missing(user, allow_doctype, for_value):
	"""Create a User Permission if it doesn't already exist."""
	exists = frappe.db.exists("User Permission", {
		"user": user,
		"allow": allow_doctype,
		"for_value": for_value
	})
	if not exists:
		frappe.get_doc({
			"doctype": "User Permission",
			"user": user,
			"allow": allow_doctype,
			"for_value": for_value,
			"apply_to_all_doctypes": 0
		}).insert(ignore_permissions=True)


def _remove_user_permission(user, allow_doctype, for_value):
	"""Remove a User Permission if it exists."""
	perms = frappe.get_all("User Permission", filters={
		"user": user,
		"allow": allow_doctype,
		"for_value": for_value
	}, pluck="name")
	for p in perms:
		frappe.delete_doc("User Permission", p, ignore_permissions=True)
