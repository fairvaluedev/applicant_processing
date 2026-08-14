frappe.listview_settings["Contract Request"] = {
    add_fields: ["full_name", "applicant", "contractor", "status", "cv_reference"],
    get_indicator(doc) {
        const status_colors = {
            "Draft": "gray",
            "Sent": "orange",
            "Accepted": "green",
            "Closed": "darkgray"
        };
        const color = status_colors[doc.status] || "gray";
        return [__(doc.status || "Draft"), color, `status,=,${doc.status}`];
    }
};
