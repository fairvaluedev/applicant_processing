frappe.listview_settings["DSR Ticket"] = {
    add_fields: ["full_name", "dsr", "passport_number", "ticket_number", "status"],
    get_indicator(doc) {
        if (doc.status === "Booked") {
            return [__("Booked"), "green", "status,=,Booked"];
        } else if (doc.status === "Cancelled") {
            return [__("Cancelled"), "red", "status,=,Cancelled"];
        }
        return [__("Pending"), "orange", "status,=,Pending"];
    }
};
