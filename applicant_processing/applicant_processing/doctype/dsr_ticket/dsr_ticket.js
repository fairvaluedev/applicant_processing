// Copyright (c) 2026, Admin and contributors
// For license information, please see license.txt

frappe.ui.form.on('DSR Ticket', {
	refresh: function(frm) {
		if (!frm.is_new() && frm.doc.ticket_number) {
			frappe.db.get_list('DSR Departure', {
				filters: { 'dsr': frm.doc.dsr },
				limit: 1
			}).then(records => {
				if (records.length === 0) {
					frm.add_custom_button('Proceed to Departure', () => {
						frappe.new_doc('DSR Departure', {
							dsr: frm.doc.dsr
						});
					}).addClass('btn-primary');
				}
			});
		}
	}
});
