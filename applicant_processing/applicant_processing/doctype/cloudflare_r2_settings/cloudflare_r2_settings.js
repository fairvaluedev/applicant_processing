// Copyright (c) 2026, Admin and contributors
// For license information, please see license.txt

frappe.ui.form.on('Cloudflare R2 Settings', {
    refresh: function(frm) {
        frm.add_custom_button(__('Test Connection'), function() {
            frappe.call({
                method: 'applicant_processing.applicant_processing.doctype.cloudflare_r2_settings.cloudflare_r2_settings.test_r2_connection',
                freeze: true,
                freeze_message: __('Testing Cloudflare R2 Connection...'),
                callback: function(r) {
                    if (r.message && r.message.status === 'success') {
                        frappe.msgprint({
                            title: __('Connection Successful'),
                            indicator: 'green',
                            message: r.message.message
                        });
                        frm.set_value('test_status', 'SUCCESS: ' + r.message.message);
                    } else {
                        frappe.msgprint({
                            title: __('Connection Failed'),
                            indicator: 'red',
                            message: (r.message && r.message.message) || __('Could not connect to Cloudflare R2.')
                        });
                        frm.set_value('test_status', 'FAILED: ' + ((r.message && r.message.message) || 'Unknown error'));
                    }
                }
            });
        });
    }
});
