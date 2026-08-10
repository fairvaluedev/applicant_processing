// Copyright (c) 2026, Admin and contributors
// For license information, please see license.txt

frappe.ui.form.on("CV Record", {
    refresh(frm) {
        if (frm.is_new()) return;

        // Show "Create Contract Request" primary button when CV is Final
        if (frm.doc.status === "Final") {
            frm.add_custom_button(__("Create Contract Request"), function () {
                frappe.confirm(
                    `Create a Contract Request using CV <strong>${frm.doc.name}</strong>?`,
                    function () {
                        frappe.new_doc("Contract Request", {
                            cv_reference: frm.doc.name,
                            applicant: frm.doc.applicant,
                            created_by: frappe.session.user,
                            created_date: frappe.datetime.now_datetime(),
                        });
                    }
                );
            }).addClass("btn-primary");
        }
    }
});
