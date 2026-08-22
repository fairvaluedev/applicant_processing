// Copyright (c) 2026, Admin and contributors
// For license information, please see license.txt

frappe.ui.form.on("Contractor", {
    refresh(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__("Export Unpaid Commissions"), function () {
                open_commission_export_dialog(frm);
            }, __("Commission & Billing"));

            frm.add_custom_button(__("Mark Commissions Paid"), function () {
                open_mark_paid_dialog(frm);
            }, __("Commission & Billing"));

            // Add indicator on form
            frappe.call({
                method: "applicant_processing.applicant_processing.utils.commission_export.get_unpaid_commission_summary",
                args: { contractor: frm.doc.name },
                callback: function (r) {
                    if (r.message && r.message.summary) {
                        let sum = r.message.summary;
                        if (sum.total_count > 0) {
                            frm.dashboard.clear_headline();
                            frm.dashboard.set_headline_alert(
                                `<div class="row align-items-center">
                                    <div class="col">
                                        <b>${sum.total_count} Departed Candidates</b> with Unpaid Commissions 
                                        (<span class="text-danger font-weight-bold">${frappe.format(sum.total_amount, { fieldtype: 'Currency' })} ${sum.currency}</span>)
                                    </div>
                                    <div class="col-auto">
                                        <button class="btn btn-xs btn-primary font-weight-bold" id="btn-quick-export-comm">Export Statement</button>
                                    </div>
                                </div>`,
                                "orange"
                            );
                            frm.dashboard.headline.find("#btn-quick-export-comm").on("click", function () {
                                open_commission_export_dialog(frm);
                            });
                        }
                    }
                }
            });
        }
    }
});

function open_commission_export_dialog(frm) {
    let contractor_name = frm.doc.name;
    let default_rate = frm.doc.default_commission_amount || 1000;
    let currency = frm.doc.default_commission_currency || "SAR";

    let d = new frappe.ui.Dialog({
        title: __("Agency Commission Billing & Export Statement"),
        fields: [
            {
                fieldname: "html_banner",
                fieldtype: "HTML",
                options: `<div style="padding: 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 12px;">
                    <div style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase;">Partner Agency</div>
                    <div style="font-size: 15px; font-weight: 800; color: #0f172a;">${frm.doc.company_name} (${frm.doc.country || 'Gulf Corridor'})</div>
                    <div style="margin-top: 6px; font-size: 12px; color: #334155;">
                        Preconfigured Rate: <b>${frappe.format(default_rate, { fieldtype: 'Currency' })} ${currency}</b> / candidate
                    </div>
                    <div id="dialog-stat-loading" style="margin-top: 6px; font-size: 11px; color: #0284c7;">
                        <span class="spinner-border spinner-border-sm"></span> Loading departed candidate counts...
                    </div>
                </div>`
            },
            {
                fieldname: "batch_size",
                label: __("Select Batch Size / Scope"),
                fieldtype: "Select",
                options: "30\n40\n50\n100\nAll",
                default: "30",
                reqd: 1,
                description: __("Export latest departed candidates in batches (e.g. Last 30 or 40)")
            },
            {
                fieldname: "export_format",
                label: __("Export Format"),
                fieldtype: "Select",
                options: "Excel Spreadsheet (.xlsx)\nPDF Statement / Invoice (.pdf)",
                default: "Excel Spreadsheet (.xlsx)",
                reqd: 1
            },
            {
                fieldname: "sec_dates",
                fieldtype: "Section Break",
                label: __("Optional Date Range Filters")
            },
            {
                fieldname: "from_date",
                label: __("Departure From Date"),
                fieldtype: "Date"
            },
            {
                fieldname: "to_date",
                label: __("Departure To Date"),
                fieldtype: "Date"
            }
        ],
        primary_action_label: __("Download Export File"),
        primary_action(values) {
            let format_val = values.export_format.includes("PDF") ? "pdf" : "excel";
            let batch_val = values.batch_size;
            let from_val = values.from_date || "";
            let to_val = values.to_date || "";

            let url = `/api/method/applicant_processing.applicant_processing.utils.commission_export.export_unpaid_commission_report?contractor=${encodeURIComponent(contractor_name)}&export_format=${format_val}&limit=${batch_val}&from_date=${from_val}&to_date=${to_val}`;

            window.open(url, "_blank");
            d.hide();
        }
    });

    d.add_custom_action(__("Mark Batch as Paid"), function () {
        let values = d.get_values();
        d.hide();
        open_mark_paid_dialog(frm, values ? values.batch_size : 30);
    });

    d.show();

    // Fetch live summary counts
    frappe.call({
        method: "applicant_processing.applicant_processing.utils.commission_export.get_unpaid_commission_summary",
        args: { contractor: contractor_name },
        callback: function (r) {
            if (r.message && r.message.summary) {
                let sum = r.message.summary;
                let loadingEl = d.$wrapper.find("#dialog-stat-loading");
                loadingEl.html(`
                    <div style="display: flex; gap: 12px; margin-top: 8px;">
                        <span class="badge badge-danger" style="font-size: 11px; padding: 5px 8px;">
                            ${sum.total_count} Departed Candidates Unpaid
                        </span>
                        <span class="badge badge-success" style="font-size: 11px; padding: 5px 8px;">
                            Total Outstanding: ${frappe.format(sum.total_amount, { fieldtype: 'Currency' })} ${sum.currency}
                        </span>
                    </div>
                `);
            }
        }
    });
}

function open_mark_paid_dialog(frm, default_limit = 30) {
    let contractor_name = frm.doc.name;

    let d = new frappe.ui.Dialog({
        title: __("Mark Agency Commissions as Settled / Paid"),
        fields: [
            {
                fieldname: "html_info",
                fieldtype: "HTML",
                options: `<p style="font-size: 12px; color: #475569;">
                    This will mark the selected batch of departed candidates for <b>${frm.doc.company_name}</b> as <b>Paid</b> and automatically generate Income Logs in the accounting ledger.
                </p>`
            },
            {
                fieldname: "batch_limit",
                label: __("Batch Scope (Candidates Count)"),
                fieldtype: "Select",
                options: "30\n40\n50\n100\nAll",
                default: String(default_limit || "30"),
                reqd: 1
            },
            {
                fieldname: "payment_date",
                label: __("Payment / Settlement Date"),
                fieldtype: "Date",
                default: frappe.datetime.get_today(),
                reqd: 1
            },
            {
                fieldname: "reference",
                label: __("Bank Transfer / Invoice Reference #"),
                fieldtype: "Data",
                placeholder: "e.g. WIRE-SA-2026-9912 or Musaned Receipt #",
                reqd: 1
            }
        ],
        primary_action_label: __("Confirm Settlement & Post Ledger"),
        primary_action(values) {
            frappe.confirm(
                __("Are you sure you want to mark up to {0} candidates as Paid with reference '{1}'?", [values.batch_limit, values.reference]),
                function () {
                    frappe.call({
                        method: "applicant_processing.applicant_processing.utils.commission_export.mark_commissions_as_paid",
                        args: {
                            contractor: contractor_name,
                            limit: values.batch_limit,
                            reference: values.reference,
                            payment_date: values.payment_date
                        },
                        freeze: true,
                        freeze_message: __("Updating candidate commission records and posting ledger..."),
                        callback: function (r) {
                            if (r.message && r.message.status === "success") {
                                frappe.msgprint({
                                    title: __("Commissions Settled"),
                                    indicator: "green",
                                    message: r.message.message
                                });
                                d.hide();
                                frm.reload_doc();
                            } else {
                                frappe.msgprint({
                                    title: __("Settlement Notice"),
                                    indicator: "orange",
                                    message: r.message ? r.message.message : __("No candidates updated.")
                                });
                            }
                        }
                    });
                }
            );
        }
    });

    d.show();
}
