// Copyright (c) 2026, Admin and contributors
// For license information, please see license.txt

frappe.ui.form.on("Applicant Dossier", {
    refresh(frm) {
        // Auto-load & initialize Chrome Desktop Notifications
        frappe.require("/assets/applicant_processing/js/web_push.js", function () {
            if (window.ApplicantWebPush) {
                window.ApplicantWebPush.init();
            }
        });

        // Notifications action group
        frm.add_custom_button(__("Enable Desktop Alerts (Chrome)"), function () {
            frappe.require("/assets/applicant_processing/js/web_push.js", function () {
                window.ApplicantWebPush.subscribeUser(true);
            });
        }, __("Notifications"));

        frm.add_custom_button(__("Test Desktop Notification"), function () {
            frappe.require("/assets/applicant_processing/js/web_push.js", function () {
                window.ApplicantWebPush.sendTestPush();
            });
        }, __("Notifications"));

        if (!frm.is_new() && frm.doc.docstatus === 0) {
            if (frm.doc.attached_file) {
                frm.add_custom_button(__("Parse Contract (PyMuPDF)"), function () {
                    frappe.call({
                        method: "applicant_processing.applicant_processing.doctype.applicant_dossier.applicant_dossier.parse_dossier_file",
                        args: { dossier_name: frm.doc.name },
                        freeze: true,
                        freeze_message: __("Extracting & Structuring Contract Data via PyMuPDF..."),
                        callback: function(r) {
                            if (!r.exc) {
                                frappe.show_alert({
                                    message: r.message || __("Contract parsed successfully!"),
                                    indicator: 'green'
                                }, 6);
                                frm.reload_doc();
                            }
                        }
                    });
                }, __("Actions")).addClass("btn-primary");
            }
        }
    },

    attached_file(frm) {
        if (frm.doc.attached_file && !frm.doc.is_parsed && !frm.is_new()) {
            frappe.show_alert({
                message: __("Contract attached. Click 'Parse Contract (PyMuPDF)' in Actions to extract details."),
                indicator: 'blue'
            }, 5);
        }
    },

    contract_request(frm) {
        if (!frm.doc.contract_request) {
            frm.set_value("applicant", "");
            frm.set_value("cv_record", "");
            frm.set_value("contract_status", "");
            frm.set_value("cv_status", "");
            frm.set_value("contractor_name", "");
            frm.set_value("first_name", "");
            frm.set_value("last_name", "");
            frm.set_value("nationality", "");
            frm.set_value("passport_number", "");
            return;
        }

        frappe.db.get_value("Contract Request", frm.doc.contract_request, [
            "applicant", "cv_reference", "status", "contractor"
        ], function(cr) {
            if (!cr) return;
            frm.set_value("applicant", cr.applicant || "");
            frm.set_value("cv_record", cr.cv_reference || "");
            frm.set_value("contract_status", cr.status || "");
            if (cr.contractor) {
                frm.set_value("contractor_name", cr.contractor);
            }

            if (cr.applicant) {
                frappe.db.get_value("Applicant", cr.applicant, [
                    "first_name", "last_name", "nationality", "passport_number"
                ], function(app) {
                    if (!app) return;
                    frm.set_value("first_name", app.first_name || "");
                    frm.set_value("last_name", app.last_name || "");
                    frm.set_value("nationality", app.nationality || "");
                    frm.set_value("passport_number", app.passport_number || "");
                });
            }

            if (cr.cv_reference) {
                frappe.db.get_value("CV Record", cr.cv_reference, "status", function(val) {
                    if (val) {
                        frm.set_value("cv_status", val.status || val);
                    }
                });
            }
        });
    }
});
