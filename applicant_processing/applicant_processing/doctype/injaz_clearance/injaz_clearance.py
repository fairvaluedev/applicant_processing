# Copyright (c) 2026, Admin and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class InjazClearance(Document):
	def on_update(self):
		if self.dsr:
			frappe.db.set_value("DSR", self.dsr, "injaz_status", self.status, update_modified=False)
