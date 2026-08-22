# Copyright (c) 2026, Admin and contributors
# For license information, please see license.txt

import frappe
from applicant_processing.applicant_processing.utils.commission_export import (
    get_unpaid_commission_data,
    get_unpaid_commission_summary,
    get_unpaid_commission_candidates_list,
    export_unpaid_commission_report,
    mark_commissions_as_paid
)

@frappe.whitelist()
def get_initial_desk_data():
    """Returns the list of active contractors and default agency for the page load."""
    contractors = frappe.get_all(
        "Contractor",
        filters={"active_status": 1},
        fields=["name", "company_name", "country", "default_commission_amount", "default_commission_currency"],
        order_by="company_name asc"
    )
    first_contractor = contractors[0].name if contractors else ""
    return {
        "contractors": contractors,
        "default_contractor": first_contractor
    }
