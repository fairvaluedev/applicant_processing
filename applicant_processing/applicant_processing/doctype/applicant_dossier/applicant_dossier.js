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
    }
});
