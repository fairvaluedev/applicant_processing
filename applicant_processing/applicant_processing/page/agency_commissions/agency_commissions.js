// Copyright (c) 2026, Admin and contributors
// For license information, please see license.txt

frappe.pages['agency-commissions'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __('Agency Commission & Billing Desk'),
        single_column: true
    });

    wrapper.commission_desk = new AgencyCommissionDesk(page, wrapper);
};

class AgencyCommissionDesk {
    constructor(page, wrapper) {
        this.page = page;
        this.wrapper = $(wrapper);
        this.contractor = '';
        this.candidates = [];
        this.summary = {};
        this.searchQuery = '';
        this.setup();
    }

    setup() {
        this.make_filters();
        this.make_body();
        this.load_initial_data();
    }

    make_filters() {
        let me = this;

        this.contractor_field = this.page.add_field({
            fieldname: 'contractor',
            label: __('Partner Agency'),
            fieldtype: 'Link',
            options: 'Contractor',
            change: () => {
                me.contractor = me.contractor_field.get_value();
                me.fetch_and_render();
            }
        });

        this.batch_field = this.page.add_field({
            fieldname: 'batch_size',
            label: __('Batch Scope'),
            fieldtype: 'Select',
            options: '30\n40\n50\n100\nAll',
            default: '30',
            change: () => me.fetch_and_render()
        });

        this.from_date_field = this.page.add_field({
            fieldname: 'from_date',
            label: __('Departure From'),
            fieldtype: 'Date',
            change: () => me.fetch_and_render()
        });

        this.to_date_field = this.page.add_field({
            fieldname: 'to_date',
            label: __('Departure To'),
            fieldtype: 'Date',
            change: () => me.fetch_and_render()
        });

        this.page.set_primary_action(__('Export Excel (.xlsx)'), () => me.export_report('excel'), 'download');

        this.page.add_inner_button(__('Export PDF Statement'), () => me.export_report('pdf'), __('Export Actions'));
        this.page.add_inner_button(__('Refresh Data'), () => me.fetch_and_render(), __('Actions'));
        this.page.add_inner_button(__('Settle / Mark Batch Paid'), () => me.open_mark_paid_modal(), __('Actions'));
    }

    load_initial_data() {
        let me = this;
        frappe.call({
            method: 'applicant_processing.applicant_processing.page.agency_commissions.agency_commissions.get_initial_desk_data',
            callback: function(r) {
                if (r.message && r.message.default_contractor) {
                    me.contractor_field.set_value(r.message.default_contractor);
                } else {
                    me.fetch_and_render();
                }
            }
        });
    }

    make_body() {
        this.page.main.html(`
            <div class="commission-desk-wrapper" style="padding: 10px 0;">
                <!-- Hero Metric Cards -->
                <div class="commission-hero-card" style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #fff; border-radius: 16px; padding: 22px; margin-bottom: 20px; box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.2); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px;">
                    <div>
                        <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: #38bdf8; margin-bottom: 4px;">Recruitment Ledger & Billing</div>
                        <h2 id="hero-agency-name" style="font-size: 22px; font-weight: 800; color: #ffffff; margin: 0 0 6px 0;">Select a Partner Agency</h2>
                        <p id="hero-agency-desc" style="font-size: 13px; color: #94a3b8; margin: 0; max-width: 600px; line-height: 1.4;">
                            Tracking departed & deployed candidates with unpaid partner commissions. Export batches in Excel or PDF statement formats.
                        </p>
                    </div>
                    <div style="display: flex; gap: 12px; flex-wrap: wrap;">
                        <div style="background: rgba(255,255,255,0.08); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.12); padding: 12px 18px; border-radius: 12px; text-align: center; min-width: 120px;">
                            <div id="stat-rate" style="font-size: 20px; font-weight: 800; color: #38bdf8;">--</div>
                            <div style="font-size: 10px; font-weight: 600; color: #cbd5e1; text-transform: uppercase;">Agreed Rate</div>
                        </div>
                        <div style="background: rgba(255,255,255,0.08); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.12); padding: 12px 18px; border-radius: 12px; text-align: center; min-width: 120px;">
                            <div id="stat-unpaid-count" style="font-size: 20px; font-weight: 800; color: #f87171;">--</div>
                            <div style="font-size: 10px; font-weight: 600; color: #cbd5e1; text-transform: uppercase;">Unpaid Departed</div>
                        </div>
                        <div style="background: rgba(255,255,255,0.08); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.12); padding: 12px 18px; border-radius: 12px; text-align: center; min-width: 140px;">
                            <div id="stat-total-amount" style="font-size: 20px; font-weight: 800; color: #4ade80;">--</div>
                            <div style="font-size: 10px; font-weight: 600; color: #cbd5e1; text-transform: uppercase;">Total Outstanding</div>
                        </div>
                    </div>
                </div>

                <!-- Table Container with Search & Batch Controls -->
                <div class="card" style="border: 1px solid #e2e8f0; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); overflow: hidden; background: #fff;">
                    <div class="card-header" style="padding: 14px 20px; background: #f8fafc; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <h4 style="margin: 0; font-size: 15px; font-weight: 700; color: #1e293b;">Departed Candidates List</h4>
                            <span id="table-badge-count" class="badge badge-secondary" style="font-size: 12px; padding: 4px 8px;">0 Candidates</span>
                        </div>
                        <div style="display: flex; gap: 10px; align-items: center;">
                            <input type="text" id="comm-search-input" class="form-control form-control-sm" placeholder="Search candidate or passport..." style="max-width: 250px;">
                            <button id="btn-header-export-excel" class="btn btn-sm btn-outline-primary font-weight-bold">
                                📥 Export Excel
                            </button>
                            <button id="btn-header-export-pdf" class="btn btn-sm btn-outline-secondary font-weight-bold">
                                📄 Export PDF
                            </button>
                        </div>
                    </div>

                    <div id="commission-table-container" style="padding: 0; overflow-x: auto;">
                        <div style="text-align: center; padding: 40px; color: #64748b;">
                            <span class="spinner-border spinner-border-sm" role="status"></span> Loading candidate records...
                        </div>
                    </div>
                </div>
            </div>
        `);

        let me = this;
        this.page.main.find('#comm-search-input').on('input', function() {
            me.searchQuery = $(this).val().toLowerCase().trim();
            me.render_table();
        });

        this.page.main.find('#btn-header-export-excel').on('click', () => me.export_report('excel'));
        this.page.main.find('#btn-header-export-pdf').on('click', () => me.export_report('pdf'));
    }

    fetch_and_render() {
        let me = this;
        let contractor = this.contractor_field.get_value();
        let batch_size = this.batch_field.get_value() || '30';
        let from_date = this.from_date_field.get_value() || '';
        let to_date = this.to_date_field.get_value() || '';

        if (!contractor) {
            me.page.main.find('#commission-table-container').html(
                '<div style="text-align: center; padding: 50px; color: #64748b; font-size: 14px;">Please select a Partner Agency from the top filter.</div>'
            );
            return;
        }

        me.page.main.find('#commission-table-container').html(
            '<div style="text-align: center; padding: 40px; color: #64748b;"><span class="spinner-border spinner-border-sm"></span> Loading candidate records...</div>'
        );

        frappe.call({
            method: 'applicant_processing.applicant_processing.utils.commission_export.get_unpaid_commission_candidates_list',
            args: {
                contractor: contractor,
                limit: batch_size,
                from_date: from_date,
                to_date: to_date
            },
            callback: function(r) {
                if (r.message) {
                    me.summary = r.message.summary || {};
                    me.candidates = r.message.candidates || [];
                    me.update_hero();
                    me.render_table();
                }
            }
        });
    }

    update_hero() {
        let s = this.summary;
        let curr = s.currency || 'SAR';

        this.page.main.find('#hero-agency-name').text(s.company_name || this.contractor_field.get_value());
        this.page.main.find('#hero-agency-desc').html(
            `<b>Corridor:</b> ${s.country || '-'} &nbsp;|&nbsp; <b>Contact:</b> ${s.contact_person || '-'} &nbsp;|&nbsp; <b>Phone:</b> ${s.phone || '-'} &nbsp;|&nbsp; <b>Scope:</b> ${s.batch_label || 'Batch'}`
        );

        this.page.main.find('#stat-rate').text(frappe.format(s.default_rate || 1000, { fieldtype: 'Currency' }) + ' ' + curr);
        this.page.main.find('#stat-unpaid-count').text((s.total_count || 0) + ' Cand.');
        this.page.main.find('#stat-total-amount').text(frappe.format(s.total_amount || 0, { fieldtype: 'Currency' }) + ' ' + curr);
        this.page.main.find('#table-badge-count').text(`${s.total_count || 0} Candidates`);
    }

    render_table() {
        let me = this;
        let container = this.page.main.find('#commission-table-container');

        let filtered = this.candidates.filter(c => {
            if (!me.searchQuery) return true;
            let q = me.searchQuery;
            return (
                (c.name || '').toLowerCase().includes(q) ||
                (c.full_name || '').toLowerCase().includes(q) ||
                (c.passport_number || '').toLowerCase().includes(q) ||
                (c.job_applied || '').toLowerCase().includes(q) ||
                (c.sponsor_name || '').toLowerCase().includes(q)
            );
        });

        if (!filtered.length) {
            container.html(`
                <div style="text-align: center; padding: 50px; color: #64748b;">
                    <div style="font-size: 32px; margin-bottom: 10px;">📋</div>
                    <h5>No Unpaid Departed Candidates Found</h5>
                    <p style="font-size: 13px; color: #94a3b8; margin: 0;">All departed candidates under this partner agency have been settled or no departed records match the filter.</p>
                </div>
            `);
            return;
        }

        let rows_html = filtered.map((c, i) => {
            return `
                <tr style="border-bottom: 1px solid #f1f5f9;">
                    <td style="text-align: center; font-weight: 700; color: #64748b; font-size: 12px;">${i + 1}</td>
                    <td style="font-weight: 700;">
                        <a href="/app/applicant/${c.name}" target="_blank" style="color: #2563eb; text-decoration: none;">
                            ${c.name} ↗
                        </a>
                    </td>
                    <td style="font-weight: 700; color: #0f172a;">${c.full_name}</td>
                    <td style="font-family: monospace; font-size: 12px; color: #334155;">${c.passport_number}</td>
                    <td><span class="badge badge-info" style="font-size: 11px;">${c.destination_country}</span></td>
                    <td style="color: #475569; font-size: 12px;">${c.job_applied}</td>
                    <td style="color: #334155; font-size: 12px; font-weight: 600;">${c.departure_date || '-'}</td>
                    <td style="color: #475569; font-size: 12px;">${c.sponsor_name || '-'}</td>
                    <td style="font-family: monospace; font-size: 11px;">${c.visa_number || '-'}</td>
                    <td style="text-align: right; font-weight: 800; color: #0f766e; font-size: 13px;">
                        ${frappe.format(c.commission_rate, { fieldtype: 'Currency' })} ${c.commission_currency}
                    </td>
                    <td style="text-align: center;">
                        <span class="badge badge-danger" style="font-size: 10px; text-transform: uppercase;">${c.commission_status}</span>
                    </td>
                </tr>
            `;
        }).join('');

        let table_html = `
            <table class="table table-hover" style="margin: 0; width: 100%;">
                <thead style="background: #f8fafc; font-size: 11px; text-transform: uppercase; color: #475569;">
                    <tr>
                        <th style="width: 4%; text-align: center;">#</th>
                        <th style="width: 12%;">Applicant ID</th>
                        <th style="width: 18%;">Full Name</th>
                        <th style="width: 11%;">Passport No</th>
                        <th style="width: 10%;">Destination</th>
                        <th style="width: 12%;">Job Position</th>
                        <th style="width: 10%;">Departure</th>
                        <th style="width: 13%;">Sponsor / Employer</th>
                        <th style="width: 10%;">Visa No</th>
                        <th style="width: 12%; text-align: right;">Commission</th>
                        <th style="width: 8%; text-align: center;">Status</th>
                    </tr>
                </thead>
                <tbody>
                    ${rows_html}
                </tbody>
                <tfoot style="background: #f0fdf4; font-weight: 800; font-size: 13px; color: #047857;">
                    <tr>
                        <td colspan="9" style="text-align: right; padding: 12px;">
                            TOTAL OUTSTANDING AMOUNT (${filtered.length} CANDIDATES):
                        </td>
                        <td style="text-align: right; padding: 12px; font-size: 14px;">
                            ${frappe.format(this.summary.total_amount || 0, { fieldtype: 'Currency' })} ${this.summary.currency || 'SAR'}
                        </td>
                        <td style="text-align: center; padding: 12px;">
                            <span class="badge badge-danger">UNPAID</span>
                        </td>
                    </tr>
                </tfoot>
            </table>
        `;

        container.html(table_html);
    }

    export_report(format = 'excel') {
        let contractor = this.contractor_field.get_value();
        let batch_size = this.batch_field.get_value() || '30';
        let from_date = this.from_date_field.get_value() || '';
        let to_date = this.to_date_field.get_value() || '';

        if (!contractor) {
            frappe.msgprint(__('Please select a Partner Agency before exporting.'));
            return;
        }

        let url = `/api/method/applicant_processing.applicant_processing.utils.commission_export.export_unpaid_commission_report?contractor=${encodeURIComponent(contractor)}&export_format=${format}&limit=${batch_size}&from_date=${from_date}&to_date=${to_date}`;
        window.open(url, '_blank');
    }

    open_mark_paid_modal() {
        let me = this;
        let contractor = this.contractor_field.get_value();
        let batch_size = this.batch_field.get_value() || '30';

        if (!contractor) {
            frappe.msgprint(__('Please select a Partner Agency first.'));
            return;
        }

        let d = new frappe.ui.Dialog({
            title: __('Settle Batch Commissions as Paid'),
            fields: [
                {
                    fieldname: 'html_desc',
                    fieldtype: 'HTML',
                    options: `<p style="font-size: 12px; color: #475569;">
                        Marking up to <b>${batch_size}</b> departed candidates for <b>${me.summary.company_name || contractor}</b> as <b>Paid</b>.
                    </p>`
                },
                {
                    fieldname: 'payment_date',
                    label: __('Settlement Date'),
                    fieldtype: 'Date',
                    default: frappe.datetime.get_today(),
                    reqd: 1
                },
                {
                    fieldname: 'reference',
                    label: __('Bank Wire / Receipt Reference'),
                    fieldtype: 'Data',
                    placeholder: 'e.g. WIRE-2026-SA-0081 or Musaned Batch #',
                    reqd: 1
                }
            ],
            primary_action_label: __('Confirm & Post to Ledger'),
            primary_action(values) {
                frappe.call({
                    method: 'applicant_processing.applicant_processing.utils.commission_export.mark_commissions_as_paid',
                    args: {
                        contractor: contractor,
                        limit: batch_size,
                        reference: values.reference,
                        payment_date: values.payment_date
                    },
                    freeze: true,
                    freeze_message: __('Settling commissions and posting financial ledger...'),
                    callback: function(r) {
                        if (r.message && r.message.status === 'success') {
                            frappe.msgprint({
                                title: __('Commissions Settled'),
                                indicator: 'green',
                                message: r.message.message
                            });
                            d.hide();
                            me.fetch_and_render();
                        } else {
                            frappe.msgprint(r.message ? r.message.message : __('No records updated.'));
                        }
                    }
                });
            }
        });

        d.show();
    }
}
