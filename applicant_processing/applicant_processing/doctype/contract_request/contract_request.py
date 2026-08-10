# Copyright (c) 2026, Admin and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

# Fields to mirror — sourced exclusively from the linked CV Record
CV_FIELDS = [
	"applicant",
	"first_name", "middle_name", "last_name",
	"date_of_birth", "gender", "nationality",
	"email", "phone_number",
	"passport_number", "passport_expiry", "national_id",
	"highest_education", "institution", "graduation_year",
]


class ContractRequest(Document):
	def validate(self):
		if not self.applicant:
			if self.cv_reference:
				self.applicant = frappe.db.get_value("CV Record", self.cv_reference, "applicant")
			else:
				frappe.throw("Applicant is required.")

		# Block if applicant is still in Draft state
		state = frappe.db.get_value("Applicant", self.applicant, "applicant_state")
		if state == "Draft":
			frappe.throw(
				f"Cannot create a Contract Request — the applicant "
				f"is still in Draft state."
			)

		if not self.cv_reference:
			frappe.throw("CV Reference is required.")
		cv = frappe.get_doc("CV Record", self.cv_reference)
		# Ensure applicant matches CV
		if self.applicant != cv.applicant:
			frappe.throw("Applicant does not match the CV Record's Applicant.")
		
		for field in CV_FIELDS:
			if self.meta.has_field(field):
				setattr(self, field, getattr(cv, field, None))

	def on_update(self):
		if self.cv_reference:
			frappe.db.set_value("CV Record", self.cv_reference, {
				"contract_request": self.name,
				"has_contract_request": 1,
				"contract_request_status": self.status
			}, update_modified=False)


@frappe.whitelist()
def send_contract_request(contract_request_name):
	cr = frappe.get_doc("Contract Request", contract_request_name)
	
	if not cr.contractor:
		frappe.throw("Please select a Contractor before sending the Contract Request.")
		
	contractor = frappe.get_doc("Contractor", cr.contractor)
	
	cr.status = "Sent"
	cr.save(ignore_permissions=True)
	
	# Auto-sync link and status back to CV Record
	if cr.cv_reference:
		frappe.db.set_value("CV Record", cr.cv_reference, {
			"contract_request": cr.name,
			"has_contract_request": 1,
			"contract_request_status": "Sent"
		}, update_modified=False)

	# Send notification via PushApi
	from applicant_processing.applicant_processing.utils.push_api import send_notification
	send_notification("contract_request_sent", {
		"contract_request": cr.name,
		"applicant": cr.applicant,
		"cv_reference": cr.cv_reference,
		"contractor": contractor.name,
		"contact_person": contractor.contact_person,
		"phone": contractor.phone,
		"email": contractor.email,
		"whatsapp": contractor.whatsapp
	})
	
	contact_info = contractor.phone or contractor.email or contractor.whatsapp or "No contact info"
	return f"Contract Request {cr.name} successfully sent to Contractor: {contractor.company_name} ({contact_info})."
