frappe.listview_settings["DSR"] = {
    add_fields: ["full_name", "applicant_dossier", "passport_number", "sponsor_name", "contractor_name", "stamp_status", "ticket_status", "departure_status"],
    get_indicator(doc) {
        if (doc.departure_status === "Departed") {
            return [__("Departed"), "green", "departure_status,=,Departed"];
        } else if (doc.ticket_status === "Booked") {
            return [__("Ticketed"), "darkgreen", "ticket_status,=,Booked"];
        } else if (doc.stamp_status === "Completed") {
            return [__("Stamped"), "cyan", "stamp_status,=,Completed"];
        }
        return [__("In Progress"), "orange", "docstatus,=,0"];
    }
};
