// Copyright (c) 2026, Admin and contributors
// For license information, please see license.txt

frappe.ui.form.on("DSR", {
	refresh(frm) {
		if (frm.is_new()) return;

		const lms_done = frm.doc.lms_status === "Completed";
		const wakala_done = frm.doc.wakala_status === "Completed";
		const injaz_done = frm.doc.injaz_status === "Completed";

		const all_clearances_done = lms_done && wakala_done && injaz_done;

		if (!all_clearances_done) {
			const pending = [];
			if (!injaz_done) pending.push("INJAZ");
			if (!wakala_done) pending.push("Wakala");
			if (!lms_done) pending.push("LMS");

			frm.dashboard.set_headline_alert(
				__("Clearances Incomplete: ") + pending.join(", ") + __(". Stamp, Ticket, and Departure are locked until all 3 clearances are completed."),
				"orange"
			);
		} else {
			frm.dashboard.set_headline_alert(
				__("All Clearances Completed (INJAZ + Wakala + LMS). Stamp, Ticket, and Departure actions unlocked."),
				"green"
			);

			// Add quick action buttons
			frm.add_custom_button(__("Create Stamp"), function () {
				frappe.new_doc("DSR Stamp", { dsr: frm.doc.name });
			}, __("Actions")).addClass("btn-primary");

			frm.add_custom_button(__("Create Ticket"), function () {
				frappe.new_doc("DSR Ticket", { dsr: frm.doc.name });
			}, __("Actions"));

			frm.add_custom_button(__("Create Departure"), function () {
				frappe.new_doc("DSR Departure", { dsr: frm.doc.name });
			}, __("Actions"));
		}
	}
});
