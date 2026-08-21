# Copyright (c) 2026, Admin and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import today, getdate


class LMSClearance(Document):
	def validate(self):
		if self.dsr:
			dsr_doc = frappe.get_doc("DSR", self.dsr)
			self.full_name = getattr(dsr_doc, "full_name", None) or f"{dsr_doc.first_name or ''} {dsr_doc.last_name or ''}".strip()
		elif not self.full_name:
			self.full_name = f"{self.first_name or ''} {self.last_name or ''}".strip()

		# Issued status requires issued_on date
		if self.status == "Issued" and not self.issued_on:
			self.issued_on = today()

		# If missing data was requested, set request date if missing
		if self.missing_data_requested and not self.missing_data_requested_at:
			self.missing_data_requested_at = today()

	def on_update(self):
		if self.dsr:
			frappe.db.set_value("DSR", self.dsr, "lms_status", self.status, update_modified=False)

		# Sync employee permissions when employee is assigned
		if self.employee:
			self._sync_employee_permissions()
			self._notify_assigned_employee()

		# Auto-post agency commission on status == "Issued"
		if self.status == "Issued":
			self._auto_post_agency_commission()

		self._recalculate_applicant()

	def on_trash(self):
		# Clean up any user permissions created for this LMS
		self._cleanup_employee_permissions()
		self._recalculate_applicant()

	def _auto_post_agency_commission(self):
		"""
		Auto-posts the foreign partner agency's configured commission to the financial ledger
		when LMS / Work Permit is Issued.
		If this candidate is fulfilling a 3-month free replacement guarantee, commission is $0.
		"""
		if not self.dsr:
			return

		# Check if commission has already been logged on this LMS Clearance
		has_comm = any(row.category == "Agency Commission" for row in (self.financials or []))
		if has_comm:
			return

		dsr_doc = frappe.get_doc("DSR", self.dsr)
		dossier_name = dsr_doc.applicant_dossier
		if not dossier_name:
			return

		dossier = frappe.get_doc("Applicant Dossier", dossier_name)
		applicant_name = dossier.applicant
		contractor_name = dossier.contractor_name

		if not contractor_name:
			return

		# Check if this applicant is a 3-month free replacement
		is_replacement = bool(frappe.db.exists("Agency Complaint", {"replacement_applicant": applicant_name}))

		if is_replacement:
			comm_amount = 0.0
			currency = "SAR"
			desc = f"3-Month Return Guarantee Free Replacement for {contractor_name} ($0.00 Commission)"
		else:
			contractor = frappe.get_doc("Contractor", contractor_name)
			comm_amount = getattr(contractor, "default_commission_amount", 1000.0) or 1000.0
			currency = getattr(contractor, "default_commission_currency", "SAR") or "SAR"
			desc = f"Recruitment Commission for {contractor_name} upon LMIS Issuance"

		# Add to child table
		self.append("financials", {
			"entry_type": "Income",
			"category": "Agency Commission",
			"amount": comm_amount,
			"description": desc,
			"date": today()
		})
		self.save(ignore_permissions=True)

		# Also mirror onto Applicant document if exists
		if applicant_name:
			app_doc = frappe.get_doc("Applicant", applicant_name)
			app_has_comm = any(row.category == "Agency Commission" for row in (app_doc.income_expense_logs or []))
			if not app_has_comm:
				app_doc.append("income_expense_logs", {
					"entry_type": "Income",
					"category": "Agency Commission",
					"amount": comm_amount,
					"description": desc,
					"date": today()
				})
				app_doc.save(ignore_permissions=True)

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

		self._cleanup_employee_permissions()
		user = self.employee

		_create_user_permission_if_missing(user, "LMS Clearance", self.name)

		tickets = frappe.get_all("DSR Ticket", filters={"dsr": self.dsr}, pluck="name")
		for ticket_name in tickets:
			_create_user_permission_if_missing(user, "DSR Ticket", ticket_name)

		departures = frappe.get_all("DSR Departure", filters={"dsr": self.dsr}, pluck="name")
		for dep_name in departures:
			_create_user_permission_if_missing(user, "DSR Departure", dep_name)

	def _cleanup_employee_permissions(self):
		"""Remove User Permissions previously created by this LMS assignment."""
		if not self.dsr:
			return

		old_employee = frappe.db.get_value("LMS Clearance", self.name, "employee")
		if not old_employee:
			return

		_remove_user_permission(old_employee, "LMS Clearance", self.name)

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
	perms = frappe.get_all("User Permission", filters={
		"user": user,
		"allow": allow_doctype,
		"for_value": for_value
	}, pluck="name")
	for p in perms:
		frappe.delete_doc("User Permission", p, ignore_permissions=True)
