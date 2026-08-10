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

    applicant(frm) {
        if (!frm.doc.applicant) {
            frm.set_value("cv_record", "");
            frm.set_value("contract_request", "");
            return;
        }

        // Auto-fetch latest CV Record
        frappe.db.get_list("CV Record", {
            filters: { applicant: frm.doc.applicant },
            order_by: "creation desc",
            limit: 1
        }).then(records => {
            if (records && records.length > 0) {
                frm.set_value("cv_record", records[0].name);
            } else {
                frm.set_value("cv_record", "");
            }
        });

        // Auto-fetch latest Contract Request
        frappe.db.get_list("Contract Request", {
            filters: { applicant: frm.doc.applicant },
            order_by: "creation desc",
            limit: 1
        }).then(records => {
            if (records && records.length > 0) {
                frm.set_value("contract_request", records[0].name);
            } else {
                frm.set_value("contract_request", "");
            }
        });
    }
});
