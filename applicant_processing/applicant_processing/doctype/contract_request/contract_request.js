// Copyright (c) 2026, Admin and contributors
// For license information, please see license.txt

frappe.ui.form.on("Contract Request", {
    refresh(frm) {
        if (frm.is_new()) return;

        // Show "Send Contract Request" primary button
        if (frm.doc.status === "Draft" || frm.doc.status === "Sent") {
            frm.add_custom_button(__("Send Contract Request"), function () {
                if (!frm.doc.contractor) {
                    frappe.msgprint({
                        title: __("Select Contractor"),
                        indicator: 'orange',
                        message: __("Please select a Contractor in the 'Select Contractor' field before sending.")
                    });
                    return;
                }

                frappe.confirm(
                    `Send Contract Request <strong>${frm.doc.name}</strong> to Contractor <strong>${frm.doc.contractor}</strong>?`,
                    function () {
                        frappe.call({
                            method: "applicant_processing.applicant_processing.doctype.contract_request.contract_request.send_contract_request",
                            args: { contract_request_name: frm.doc.name },
                            freeze: true,
                            freeze_message: "Sending Contract Request...",
                            callback: function (r) {
                                if (!r.exc) {
                                    frappe.show_alert({ message: r.message, indicator: 'green' });
                                    frm.reload_doc();
                                }
                            }
                        });
                    }
                );
            }).addClass("btn-primary");
        }
    },

    cv_reference(frm) {
        if (frm.doc.cv_reference) {
            frappe.db.get_value("CV Record", frm.doc.cv_reference, [
                "applicant", "first_name", "middle_name", "last_name",
                "date_of_birth", "gender", "nationality", "email", "phone_number",
                "passport_number", "passport_expiry", "national_id",
                "highest_education", "institution", "graduation_year", "contractor"
            ], function (value) {
                if (!value) return;
                Object.keys(value).forEach(function (field) {
                    frm.set_value(field, value[field]);
                });
            });
        }
    },

    contractor(frm) {
        if (frm.doc.contractor) {
            frappe.db.get_value("Contractor", frm.doc.contractor, [
                "contact_person", "phone", "whatsapp", "email"
            ], function (value) {
                if (!value) return;
                frm.set_value("contractor_person", value.contact_person || "");
                frm.set_value("contractor_phone", value.phone || "");
                frm.set_value("contractor_whatsapp", value.whatsapp || "");
                frm.set_value("contractor_email", value.email || "");
            });
        } else {
            frm.set_value("contractor_person", "");
            frm.set_value("contractor_phone", "");
            frm.set_value("contractor_whatsapp", "");
            frm.set_value("contractor_email", "");
        }
    }
});
