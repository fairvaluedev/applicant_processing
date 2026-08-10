# Copyright (c) 2026, Admin and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from applicant_processing.applicant_processing.doctype.dsr.dsr import check_clearances_completed


class DSRTicket(Document):
	def validate(self):
		if self.dsr:
			check_clearances_completed(self.dsr)

	def on_update(self):
		if self.dsr:
			frappe.db.set_value("DSR", self.dsr, "ticket_status", self.status, update_modified=False)
