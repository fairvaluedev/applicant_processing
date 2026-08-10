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
