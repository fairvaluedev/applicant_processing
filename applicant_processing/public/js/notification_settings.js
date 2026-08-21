frappe.ui.form.on("Notification Settings", {
    refresh(frm) {
        frappe.require("/assets/applicant_processing/js/web_push.js", function () {
            if (window.ApplicantWebPush) {
                window.ApplicantWebPush.init();
            }
        });

        frm.add_custom_button(__("🔔 Enable Chrome Desktop Alerts"), function () {
            frappe.require("/assets/applicant_processing/js/web_push.js", function () {
                window.ApplicantWebPush.subscribeUser(true);
            });
        }).addClass("btn-primary");

        frm.add_custom_button(__("Test Desktop Notification"), function () {
            frappe.require("/assets/applicant_processing/js/web_push.js", function () {
                window.ApplicantWebPush.sendTestPush();
            });
        });
    }
});
