# Copyright (c) 2026, Admin and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class DSR(Document):
	def validate(self):
		if self.applicant_dossier:
			dossier = frappe.get_doc("Applicant Dossier", self.applicant_dossier)
			self.full_name = getattr(dossier, "full_name", None) or f"{dossier.first_name or ''} {dossier.last_name or ''}".strip()
		elif not self.full_name:
			self.full_name = f"{self.first_name or ''} {self.last_name or ''}".strip()

	def after_insert(self):
		# Auto-create the 3 clearance pages linked to this DSR
		try:
			lms = frappe.get_doc({
				"doctype": "LMS Clearance",
				"dsr": self.name
			})
			lms.insert(ignore_permissions=True)
			
			wak = frappe.get_doc({
				"doctype": "Wakala Clearance",
				"dsr": self.name
			})
			wak.insert(ignore_permissions=True)
			
			inj = frappe.get_doc({
				"doctype": "Injaz Clearance",
				"dsr": self.name
			})
			inj.insert(ignore_permissions=True)

			# Notify LMS, Wakala, and Injaz officers about new pending task
			self._notify_clearance_tasks(lms, wak, inj)

			# Recalculate linked applicant state
			self._recalculate_applicant()
		except Exception as e:
			frappe.log_error(title=f"Failed to auto-create clearances for DSR {self.name}", message=str(e))

	def on_update(self):
		self._recalculate_applicant()

	def on_trash(self):
		self._recalculate_applicant()

	def _recalculate_applicant(self):
		applicant = getattr(self, "applicant", None)
		if not applicant and self.applicant_dossier:
			applicant = frappe.db.get_value("Applicant Dossier", self.applicant_dossier, "applicant")
		if applicant:
			from applicant_processing.applicant_processing.doctype.applicant.applicant import recalculate_applicant_state
			recalculate_applicant_state(applicant)

	def _notify_clearance_tasks(self, lms_doc, wak_doc, inj_doc):
		from applicant_processing.applicant_processing.utils.push_api import notify_user_task, get_clearance_target_users

		full_name = f"{self.first_name or ''} {self.last_name or ''}".strip() or self.name

		clearance_items = [
			("LMS Clearance", lms_doc, getattr(lms_doc, "employee", None)),
			("Wakala Clearance", wak_doc, getattr(wak_doc, "employee", None)),
			("Injaz Clearance", inj_doc, getattr(inj_doc, "employee", None)),
		]

		for label, doc, employee in clearance_items:
			target_users = get_clearance_target_users(doc.doctype, employee, self.owner)
			subject = f"New {label} Task Pending for DSR {self.name}"
			message = f"A new {label} ({doc.name}) is pending for DSR {self.name} (Applicant: {full_name})."

			for user in target_users:
				notify_user_task(
					user=user,
					subject=subject,
					description=message,
					reference_doctype=doc.doctype,
					reference_name=doc.name,
					event_type="dsr_clearance_task_created",
					payload={
						"dsr": self.name,
						"clearance_doctype": doc.doctype,
						"clearance_name": doc.name,
						"applicant_name": full_name
					}
				)


def check_clearances_completed(dsr_name):
	"""
	Enforces that an Applicant (via DSR) must have completed:
	- INJAZ Clearance (injaz_status == 'Completed')
	- Wakala Clearance (wakala_status == 'Completed')
	- LMS Clearance (lms_status == 'Completed')
	before allowing Stamp, Ticket, or Departure records to be created/saved.
	"""
	if not dsr_name:
		return

	dsr = frappe.get_doc("DSR", dsr_name)

	# Check each clearance status
	lms_done = (dsr.lms_status == "Completed") or bool(frappe.db.exists("LMS Clearance", {"dsr": dsr_name, "status": "Completed"}))
	wakala_done = (dsr.wakala_status == "Completed") or bool(frappe.db.exists("Wakala Clearance", {"dsr": dsr_name, "status": "Completed"}))
	injaz_done = (dsr.injaz_status == "Completed") or bool(frappe.db.exists("Injaz Clearance", {"dsr": dsr_name, "status": "Completed"}))

	pending = []
	if not injaz_done:
		pending.append("Injaz Clearance")
	if not wakala_done:
		pending.append("Wakala Clearance")
	if not lms_done:
		pending.append("LMS Clearance")

	if pending:
		frappe.throw(
			f"Cannot proceed with Stamp / Ticket / Departure. "
			f"The following required clearance(s) are incomplete: {', '.join(pending)}. "
			f"INJAZ, Wakala, and LMS clearances must ALL be completed first."
		)
