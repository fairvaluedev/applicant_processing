frappe.listview_settings["Applicant"] = {
    add_fields: ["full_name", "applicant_state", "phone_number", "passport_number", "nationality"],
    get_indicator(doc) {
        const state_colors = {
            "Draft": "gray",
            "Registered": "blue",
            "CV Generated": "cyan",
            "Request Pending": "orange",
            "Selected": "purple",
            "Processing": "yellow",
            "Stamped": "green",
            "Ticketed": "teal",
            "Departed": "darkgreen",
            "Cancelled": "red"
        };
        const color = state_colors[doc.applicant_state] || "gray";
        return [__(doc.applicant_state || "Draft"), color, `applicant_state,=,${doc.applicant_state}`];
    }
};
