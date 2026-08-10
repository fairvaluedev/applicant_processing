# Copyright (c) 2026, Admin and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class DSR(Document):
	def after_insert(self):
		# Auto-create the 3 clearance pages linked to this DSR
		try:
			frappe.get_doc({
				"doctype": "LMS Clearance",
				"dsr": self.name
			}).insert(ignore_permissions=True)
			
			frappe.get_doc({
				"doctype": "Wakala Clearance",
				"dsr": self.name
			}).insert(ignore_permissions=True)
			
			frappe.get_doc({
				"doctype": "Injaz Clearance",
				"dsr": self.name
			}).insert(ignore_permissions=True)
		except Exception as e:
			frappe.log_error(title=f"Failed to auto-create clearances for DSR {self.name}", message=str(e))


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
