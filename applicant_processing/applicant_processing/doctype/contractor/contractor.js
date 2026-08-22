// Copyright (c) 2026, Admin and contributors
// For license information, please see license.txt

frappe.ui.form.on("Contractor", {
	refresh(frm) {
		frm.add_custom_button(__("View Commission Desk"), function () {
			frappe.set_route("agency-commissions");
		}, __("Commission"));

		frm.add_custom_button(__("Export Statement"), function () {
			_open_export_dialog(frm);
		}, __("Commission"));

		frm.add_custom_button(__("Mark Batch as Paid"), function () {
			_open_settlement_dialog(frm);
		}, __("Commission"));

		// Lazy-load a live count banner only on saved docs
		if (!frm.is_new()) {
			frappe.call({
				method: "applicant_processing.applicant_processing.utils.commission_export.get_unpaid_commission_summary",
				args: { contractor: frm.doc.name },
				callback(r) {
					if (!r.message || !r.message.summary) return;
					const s = r.message.summary;
					if (s.total_count > 0) {
						frm.dashboard.set_headline_alert(
							`<span>
								<strong>${s.total_count}</strong> ${__("departed candidates with unpaid commissions")} —
								<strong>${frappe.format(s.total_amount, { fieldtype: "Currency" })} ${frappe.utils.escape_html(s.currency)}</strong>
							</span>
							<a href="/app/agency-commissions?contractor=${encodeURIComponent(frm.doc.name)}"
							   style="margin-left:12px;"
							   class="btn btn-xs btn-warning">
							   ${__("Open Commission Desk")}
							</a>`,
							"orange"
						);
					}
				},
			});
		}
	},
});

// ─────────────────────────────────────────────────────────────────────────────

function _open_export_dialog(frm) {
	const contractor = frm.doc.name;
	const rate = frm.doc.default_commission_amount || 0;
	const currency = frm.doc.default_commission_currency || "SAR";

	const d = new frappe.ui.Dialog({
		title: __("Export Unpaid Commission Statement"),
		fields: [
			{
				fieldname: "summary_html",
				fieldtype: "HTML",
				options: `
					<div style="background:var(--subtle-fg,#f8fafc);border:1px solid var(--border-color,#e2e8f0);
					            border-radius:var(--border-radius,6px);padding:10px 14px;margin-bottom:6px;font-size:12px;">
						<div><strong>${__("Agency:")}</strong> ${frappe.utils.escape_html(frm.doc.company_name)}</div>
						<div><strong>${__("Rate / Candidate:")}</strong>
							${frappe.format(rate, { fieldtype: "Currency" })} ${frappe.utils.escape_html(currency)}
						</div>
						<div id="export-dlg-count" style="color:var(--text-muted);margin-top:4px;">
							${__("Loading candidate count…")}
						</div>
					</div>
				`,
			},
			{
				fieldname: "batch_size",
				label: __("Batch Limit"),
				fieldtype: "Select",
				options: "30\n40\n50\n100\nAll",
				default: "30",
				reqd: 1,
			},
			{
				fieldname: "export_format",
				label: __("Format"),
				fieldtype: "Select",
				options: `Excel Spreadsheet (.xlsx)\nPDF Statement`,
				default: "Excel Spreadsheet (.xlsx)",
				reqd: 1,
			},
			{
				fieldname: "col_break",
				fieldtype: "Column Break",
			},
			{
				fieldname: "from_date",
				label: __("Departure From"),
				fieldtype: "Date",
			},
			{
				fieldname: "to_date",
				label: __("Departure To"),
				fieldtype: "Date",
			},
		],
		primary_action_label: __("Download"),
		primary_action(values) {
			const fmt = values.export_format.includes("PDF") ? "pdf" : "excel";
			const params = new URLSearchParams({
				contractor,
				export_format: fmt,
				limit: values.batch_size,
				from_date: values.from_date || "",
				to_date: values.to_date || "",
			});
			window.open(
				`/api/method/applicant_processing.applicant_processing.utils.commission_export.export_unpaid_commission_report?${params}`,
				"_blank"
			);
			d.hide();
		},
	});

	d.show();

	// Async count fetch once dialog is open
	frappe.call({
		method: "applicant_processing.applicant_processing.utils.commission_export.get_unpaid_commission_summary",
		args: { contractor },
		callback(r) {
			if (r.message && r.message.summary) {
				const s = r.message.summary;
				d.$wrapper.find("#export-dlg-count").html(
					`<strong>${s.total_count}</strong> ${__("unpaid departed candidates")} — ${__("Total:")}
					<strong>${frappe.format(s.total_amount, { fieldtype: "Currency" })} ${frappe.utils.escape_html(s.currency)}</strong>`
				);
			}
		},
	});
}

// ─────────────────────────────────────────────────────────────────────────────

function _open_settlement_dialog(frm) {
	const contractor = frm.doc.name;

	const d = new frappe.ui.Dialog({
		title: __("Settle Commission Batch"),
		fields: [
			{
				fieldname: "batch_limit",
				label: __("Batch Limit"),
				fieldtype: "Select",
				options: "30\n40\n50\n100\nAll",
				default: "30",
				reqd: 1,
			},
			{
				fieldname: "payment_date",
				label: __("Settlement Date"),
				fieldtype: "Date",
				default: frappe.datetime.get_today(),
				reqd: 1,
			},
			{
				fieldname: "reference",
				label: __("Bank Transfer / Receipt Reference"),
				fieldtype: "Data",
				placeholder: __("e.g. WIRE-SA-2026-9901"),
				reqd: 1,
				description: __("Recorded in the ledger against each candidate."),
			},
		],
		primary_action_label: __("Confirm & Post to Ledger"),
		primary_action(values) {
			frappe.call({
				method: "applicant_processing.applicant_processing.utils.commission_export.mark_commissions_as_paid",
				args: {
					contractor,
					limit: values.batch_limit,
					reference: values.reference,
					payment_date: values.payment_date,
				},
				freeze: true,
				freeze_message: __("Settling commissions and posting to financial ledger…"),
				callback(r) {
					if (r.message) {
						frappe.msgprint({
							title: __("Settlement Complete"),
							indicator: r.message.status === "success" ? "green" : "orange",
							message: r.message.message,
						});
						d.hide();
						frm.reload_doc();
					}
				},
				error() {
					frappe.msgprint({
						title: __("Error"),
						indicator: "red",
						message: __("An error occurred. Check the Error Log."),
					});
				},
			});
		},
	});

	d.show();
}
