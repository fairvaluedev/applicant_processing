// Copyright (c) 2026, Admin and contributors
// For license information, please see license.txt

function calculate_applicant_computed_days(frm) {
    const today = frappe.datetime.get_today();

    if (frm.doc.exam_date) {
        const diff_exam = frappe.datetime.get_diff(frm.doc.exam_date, today);
        if (frm.doc.exam_remaining_days !== diff_exam) {
            frm.set_value("exam_remaining_days", diff_exam);
        }
    } else {
        if (frm.doc.exam_remaining_days !== null && frm.doc.exam_remaining_days !== undefined) {
            frm.set_value("exam_remaining_days", null);
        }
    }

    if (frm.doc.medical_expiry_date) {
        const diff_med = frappe.datetime.get_diff(frm.doc.medical_expiry_date, today);
        if (frm.doc.medical_remaining_days !== diff_med) {
            frm.set_value("medical_remaining_days", diff_med);
        }
    } else {
        if (frm.doc.medical_remaining_days !== null && frm.doc.medical_remaining_days !== undefined) {
            frm.set_value("medical_remaining_days", null);
        }
    }
}

frappe.ui.form.on("Applicant", {
    onload_post_render(frm) {
        calculate_applicant_computed_days(frm);
    },

    exam_date(frm) {
        calculate_applicant_computed_days(frm);
    },

    medical_expiry_date(frm) {
        calculate_applicant_computed_days(frm);
    },

    refresh(frm) {
        // State field is always read-only — system controls it
        frm.set_df_property("applicant_state", "read_only", 1);
        // Date of birth cannot be in the future
        frm.set_df_property("date_of_birth", "max_date", frappe.datetime.get_today());

        calculate_applicant_computed_days(frm);

        // Show cancellation fields only when cancelled or when remarks exist
        frm.toggle_display(["cancel_remarks", "cancelled_at", "cancelled_by"], frm.doc.applicant_state === "Cancelled" || !!frm.doc.cancel_remarks);

        if (frm.is_new()) return;

        // --- Action Buttons based on current state ---
        const state = frm.doc.applicant_state;

        if (state === "Draft") {
            frm.add_custom_button(__("Register Applicant"), function () {
                // Client-side quick check for missing registration fields
                const reg_fields = [
                    { field: "date_of_birth", label: "Date of Birth" },
                    { field: "passport_number", label: "Passport Number" },
                    { field: "highest_education", label: "Highest Education Level" },
                    { field: "labour_id", label: "Labour ID" },
                    { field: "contact_person_name", label: "Contact Person Name" },
                    { field: "contact_person_phone", label: "Contact Person Phone" },
                    { field: "coc_status", label: "COC Status" },
                    { field: "exam_date", label: "COC Exam Date" },
                    { field: "medical_status", label: "Medical Status" },
                    { field: "medical_expiry_date", label: "Medical Expiration Date" }
                ];

                const missing = reg_fields.filter(f => !frm.doc[f.field]).map(f => f.label);
                if (missing.length > 0) {
                    frappe.msgprint({
                        title: __("Missing Registration Data"),
                        indicator: "orange",
                        message: __("Please fill the following required fields before registering:") + "<br><br>• <strong>" + missing.join("</strong><br>• <strong>") + "</strong>"
                    });
                    return;
                }

                if (frm.doc.medical_status === "UNFIT") {
                    frappe.msgprint({
                        title: __("Medical Status UNFIT"),
                        indicator: "red",
                        message: __("Cannot register applicant: Medical Status is marked as 'UNFIT'.")
                    });
                    return;
                }

                frappe.confirm(
                    `Register applicant <strong>${frm.doc.full_name || frm.doc.name}</strong>?`,
                    function () {
                        frappe.call({
                            method: "applicant_processing.applicant_processing.doctype.applicant.applicant.register_applicant",
                            args: { applicant_name: frm.doc.name },
                            freeze: true,
                            freeze_message: __("Registering Applicant..."),
                            callback: function (r) {
                                if (!r.exc) {
                                    frm.reload_doc();
                                    frappe.msgprint({
                                        title: __("Registered"),
                                        indicator: "green",
                                        message: r.message || __("Applicant registered successfully.")
                                    });
                                }
                            }
                        });
                    }
                );
            }).addClass("btn-primary");
        }

        // CV can be generated for anyone who is Registered or further along.
        const eligible_for_cv = [
            "Registered", "CV Generated", "Request Pending", 
            "Selected", "Processing", "Stamped", "Ticketed", "Departed"
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

        // Cancel Process action (available for any active applicant)
        if (state !== "Departed" && state !== "Cancelled") {
            frm.add_custom_button(__("Cancel Process"), function () {
                frappe.prompt([
                    {
                        label: __("Cancellation Remarks / Reason (Optional)"),
                        fieldname: "cancel_remarks",
                        fieldtype: "Small Text",
                        reqd: 0
                    }
                ], function (values) {
                    frappe.call({
                        method: "applicant_processing.applicant_processing.doctype.applicant.applicant.cancel_applicant",
                        args: {
                            applicant_name: frm.doc.name,
                            cancel_remarks: values ? values.cancel_remarks : ""
                        },
                        freeze: true,
                        freeze_message: __("Cancelling Applicant Process..."),
                        callback: function (r) {
                            if (!r.exc) {
                                frm.reload_doc();
                                frappe.msgprint({
                                    title: __("Process Cancelled"),
                                    indicator: "red",
                                    message: r.message || __("Applicant process has been cancelled.")
                                });
                            }
                        }
                    });
                }, __("Cancel Applicant Process"), __("Confirm Cancellation"));
            }, __("Actions"));
        }

        // Restore Process action (available for Cancelled applicant)
        if (state === "Cancelled") {
            frm.add_custom_button(__("Restore / Uncancel Process"), function () {
                frappe.confirm(
                    __("Are you sure you want to restore this applicant back into the active processing pipeline?"),
                    function () {
                        frappe.call({
                            method: "applicant_processing.applicant_processing.doctype.applicant.applicant.restore_applicant",
                            args: { applicant_name: frm.doc.name },
                            freeze: true,
                            freeze_message: __("Restoring Applicant Process..."),
                            callback: function (r) {
                                if (!r.exc) {
                                    frm.reload_doc();
                                    frappe.msgprint({
                                        title: __("Applicant Restored"),
                                        indicator: "green",
                                        message: r.message || __("Applicant has been restored.")
                                    });
                                }
                            }
                        });
                    }
                );
            }, __("Actions")).addClass("btn-primary");
        }
    }
});