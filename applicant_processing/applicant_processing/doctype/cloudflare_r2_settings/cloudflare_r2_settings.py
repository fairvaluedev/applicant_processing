# Copyright (c) 2026, Admin and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class CloudflareR2Settings(Document):
    pass


@frappe.whitelist()
def test_r2_connection():
    """Tests the connection to Cloudflare R2 and returns status."""
    from applicant_processing.applicant_processing.utils.r2_storage import test_connection
    return test_connection()
