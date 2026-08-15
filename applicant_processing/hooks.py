app_name = "applicant_processing"
app_title = "Applicant Processing"
app_publisher = "Admin"
app_description = "Applicant Management System"
app_email = "admin@example.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "applicant_processing",
# 		"logo": "/assets/applicant_processing/logo.png",
# 		"title": "Applicant Processing",
# 		"route": "/applicant_processing",
# 		"has_permission": "applicant_processing.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/applicant_processing/css/applicant_processing.css"
# app_include_js = "/assets/applicant_processing/js/applicant_processing.js"

# include js, css files in header of web template
# web_include_css = "/assets/applicant_processing/css/applicant_processing.css"
# web_include_js = "/assets/applicant_processing/js/applicant_processing.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "applicant_processing/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "applicant_processing/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "applicant_processing.utils.jinja_methods",
# 	"filters": "applicant_processing.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "applicant_processing.install.before_install"
# after_install = "applicant_processing.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "applicant_processing.uninstall.before_uninstall"
# after_uninstall = "applicant_processing.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "applicant_processing.utils.before_app_install"
# after_app_install = "applicant_processing.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "applicant_processing.utils.before_app_uninstall"
# after_app_uninstall = "applicant_processing.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "applicant_processing.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduler Events
# ----------------
scheduler_events = {
	"daily": [
		"applicant_processing.applicant_processing.utils.push_api.check_medical_expirations"
	]
}


# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

