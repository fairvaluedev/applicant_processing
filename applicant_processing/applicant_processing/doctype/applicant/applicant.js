// Copyright (c) 2026, Admin and contributors
// For license information, please see license.txt

frappe.ui.form.on("Applicant", {
    refresh(frm) {
        // State field is always read-only — system controls it
        frm.set_df_property("applicant_state", "read_only", 1);

        if (frm.is_new()) return;

        // --- Action Buttons based on current state ---
        const state = frm.doc.applicant_state;

        if (state === "Draft") {
            frm.add_custom_button(__("Register Applicant"), function () {
                frappe.confirm(
                    "Register this applicant? They must have all required registration data.",
                    function () {
                        frappe.call({
                            method: "applicant_processing.applicant_processing.doctype.applicant.applicant.register_applicant",
                            args: { applicant_name: frm.doc.name },
                            callback: function (r) {
                                if (!r.exc) {
                                    frm.reload_doc();
                                    frappe.msgprint(r.message || "Applicant registered successfully.");
                                }
                            }
                        });
                    }
                );
            }).addClass("btn-primary");
        }

        // CV can be generated for anyone who is Registered or further along.
        const eligible_for_cv = [
            "Registered", "CV Generated", "Contract Requested", 
            "VSR In Progress", "Stamped", "Ticketed", "Departed"
        ];
        
        if (eligible_for_cv.includes(state)) {
            frm.add_custom_button(__("Generate CV"), function () {
                frappe.confirm(
                    "Generate a PDF CV for this applicant from their current profile data?",
                    function () {
                        frappe.show_progress("Generating CV...", 0, 100, "Please wait");
                        frappe.call({
                            method: "applicant_processing.applicant_processing.doctype.applicant.applicant.generate_cv",
                            args: { applicant_name: frm.doc.name },
                            callback: function (r) {
                                frappe.hide_progress();
                                if (!r.exc && r.message) {
                                    frm.reload_doc();
                                    frappe.show_alert({
                                        message: __("CV generated: ") + r.message.cv_record,
                                        indicator: "green"
                                    }, 6);
                                    // Open the new CV Record
                                    frappe.set_route("Form", "CV Record", r.message.cv_record);
                                }
                            }
                        });
                    }
                );
            }).addClass("btn-success");
        }
    }
});