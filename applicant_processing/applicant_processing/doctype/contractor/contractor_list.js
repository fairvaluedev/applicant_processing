frappe.listview_settings["Contractor"] = {
    add_fields: ["company_name", "contact_person", "phone", "email", "active_status"],
    get_indicator(doc) {
        if (doc.active_status) {
            return [__("Active"), "green", "active_status,=,1"];
        }
        return [__("Inactive"), "gray", "active_status,=,0"];
    }
};
