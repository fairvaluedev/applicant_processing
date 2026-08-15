// Copyright (c) 2026, Admin and contributors
// For license information, please see license.txt

frappe.ui.form.on("DSR Departure", {
	refresh(frm) {
		frm.trigger("toggle_medical_2_fields");
	},

	medical_2_result(frm) {
		frm.trigger("toggle_medical_2_fields");
	},

	toggle_medical_2_fields(frm) {
		const is_fail = frm.doc.medical_2_result === "Fail";
		frm.set_df_property("medical_2_remark", "reqd", is_fail ? 1 : 0);

		if (is_fail) {
			frm.dashboard.set_headline_alert(
				__("Medical 2 FAILED: Applicant cannot be departed. Please add remarks explaining the medical condition."),
				"red"
			);
		} else if (frm.doc.medical_2_result === "Pass") {
			frm.dashboard.set_headline_alert(
				__("Medical 2 PASSED: Applicant is cleared for departure."),
				"green"
			);
		} else {
			frm.dashboard.clear_headline();
		}
	}
});
