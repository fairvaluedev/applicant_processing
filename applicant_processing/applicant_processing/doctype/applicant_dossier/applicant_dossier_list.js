frappe.listview_settings["Applicant Dossier"] = {
    add_fields: ["full_name", "applicant", "contract_request", "contractor_name", "sponsor_name", "docstatus"],
    get_indicator(doc) {
        if (doc.docstatus === 1) {
            return [__("Submitted"), "blue", "docstatus,=,1"];
        } else if (doc.docstatus === 2) {
            return [__("Cancelled"), "red", "docstatus,=,2"];
        }
        return [__("Draft"), "gray", "docstatus,=,0"];
    }
};
