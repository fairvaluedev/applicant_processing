frappe.listview_settings["Contractor"] = {
    add_fields: ["company_name", "country", "contact_person", "phone", "email", "active_status", "default_commission_amount", "default_commission_currency"],
    get_indicator(doc) {
        if (doc.active_status) {
            return [__("Active"), "green", "active_status,=,1"];
        }
        return [__("Inactive"), "gray", "active_status,=,0"];
    },
    onload(listview) {
        listview.page.add_inner_button(__("Commission Billing Export"), function () {
            let selected = listview.get_checked_items();
            let contractor_name = selected.length > 0 ? selected[0].name : "";

            let d = new frappe.ui.Dialog({
                title: __("Quick Commission Billing Export"),
                fields: [
                    {
                        fieldname: "contractor",
                        label: __("Select Partner Agency"),
                        fieldtype: "Link",
                        options: "Contractor",
                        default: contractor_name,
                        reqd: 1
                    },
                    {
                        fieldname: "batch_size",
                        label: __("Batch Scope"),
                        fieldtype: "Select",
                        options: "30\n40\n50\n100\nAll",
                        default: "30",
                        reqd: 1
                    },
                    {
                        fieldname: "export_format",
                        label: __("Format"),
                        fieldtype: "Select",
                        options: "Excel Spreadsheet (.xlsx)\nPDF Statement / Invoice (.pdf)",
                        default: "Excel Spreadsheet (.xlsx)",
                        reqd: 1
                    }
                ],
                primary_action_label: __("Download Export"),
                primary_action(values) {
                    let fmt = values.export_format.includes("PDF") ? "pdf" : "excel";
                    let url = `/api/method/applicant_processing.applicant_processing.utils.commission_export.export_unpaid_commission_report?contractor=${encodeURIComponent(values.contractor)}&export_format=${fmt}&limit=${values.batch_size}`;
                    window.open(url, "_blank");
                    d.hide();
                }
            });

            d.show();
        });
    }
};
