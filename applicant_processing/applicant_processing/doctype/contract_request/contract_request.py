# Copyright (c) 2026, Admin and contributors
# For license information, please see license.txt

import frappe
import os
from frappe.model.document import Document

# Fields to mirror — sourced exclusively from the linked CV Record
CV_FIELDS = [
	"applicant",
	"first_name", "middle_name", "last_name", "full_name",
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

		# Block if applicant is UNFIT or in Draft/Registered state without CV
		if self.applicant and frappe.db.exists("Applicant", self.applicant):
			app = frappe.get_doc("Applicant", self.applicant)
			if app.medical_status == "UNFIT":
				frappe.throw(
					f"Cannot create Contract Request for Applicant {self.applicant} — Medical status is marked as 'UNFIT'."
				)
			if app.applicant_state in ["Draft", "Registered"]:
				frappe.throw(
					f"Cannot create Contract Request — Applicant {self.applicant} "
					f"is in '{app.applicant_state}' state. CV must be generated first."
				)

		if not self.cv_reference:
			frappe.throw("CV Reference is required.")
		cv = frappe.get_doc("CV Record", self.cv_reference)
		if not cv.file_attachment:
			frappe.throw(
				f"Cannot create Contract Request — CV Record {self.cv_reference} "
				f"does not have a generated CV PDF file. Please generate the CV first."
			)

		# Ensure applicant matches CV
		if self.applicant != cv.applicant:
			frappe.throw("Applicant does not match the CV Record's Applicant.")
		
		for field in CV_FIELDS:
			if self.meta.has_field(field):
				setattr(self, field, getattr(cv, field, None))

		if not self.full_name and self.applicant:
			self.full_name = frappe.db.get_value("Applicant", self.applicant, "full_name")

	def on_update(self):
		if self.cv_reference:
			frappe.db.set_value("CV Record", self.cv_reference, {
				"contract_request": self.name,
				"has_contract_request": 1,
				"contract_request_status": self.status
			}, update_modified=False)

		if self.applicant:
			from applicant_processing.applicant_processing.doctype.applicant.applicant import recalculate_applicant_state
			recalculate_applicant_state(self.applicant)

	def on_trash(self):
		if self.applicant:
			from applicant_processing.applicant_processing.doctype.applicant.applicant import recalculate_applicant_state
			recalculate_applicant_state(self.applicant)


import urllib.parse

@frappe.whitelist()
def send_contract_request(contract_request_name):
	cr = frappe.get_doc("Contract Request", contract_request_name)
	
	if not cr.contractor:
		frappe.throw("Please select a Contractor before sending the Contract Request.")

	# Validate Applicant readiness & medical fitness
	if cr.applicant and frappe.db.exists("Applicant", cr.applicant):
		app = frappe.get_doc("Applicant", cr.applicant)
		if app.medical_status == "UNFIT":
			frappe.throw(f"Cannot send Contract Request for Applicant {cr.applicant}: Medical status is marked as 'UNFIT'.")
		if app.applicant_state in ["Draft", "Registered"]:
			frappe.throw(f"Cannot send Contract Request for Applicant {cr.applicant}: Applicant is in '{app.applicant_state}' state. CV has not been generated yet.")

	if not cr.cv_reference:
		frappe.throw("Cannot send Contract Request: CV Reference is missing.")

	cv_file = frappe.db.get_value("CV Record", cr.cv_reference, "file_attachment")
	if not cv_file:
		frappe.throw(f"Cannot send Contract Request: CV Record {cr.cv_reference} has no generated CV PDF attachment. Please generate the CV first.")
		
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

	# Auto-advance Applicant state to 'Request Pending'
	if cr.applicant:
		app = frappe.get_doc("Applicant", cr.applicant)
		if app.applicant_state in ["Draft", "Registered", "CV Generated"]:
			app.applicant_state = "Request Pending"
			app.save(ignore_permissions=True)

	# Fetch CV File Attachment and resolve local disk path
	cv_file_url = None
	local_file_path = None
	if cr.cv_reference and frappe.db.exists("CV Record", cr.cv_reference):
		cv_file = frappe.db.get_value("CV Record", cr.cv_reference, "file_attachment")
		if cv_file and not str(cv_file).startswith("http"):
			cv_file_url = frappe.utils.get_url(cv_file)
			local_file_path = frappe.get_site_path(str(cv_file).lstrip("/"))
		elif cv_file:
			cv_file_url = cv_file

		# Auto-generate PDF document binary if local file is missing on disk
		if not local_file_path or not os.path.exists(local_file_path):
			try:
				pdf_dir = frappe.get_site_path("public", "files")
				os.makedirs(pdf_dir, exist_ok=True)
				pdf_path = os.path.join(pdf_dir, f"CV_{cr.cv_reference}.pdf")
				if not os.path.exists(pdf_path):
					pdf_bytes = frappe.get_print("CV Record", cr.cv_reference, as_pdf=True)
					with open(pdf_path, "wb") as f:
						f.write(pdf_bytes)
				local_file_path = pdf_path
				cv_file_url = frappe.utils.get_url(f"/files/CV_{cr.cv_reference}.pdf")
			except Exception as err:
				frappe.log_error(title="CV PDF Generation Warning", message=str(err))

	# Send notification via PushApi
	from applicant_processing.applicant_processing.utils.push_api import send_notification
	send_notification("contract_request_sent", {
		"contract_request": cr.name,
		"applicant": cr.applicant,
		"cv_reference": cr.cv_reference,
		"cv_file_url": cv_file_url,
		"contractor": contractor.name,
		"contact_person": contractor.contact_person,
		"phone": contractor.phone,
		"email": contractor.email,
		"whatsapp": contractor.whatsapp
	})
	
	whatsapp_num = contractor.whatsapp or contractor.phone or ""
	clean_phone = "".join(filter(str.isdigit, str(whatsapp_num)))
	applicant_name = cr.applicant or "Applicant"
	passport_num = getattr(cr, "passport_number", None)
	if cr.applicant and frappe.db.exists("Applicant", cr.applicant):
		app_data = frappe.db.get_value("Applicant", cr.applicant, ["first_name", "last_name", "passport_number"], as_dict=True)
		if app_data:
			full_n = f"{app_data.first_name or ''} {app_data.last_name or ''}".strip()
			if full_n:
				applicant_name = full_n
			if not passport_num:
				passport_num = app_data.get("passport_number")

	msg_text = (
		f"Hello {contractor.contact_person or contractor.company_name},\n\n"
		f"A new Contract Request *{cr.name}* has been sent to you for Applicant *{applicant_name}*.\n"
		f"Passport: {passport_num or 'N/A'}\n\n"
		f"Please review and confirm."
	)

	# Attempt direct Meta WhatsApp Cloud API send (dispatches direct PDF document file into WhatsApp chat)
	api_sent, api_msg = False, None
	if clean_phone:
		from applicant_processing.applicant_processing.utils.push_api import send_whatsapp_cloud_api
		cv_filename = f"CV_{applicant_name.replace(' ', '_')}.pdf"
		api_sent, api_msg = send_whatsapp_cloud_api(
			recipient_phone=clean_phone,
			message_text=msg_text,
			media_url=cv_file_url,
			local_file_path=local_file_path,
			filename=cv_filename
		)

	whatsapp_url = None
	if clean_phone:
		encoded_msg = urllib.parse.quote(msg_text)
		whatsapp_url = f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded_msg}"

	contact_info = whatsapp_num or contractor.email or contractor.phone or "No contact info"
	
	return {
		"status": "success",
		"message": f"Contract Request {cr.name} successfully sent to Contractor: {contractor.company_name} ({contact_info}).",
		"whatsapp_url": whatsapp_url,
		"whatsapp_number": clean_phone,
		"whatsapp_api_sent": api_sent,
		"whatsapp_api_message": api_msg,
		"contractor_name": contractor.company_name
	}


@frappe.whitelist()
def batch_send_contract_requests(cv_references, contractor):
	"""
	Batch dispatches contract requests:
	1. Takes a list of CV Record names (JSON array or list) and a Contractor name.
	2. For each CV, finds or creates a Contract Request.
	3. Sends the Contract Request to the contractor via Meta Cloud API / notification.
	4. Updates Applicant state to 'Request Pending'.
	"""
	import json
	if isinstance(cv_references, str):
		try:
			cv_references = json.loads(cv_references)
		except Exception:
			cv_references = [c.strip() for c in cv_references.split(",") if c.strip()]

	if not cv_references:
		frappe.throw("Please select at least one CV Record.")
	if not contractor:
		frappe.throw("Please select a Contractor.")

	results = []
	created_count = 0
	sent_count = 0
	failed_count = 0

	for cv_name in cv_references:
		try:
			if not frappe.db.exists("CV Record", cv_name):
				results.append({"cv_reference": cv_name, "status": "error", "message": "CV Record not found"})
				failed_count += 1
				continue

			cv = frappe.get_doc("CV Record", cv_name)
			applicant_name = cv.applicant

			# 1. Block if CV has no generated PDF attachment
			if not cv.file_attachment:
				failed_count += 1
				results.append({
					"cv_reference": cv_name,
					"applicant": applicant_name,
					"status": "error",
					"message": f"CV has not been generated for Applicant {applicant_name}. Please generate the CV first."
				})
				continue

			# 2. Block if Applicant is UNFIT or has not reached CV Generated state
			if applicant_name and frappe.db.exists("Applicant", applicant_name):
				app = frappe.get_doc("Applicant", applicant_name)
				if app.medical_status == "UNFIT":
					failed_count += 1
					results.append({
						"cv_reference": cv_name,
						"applicant": applicant_name,
						"status": "error",
						"message": f"Cannot send Contract Request: Applicant {applicant_name} medical status is marked as 'UNFIT'."
					})
					continue
				if app.applicant_state in ["Draft", "Registered"]:
					failed_count += 1
					results.append({
						"cv_reference": cv_name,
						"applicant": applicant_name,
						"status": "error",
						"message": f"Applicant {applicant_name} is in '{app.applicant_state}' state. CV must be generated first."
					})
					continue

			# Check if open Contract Request exists for this CV
			existing_cr = frappe.db.get_value("Contract Request", {"cv_reference": cv_name}, "name")
			if existing_cr:
				cr = frappe.get_doc("Contract Request", existing_cr)
				if cr.contractor != contractor:
					cr.contractor = contractor
					cr.save(ignore_permissions=True)
			else:
				cr = frappe.get_doc({
					"doctype": "Contract Request",
					"applicant": applicant_name,
					"cv_reference": cv_name,
					"contractor": contractor,
					"status": "Draft"
				})
				cr.insert(ignore_permissions=True)
				created_count += 1

			# Dispatch send
			send_res = send_contract_request(cr.name)
			sent_count += 1
			results.append({
				"cv_reference": cv_name,
				"contract_request": cr.name,
				"applicant": applicant_name,
				"status": "success",
				"details": send_res
			})
		except Exception as e:
			failed_count += 1
			results.append({
				"cv_reference": cv_name,
				"status": "error",
				"message": str(e)
			})

	return {
		"total": len(cv_references),
		"created_count": created_count,
		"sent_count": sent_count,
		"failed_count": failed_count,
		"results": results
	}


