frappe.listview_settings["CV Record"] = {
    add_fields: ["full_name", "applicant", "status", "has_contract_request", "contract_request_status", "passport_number"],
    get_indicator(doc) {
        if (doc.status === "Final") {
            return [__("Final"), "green", "status,=,Final"];
        }
        return [__("Draft"), "gray", "status,=,Draft"];
    },
    onload(listview) {
        listview.page.add_action_item(__("Send to Contractor (Batch)"), function () {
            const checked_docs = listview.get_checked_items();
            if (checked_docs.length === 0) {
                frappe.msgprint(__("Please select at least one CV Record from the list."));
                return;
            }

            const cv_names = checked_docs.map(d => d.name);

            frappe.prompt([
                {
                    label: __("Select Contractor"),
                    fieldname: "contractor",
                    fieldtype: "Link",
                    options: "Contractor",
                    reqd: 1
                }
            ], function (values) {
                frappe.call({
                    method: "applicant_processing.applicant_processing.doctype.contract_request.contract_request.batch_send_contract_requests",
                    args: {
                        cv_references: cv_names,
                        contractor: values.contractor
                    },
                    freeze: true,
                    freeze_message: __(`Dispatching ${cv_names.length} Contract Request(s)...`),
                    callback: function (r) {
                        if (!r.exc && r.message) {
                            const res = r.message;
                            frappe.msgprint({
                                title: __("Batch Dispatch Complete"),
                                indicator: res.failed_count > 0 ? "orange" : "green",
                                message: `<strong>Total Selected:</strong> ${res.total}<br>` +
                                         `<strong>Sent Successfully:</strong> ${res.sent_count}<br>` +
                                         `<strong>Created Requests:</strong> ${res.created_count}<br>` +
                                         (res.failed_count > 0 ? `<strong class="text-danger">Failed:</strong> ${res.failed_count}` : "")
                            });
                            listview.refresh();
                        }
                    }
                });
            }, __(`Send ${cv_names.length} CV(s) to Contractor`), __("Send Contract Requests"));
        });
    }
};
