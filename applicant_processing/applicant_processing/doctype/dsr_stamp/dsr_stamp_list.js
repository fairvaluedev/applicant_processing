frappe.listview_settings["DSR Stamp"] = {
    add_fields: ["full_name", "dsr", "passport_number", "stamp_number", "status", "stamp_date"],
    get_indicator(doc) {
        if (doc.status === "Completed") {
            return [__("Completed"), "green", "status,=,Completed"];
        }
        return [__("Pending"), "orange", "status,=,Pending"];
    }
};
