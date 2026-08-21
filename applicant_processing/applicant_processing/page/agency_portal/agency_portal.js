frappe.pages['agency-portal'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __('Agency Candidate Selection Portal'),
        single_column: true
    });

    wrapper.agency_portal = new AgencySelectionDesk(page, wrapper);
};

class AgencySelectionDesk {
    constructor(page, wrapper) {
        this.page = page;
        this.wrapper = $(wrapper);
        this.candidates = [];
        this.activeContractor = '';
        this.setup();
    }

    setup() {
        this.make_filters();
        this.make_body();
        this.load_contractors();
    }

    make_filters() {
        let me = this;

        this.contractor_field = this.page.add_field({
            fieldname: 'contractor',
            label: __('Selecting Agency'),
            fieldtype: 'Link',
            options: 'Contractor',
            change: () => me.fetch_and_render()
        });

        this.country_field = this.page.add_field({
            fieldname: 'destination_country',
            label: __('Corridor'),
            fieldtype: 'Select',
            options: '\nSaudi Arabia\nKuwait\nUAE\nQatar\nJordan',
            default: 'Saudi Arabia',
            change: () => me.fetch_and_render()
        });

        this.job_field = this.page.add_field({
            fieldname: 'job_applied',
            label: __('Job Position'),
            fieldtype: 'Select',
            options: '\nHousemaid\nCook\nBaby Sitting\nElderly Care\nDriver',
            change: () => me.fetch_and_render()
        });

        this.page.set_primary_action(__('Refresh Candidates'), () => me.fetch_and_render(), 'refresh');
    }

    load_contractors() {
        let me = this;
        frappe.call({
            method: 'applicant_processing.applicant_processing.page.agency_portal.agency_portal.get_desk_portal_data',
            callback: function(r) {
                if (r.message && r.message.contractors && r.message.contractors.length > 0) {
                    me.contractor_field.set_value(r.message.contractors[0].name);
                } else {
                    me.fetch_and_render();
                }
            }
        });
    }

    make_body() {
        this.page.main.html(`
            <div class="agency-portal-container" style="padding: 15px 0;">
                <div id="agency-candidate-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px;">
                    <div class="text-muted" style="padding: 40px; text-align: center; grid-column: 1/-1;">Loading candidates...</div>
                </div>
            </div>
        `);
    }

    fetch_and_render() {
        let me = this;
        let contractor = me.contractor_field.get_value() || '';
        let country = me.country_field.get_value() || '';
        let job = me.job_field.get_value() || '';

        let grid = me.page.main.find('#agency-candidate-grid');
        grid.html('<div class="text-muted" style="padding: 40px; text-align: center; grid-column: 1/-1;">Loading candidate pool...</div>');

        frappe.call({
            method: 'applicant_processing.applicant_processing.api.get_portal_available_candidates',
            args: {
                contractor: contractor,
                destination_country: country,
                job_applied: job
            },
            callback: function(r) {
                me.candidates = r.message || [];
                me.render_grid(me.candidates, contractor);
            }
        });
    }

    render_grid(candidates, activeContractor) {
        let me = this;
        let grid = me.page.main.find('#agency-candidate-grid');

        if (!candidates.length) {
            grid.html(`
                <div style="grid-column: 1/-1; text-align: center; padding: 60px; background: #fafafa; border: 1px dashed #d1d5db; border-radius: 8px;">
                    <h4>No Available Candidates Found</h4>
                    <p class="text-muted">No unreserved applicants currently match the selected corridor/job filters.</p>
                </div>
            `);
            return;
        }

        let html = candidates.map(c => {
            let fullName = c.full_name || `${c.first_name || ''} ${c.last_name || ''}`;
            let photo = c.photo_passport || c.photo_full_body || '';
            let isLockedToMe = c.locked_contractor === activeContractor && activeContractor !== '';

            let skills = [];
            if (c.skill_cleaning) skills.push('Cleaning');
            if (c.skill_cooking) skills.push('Cooking');
            if (c.skill_arabic_cooking) skills.push('Arabic Chef');
            if (c.skill_baby_sitting) skills.push('Babysitting');
            if (c.skill_elderly_care) skills.push('Elderly Care');

            return `
                <div class="card" style="border-radius: 12px; border: 1px solid #e5e7eb; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.05); display: flex; flex-direction: column;">
                    <div style="height: 160px; background: #f3f4f6; display: flex; align-items: center; justify-content: center; position: relative; overflow: hidden;">
                        ${photo ? `<img src="${photo}" style="width: 100%; height: 100%; object-fit: cover;">` : `<span style="font-size: 3rem; color: #9ca3af; font-weight: bold;">${c.first_name ? c.first_name[0] : 'A'}</span>`}
                        <span style="position: absolute; top: 8px; right: 8px; background: rgba(0,0,0,0.75); color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">
                            ${c.destination_country || 'Saudi Arabia'}
                        </span>
                    </div>

                    <div style="padding: 16px; flex: 1; display: flex; flex-direction: column;">
                        <h4 style="margin: 0 0 4px 0; font-size: 16px; font-weight: 700;">${fullName}</h4>
                        <div style="font-size: 12px; font-weight: 700; color: #2563eb; text-transform: uppercase; margin-bottom: 12px;">
                            ${c.job_applied || 'Housemaid'}
                        </div>

                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; font-size: 12px; margin-bottom: 12px; background: #f9fafb; padding: 8px; border-radius: 6px;">
                            <div><span class="text-muted">Age:</span> <b>${c.age || '24'} Yrs</b></div>
                            <div><span class="text-muted">Religion:</span> <b>${c.religion || 'Muslim'}</b></div>
                            <div><span class="text-muted">Salary:</span> <b>${c.monthly_salary || '1000'} ${c.destination_country === 'Kuwait' ? 'KWD' : 'SAR'}</b></div>
                            <div><span class="text-muted">Status:</span> <b>${c.applicant_state || 'CV Generated'}</b></div>
                        </div>

                        <div style="display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 16px; flex: 1;">
                            ${skills.length ? skills.map(s => `<span class="badge" style="background: #eff6ff; color: #1d4ed8; font-size: 10px; padding: 2px 6px;">${s}</span>`).join('') : '<span class="badge" style="background: #f3f4f6; color: #4b5563; font-size: 10px; padding: 2px 6px;">General Maid</span>'}
                        </div>

                        <div style="display: flex; gap: 8px; margin-top: auto; border-top: 1px solid #f3f4f6; padding-top: 12px;">
                            <a href="/app/applicant/${c.name}" class="btn btn-default btn-xs" style="flex: 1; font-weight: 600;">View Profile</a>
                            <button class="btn btn-primary btn-xs btn-select-candidate" data-id="${c.name}" data-name="${fullName}" style="flex: 1.5; font-weight: 700; background: ${isLockedToMe ? '#059669' : '#2563eb'}; border: none;" ${isLockedToMe ? 'disabled' : ''}>
                                ${isLockedToMe ? 'Reserved' : 'Select Candidate'}
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        grid.html(html);

        grid.find('.btn-select-candidate').on('click', function() {
            let applicantId = $(this).attr('data-id');
            let candidateName = $(this).attr('data-name');
            let contractor = me.contractor_field.get_value();

            if (!contractor) {
                frappe.msgprint(__('Please select an active Agency (Contractor) in the filter above first.'));
                return;
            }

            frappe.confirm(
                __(`Are you sure you want to select and reserve candidate <b>${candidateName}</b> for <b>${contractor}</b>? This will lock the candidate for contract issuance.`),
                function() {
                    frappe.call({
                        method: 'applicant_processing.applicant_processing.api.portal_select_candidate',
                        args: {
                            applicant_id: applicantId,
                            contractor: contractor
                        },
                        callback: function(r) {
                            if (r.message && r.message.status === 'success') {
                                frappe.show_alert({message: r.message.message, indicator: 'green'});
                                me.fetch_and_render();
                            }
                        }
                    });
                }
            );
        });
    }
}
