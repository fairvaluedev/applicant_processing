frappe.listview_settings["Injaz Clearance"] = {
    add_fields: ["full_name", "dsr", "passport_number", "status", "employee"],
    get_indicator(doc) {
        if (doc.status === "Completed") {
            return [__("Completed"), "green", "status,=,Completed"];
        }
        return [__("Pending"), "orange", "status,=,Pending"];
    }
};
