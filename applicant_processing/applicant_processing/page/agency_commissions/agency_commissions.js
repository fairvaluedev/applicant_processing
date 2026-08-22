// Copyright (c) 2026, Admin and contributors
// For license information, please see license.txt

frappe.pages["agency-commissions"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Agency Commission Desk"),
		single_column: true,
	});

	wrapper.commission_desk = new AgencyCommissionDesk(page, wrapper);
};

// ─────────────────────────────────────────────────────────────────────────────

class AgencyCommissionDesk {
	constructor(page, wrapper) {
		this.page = page;
		this.$wrapper = $(wrapper);
		this.candidates = [];
		this.summary = {};
		this._searchQuery = "";
		this._loading = false;

		this._setup();
	}

	_setup() {
		this._make_filters();
		this._render_skeleton();
		this._bind_toolbar();
	}

	// ── Toolbar & Filters ────────────────────────────────────────────────────

	_make_filters() {
		const me = this;

		this.$contractor = this.page.add_field({
			fieldname: "contractor",
			label: __("Partner Agency"),
			fieldtype: "Link",
			options: "Contractor",
			change() {
				me._on_filter_change();
			},
		});

		this.$batch = this.page.add_field({
			fieldname: "batch_size",
			label: __("Batch Limit"),
			fieldtype: "Select",
			options: "30\n40\n50\n100\nAll",
			default: "30",
			change() {
				me._on_filter_change();
			},
		});

		this.$from_date = this.page.add_field({
			fieldname: "from_date",
			label: __("Departed After"),
			fieldtype: "Date",
			change() {
				me._on_filter_change();
			},
		});

		this.$to_date = this.page.add_field({
			fieldname: "to_date",
			label: __("Departed Before"),
			fieldtype: "Date",
			change() {
				me._on_filter_change();
			},
		});

		this.page.set_primary_action(
			__("Export Excel"),
			() => this._export("excel"),
			"file-excel"
		);

		this.page.add_inner_button(__("Export PDF Statement"), () => this._export("pdf"));
		this.page.add_inner_button(__("Mark Batch as Paid"), () => this._open_settlement_dialog());
	}

	_bind_toolbar() {
		const me = this;
		this.$wrapper.on("input", "#comm-search", function () {
			me._searchQuery = $(this).val().toLowerCase().trim();
			me._render_rows();
		});
		this.$wrapper.on("click", "#btn-export-excel", () => this._export("excel"));
		this.$wrapper.on("click", "#btn-export-pdf", () => this._export("pdf"));
	}

	_on_filter_change() {
		const contractor = this.$contractor.get_value();
		if (!contractor) {
			this._render_empty_state(__("Select a partner agency to view unpaid commissions."));
			return;
		}
		this._fetch();
	}

	// ── HTML Skeleton ────────────────────────────────────────────────────────

	_render_skeleton() {
		this.page.main.html(`
			<div id="comm-desk" class="comm-desk">

				<div id="comm-hero" class="comm-hero">
					<div class="comm-hero-left">
						<div class="comm-hero-eyebrow">${__("Recruitment Commission Ledger")}</div>
						<div id="hero-title" class="comm-hero-title">${__("Select a Partner Agency")}</div>
						<div id="hero-meta" class="comm-hero-meta">
							${__("View and export unpaid commission statements for departed candidates.")}
						</div>
					</div>
					<div class="comm-kpi-row" id="comm-kpi-row">
						<div class="comm-kpi-card">
							<div id="kpi-rate" class="comm-kpi-val">—</div>
							<div class="comm-kpi-label">${__("Agreed Rate")}</div>
						</div>
						<div class="comm-kpi-card">
							<div id="kpi-count" class="comm-kpi-val" style="color: var(--red-400);">—</div>
							<div class="comm-kpi-label">${__("Unpaid Departed")}</div>
						</div>
						<div class="comm-kpi-card comm-kpi-card--accent">
							<div id="kpi-total" class="comm-kpi-val" style="color: var(--green-600);">—</div>
							<div class="comm-kpi-label">${__("Total Outstanding")}</div>
						</div>
					</div>
				</div>

				<div class="comm-table-wrapper">
					<div class="comm-table-header">
						<div class="comm-table-title-group">
							<span class="comm-table-title">${__("Departed Candidates")}</span>
							<span id="comm-badge" class="badge badge-secondary">0</span>
						</div>
						<div class="comm-table-actions">
							<input
								type="search"
								id="comm-search"
								class="form-control form-control-sm"
								placeholder="${__("Search name, passport…")}"
								style="width: 220px;"
							>
							<button id="btn-export-excel" class="btn btn-sm btn-default">
								${__("Export Excel")}
							</button>
							<button id="btn-export-pdf" class="btn btn-sm btn-default">
								${__("Export PDF")}
							</button>
						</div>
					</div>

					<div id="comm-body">
						${this._loading_html()}
					</div>
				</div>

			</div>

			<style>
				.comm-desk { padding: 4px 0 24px; }

				/* Hero */
				.comm-hero {
					background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%);
					border-radius: var(--border-radius-lg, 8px);
					padding: 20px 24px;
					display: flex;
					justify-content: space-between;
					align-items: center;
					gap: 20px;
					flex-wrap: wrap;
					margin-bottom: 18px;
					box-shadow: 0 4px 14px rgba(0,0,0,0.14);
				}
				.comm-hero-eyebrow { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .1em; color: #38bdf8; margin-bottom: 4px; }
				.comm-hero-title { font-size: 20px; font-weight: 800; color: #fff; margin-bottom: 4px; line-height: 1.2; }
				.comm-hero-meta { font-size: 12px; color: #94a3b8; max-width: 520px; line-height: 1.5; }

				/* KPI cards */
				.comm-kpi-row { display: flex; gap: 10px; flex-wrap: wrap; }
				.comm-kpi-card {
					background: rgba(255,255,255,0.07);
					border: 1px solid rgba(255,255,255,0.1);
					border-radius: var(--border-radius-lg, 8px);
					padding: 12px 16px;
					text-align: center;
					min-width: 110px;
				}
				.comm-kpi-card--accent { background: rgba(4,120,87,0.18); border-color: rgba(4,120,87,0.35); }
				.comm-kpi-val { font-size: 18px; font-weight: 800; color: #e2e8f0; }
				.comm-kpi-label { font-size: 9px; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; color: #94a3b8; margin-top: 3px; }

				/* Table wrapper */
				.comm-table-wrapper {
					border: 1px solid var(--border-color, #e2e8f0);
					border-radius: var(--border-radius-lg, 8px);
					overflow: hidden;
					background: var(--fg-color, #fff);
					box-shadow: 0 1px 4px rgba(0,0,0,0.04);
				}
				.comm-table-header {
					display: flex;
					justify-content: space-between;
					align-items: center;
					flex-wrap: wrap;
					gap: 10px;
					padding: 12px 16px;
					background: var(--subtle-fg, #f8fafc);
					border-bottom: 1px solid var(--border-color, #e2e8f0);
				}
				.comm-table-title-group { display: flex; align-items: center; gap: 8px; }
				.comm-table-title { font-size: 14px; font-weight: 700; color: var(--text-color, #1e293b); }
				.comm-table-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

				/* Data table */
				#comm-body table { width: 100%; border-collapse: collapse; font-size: 12px; }
				#comm-body thead th {
					background: var(--subtle-fg, #f1f5f9);
					color: var(--text-muted, #475569);
					font-size: 10px;
					font-weight: 700;
					text-transform: uppercase;
					letter-spacing: .04em;
					padding: 9px 10px;
					border-bottom: 2px solid var(--border-color, #e2e8f0);
					white-space: nowrap;
				}
				#comm-body tbody td { padding: 9px 10px; border-bottom: 1px solid var(--border-color, #f1f5f9); vertical-align: middle; }
				#comm-body tbody tr:last-child td { border-bottom: none; }
				#comm-body tbody tr:hover td { background: var(--fg-hover-color, #f8fafc); }
				#comm-body tfoot td {
					padding: 11px 10px;
					font-weight: 700;
					color: #047857;
					background: #ecfdf5;
					border-top: 2px solid #86efac;
				}

				/* Misc helpers */
				.tc { text-align: center; }
				.tr { text-align: right; }
				.mono { font-family: "Courier New", monospace; font-size: 11px; letter-spacing: .03em; }
				.badge-unpaid { background: #fee2e2; color: #b91c1c; font-size: 9px; padding: 2px 6px; border-radius: 4px; font-weight: 700; text-transform: uppercase; }
				.app-link { color: var(--primary, #2563eb); font-weight: 600; text-decoration: none; white-space: nowrap; }
				.app-link:hover { text-decoration: underline; }
				.comm-empty { text-align: center; padding: 56px 20px; color: var(--text-muted, #64748b); }
				.comm-empty-icon { font-size: 36px; margin-bottom: 10px; }
				.comm-empty h5 { margin: 0 0 6px; font-weight: 700; }
				.comm-empty p { font-size: 13px; margin: 0; color: #94a3b8; }
			</style>
		`);
	}

	_loading_html() {
		return `<div style="text-align:center;padding:48px;color:var(--text-muted);">
			<div class="spinner-border spinner-border-sm" role="status"></div>
			<div style="margin-top:10px;font-size:13px;">${__("Loading records…")}</div>
		</div>`;
	}

	// ── Data Fetch ───────────────────────────────────────────────────────────

	_fetch() {
		if (this._loading) return;
		const contractor = this.$contractor.get_value();
		if (!contractor) return;

		this._loading = true;
		this.$wrapper.find("#comm-body").html(this._loading_html());

		frappe.call({
			method: "applicant_processing.applicant_processing.utils.commission_export.get_unpaid_commission_candidates_list",
			args: {
				contractor,
				limit: this.$batch.get_value() || "30",
				from_date: this.$from_date.get_value() || "",
				to_date: this.$to_date.get_value() || "",
			},
			callback: (r) => {
				this._loading = false;
				if (r.message) {
					this.summary = r.message.summary || {};
					this.candidates = r.message.candidates || [];
					this._update_hero();
					this._render_rows();
				} else {
					this._render_error(__("Unexpected response from server."));
				}
			},
			error: () => {
				this._loading = false;
				this._render_error(__("Failed to load commission data. Please try again."));
			},
		});
	}

	// ── Render: Hero ─────────────────────────────────────────────────────────

	_update_hero() {
		const s = this.summary;
		const curr = s.currency || "SAR";

		this.$wrapper.find("#hero-title").text(s.company_name || "—");
		this.$wrapper.find("#hero-meta").html(
			[
				s.country && `<strong>${__("Country:")}</strong> ${frappe.utils.escape_html(s.country)}`,
				s.contact_person && s.contact_person !== "—" && `<strong>${__("Contact:")}</strong> ${frappe.utils.escape_html(s.contact_person)}`,
				s.batch_label && `<strong>${__("Scope:")}</strong> ${frappe.utils.escape_html(s.batch_label)}`,
			]
				.filter(Boolean)
				.join(" &nbsp;|&nbsp; ")
		);

		this.$wrapper.find("#kpi-rate").text(
			`${frappe.format(s.default_rate || 0, { fieldtype: "Currency" })} ${curr}`
		);
		this.$wrapper.find("#kpi-count").text(s.total_count || 0);
		this.$wrapper.find("#kpi-total").text(
			`${frappe.format(s.total_amount || 0, { fieldtype: "Currency" })} ${curr}`
		);
		this.$wrapper.find("#comm-badge")
			.text(s.total_count || 0)
			.removeClass("badge-secondary badge-warning")
			.addClass(s.total_count > 0 ? "badge-warning" : "badge-secondary");
	}

	// ── Render: Table ────────────────────────────────────────────────────────

	_render_rows() {
		const q = this._searchQuery;
		const filtered = q
			? this.candidates.filter((c) =>
				[c.name, c.full_name, c.passport_number, c.job_applied, c.sponsor_name]
					.some((v) => (v || "").toLowerCase().includes(q))
			)
			: this.candidates;

		if (!filtered.length) {
			this._render_empty_state(
				q
					? __("No candidates match your search.")
					: __("No unpaid departed candidates found for this agency and filter combination.")
			);
			return;
		}

		const filteredTotal = filtered.reduce((s, c) => s + (c.commission_rate || 0), 0);
		const curr = this.summary.currency || "SAR";

		const rows = filtered
			.map(
				(c, i) => `
			<tr>
				<td class="tc" style="color:var(--text-muted);font-size:11px;">${i + 1}</td>
				<td>
					<a href="/app/applicant/${frappe.utils.escape_html(c.name)}"
					   target="_blank"
					   class="app-link">
						${frappe.utils.escape_html(c.name)}
					</a>
				</td>
				<td style="font-weight:600;">${frappe.utils.escape_html(c.full_name)}</td>
				<td class="mono">${frappe.utils.escape_html(c.passport_number)}</td>
				<td>
					<span class="indicator-pill no-indicator-dot blue">
						${frappe.utils.escape_html(c.destination_country)}
					</span>
				</td>
				<td style="color:var(--text-muted);">${frappe.utils.escape_html(c.job_applied)}</td>
				<td class="tc" style="font-weight:600;">${frappe.utils.escape_html(c.departure_date || "—")}</td>
				<td style="color:var(--text-muted);">${frappe.utils.escape_html(c.sponsor_name)}</td>
				<td class="mono">${frappe.utils.escape_html(c.visa_number)}</td>
				<td class="tr" style="font-weight:700;color:#0f766e;">
					${frappe.format(c.commission_rate, { fieldtype: "Currency" })} ${frappe.utils.escape_html(c.commission_currency)}
				</td>
				<td class="tc">
					<span class="badge-unpaid">${__("Unpaid")}</span>
				</td>
			</tr>`
			)
			.join("");

		this.$wrapper.find("#comm-body").html(`
			<div style="overflow-x:auto;">
				<table>
					<thead>
						<tr>
							<th style="width:4%;" class="tc">#</th>
							<th style="width:11%;">${__("App. ID")}</th>
							<th style="width:18%;">${__("Full Name")}</th>
							<th style="width:12%;">${__("Passport No")}</th>
							<th style="width:10%;">${__("Destination")}</th>
							<th style="width:11%;">${__("Position")}</th>
							<th style="width:9%;" class="tc">${__("Departed")}</th>
							<th style="width:12%;">${__("Sponsor")}</th>
							<th style="width:9%;">${__("Visa No")}</th>
							<th style="width:10%;" class="tr">${__("Commission")}</th>
							<th style="width:7%;" class="tc">${__("Status")}</th>
						</tr>
					</thead>
					<tbody>${rows}</tbody>
					<tfoot>
						<tr>
							<td colspan="9" class="tr">
								${__("Total Outstanding")} (${filtered.length} ${__("candidates")}):
							</td>
							<td class="tr">
								${frappe.format(filteredTotal, { fieldtype: "Currency" })} ${frappe.utils.escape_html(curr)}
							</td>
							<td class="tc">
								<span class="badge-unpaid">${__("Unpaid")}</span>
							</td>
						</tr>
					</tfoot>
				</table>
			</div>
		`);
	}

	_render_empty_state(msg) {
		this.$wrapper.find("#comm-body").html(`
			<div class="comm-empty">
				<div class="comm-empty-icon">📋</div>
				<h5>${__("No Records Found")}</h5>
				<p>${frappe.utils.escape_html(msg)}</p>
			</div>
		`);
	}

	_render_error(msg) {
		this.$wrapper.find("#comm-body").html(`
			<div class="comm-empty">
				<div class="comm-empty-icon">⚠</div>
				<h5>${__("Could Not Load Data")}</h5>
				<p>${frappe.utils.escape_html(msg)}</p>
				<button class="btn btn-sm btn-default" style="margin-top:12px;" onclick="window.location.reload();">
					${__("Retry")}
				</button>
			</div>
		`);
	}

	// ── Export ───────────────────────────────────────────────────────────────

	_export(format) {
		const contractor = this.$contractor.get_value();
		if (!contractor) {
			frappe.msgprint({ message: __("Select a partner agency before exporting."), indicator: "orange" });
			return;
		}

		const params = new URLSearchParams({
			contractor,
			export_format: format,
			limit: this.$batch.get_value() || "30",
			from_date: this.$from_date.get_value() || "",
			to_date: this.$to_date.get_value() || "",
		});

		window.open(
			`/api/method/applicant_processing.applicant_processing.utils.commission_export.export_unpaid_commission_report?${params}`,
			"_blank"
		);
	}

	// ── Settlement Dialog ────────────────────────────────────────────────────

	_open_settlement_dialog() {
		const me = this;
		const contractor = this.$contractor.get_value();
		if (!contractor) {
			frappe.msgprint({ message: __("Select a partner agency first."), indicator: "orange" });
			return;
		}

		const batchSize = this.$batch.get_value() || "30";
		const agencyName = this.summary.company_name || contractor;
		const totalCount = this.summary.total_count || 0;
		const totalAmount = this.summary.total_amount || 0;
		const currency = this.summary.currency || "SAR";

		const d = new frappe.ui.Dialog({
			title: __("Settle Agency Commission Batch"),
			fields: [
				{
					fieldname: "info_html",
					fieldtype: "HTML",
					options: `
						<div style="background:var(--subtle-fg,#f8fafc);border:1px solid var(--border-color,#e2e8f0);
						            border-radius:var(--border-radius,6px);padding:12px 14px;margin-bottom:4px;">
							<table style="width:100%;font-size:12px;">
								<tr>
									<td style="color:var(--text-muted);">${__("Agency")}</td>
									<td style="font-weight:700;">${frappe.utils.escape_html(agencyName)}</td>
									<td style="color:var(--text-muted);">${__("Batch Limit")}</td>
									<td style="font-weight:700;">${frappe.utils.escape_html(batchSize)}</td>
								</tr>
								<tr>
									<td style="color:var(--text-muted);">${__("Candidates")}</td>
									<td style="font-weight:700;">${totalCount}</td>
									<td style="color:var(--text-muted);">${__("Est. Total")}</td>
									<td style="font-weight:700;color:#047857;">
										${frappe.format(totalAmount, { fieldtype: "Currency" })} ${frappe.utils.escape_html(currency)}
									</td>
								</tr>
							</table>
						</div>
					`,
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
					placeholder: __("e.g. WIRE-SA-2026-9901 or Musaned Invoice #"),
					reqd: 1,
					description: __("This reference will be recorded in the financial ledger for each candidate."),
				},
			],
			primary_action_label: __("Confirm & Post to Ledger"),
			primary_action(values) {
				frappe.confirm(
					__(
						"Mark up to {0} candidates for <strong>{1}</strong> as Paid with reference <strong>{2}</strong>?",
						[batchSize, frappe.utils.escape_html(agencyName), frappe.utils.escape_html(values.reference)]
					),
					() => {
						frappe.call({
							method: "applicant_processing.applicant_processing.utils.commission_export.mark_commissions_as_paid",
							args: {
								contractor,
								limit: batchSize,
								reference: values.reference,
								payment_date: values.payment_date,
							},
							freeze: true,
							freeze_message: __("Settling commissions and posting to financial ledger…"),
							callback(r) {
								if (r.message) {
									const indicator = r.message.status === "success" ? "green" : "orange";
									frappe.msgprint({
										title: __("Settlement Complete"),
										indicator,
										message: r.message.message,
									});
									d.hide();
									me._fetch();
								}
							},
							error() {
								frappe.msgprint({
									title: __("Settlement Failed"),
									indicator: "red",
									message: __("An error occurred while settling commissions. Check the Error Log for details."),
								});
							},
						});
					}
				);
			},
		});

		d.show();
	}
}
