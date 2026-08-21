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

function apply_passport_mrz_data(frm, data) {
    if (!data) return;

    let updated_fields = [];

    if (data.passport_number && frm.doc.passport_number !== data.passport_number) {
        frm.set_value("passport_number", data.passport_number);
        updated_fields.push("Passport Number: " + data.passport_number);
    }
    if (data.first_name && frm.doc.first_name !== data.first_name) {
        frm.set_value("first_name", data.first_name);
        updated_fields.push("First Name: " + data.first_name);
    }
    if (data.middle_name && frm.doc.middle_name !== data.middle_name) {
        frm.set_value("middle_name", data.middle_name);
        updated_fields.push("Middle Name: " + data.middle_name);
    }
    if (data.last_name && frm.doc.last_name !== data.last_name) {
        frm.set_value("last_name", data.last_name);
        updated_fields.push("Last Name: " + data.last_name);
    }
    if (data.nationality && frm.doc.nationality !== data.nationality) {
        frm.set_value("nationality", data.nationality);
        updated_fields.push("Nationality: " + data.nationality);
    }
    if (data.date_of_birth && frm.doc.date_of_birth !== data.date_of_birth) {
        frm.set_value("date_of_birth", data.date_of_birth);
        updated_fields.push("Date of Birth: " + data.date_of_birth);
    }
    if (data.gender && frm.doc.gender !== data.gender) {
        frm.set_value("gender", data.gender);
        updated_fields.push("Gender: " + data.gender);
    }
    if (data.passport_expiry && frm.doc.passport_expiry !== data.passport_expiry) {
        frm.set_value("passport_expiry", data.passport_expiry);
        updated_fields.push("Passport Expiry: " + data.passport_expiry);
    }
    if (data.place_of_issue && frm.doc.place_of_issue !== data.place_of_issue) {
        frm.set_value("place_of_issue", data.place_of_issue);
        updated_fields.push("Place of Issue: " + data.place_of_issue);
    }
    if (data.national_id && !frm.doc.national_id) {
        frm.set_value("national_id", data.national_id);
        updated_fields.push("National ID: " + data.national_id);
    }

    if (updated_fields.length > 0) {
        frappe.msgprint({
            title: __("Passport Data Extracted (MRZ + Checksum Validated)"),
            indicator: "green",
            message: __("The following fields were auto-populated from the passport scan:") + "<br><br>• <strong>" + updated_fields.join("</strong><br>• <strong>") + "</strong>"
        });
    }
}

frappe.ui.form.on("Applicant", {
    onload_post_render(frm) {
        calculate_applicant_computed_days(frm);
    },

    passport_scan(frm) {
        if (frm.doc.passport_scan) {
            frappe.show_progress(__("Scanning Passport..."), 30, 100, __("Running MRZ-Targeted OCR & Checksum Decoder"));
            frappe.call({
                method: "applicant_processing.applicant_processing.doctype.applicant.applicant.scan_and_populate_passport",
                args: {
                    file_url: frm.doc.passport_scan,
                    applicant_name: frm.is_new() ? null : frm.doc.name
                },

                callback: function (r) {
                    frappe.hide_progress();
                    if (!r.exc && r.message && r.message.status === "success") {
                        apply_passport_mrz_data(frm, r.message.data);
                    } else if (r.message && r.message.status === "error") {
                        frappe.show_alert({
                            message: r.message.message || __("Could not detect MRZ from passport image."),
                            indicator: "orange"
                        }, 5);
                    }
                }
            });
        }
    },

    exam_date(frm) {
        calculate_applicant_computed_days(frm);
    },

    medical_expiry_date(frm) {
        calculate_applicant_computed_days(frm);
    },

    date_of_birth(frm) {
        if (frm.doc.date_of_birth) {
            const dob = new Date(frm.doc.date_of_birth);
            const today = new Date();
            let age = today.getFullYear() - dob.getFullYear();
            const m = today.getMonth() - dob.getMonth();
            if (m < 0 || (m === 0 && today.getDate() < dob.getDate())) {
                age--;
            }
            if (age > 0) {
                frm.set_value("age", age);
            }
        }
    },

    refresh(frm) {
        // State field is always read-only — system controls it
        frm.set_df_property("applicant_state", "read_only", 1);
        // Date of birth cannot be in the future
        frm.set_df_property("date_of_birth", "max_date", frappe.datetime.get_today());

        calculate_applicant_computed_days(frm);

        // Show cancellation fields only when cancelled or when remarks exist
        frm.toggle_display(["cancel_remarks", "cancelled_at", "cancelled_by"], frm.doc.applicant_state === "Cancelled" || !!frm.doc.cancel_remarks);

        // Auto-load & initialize Chrome Desktop Notifications
        frappe.require("/assets/applicant_processing/js/web_push.js", function () {
            if (window.ApplicantWebPush) {
                window.ApplicantWebPush.init();
            }
        });

        // Notifications action group on form header
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

        // Action button to Upload & Scan Passport - Available BEFORE saving Draft and on existing records!
        frm.add_custom_button(__("Upload & Scan Passport"), function () {
            new frappe.ui.FileUploader({
                folder: "Home/Attachments",
                allow_multiple: false,
                restrictions: {
                    allowed_file_types: ["image/*", ".pdf"]
                },
                on_success: (file_doc) => {
                    frm.set_value("passport_scan", file_doc.file_url);
                    frappe.show_progress(__("Scanning Passport..."), 30, 100, __("Running MRZ-Targeted OCR & Checksum Decoder"));
                    frappe.call({
                        method: "applicant_processing.applicant_processing.doctype.applicant.applicant.scan_and_populate_passport",
                        args: {
                            file_url: file_doc.file_url,
                            applicant_name: frm.is_new() ? null : frm.doc.name
                        },
                        callback: function (r) {
                            frappe.hide_progress();
                            if (!r.exc && r.message && r.message.status === "success") {
                                apply_passport_mrz_data(frm, r.message.data);
                            } else if (r.message && r.message.status === "error") {
                                frappe.msgprint({
                                    title: __("Passport Scan Result"),
                                    indicator: "orange",
                                    message: r.message.message || __("Could not detect MRZ from passport image.")
                                });
                            }
                        }
                    });
                }
            });
        }).addClass("btn-primary");

        // Action button to re-scan already uploaded passport_scan
        if (frm.doc.passport_scan) {
            frm.add_custom_button(__("Scan Passport (OCR)"), function () {
                frappe.show_progress(__("Scanning Passport..."), 30, 100, __("Running MRZ-Targeted OCR & Checksum Decoder"));
                frappe.call({
                    method: "applicant_processing.applicant_processing.doctype.applicant.applicant.scan_and_populate_passport",
                    args: {
                        file_url: frm.doc.passport_scan,
                        applicant_name: frm.is_new() ? null : frm.doc.name
                    },
                    callback: function (r) {
                        frappe.hide_progress();
                        if (!r.exc && r.message && r.message.status === "success") {
                            apply_passport_mrz_data(frm, r.message.data);
                        } else if (r.message && r.message.status === "error") {
                            frappe.msgprint({
                                title: __("Passport Scan Result"),
                                indicator: "orange",
                                message: (r.message.message || __("Could not detect MRZ from passport image.")) +
                                    "<br><br>" + __("Tip: You can also use <strong>Actions > Paste MRZ Text</strong> to decode and validate instantly.")
                            });
                        }
                    }
                });
            }, __("Actions"));
        }

        // Action button to Paste / Decode Raw MRZ Text directly (100% reliable fallback)
        frm.add_custom_button(__("Paste MRZ Text"), function () {
            frappe.prompt([
                {
                    label: __("Passport MRZ Lines (2 lines of 44 characters, e.g. PQETH...)"),
                    fieldname: "raw_mrz_text",
                    fieldtype: "Code",
                    options: "Text",
                    reqd: 1,
                    description: __("Paste the 2 bottom lines from the passport (e.g. Line 1: PQETH... Line 2: EQ257...)")
                }
            ], function (values) {
                frappe.call({
                    method: "applicant_processing.applicant_processing.doctype.applicant.applicant.scan_and_populate_passport",
                    args: {
                        raw_mrz_text: values.raw_mrz_text,
                        applicant_name: frm.is_new() ? null : frm.doc.name
                    },
                    callback: function (r) {
                        if (!r.exc && r.message && r.message.status === "success") {
                            apply_passport_mrz_data(frm, r.message.data);
                        } else {
                            frappe.msgprint({
                                title: __("MRZ Decode Failed"),
                                indicator: "red",
                                message: r.message ? r.message.message : __("Invalid MRZ line format.")
                            });
                        }
                    }
                });
            }, __("Decode Passport MRZ Text"), __("Decode & Populate"));
        }, __("Actions"));


        if (frm.is_new()) return;

        const state = frm.doc.applicant_state;

        if (state === "Draft") {
            frm.add_custom_button(__("Register Applicant"), function () {
                // Client-side quick check for missing registration fields
                const reg_fields = [
                    { field: "passport_number", label: "Passport Number" },
                    { field: "passport_issue_date", label: "Passport Issue Date" },
                    { field: "passport_expiry", label: "Passport Expiry Date" },
                    { field: "place_of_issue", label: "Place of Issue" },
                    { field: "job_applied", label: "Job / Position Applied" },
                    { field: "highest_education", label: "Educational Qualification" },
                    { field: "photo_passport", label: "Small / Passport Photo" },
                    { field: "photo_full_body", label: "Full Body Photo" },
                    { field: "passport_scan", label: "Scanned Passport Copy" },
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
                if (frm.doc.medical_status === "UNFIT") {
                    frappe.msgprint({
                        title: __("Medical Status UNFIT"),
                        indicator: "red",
                        message: __("Cannot generate CV: Medical Status is marked as 'UNFIT'.")
                    });
                    return;
                }

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
                frappe.prompt([
                    {
                        label: __("Restore Option"),
                        fieldname: "restore_option",
                        fieldtype: "Select",
                        options: [
                            { label: __("Resume from previous stage (Auto-detect)"), value: "auto" },
                            { label: __("Reset to Registered (Start from beginning)"), value: "registered" },
                            { label: __("Reset to Draft"), value: "draft" }
                        ],
                        default: "auto",
                        reqd: 1
                    }
                ], function (values) {
                    frappe.call({
                        method: "applicant_processing.applicant_processing.doctype.applicant.applicant.restore_applicant",
                        args: {
                            applicant_name: frm.doc.name,
                            restore_option: values.restore_option || "auto"
                        },
                        freeze: true,
                        freeze_message: __("Restoring Applicant Process..."),
                        callback: function (r) {
                            if (!r.exc) {
                                frm.reload_doc();
                                const msg = r.message && r.message.message ? r.message.message : (r.message || __("Applicant has been restored."));
                                frappe.msgprint({
                                    title: __("Applicant Restored"),
                                    indicator: "green",
                                    message: msg
                                });
                            }
                        }
                    });
                }, __("Restore Applicant Process"), __("Restore"));
            }, __("Actions")).addClass("btn-primary");
        }
    }
});