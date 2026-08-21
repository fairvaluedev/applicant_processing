frappe.pages['agency-portal'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __('Agency Candidate Sourcing & Selection Desk'),
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
        this.searchQuery = '';
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
            label: __('Selecting Partner Agency'),
            fieldtype: 'Link',
            options: 'Contractor',
            change: () => me.fetch_and_render()
        });

        this.country_field = this.page.add_field({
            fieldname: 'destination_country',
            label: __('Target Corridor'),
            fieldtype: 'Select',
            options: '\nSaudi Arabia\nKuwait\nUAE\nQatar\nJordan\nOman',
            default: '',
            change: () => me.fetch_and_render()
        });

        this.job_field = this.page.add_field({
            fieldname: 'job_applied',
            label: __('Position / Skill'),
            fieldtype: 'Select',
            options: '\nHousemaid\nCook\nArabic Chef\nBaby Sitting\nElderly Care\nDriver\nGeneral Cleaner',
            default: '',
            change: () => me.fetch_and_render()
        });

        this.page.set_primary_action(__('Refresh Candidate Pool'), () => me.fetch_and_render(), 'refresh');

        this.page.add_inner_button(__('Open Partner Portal ↗'), () => {
            window.open('/agency_portal', '_blank');
        });
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
            <div class="agency-portal-wrapper" style="padding: 10px 0;">
                <!-- Hero Metrics Banner -->
                <div class="portal-hero-card" style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #fff; border-radius: 16px; padding: 24px; margin-bottom: 20px; box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.2); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px;">
                    <div>
                        <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: #38bdf8; margin-bottom: 4px;">Verified Talent Pool</div>
                        <h2 style="font-size: 22px; font-weight: 800; color: #ffffff; margin: 0 0 6px 0;">Candidate Selection & Reservation Desk</h2>
                        <p style="font-size: 13px; color: #94a3b8; margin: 0; max-width: 600px; line-height: 1.4;">
                            Browse pre-screened, medical-verified candidates. Reserve candidates with atomic row locking to issue Musaned contracts and start visa stamping.
                        </p>
                    </div>
                    <div style="display: flex; gap: 12px; flex-wrap: wrap;">
                        <div style="background: rgba(255,255,255,0.08); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.12); padding: 12px 18px; border-radius: 12px; text-align: center; min-width: 110px;">
                            <div id="stat-available" style="font-size: 24px; font-weight: 800; color: #38bdf8;">--</div>
                            <div style="font-size: 11px; font-weight: 600; color: #cbd5e1; text-transform: uppercase;">Available Pool</div>
                        </div>
                        <div style="background: rgba(255,255,255,0.08); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.12); padding: 12px 18px; border-radius: 12px; text-align: center; min-width: 110px;">
                            <div id="stat-selected" style="font-size: 24px; font-weight: 800; color: #10b981;">--</div>
                            <div style="font-size: 11px; font-weight: 600; color: #cbd5e1; text-transform: uppercase;">Reserved Today</div>
                        </div>
                    </div>
                </div>

                <!-- Instant Search & Quick Filter Bar -->
                <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px 18px; margin-bottom: 20px; display: flex; gap: 14px; align-items: center; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
                    <div style="font-size: 18px; color: #64748b;">🔍</div>
                    <input type="text" id="candidate-live-search" placeholder="Type candidate name, passport number, religion, or skill to filter instantly..." style="flex: 1; border: none; outline: none; font-size: 14px; font-weight: 500; color: #1e293b;" />
                    <button id="btn-clear-search" style="display: none; background: #f1f5f9; border: none; border-radius: 6px; padding: 4px 10px; font-size: 12px; font-weight: 600; color: #64748b; cursor: pointer;">Clear</button>
                </div>

                <!-- Candidate Grid -->
                <div id="agency-candidate-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 20px;">
                    <div class="text-muted" style="padding: 60px; text-align: center; grid-column: 1/-1;">Loading candidate pool...</div>
                </div>
            </div>
        `);

        let me = this;
        this.page.main.find('#candidate-live-search').on('input', function() {
            let val = $(this).val().toLowerCase().trim();
            me.searchQuery = val;
            me.page.main.find('#btn-clear-search').toggle(!!val);
            me.filter_and_render_cards();
        });

        this.page.main.find('#btn-clear-search').on('click', function() {
            me.page.main.find('#candidate-live-search').val('').trigger('input');
        });
    }

    fetch_and_render() {
        let me = this;
        let contractor = me.contractor_field.get_value() || '';
        let country = me.country_field.get_value() || '';
        let job = me.job_field.get_value() || '';

        let grid = me.page.main.find('#agency-candidate-grid');
        grid.html('<div class="text-muted" style="padding: 60px; text-align: center; grid-column: 1/-1;"><span class="spinner-border spinner-border-sm" role="status"></span> Fetching verified candidates...</div>');

        frappe.call({
            method: 'applicant_processing.applicant_processing.api.get_portal_available_candidates',
            args: {
                contractor: contractor,
                destination_country: country,
                job_applied: job,
                limit: 100
            },
            callback: function(r) {
                me.candidates = r.message || [];
                me.update_stats();
                me.filter_and_render_cards();
            }
        });
    }

    update_stats() {
        let me = this;
        let availableCount = me.candidates.filter(c => !c.locked_contractor).length;
        let reservedCount = me.candidates.filter(c => !!c.locked_contractor).length;

        me.page.main.find('#stat-available').text(availableCount);
        me.page.main.find('#stat-selected').text(reservedCount);
    }

    filter_and_render_cards() {
        let me = this;
        let contractor = me.contractor_field.get_value() || '';
        let q = me.searchQuery;

        let filtered = me.candidates;
        if (q) {
            filtered = me.candidates.filter(c => {
                let name = (c.full_name || `${c.first_name || ''} ${c.last_name || ''}`).toLowerCase();
                let pass = (c.passport_number || '').toLowerCase();
                let job = (c.job_applied || '').toLowerCase();
                let religion = (c.religion || '').toLowerCase();
                let country = (c.destination_country || '').toLowerCase();
                return name.includes(q) || pass.includes(q) || job.includes(q) || religion.includes(q) || country.includes(q);
            });
        }

        me.render_grid(filtered, contractor);
    }

    render_grid(candidates, activeContractor) {
        let me = this;
        let grid = me.page.main.find('#agency-candidate-grid');

        if (!candidates.length) {
            grid.html(`
                <div style="grid-column: 1/-1; text-align: center; padding: 70px 20px; background: #ffffff; border: 2px dashed #e2e8f0; border-radius: 16px;">
                    <div style="font-size: 40px; margin-bottom: 12px;">📋</div>
                    <h4 style="font-weight: 700; color: #1e293b; margin-bottom: 6px;">No Matching Candidates in Pool</h4>
                    <p style="color: #64748b; font-size: 13px; max-width: 420px; margin: 0 auto 16px auto;">
                        No unreserved candidates match your current corridor, job, or search filters.
                    </p>
                    <button class="btn btn-sm btn-primary" onclick="cur_page.main.find('#candidate-live-search').val('').trigger('input');">
                        Reset Search Filters
                    </button>
                </div>
            `);
            return;
        }

        let countryFlags = {
            'Saudi Arabia': '🇸🇦 KSA',
            'Kuwait': '🇰🇼 Kuwait',
            'UAE': '🇦🇪 UAE',
            'Qatar': '🇶🇦 Qatar',
            'Jordan': '🇯🇴 Jordan',
            'Oman': '🇴🇲 Oman'
        };

        let html = candidates.map(c => {
            let fullName = c.full_name || `${c.first_name || ''} ${c.last_name || ''}`;
            let photo = c.photo_passport || c.photo_full_body || '';
            let isLockedToMe = c.locked_contractor === activeContractor && activeContractor !== '';
            let isLockedToOther = c.locked_contractor && c.locked_contractor !== activeContractor;
            let flagBadge = countryFlags[c.destination_country] || `🌐 ${c.destination_country || 'GCC'}`;

            let skills = [];
            if (c.skill_cleaning) skills.push('🧹 Cleaning');
            if (c.skill_cooking) skills.push('🍳 Cooking');
            if (c.skill_arabic_cooking) skills.push('🍲 Arabic Chef');
            if (c.skill_baby_sitting) skills.push('👶 Child Care');
            if (c.skill_elderly_care) skills.push('👵 Elderly Care');
            if (c.skill_sewing) skills.push('🧵 Sewing');

            let experienceBadge = c.experience_country ? `${c.experience_country} (${c.experience_period || 'Exp'})` : 'First Timer';

            let actionButton = '';
            if (isLockedToMe) {
                actionButton = `
                    <div style="display: flex; gap: 8px; width: 100%;">
                        <button class="btn btn-sm" style="flex: 1; background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; font-weight: 700; font-size: 12px; cursor: default;">
                            ✓ Reserved by You
                        </button>
                        <button class="btn btn-sm btn-outline-danger btn-release-candidate" data-id="${c.name}" style="font-weight: 600; font-size: 12px;" title="Release candidate back to public pool">
                            Release
                        </button>
                    </div>
                `;
            } else if (isLockedToOther) {
                actionButton = `
                    <button class="btn btn-sm btn-light" disabled style="width: 100%; color: #94a3b8; font-weight: 600; font-size: 12px;">
                        🔒 Reserved by ${c.locked_contractor}
                    </button>
                `;
            } else {
                actionButton = `
                    <button class="btn btn-sm btn-primary btn-select-candidate" data-id="${c.name}" style="width: 100%; font-weight: 700; font-size: 13px; border-radius: 8px; box-shadow: 0 2px 6px rgba(37, 99, 235, 0.25);">
                        ⚡ Select & Reserve Candidate
                    </button>
                `;
            }

            return `
                <div class="candidate-desk-card" style="background: #ffffff; border-radius: 16px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); display: flex; flex-direction: column; transition: all 0.2s ease;">
                    <!-- Photo Card Header -->
                    <div style="height: 180px; background: #f1f5f9; position: relative; overflow: hidden; display: flex; align-items: center; justify-content: center;">
                        ${photo ? `<img src="${photo}" style="width: 100%; height: 100%; object-fit: cover; object-position: top;" onerror="this.style.display='none'">` : ''}
                        ${!photo ? `<div style="font-size: 48px; color: #cbd5e1; font-weight: 800;">${c.first_name ? c.first_name[0] : 'A'}</div>` : ''}

                        <span style="position: absolute; top: 12px; right: 12px; background: rgba(15, 23, 42, 0.85); backdrop-filter: blur(6px); color: #ffffff; padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: 700;">
                            ${flagBadge}
                        </span>

                        <span style="position: absolute; bottom: 12px; left: 12px; background: #ffffff; color: #1e293b; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 700; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                            ${experienceBadge}
                        </span>
                    </div>

                    <!-- Details Body -->
                    <div style="padding: 16px; flex: 1; display: flex; flex-direction: column;">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 4px;">
                            <h4 style="margin: 0; font-size: 16px; font-weight: 800; color: #0f172a;">${fullName}</h4>
                            <span style="font-size: 11px; font-weight: 600; color: #64748b; background: #f1f5f9; padding: 2px 6px; border-radius: 4px;">${c.name}</span>
                        </div>

                        <div style="font-size: 12px; font-weight: 700; color: #2563eb; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px;">
                            ${c.job_applied || 'Housemaid'}
                        </div>

                        <!-- Meta Grid -->
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; font-size: 12px; margin-bottom: 12px; background: #f8fafc; padding: 10px; border-radius: 10px; border: 1px solid #f1f5f9;">
                            <div><span style="color: #64748b;">Age:</span> <b style="color: #1e293b;">${c.age || '25'} Yrs</b></div>
                            <div><span style="color: #64748b;">Religion:</span> <b style="color: #1e293b;">${c.religion || 'Muslim'}</b></div>
                            <div><span style="color: #64748b;">Salary:</span> <b style="color: #10b981;">${c.monthly_salary || '1000'} ${c.destination_country === 'Kuwait' ? 'KWD' : 'SAR'}</b></div>
                            <div><span style="color: #64748b;">Status:</span> <b style="color: #1e293b;">${c.applicant_state || 'Registered'}</b></div>
                        </div>

                        <!-- Skill Tags -->
                        <div style="display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 14px; min-height: 48px; align-content: flex-start;">
                            ${skills.map(s => `<span style="background: #eff6ff; color: #1e40af; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 6px;">${s}</span>`).join('')}
                            ${!skills.length ? `<span style="color: #94a3b8; font-size: 11px;">Standard General Skills</span>` : ''}
                        </div>

                        <!-- Action Footer -->
                        <div style="margin-top: auto; padding-top: 12px; border-top: 1px solid #f1f5f9; display: flex; flex-direction: column; gap: 8px;">
                            ${c.cv_file_url ? `
                                <a href="${c.cv_file_url}" target="_blank" class="btn btn-xs btn-default" style="font-weight: 600; font-size: 11px; text-align: center; padding: 5px;">
                                    📄 View Bilingual CV (PDF)
                                </a>
                            ` : ''}
                            ${actionButton}
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        grid.html(html);

        // Bind Select Action
        grid.find('.btn-select-candidate').on('click', function(e) {
            e.preventDefault();
            let appName = $(this).data('id');
            me.select_candidate(appName);
        });

        // Bind Release Action
        grid.find('.btn-release-candidate').on('click', function(e) {
            e.preventDefault();
            let appName = $(this).data('id');
            me.release_candidate(appName);
        });
    }

    select_candidate(applicantName) {
        let me = this;
        let contractor = me.contractor_field.get_value();

        if (!contractor) {
            frappe.msgprint({
                title: __('Selecting Agency Required'),
                indicator: 'orange',
                message: __('Please choose the <strong>Selecting Partner Agency</strong> in the top filter before reserving a candidate.')
            });
            return;
        }

        frappe.confirm(
            __('Are you sure you want to reserve candidate <b>{0}</b> for <b>{1}</b>?<br><br>This will lock the candidate and create an active Contract Request.', [applicantName, contractor]),
            function() {
                frappe.call({
                    method: 'applicant_processing.applicant_processing.api.portal_select_candidate',
                    args: {
                        applicant_id: applicantName,
                        contractor: contractor
                    },
                    freeze: true,
                    freeze_message: __('Acquiring Atomic Row Lock & Reserving Candidate...'),
                    callback: function(r) {
                        if (!r.exc && r.message && r.message.status === 'success') {
                            frappe.show_alert({
                                message: r.message.message || __('Candidate successfully reserved!'),
                                indicator: 'green'
                            }, 5);
                            me.fetch_and_render();
                        }
                    }
                });
            }
        );
    }

    release_candidate(applicantName) {
        let me = this;
        let contractor = me.contractor_field.get_value();

        frappe.confirm(
            __('Release reservation for candidate <b>{0}</b> back to the public pool?', [applicantName]),
            function() {
                frappe.call({
                    method: 'applicant_processing.applicant_processing.api.portal_release_candidate',
                    args: {
                        applicant_id: applicantName,
                        contractor: contractor
                    },
                    freeze: true,
                    freeze_message: __('Releasing Candidate Lock...'),
                    callback: function(r) {
                        if (!r.exc) {
                            frappe.show_alert({
                                message: r.message.message || __('Candidate released back to pool.'),
                                indicator: 'blue'
                            }, 5);
                            me.fetch_and_render();
                        }
                    }
                });
            }
        );
    }
}
