import frappe
import os
import json
import base64
import requests
# pyrefly: ignore [missing-import]
from frappe.utils import today, date_diff, add_days, getdate, now_datetime


# =========================================================================
# CHROME / OS DESKTOP WEB PUSH NOTIFICATIONS (VAPID & SERVICE WORKER)
# =========================================================================

def ensure_vapid_keys():
	"""Ensures VAPID ECDSA P-256 keys exist in Notification Config. Generates pair if missing."""
	pub_key = frappe.db.get_single_value("Notification Config", "vapid_public_key")
	priv_key = frappe.db.get_single_value("Notification Config", "vapid_private_key")

	if not pub_key or not priv_key:
		try:
			from py_vapid import Vapid
			from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, PrivateFormat, NoEncryption

			vapid = Vapid()
			vapid.generate_keys()

			raw_pub = vapid.public_key.public_bytes(
				encoding=Encoding.X962,
				format=PublicFormat.UncompressedPoint
			)
			pub_b64 = base64.urlsafe_b64encode(raw_pub).decode("utf-8").rstrip("=")

			priv_pem = vapid.private_key.private_bytes(
				encoding=Encoding.PEM,
				format=PrivateFormat.PKCS8,
				encryption_algorithm=NoEncryption()
			).decode("utf-8")

			frappe.db.set_single_value("Notification Config", "vapid_public_key", pub_b64)
			frappe.db.set_single_value("Notification Config", "vapid_private_key", priv_pem)
			frappe.db.set_single_value("Notification Config", "vapid_subject", "mailto:admin@example.com")
			frappe.db.set_single_value("Notification Config", "webpush_enabled", 1)
			frappe.db.commit()
			pub_key = pub_b64
			priv_key = priv_pem
		except Exception as e:
			frappe.log_error(title="Failed to generate VAPID keys", message=str(e))
	return {"public_key": pub_key, "private_key": priv_key}


@frappe.whitelist(allow_guest=True)
def get_vapid_public_key():
	"""Public endpoint allowing browsers to fetch the VAPID applicationServerKey."""
	vapid = ensure_vapid_keys()
	enabled = frappe.db.get_single_value("Notification Config", "webpush_enabled")
	return {
		"public_key": vapid.get("public_key"),
		"enabled": 1 if enabled is None else enabled
	}


@frappe.whitelist()
def save_web_push_subscription(endpoint, p256dh, auth, user_agent=None):
	"""Registers or updates a browser Web Push subscription for the active user."""
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw("Must be logged in to register for Web Push notifications.", frappe.PermissionError)

	existing = frappe.db.get_value("Web Push Subscription", {"endpoint": endpoint}, "name")
	if existing:
		doc = frappe.get_doc("Web Push Subscription", existing)
		doc.user = user
		doc.p256dh = p256dh
		doc.auth = auth
		doc.user_agent = user_agent or doc.user_agent
		doc.is_active = 1
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc({
			"doctype": "Web Push Subscription",
			"user": user,
			"endpoint": endpoint,
			"p256dh": p256dh,
			"auth": auth,
			"user_agent": user_agent,
			"is_active": 1
		})
		doc.insert(ignore_permissions=True)

	frappe.db.commit()
	return {"status": "success", "message": "Subscribed to Web Push notifications."}


def _dispatch_web_push_record(sub_name, payload_str):
	"""Internal worker that transmits an encrypted WebPush notification via pywebpush."""
	try:
		if not frappe.db.exists("Web Push Subscription", sub_name):
			return
		sub = frappe.get_doc("Web Push Subscription", sub_name)
		if not sub.is_active:
			return

		enabled = frappe.db.get_single_value("Notification Config", "webpush_enabled")
		if enabled == 0:
			return

		priv_key = frappe.db.get_single_value("Notification Config", "vapid_private_key")
		if not priv_key:
			ensure_vapid_keys()
			priv_key = frappe.db.get_single_value("Notification Config", "vapid_private_key")

		if not priv_key:
			return

		import pywebpush
		from py_vapid import Vapid

		vapid_obj = Vapid.from_pem(priv_key.encode("utf-8") if isinstance(priv_key, str) else priv_key)

		subscription_info = {
			"endpoint": sub.endpoint,
			"keys": {
				"p256dh": sub.p256dh,
				"auth": sub.auth
			}
		}

		subject = frappe.db.get_single_value("Notification Config", "vapid_subject") or "mailto:admin@example.com"
		claims = {"sub": subject}
		pywebpush.webpush(
			subscription_info=subscription_info,
			data=payload_str,
			vapid_private_key=vapid_obj,
			vapid_claims=claims,
			ttl=86400,  # Retain in Google FCM / Mozilla push queue for 24h while PC is off/offline
			headers={"Urgency": "high", "TTL": "86400"},
			timeout=15
		)
	except Exception as e:
		# Check for subscription expired (404/410)
		ex_str = str(e)
		if "404" in ex_str or "410" in ex_str or "Gone" in ex_str:
			try:
				frappe.db.set_value("Web Push Subscription", sub_name, "is_active", 0)
				frappe.db.commit()
			except Exception:
				pass
		else:
			frappe.log_error(title="WebPush Dispatch Error", message=ex_str)


def send_web_push(user, title, body, url=None, icon=None, badge=None):
	"""
	Sends an encrypted Chrome Desktop / OS native rectangular Web Push Notification.
	Appears in Windows / macOS even if tab/website is closed.
	"""
	try:
		config = frappe.get_single("Notification Config")
		if hasattr(config, "webpush_enabled") and not config.webpush_enabled:
			return

		subs = frappe.get_all(
			"Web Push Subscription",
			filters={"user": user, "is_active": 1},
			fields=["name"]
		)
		if not subs:
			return

		payload = {
			"title": title,
			"body": body,
			"url": url or "/app",
			"icon": icon or "/assets/applicant_processing/images/icon-192.png",
			"badge": badge or "/assets/applicant_processing/images/icon-72.png",
			"tag": f"ap-alert-{now_datetime().strftime('%Y%m%d%H%M%S')}"
		}
		payload_str = json.dumps(payload)

		for s in subs:
			try:
				_dispatch_web_push_record(s.name, payload_str)
			except Exception as e:
				frappe.log_error(title=f"WebPush dispatch failed for {s.name}", message=str(e))
	except Exception as e:
		frappe.log_error(title=f"send_web_push failed for {user}", message=str(e))


@frappe.whitelist()
def send_test_web_push():
	"""Sends an immediate test Chrome desktop notification to the current user."""
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw("Must be logged in to send a test notification.", frappe.PermissionError)

	subs = frappe.get_all("Web Push Subscription", filters={"user": user, "is_active": 1})
	if not subs:
		return {
			"status": "warning",
			"message": "No active browser subscription found. Please click 'Enable Desktop Alerts' first."
		}

	send_web_push(
		user=user,
		title="Applicant Processing Alert",
		body="Chrome desktop rectangular notifications are working perfectly!",
		url="/app"
	)
	return {
		"status": "success",
		"message": f"Test push notification dispatched to {len(subs)} active device(s)!"
	}



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
	2. Users with role matching the stage (e.g. 'LMS Officer', 'Wakala Officer', 'Injaz Officer', 'Telesign Officer', 'Embassy Officer')
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
	elif "Telesign" in clearance_doctype:
		role_names = ["Telesign Officer", "LMS Officer"]
	elif "Embassy" in clearance_doctype:
		role_names = ["Embassy Officer", "LMS Officer"]

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

	# 4. Dispatch Chrome Desktop Web Push Notification (Rectangular OS alert)
	target_url = f"/app/{reference_doctype.lower().replace(' ', '-')}/{reference_name}" if reference_doctype and reference_name else "/app"
	send_web_push(
		user=user,
		title=subject,
		body=description,
		url=target_url
	)


# =========================================================================
# COMPLIANCE WATCHDOGS & SCHEDULED TIMERS
# =========================================================================

def check_medical_expirations():
	"""
	Multi-Tier Daily Scheduler Task (Module 7):
	Checks all active applicants (EXCLUDING 'Departed' and 'Cancelled').
	Triggers alerts at exact countdown intervals:
	- 14 Days Left (2 Weeks)
	- 10 Days Left
	- 7 Days Left (1 Week)
	- 3 Days Left
	- 1 Day Left (Tomorrow)
	- Expired (<= 0 Days)
	"""
	current_date = getdate(today())
	target_date = add_days(current_date, 14)

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

	countdown_schedule = {14, 10, 7, 3, 1, 0}

	for app in applicants:
		expiry_dt = getdate(app.medical_expiry_date)
		days_left = date_diff(expiry_dt, current_date)
		full_name = f"{app.first_name or ''} {app.last_name or ''}".strip() or app.name

		# Alert at specific milestones or if already expired
		if days_left in countdown_schedule or days_left < 0:
			urgency = "CRITICAL" if days_left <= 3 else "WARNING"
			subject = f"[{urgency}] Medical Expiry: {full_name} ({days_left} day(s) left)" if days_left > 0 else f"[EXPIRED] Medical for {full_name} is Expired!"
			description = (
				f"GAMCA Medical for Applicant {full_name} ({app.name}) expires on {app.medical_expiry_date} "
				f"({days_left} day(s) remaining). Current stage: {app.applicant_state}."
			)

			target_users = set()
			if app.owner: target_users.add(app.owner)
			if app.lms_employee: target_users.add(app.lms_employee)
			if app.wakala_employee: target_users.add(app.wakala_employee)
			if app.injaz_employee: target_users.add(app.injaz_employee)

			for u in get_clearance_target_users("LMS Clearance", app.lms_employee, app.owner):
				target_users.add(u)

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


def check_lms_missing_data_requests():
	"""
	Daily Scheduler Task (Module 7):
	Checks LMS Clearances where missing data (e.g. COC Certificate or GAMCA Medical) was requested.
	If 7 to 10 days have elapsed without receipt (missing_data_status == 'Pending'),
	dispatches urgent alerts to LMS Officers and Registering Officers.
	"""
	curr_today = getdate(today())
	threshold_date = add_days(curr_today, -7)

	pending_requests = frappe.db.sql("""
		SELECT
			lms.name,
			lms.dsr,
			lms.full_name,
			lms.missing_data_type,
			lms.missing_data_requested_at,
			lms.employee,
			lms.owner
		FROM `tabLMS Clearance` lms
		WHERE lms.missing_data_requested = 1
		  AND lms.missing_data_status = 'Pending'
		  AND lms.missing_data_requested_at <= %s
	""", (threshold_date,), as_dict=True)

	for req in pending_requests:
		elapsed_days = date_diff(curr_today, getdate(req.missing_data_requested_at))
		doc_type_label = req.missing_data_type or "COC / Medical Data"
		subject = f"URGENT: Missing {doc_type_label} Pending {elapsed_days} Days for {req.full_name}"
		description = (
			f"Missing data request for {req.full_name} ({doc_type_label}) has been pending "
			f"for {elapsed_days} days (requested on {req.missing_data_requested_at}). "
			f"Please follow up with applicant or partner agency."
		)

		target_users = get_clearance_target_users("LMS Clearance", req.employee, req.owner)
		for u in target_users:
			notify_user_task(
				user=u,
				subject=subject,
				description=description,
				reference_doctype="LMS Clearance",
				reference_name=req.name,
				event_type="lms_missing_data_timeout",
				payload={"lms_clearance": req.name, "elapsed_days": elapsed_days, "applicant": req.full_name}
			)


def check_pending_wakalas_biweekly():
	"""
	Monday & Thursday Scheduled Routine (Module 7):
	Scans all DSRs with pending Wakalas and triggers automated reminders to foreign partner agencies.
	"""
	pending_wakalas = frappe.db.sql("""
		SELECT
			wak.name,
			wak.dsr,
			wak.full_name,
			dsr.contractor_name,
			dsr.passport_number
		FROM `tabWakala Clearance` wak
		JOIN `tabDSR` dsr ON wak.dsr = dsr.name
		WHERE wak.status = 'Pending'
	""", as_dict=True)

	for w in pending_wakalas:
		if not w.contractor_name:
			continue

		contractor_email = frappe.db.get_value("Contractor", w.contractor_name, "email") if frappe.db.exists("Contractor", w.contractor_name) else None
		subject = f"Weekly Wakala Reminder: Payment Pending for {w.full_name}"
		message = (
			f"Bi-weekly Reminder: Musaned Wakala payment is still pending for candidate "
			f"{w.full_name} (Passport: {w.passport_number or 'N/A'}). "
			f"Please process payment to allow embassy stamping."
		)

		# Dispatches push alert to contractor portal accounts
		contractor_users = frappe.get_all("User Permission", filters={"allow": "Contractor", "for_value": w.contractor_name}, pluck="user")
		if not contractor_users and contractor_email:
			contractor_users = [contractor_email]

		for u in contractor_users:
			if u and frappe.db.exists("User", u):
				notify_user_task(
					user=u,
					subject=subject,
					description=message,
					reference_doctype="Wakala Clearance",
					reference_name=w.name,
					event_type="biweekly_wakala_reminder",
					payload={"dsr": w.dsr, "contractor": w.contractor_name}
				)
