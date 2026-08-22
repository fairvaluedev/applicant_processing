frappe.listview_settings["Contractor"] = {
	add_fields: ["company_name", "country", "contact_person", "phone", "active_status"],

	get_indicator(doc) {
		return doc.active_status
			? [__("Active"), "green", "active_status,=,1"]
			: [__("Inactive"), "gray", "active_status,=,0"];
	},

	onload(listview) {
		listview.page.add_inner_button(__("Commission Billing Export"), function () {
			const selected = listview.get_checked_items();
			const default_contractor = selected.length > 0 ? selected[0].name : "";

			const d = new frappe.ui.Dialog({
				title: __("Quick Commission Billing Export"),
				fields: [
					{
						fieldname: "contractor",
						label: __("Partner Agency"),
						fieldtype: "Link",
						options: "Contractor",
						default: default_contractor,
						reqd: 1,
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
						options: "Excel Spreadsheet (.xlsx)\nPDF Statement",
						default: "Excel Spreadsheet (.xlsx)",
						reqd: 1,
					},
				],
				primary_action_label: __("Download"),
				primary_action(values) {
					const fmt = values.export_format.includes("PDF") ? "pdf" : "excel";
					const params = new URLSearchParams({
						contractor: values.contractor,
						export_format: fmt,
						limit: values.batch_size,
					});
					window.open(
						`/api/method/applicant_processing.applicant_processing.utils.commission_export.export_unpaid_commission_report?${params}`,
						"_blank"
					);
					d.hide();
				},
			});

			d.show();
		});
	},
};
