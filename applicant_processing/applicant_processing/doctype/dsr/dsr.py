# Copyright (c) 2026, Admin and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class DSR(Document):
	def validate(self):
		if self.applicant_dossier:
			dossier = frappe.get_doc("Applicant Dossier", self.applicant_dossier)
			self.full_name = getattr(dossier, "full_name", None) or f"{dossier.first_name or ''} {dossier.last_name or ''}".strip()
			if not self.destination_country and getattr(dossier, "destination_country", None):
				self.destination_country = dossier.destination_country
		elif not self.full_name:
			self.full_name = f"{self.first_name or ''} {self.last_name or ''}".strip()

		if not self.destination_country:
			self.destination_country = "Saudi Arabia"

	def after_insert(self):
		# Auto-create clearances linked to this DSR based on destination country
		try:
			full_name = f"{self.first_name or ''} {self.last_name or ''}".strip() or self.name

			# 1. LMS Clearance is universal for all corridors
			lms = frappe.get_doc({
				"doctype": "LMS Clearance",
				"dsr": self.name
			})
			lms.insert(ignore_permissions=True)

			if self.destination_country == "Kuwait":
				# Corridor B: Kuwait Clearance Suite
				tsg = frappe.get_doc({
					"doctype": "Telesign Clearance",
					"dsr": self.name
				})
				tsg.insert(ignore_permissions=True)

				emb = frappe.get_doc({
					"doctype": "Embassy Clearance",
					"dsr": self.name,
					"destination_country": "Kuwait"
				})
				emb.insert(ignore_permissions=True)

				self._notify_clearance_tasks([
					("LMS Clearance", lms, getattr(lms, "employee", None)),
					("Telesign Clearance", tsg, getattr(tsg, "employee", None)),
					("Embassy Clearance", emb, getattr(emb, "employee", None)),
				])
			else:
				# Corridor A: Saudi Arabia Clearance Suite
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

				self._notify_clearance_tasks([
					("LMS Clearance", lms, getattr(lms, "employee", None)),
					("Wakala Clearance", wak, getattr(wak, "employee", None)),
					("Injaz Clearance", inj, getattr(inj, "employee", None)),
				])

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

	def _notify_clearance_tasks(self, clearance_items):
		from applicant_processing.applicant_processing.utils.push_api import notify_user_task, get_clearance_target_users

		full_name = f"{self.first_name or ''} {self.last_name or ''}".strip() or self.name

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
	Enforces that an Applicant (via DSR) must have completed clearances before allowing
	Stamp, Ticket, or Departure records to be created/saved.
	Supports Manager Override and dynamic multi-country corridor evaluation.
	"""
	if not dsr_name:
		return

	dsr = frappe.get_doc("DSR", dsr_name)

	# 1. Manager Override Valve: if authorized manager granted override, allow bypass
	if dsr.manager_override:
		frappe.msgprint(f"Clearance requirements bypassed via Manager Override ({dsr.override_by or 'Manager'}).", indicator="orange")
		return

	dest_country = dsr.destination_country or "Saudi Arabia"

	if dest_country == "Kuwait":
		# Kuwait Corridor Clearance Checks
		lms_done = (dsr.lms_status in ("Issued", "Completed")) or bool(frappe.db.exists("LMS Clearance", {"dsr": dsr_name, "status": ["in", ["Issued", "Completed"]]}))
		tsg_done = (dsr.telesign_status in ("Authenticated", "Completed")) or bool(frappe.db.exists("Telesign Clearance", {"dsr": dsr_name, "status": ["in", ["Authenticated", "Completed"]]}))
		emb_done = (dsr.embassy_status in ("Approved", "Completed")) or bool(frappe.db.exists("Embassy Clearance", {"dsr": dsr_name, "status": ["in", ["Approved", "Completed"]], "fee_status": "Paid"}))

		pending = []
		if not lms_done:
			pending.append("LMIS Police / Work Permit Clearance")
		if not tsg_done:
			pending.append("Telesign Online Document Authentication")
		if not emb_done:
			pending.append("Kuwait Embassy Submission & Fee Payment")

		if pending:
			frappe.throw(
				f"Cannot proceed with Stamp / Ticket / Departure for Kuwait Candidate. "
				f"The following clearance(s) are incomplete: {', '.join(pending)}. "
				f"All Kuwait clearances must be completed first or granted a Manager Override."
			)
	else:
		# Saudi Arabia Corridor Clearance Checks
		lms_done = (dsr.lms_status in ("Issued", "Completed")) or bool(frappe.db.exists("LMS Clearance", {"dsr": dsr_name, "status": ["in", ["Issued", "Completed"]]}))
		wakala_done = (dsr.wakala_status in ("Completed", "Paid")) or bool(frappe.db.exists("Wakala Clearance", {"dsr": dsr_name, "status": ["in", ["Completed", "Paid"]]}))
		injaz_done = (dsr.injaz_status == "Completed") or bool(frappe.db.exists("Injaz Clearance", {"dsr": dsr_name, "status": "Completed"}))

		pending = []
		if not injaz_done:
			pending.append("Injaz Clearance")
		if not wakala_done:
			pending.append("Wakala Clearance (Musaned Paid)")
		if not lms_done:
			pending.append("LMS Clearance")

		if pending:
			frappe.throw(
				f"Cannot proceed with Stamp / Ticket / Departure for Saudi Candidate. "
				f"The following clearance(s) are incomplete: {', '.join(pending)}. "
				f"INJAZ, Wakala, and LMS clearances must ALL be completed first or granted a Manager Override."
			)


@frappe.whitelist()
def grant_clearance_override(dsr_name, reason):
	"""
	Allows a System Manager or Authorized Supervisor to grant an exception override
	for a DSR, allowing ticketing/stamping despite incomplete clearance steps.
	"""
	if not dsr_name or not reason:
		frappe.throw("DSR Name and Override Reason are mandatory.")

	dsr = frappe.get_doc("DSR", dsr_name)
	dsr.manager_override = 1
	dsr.override_by = frappe.session.user
	dsr.override_at = now_datetime()
	dsr.override_reason = reason
	dsr.save(ignore_permissions=True)

	# Add comment in audit timeline
	dsr.add_comment("Comment", f"<b>Manager Clearance Override Granted</b> by {frappe.session.user}. Reason: {reason}")

	return {"message": "Clearance override successfully granted and logged.", "status": "success"}
