// Copyright (c) 2026, Admin and contributors
// For license information, please see license.txt

frappe.ui.form.on("Notification Config", {
    refresh(frm) {
        // Dynamic script require for WebPush
        frappe.require("/assets/applicant_processing/js/web_push.js", function () {
            if (window.ApplicantWebPush) {
                window.ApplicantWebPush.init();
            }
        });

        // Primary Action: Enable Desktop Notifications
        frm.add_custom_button(__("🔔 Enable Chrome Desktop Alerts"), function () {
            frappe.require("/assets/applicant_processing/js/web_push.js", function () {
                window.ApplicantWebPush.subscribeUser(true);
            });
        }).addClass("btn-primary");

        // Action: Send Test Notification
        frm.add_custom_button(__("Test Desktop Notification"), function () {
            frappe.require("/assets/applicant_processing/js/web_push.js", function () {
                window.ApplicantWebPush.sendTestPush();
            });
        });
    }
});
