// Copyright (c) 2026, Admin and contributors
// For license information, please see license.txt

frappe.ui.form.on("Applicant Dossier", {
    refresh(frm) {
        if (!frm.is_new() && frm.doc.docstatus === 0 && !frm.doc.is_parsed) { // Draft and not parsed
            if (frm.doc.attached_file) {
                frm.add_custom_button(__("Parse File"), function () {
                    frappe.call({
                        method: "applicant_processing.applicant_processing.doctype.applicant_dossier.applicant_dossier.parse_dossier_file",
                        args: { dossier_name: frm.doc.name },
                        freeze: true,
                        freeze_message: "Parsing document...",
                        callback: function(r) {
                            if (!r.exc) {
                                frappe.show_alert({message: r.message, indicator: 'green'});
                                frm.reload_doc();
                            }
                        }
                    });
                }, __("Actions")).addClass("btn-primary");
            }
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
