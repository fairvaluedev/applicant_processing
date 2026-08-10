import frappe
import requests

def send_notification(event_type, data):
	config = frappe.get_single("Notification Config")
	if not config.enabled or not config.push_api_url:
		return

	headers = {}
	if config.push_api_key:
		headers["Authorization"] = f"Bearer {config.push_api_key}"

	payload = {
		"event_type": event_type,
		"data": data,
		"timestamp": frappe.utils.now_datetime().isoformat()
	}

	try:
		# Using timeout so it doesn't block Frappe worker indefinitely
		response = requests.post(config.push_api_url, json=payload, headers=headers, timeout=5)
		response.raise_for_status()
		
		# Optional: Log success to a Notification Log doctype
	except Exception as e:
		frappe.log_error(title=f"Push API Failed: {event_type}", message=str(e))

def check_reminders():
	# Example cron job function
	# Look for VSR clearances that are Pending or In Progress where reminder is due
	# This would be configured in hooks.py
	pass
