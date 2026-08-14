import frappe
import os
import requests
from frappe.utils import today, date_diff, add_days, getdate, now_datetime


def _dispatch_webhook(event_type, data):
	"""Internal worker that sends the HTTP POST webhook."""
	try:
		config = frappe.get_single("Notification Config")
		if not config.enabled or not config.push_api_url:
			return
		if "example.com" in config.push_api_url:
			return

		headers = {}
		if config.push_api_key:
			headers["Authorization"] = f"Bearer {config.push_api_key}"

		payload = {
			"event_type": event_type,
			"data": data,
			"timestamp": now_datetime().isoformat()
		}

		response = requests.post(config.push_api_url, json=payload, headers=headers, timeout=3)
		response.raise_for_status()
	except Exception as e:
		frappe.log_error(title=f"Push API Failed: {event_type}", message=str(e))


def send_notification(event_type, data):
	"""Dispatches HTTP POST webhook payload asynchronously so desk UI never freezes."""
	try:
		config = frappe.get_single("Notification Config")
		if not config.enabled or not config.push_api_url or "example.com" in config.push_api_url:
			return

		# Enqueue asynchronously in background
		frappe.enqueue(
			"applicant_processing.applicant_processing.utils.push_api._dispatch_webhook",
			queue="short",
			event_type=event_type,
			data=data,
			now=frappe.flags.in_test
		)
	except Exception:
		pass



def upload_media_to_whatsapp(file_path, token, phone_number_id):
	"""Uploads a local PDF file to Meta WhatsApp Media API and returns media_id."""
	try:
		if not file_path or not os.path.exists(file_path):
			return None
		
		url = f"https://graph.facebook.com/v20.0/{phone_number_id}/media"
		headers = {
			"Authorization": f"Bearer {token}"
		}
		
		with open(file_path, "rb") as f:
			files = {
				"file": (os.path.basename(file_path), f, "application/pdf"),
				"messaging_product": (None, "whatsapp"),
				"type": (None, "document")
			}
			res = requests.post(url, headers=headers, files=files, timeout=30)
			if res.status_code == 200:
				return res.json().get("id")
			else:
				frappe.log_error(title="Meta Media Upload Error", message=res.text)
	except Exception as e:
		frappe.log_error(title="Upload Media to WhatsApp Failed", message=str(e))
	return None


def send_whatsapp_cloud_api(recipient_phone, message_text, media_url=None, local_file_path=None, filename=None, template_name="hello_world"):
	"""
	Dispatches a direct WhatsApp Cloud API message using Meta's Graph API.
	Uploads local PDF files directly via Meta Media API or sends public media URLs (type: 'document').
	"""
	try:
		config = frappe.get_single("Notification Config")
		if hasattr(config, "whatsapp_enabled") and not config.whatsapp_enabled:
			return False, "WhatsApp API is disabled in Notification Config."

		token = getattr(config, "whatsapp_access_token", None) or frappe.conf.get("whatsapp_access_token")
		phone_number_id = getattr(config, "whatsapp_phone_number_id", None) or frappe.conf.get("whatsapp_phone_number_id")

		if not token or not phone_number_id:
			return False, "WhatsApp Access Token and Phone Number ID must be configured in Notification Config."

		clean_phone = "".join(filter(str.isdigit, str(recipient_phone)))
		if not clean_phone:
			return False, "Recipient phone number is invalid."

		url = f"https://graph.facebook.com/v20.0/{phone_number_id}/messages"
		headers = {
			"Authorization": f"Bearer {token}",
			"Content-Type": "application/json"
		}

		# 1. Upload local PDF binary to Meta Media API if local_file_path is provided
		media_id = None
		if local_file_path and os.path.exists(local_file_path):
			media_id = upload_media_to_whatsapp(local_file_path, token, phone_number_id)

		# 2. Dispatch PDF Document file directly into WhatsApp chat thread
		if media_id:
			payload_doc = {
				"messaging_product": "whatsapp",
				"recipient_type": "individual",
				"to": clean_phone,
				"type": "document",
				"document": {
					"id": media_id,
					"caption": message_text,
					"filename": filename or "Applicant_CV.pdf"
				}
			}
			res_doc = requests.post(url, json=payload_doc, headers=headers, timeout=15)
			res_doc_data = res_doc.json()

			if res_doc.status_code == 200 and "messages" in res_doc_data:
				msg_id = res_doc_data["messages"][0].get("id")
				return True, f"PDF Document sent successfully via Meta WhatsApp API (ID: {msg_id})"

		elif media_url and media_url.startswith("http") and "localhost" not in media_url:
			payload_doc = {
				"messaging_product": "whatsapp",
				"recipient_type": "individual",
				"to": clean_phone,
				"type": "document",
				"document": {
					"link": media_url,
					"caption": message_text,
					"filename": filename or "Applicant_CV.pdf"
				}
			}
			res_doc = requests.post(url, json=payload_doc, headers=headers, timeout=15)
			res_doc_data = res_doc.json()

			if res_doc.status_code == 200 and "messages" in res_doc_data:
				msg_id = res_doc_data["messages"][0].get("id")
				return True, f"PDF Document sent successfully via Meta WhatsApp API (ID: {msg_id})"

		# Fallback: Send direct text message if no document binary available
		payload_text = {
			"messaging_product": "whatsapp",
			"recipient_type": "individual",
			"to": clean_phone,
			"type": "text",
			"text": {
				"preview_url": False,
				"body": message_text
			}
		}
		res_txt = requests.post(url, json=payload_text, headers=headers, timeout=15)
		res_txt_data = res_txt.json()

		if res_txt.status_code == 200 and "messages" in res_txt_data:
			msg_id = res_txt_data["messages"][0].get("id")
			return True, f"WhatsApp Message Sent (ID: {msg_id})"

		error_msg = res_txt_data.get("error", {}).get("message") or res_txt.text
		frappe.log_error(title="WhatsApp API Send Failed", message=f"Phone: {clean_phone}\nError: {error_msg}")
		return False, f"Meta API Error: {error_msg}"

	except Exception as e:
		err_str = str(e)
		frappe.log_error(title="WhatsApp Cloud API Exception", message=err_str)
		return False, f"Connection Error: {err_str}"


def get_clearance_target_users(clearance_doctype, assigned_employee=None, owner=None):
	"""
	Determines target user(s) for clearance task notifications:
	1. Explicitly assigned employee
	2. Users with role matching the stage (e.g. 'LMS Officer', 'Wakala Officer', 'Injaz Officer')
	3. Document owner
	4. Fallback to System Managers
	"""
	users = set()
	if assigned_employee:
		users.add(assigned_employee)

	role_names = []
	if "LMS" in clearance_doctype:
		role_names = ["LMS Officer", "LMS User", "LMS Manager"]
	elif "Wakala" in clearance_doctype:
		role_names = ["Wakala Officer", "Wakala User", "Wakala Manager"]
	elif "Injaz" in clearance_doctype:
		role_names = ["Injaz Officer", "Injaz User", "Injaz Manager"]

	if role_names:
		matching_users = frappe.get_all(
			"Has Role",
			filters={"role": ["in", role_names], "parenttype": "User"},
			pluck="parent"
		)
		for u in matching_users:
			users.add(u)

	if owner:
		users.add(owner)

	if not users:
		managers = frappe.get_all(
			"Has Role",
			filters={"role": "System Manager", "parenttype": "User"},
			pluck="parent"
		)
		for m in managers:
			users.add(m)

	return list(users)


def notify_user_task(user, subject, description, reference_doctype, reference_name, event_type, payload, date_val=None):
	"""
	Creates:
	1. In-app ToDo task assigned to user (if open ToDo does not already exist)
	2. In-app Notification Log bell icon alert for user
	3. Outbound PushApi webhook call
	"""
	if not user or not frappe.db.exists("User", user):
		managers = frappe.get_all("Has Role", filters={"role": "System Manager", "parenttype": "User"}, fields=["parent"])
		user = managers[0].parent if managers else "Administrator"

	# 1. Create ToDo task if open ToDo doesn't exist for this reference & user
	existing_todo = frappe.db.exists("ToDo", {
		"reference_type": reference_doctype,
		"reference_name": reference_name,
		"allocated_to": user,
		"status": "Open"
	})

	if not existing_todo:
		try:
			todo = frappe.get_doc({
				"doctype": "ToDo",
				"allocated_to": user,
				"description": description,
				"reference_type": reference_doctype,
				"reference_name": reference_name,
				"date": date_val or today(),
				"priority": "High",
				"status": "Open"
			})
			todo.insert(ignore_permissions=True)
		except Exception as e:
			frappe.log_error(title=f"Failed to create ToDo for {user}", message=str(e))

	# 2. Create Notification Log (Top-Right Bell Icon in Desk)
	try:
		nlog = frappe.get_doc({
			"doctype": "Notification Log",
			"for_user": user,
			"subject": subject,
			"email_content": description,
			"document_type": reference_doctype,
			"document_name": reference_name,
			"type": "Alert"
		})
		nlog.insert(ignore_permissions=True)
	except Exception as e:
		frappe.log_error(title=f"Failed to create Notification Log for {user}", message=str(e))

	# 3. Dispatch PushApi webhook
	send_notification(event_type, payload)


def check_medical_expirations():
	"""
	Daily Scheduler Task:
	Checks all active applicants (EXCLUDING 'Departed' and 'Cancelled').
	If medical_expiry_date is <= 16 days from today, sends targeted ToDo and Notification Log alerts to:
	- Registering Officer (applicant.owner)
	- LMS Officer (lms_clearance.employee / LMS users)
	- Wakala Officer (wakala_clearance.employee / Wakala users)
	- Injaz Officer (injaz_clearance.employee / Injaz users)
	- System Manager Admins
	"""
	current_date = getdate(today())
	target_date = add_days(current_date, 16)

	applicants = frappe.db.sql("""
		SELECT
			app.name,
			app.first_name,
			app.last_name,
			app.owner,
			app.medical_expiry_date,
			app.applicant_state,
			lms.employee AS lms_employee,
			wak.employee AS wakala_employee,
			inj.employee AS injaz_employee
		FROM `tabApplicant` app
		LEFT JOIN `tabApplicant Dossier` dos ON app.name = dos.applicant
		LEFT JOIN `tabDSR` dsr ON dos.name = dsr.applicant_dossier
		LEFT JOIN `tabLMS Clearance` lms ON dsr.name = lms.dsr
		LEFT JOIN `tabWakala Clearance` wak ON dsr.name = wak.dsr
		LEFT JOIN `tabInjaz Clearance` inj ON dsr.name = inj.dsr
		WHERE app.applicant_state NOT IN ('Departed', 'Cancelled')
		  AND app.medical_expiry_date IS NOT NULL
		  AND app.medical_expiry_date <= %s
	""", (target_date,), as_dict=True)

	for app in applicants:
		expiry_dt = getdate(app.medical_expiry_date)
		days_left = date_diff(expiry_dt, current_date)
		full_name = f"{app.first_name or ''} {app.last_name or ''}".strip() or app.name

		target_users = set()
		if app.owner: target_users.add(app.owner)
		if app.lms_employee: target_users.add(app.lms_employee)
		if app.wakala_employee: target_users.add(app.wakala_employee)
		if app.injaz_employee: target_users.add(app.injaz_employee)

		# Add stage-based role users (LMS, Wakala, Injaz Officers)
		for u in get_clearance_target_users("LMS Clearance", app.lms_employee, app.owner):
			target_users.add(u)
		for u in get_clearance_target_users("Wakala Clearance", app.wakala_employee, app.owner):
			target_users.add(u)
		for u in get_clearance_target_users("Injaz Clearance", app.injaz_employee, app.owner):
			target_users.add(u)

		subject = f"Medical Expiry Warning: {full_name} ({days_left} day(s) left)"
		description = (
			f"Medical request for Applicant {full_name} ({app.name}) expires on {app.medical_expiry_date} "
			f"({days_left} day(s) remaining). Current state: {app.applicant_state}."
		)

		payload = {
			"applicant": app.name,
			"full_name": full_name,
			"medical_expiry_date": str(app.medical_expiry_date),
			"days_remaining": days_left,
			"applicant_state": app.applicant_state
		}

		for user in target_users:
			notify_user_task(
				user=user,
				subject=subject,
				description=description,
				reference_doctype="Applicant",
				reference_name=app.name,
				event_type="medical_expiry_warning",
				payload=payload,
				date_val=app.medical_expiry_date
			)
