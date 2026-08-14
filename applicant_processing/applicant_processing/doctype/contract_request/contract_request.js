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
                                if (!r.exc && r.message) {
                                    let res = r.message;
                                    let msgText = typeof res === "string" ? res : res.message;

                                    if (typeof res === "object" && res.whatsapp_api_sent) {
                                        frappe.msgprint({
                                            title: __("Contract Request Sent via WhatsApp API"),
                                            indicator: 'green',
                                            message: `<strong>${msgText}</strong><br><br>Direct WhatsApp message sent successfully to <strong>+${res.whatsapp_number}</strong>.<br><small class="text-muted">${res.whatsapp_api_message || ''}</small>`
                                        });
                                    } else if (typeof res === "object" && res.whatsapp_url) {
                                        // Attempt auto-open in new tab
                                        try {
                                            window.open(res.whatsapp_url, '_blank');
                                        } catch (e) {
                                            console.log("Popup blocked", e);
                                        }

                                        frappe.msgprint({
                                            title: __("Contract Request Ready for WhatsApp"),
                                            indicator: 'blue',
                                            message: `<strong>${msgText}</strong><br><br>
                                            <div class="alert alert-warning p-2 my-2" style="font-size: 13px;">
                                                <strong>Note:</strong> Meta Cloud API (${res.whatsapp_api_message || 'Test Mode'}). Use the link below to send directly via WhatsApp.
                                            </div>
                                            <a href="${res.whatsapp_url}" target="_blank" class="btn btn-primary btn-md mt-2" style="font-weight: 600;">
                                                <i class="fa fa-whatsapp"></i> Click to Send via WhatsApp (+${res.whatsapp_number})
                                            </a>`
                                        });
                                    } else {
                                        frappe.show_alert({ message: msgText, indicator: 'green' });
                                    }

                                    frm.reload_doc();
                                }
                            }
                        });
                    }
                );
            }).addClass("btn-primary");
        }

        // Add direct WhatsApp button if WhatsApp number exists
        if (frm.doc.contractor_whatsapp || frm.doc.contractor_phone) {
            let phone = (frm.doc.contractor_whatsapp || frm.doc.contractor_phone).replace(/\D/g, '');
            if (phone) {
                frm.add_custom_button(__("Open WhatsApp"), function () {
                    let applicant = `${frm.doc.first_name || ''} ${frm.doc.last_name || ''}`.trim() || frm.doc.applicant;
                    let text = encodeURIComponent(`Hello! Contract Request ${frm.doc.name} for Applicant ${applicant}. CV Reference: ${frm.doc.cv_reference || ''}`);
                    window.open(`https://api.whatsapp.com/send?phone=${phone}&text=${text}`, '_blank');
                }, __("Action"));
            }
        }
    },

    cv_reference(frm) {
        if (frm.doc.cv_reference) {
            frappe.db.get_value("CV Record", frm.doc.cv_reference, [
                "applicant", "first_name", "middle_name", "last_name",
                "date_of_birth", "gender", "nationality", "email", "phone_number",
                "passport_number", "passport_expiry", "national_id",
                "highest_education", "institution", "graduation_year"
            ], function (value) {
                if (!value) return;
                Object.keys(value).forEach(function (field) {
                    if (frm.fields_dict[field]) {
                        frm.set_value(field, value[field]);
                    }
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
