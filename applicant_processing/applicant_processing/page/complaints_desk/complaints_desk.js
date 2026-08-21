frappe.pages['complaints-desk'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __('Agency Complaints & Welfare Desk'),
        single_column: true
    });

    wrapper.complaints_desk = new ComplaintsDesk(page, wrapper);
};

class ComplaintsDesk {
    constructor(page, wrapper) {
        this.page = page;
        this.wrapper = $(wrapper);
        this.activeTab = 'unresolved';
        this.setup();
    }

    setup() {
        this.make_actions();
        this.make_body();
        this.fetch_and_render();
    }

    make_actions() {
        let me = this;
        this.page.set_primary_action(__('Log New Dispute'), () => me.open_new_complaint_dialog(), 'add');
        this.page.set_secondary_action(__('Refresh Queue'), () => me.fetch_and_render(), 'refresh');

        this.contractor_filter = this.page.add_field({
            fieldname: 'contractor',
            label: __('Filter Agency'),
            fieldtype: 'Link',
            options: 'Contractor',
            change: () => me.fetch_and_render()
        });
    }

    make_body() {
        let me = this;
        this.page.main.html(`
            <div class="complaints-desk-wrapper" style="padding: 15px 0;">
                <div class="desk-tabs" style="display: flex; gap: 10px; margin-bottom: 20px; border-bottom: 2px solid #e5e7eb;">
                    <button class="btn btn-default active" id="deskTabUnresolved" style="font-weight: 700; border-bottom: 2px solid #2563eb; margin-bottom: -2px;">
                        ⏳ Unresolved Queue (Oldest Waiting First)
                    </button>
                    <button class="btn btn-default" id="deskTabNew" style="font-weight: 700; border-bottom: none;">
                        ⚡ New Disputes
                    </button>
                    <button class="btn btn-default" id="deskTabResolved" style="font-weight: 700; border-bottom: none;">
                        ✅ Resolved & Free Replacements
                    </button>
                </div>

                <div id="deskComplaintsList" style="display: flex; flex-direction: column; gap: 12px;">
                    <div class="text-muted" style="text-align: center; padding: 40px;">Loading dispute queue...</div>
                </div>
            </div>
        `);

        this.page.main.find('#deskTabUnresolved').on('click', function() {
            me.switch_tab('unresolved', $(this));
        });
        this.page.main.find('#deskTabNew').on('click', function() {
            me.switch_tab('new', $(this));
        });
        this.page.main.find('#deskTabResolved').on('click', function() {
            me.switch_tab('resolved', $(this));
        });
    }

    switch_tab(tab, btn) {
        this.activeTab = tab;
        this.page.main.find('.desk-tabs button').removeClass('active').css({'border-bottom': 'none', 'color': '#6b7280'});
        btn.addClass('active').css({'border-bottom': '2px solid #2563eb', 'color': '#2563eb'});
        this.fetch_and_render();
    }

    fetch_and_render() {
        let me = this;
        let contractor = me.contractor_filter ? me.contractor_filter.get_value() : '';
        let listContainer = me.page.main.find('#deskComplaintsList');
        listContainer.html('<div class="text-muted" style="text-align: center; padding: 40px;">Loading complaints...</div>');

        frappe.call({
            method: 'applicant_processing.applicant_processing.api.get_agency_complaints',
            args: {
                tab: me.activeTab,
                contractor: contractor
            },
            callback: function(r) {
                let complaints = r.message || [];
                me.render_list(complaints);
            }
        });
    }

    render_list(complaints) {
        let me = this;
        let listContainer = me.page.main.find('#deskComplaintsList');

        if (!complaints.length) {
            listContainer.html(`
                <div style="text-align: center; padding: 50px; background: #fafafa; border: 1px dashed #d1d5db; border-radius: 8px;">
                    <h4>No complaints found in this queue.</h4>
                    <p class="text-muted">All agency disputes are currently settled.</p>
                </div>
            `);
            return;
        }

        let html = complaints.map((c, i) => {
            let days = c.days_unresolved || 0;
            let isUrgent = me.activeTab === 'unresolved';

            return `
                <div class="card" style="padding: 16px; border-radius: 8px; border: 1px solid #e5e7eb; display: grid; grid-template-columns: auto 1fr auto auto; gap: 16px; align-items: center; ${isUrgent ? 'border-left: 5px solid #ef4444;' : ''}">
                    <div style="width: 40px; height: 40px; border-radius: 8px; background: ${c.severity === 'Critical / Emergency' ? '#fee2e2' : '#f3f4f6'}; color: ${c.severity === 'Critical / Emergency' ? '#b91c1c' : '#374151'}; display: flex; align-items: center; justify-content: center; font-weight: 800;">
                        #${i + 1}
                    </div>

                    <div>
                        <div style="font-size: 15px; font-weight: 700; margin-bottom: 4px;">
                            <a href="/app/agency-complaint/${c.name}"><b>${c.full_name || c.applicant}</b></a>
                            <span class="badge" style="background: #eff6ff; color: #1e40af; margin-left: 8px;">${c.complaint_category}</span>
                            <span class="badge" style="background: #fef2f2; color: #991b1b; margin-left: 4px;">${c.severity}</span>
                            <span class="text-muted" style="font-size: 12px; margin-left: 8px;">Agency: <b>${c.contractor}</b></span>
                        </div>
                        <div class="text-muted" style="font-size: 13px;">
                            ${c.complaint_details}
                        </div>
                        ${c.resolution_notes ? `<div style="font-size: 12px; color: #059669; font-weight: 700; margin-top: 4px;">Outcome: ${c.resolution_outcome} | ${c.resolution_notes}</div>` : ''}
                    </div>

                    <div style="text-align: right;">
                        <div style="font-size: 18px; font-weight: 800; color: ${days > 5 ? '#dc2626' : '#2563eb'};">${days} Days</div>
                        <div class="text-muted" style="font-size: 11px; text-transform: uppercase;">Waiting Time</div>
                    </div>

                    <div>
                        ${me.activeTab !== 'resolved' ? `
                            <button class="btn btn-primary btn-sm btn-resolve-action" data-id="${c.name}">
                                Resolve Dispute
                            </button>
                        ` : `
                            <a href="/app/agency-complaint/${c.name}" class="btn btn-default btn-sm">View Log</a>
                        `}
                    </div>
                </div>
            `;
        }).join('');

        listContainer.html(html);

        listContainer.find('.btn-resolve-action').on('click', function() {
            let complaintId = $(this).attr('data-id');
            me.open_resolve_dialog(complaintId);
        });
    }

    open_new_complaint_dialog() {
        let me = this;
        let d = new frappe.ui.Dialog({
            title: __('Log Formal Agency Dispute / Grievance'),
            fields: [
                { fieldname: 'contractor', label: __('Foreign Agency (Contractor)'), fieldtype: 'Link', options: 'Contractor', reqd: 1 },
                { fieldname: 'applicant', label: __('Target Candidate / Worker'), fieldtype: 'Link', options: 'Applicant', reqd: 1 },
                { 
                    fieldname: 'complaint_category', 
                    label: __('Complaint Category'), 
                    fieldtype: 'Select', 
                    options: 'Salary Delay / Non-Payment\nFood & Nutrition\nLiving Conditions / Accommodation\nPhysical / Verbal Abuse\nExcessive Work Hours / Overwork\nMedical Illness\nRunaway / Refusal to Work\nRepatriation Request\nOther',
                    reqd: 1 
                },
                { 
                    fieldname: 'severity', 
                    label: __('Severity Level'), 
                    fieldtype: 'Select', 
                    options: 'Critical / Emergency\nHigh\nNormal',
                    default: 'High',
                    reqd: 1 
                },
                { fieldname: 'complaint_details', label: __('Incident & Dispute Details'), fieldtype: 'Small Text', reqd: 1 }
            ],
            primary_action_label: __('Submit Dispute'),
            primary_action: function(values) {
                frappe.call({
                    method: 'applicant_processing.applicant_processing.api.submit_agency_complaint',
                    args: values,
                    callback: function(r) {
                        if (r.message && r.message.status === 'success') {
                            frappe.show_alert({message: r.message.message, indicator: 'green'});
                            d.hide();
                            me.fetch_and_render();
                        }
                    }
                });
            }
        });
        d.show();
    }

    open_resolve_dialog(complaintId) {
        let me = this;
        let d = new frappe.ui.Dialog({
            title: __('Resolve Dispute & Settlement'),
            fields: [
                {
                    fieldname: 'outcome',
                    label: __('Resolution Outcome'),
                    fieldtype: 'Select',
                    options: 'Resolved\nReturned / Free Replacement Required\nEscalated to MoL / Embassy\nDismissed / Closed',
                    reqd: 1
                },
                { fieldname: 'resolution_notes', label: __('Settlement / Resolution Notes'), fieldtype: 'Small Text', reqd: 1 },
                { fieldname: 'return_date', label: __('Worker Return Date (If Returned)'), fieldtype: 'Date', depends_on: 'eval:doc.outcome=="Returned / Free Replacement Required"' }
            ],
            primary_action_label: __('Finalize Resolution'),
            primary_action: function(values) {
                values.complaint_id = complaintId;
                frappe.call({
                    method: 'applicant_processing.applicant_processing.api.resolve_agency_complaint',
                    args: values,
                    callback: function(r) {
                        if (r.message && r.message.status === 'success') {
                            frappe.show_alert({message: r.message.message, indicator: 'green'});
                            d.hide();
                            me.fetch_and_render();
                        }
                    }
                });
            }
        });
        d.show();
    }
}
