// Copyright (c) 2026, Admin and contributors
// For license information, please see license.txt

frappe.ui.form.on("CV Record", {
    refresh(frm) {
        if (frm.is_new()) return;

        // Show "Create Contract Request" only when CV is Final
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

        if (frm.doc.status === "Final" || frm.doc.status === "Shared") {
            frm.add_custom_button(__("Share CV"), function () {
                let d = new frappe.ui.Dialog({
                    title: 'Share CV',
                    fields: [
                        {
                            label: 'Contractors',
                            fieldname: 'contractors',
                            fieldtype: 'MultiSelect',
                            get_data: function() {
                                // Provide simple list for multiselect
                                return frappe.db.get_list('Contractor', {
                                    fields: ['name']
                                }).then(data => {
                                    return data.map(d => d.name);
                                });
                            },
                            reqd: 1,
                            description: 'Select one or more contractors.'
                        },
                        {
                            label: 'Channel',
                            fieldname: 'channel',
                            fieldtype: 'Select',
                            options: 'WhatsApp\nEmail',
                            reqd: 1
                        }
                    ],
                    size: 'small',
                    primary_action_label: 'Share',
                    primary_action(values) {
                        let contractor_list = values.contractors.split(',').map(c => c.trim()).filter(c => c);
                        
                        frappe.call({
                            method: "applicant_processing.applicant_processing.doctype.cv_record.cv_record.share_cv",
                            args: {
                                cv_name: frm.doc.name,
                                contractors: contractor_list,
                                channel: values.channel
                            },
                            freeze: true,
                            freeze_message: "Sharing CV...",
                            callback: function(r) {
                                if (!r.exc) {
                                    d.hide();
                                    frm.reload_doc();
                                    frappe.show_alert({message: r.message, indicator: 'green'});
                                }
                            }
                        });
                    }
                });
                d.show();
            });
        }
    }
});
