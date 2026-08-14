frappe.listview_settings["DSR Departure"] = {
    add_fields: ["full_name", "dsr", "passport_number", "status", "departure_time"],
    get_indicator(doc) {
        if (doc.status === "Departed") {
            return [__("Departed"), "green", "status,=,Departed"];
        } else if (doc.status === "Cancelled") {
            return [__("Cancelled"), "red", "status,=,Cancelled"];
        }
        return [__("Pending"), "orange", "status,=,Pending"];
    }
};
