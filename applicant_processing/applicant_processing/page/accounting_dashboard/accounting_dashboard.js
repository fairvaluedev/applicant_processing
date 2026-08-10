frappe.pages["accounting-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Accounting Dashboard",
		single_column: true,
	});

	// Mount the dashboard component into the page body
	$(wrapper).find(".layout-main-section").html(
		`<div id="accounting-dashboard-root" style="padding: 20px 0;"></div>`
	);

	// Fetch data and render
	frappe.call({
		method: "applicant_processing.applicant_processing.api.get_accounting_summary",
		callback: function (r) {
			if (r.exc || !r.message) {
				frappe.msgprint("Failed to load accounting data.");
				return;
			}
			render_dashboard(r.message);
		},
	});

	page.add_action_item(__("Refresh"), function () {
		frappe.set_route("accounting-dashboard");
	});
};

function fmt_currency(val) {
	if (val == null) return "0.00";
	return frappe.format(val, { fieldtype: "Currency" });
}

function render_dashboard(data) {
	const root = document.getElementById("accounting-dashboard-root");
	if (!root) return;

	const net_class =
		data.net_balance >= 0 ? "kpi-positive" : "kpi-negative";

	// ── KPI Cards ──────────────────────────────────────────────────
	const kpi_html = `
	<div class="acc-kpi-row">
		<div class="acc-kpi-card income">
			<div class="acc-kpi-label">Total Income</div>
			<div class="acc-kpi-value">${fmt_currency(data.total_income)}</div>
			<div class="acc-kpi-sub">${data.transaction_count} transaction(s)</div>
		</div>
		<div class="acc-kpi-card expense">
			<div class="acc-kpi-label">Total Expense</div>
			<div class="acc-kpi-value">${fmt_currency(data.total_expense)}</div>
		</div>
		<div class="acc-kpi-card net ${net_class}">
			<div class="acc-kpi-label">Net Balance</div>
			<div class="acc-kpi-value">${fmt_currency(data.net_balance)}</div>
		</div>
	</div>`;

	// ── Breakdown by Stage / Part ────────────────────────────────────
	const stage_rows = (data.by_stage || [])
		.map(
			(r) =>
				`<tr>
				<td><strong>${r.stage}</strong></td>
				<td class="text-right income-text">${fmt_currency(r.income)}</td>
				<td class="text-right expense-text">${fmt_currency(r.expense)}</td>
				<td class="text-right ${r.net >= 0 ? "income-text" : "expense-text"}">${fmt_currency(r.net)}</td>
				<td class="text-right text-muted">${r.count}</td>
			</tr>`
		)
		.join("");

	const stage_html = stage_rows
		? `
	<div class="acc-section">
		<h5 class="acc-section-title">Breakdown by Stage / Component (CV, LMS, Wakala, Injaz, Stamp, Ticket, Departure)</h5>
		<table class="acc-table">
			<thead><tr>
				<th>Stage / Component</th>
				<th class="text-right">Income</th>
				<th class="text-right">Expense</th>
				<th class="text-right">Net</th>
				<th class="text-right">Transactions</th>
			</tr></thead>
			<tbody>${stage_rows}</tbody>
		</table>
	</div>`
		: "";

	// ── By Fee Type Table ──────────────────────────────────────────
	const fee_rows = Object.entries(data.by_fee_type || {})
		.sort((a, b) => b[1] - a[1])
		.map(
			([label, amount]) =>
				`<tr><td>${label}</td><td class="text-right">${fmt_currency(amount)}</td></tr>`
		)
		.join("");

	const fee_type_html = fee_rows
		? `
	<div class="acc-section">
		<h5 class="acc-section-title">Breakdown by Fee Type</h5>
		<table class="acc-table">
			<thead><tr><th>Fee Type</th><th class="text-right">Amount</th></tr></thead>
			<tbody>${fee_rows}</tbody>
		</table>
	</div>`
		: "";

	// ── Per-Applicant Table ────────────────────────────────────────
	const applicant_rows = (data.per_applicant || [])
		.map(
			(row) =>
				`<tr>
				<td><a href="/app/applicant/${row.applicant}">${row.applicant}</a></td>
				<td class="text-right income-text">${fmt_currency(row.income)}</td>
				<td class="text-right expense-text">${fmt_currency(row.expense)}</td>
				<td class="text-right ${row.net >= 0 ? "income-text" : "expense-text"}">${fmt_currency(row.net)}</td>
			</tr>`
		)
		.join("");

	const per_applicant_html = applicant_rows
		? `
	<div class="acc-section">
		<h5 class="acc-section-title">Top Applicants by Financial Activity</h5>
		<table class="acc-table">
			<thead><tr>
				<th>Applicant</th>
				<th class="text-right">Income</th>
				<th class="text-right">Expense</th>
				<th class="text-right">Net</th>
			</tr></thead>
			<tbody>${applicant_rows}</tbody>
		</table>
	</div>`
		: "";

	// ── Recent Transactions ────────────────────────────────────────
	const recent_rows = (data.recent_transactions || [])
		.map(
			(txn) =>
				`<tr>
				<td>${txn.date || ""}</td>
				<td><a href="/app/applicant/${txn.applicant}">${txn.applicant}</a></td>
				<td><span class="acc-stage-badge">${txn.stage || "Applicant"}</span></td>
				<td>
					<span class="acc-badge ${txn.transaction_type === "Income" ? "badge-income" : "badge-expense"}">
						${txn.transaction_type}
					</span>
				</td>
				<td class="text-right">${fmt_currency(txn.amount)}</td>
				<td>${txn.description || ""}</td>
				<td class="text-muted small">${txn.source_doctype || "Manual"}</td>
			</tr>`
		)
		.join("");

	const recent_html = recent_rows
		? `
	<div class="acc-section">
		<h5 class="acc-section-title">Recent Transactions Across All Stages</h5>
		<table class="acc-table">
			<thead><tr>
				<th>Date</th>
				<th>Applicant</th>
				<th>Stage</th>
				<th>Type</th>
				<th class="text-right">Amount</th>
				<th>Description</th>
				<th>Source</th>
			</tr></thead>
			<tbody>${recent_rows}</tbody>
		</table>
	</div>`
		: `<div class="acc-section acc-empty">No transactions recorded yet.</div>`;

	// ── Inject Styles ──────────────────────────────────────────────
	if (!document.getElementById("acc-dashboard-styles")) {
		const style = document.createElement("style");
		style.id = "acc-dashboard-styles";
		style.textContent = `
			.acc-kpi-row {
				display: flex;
				gap: 20px;
				margin-bottom: 28px;
				flex-wrap: wrap;
			}
			.acc-kpi-card {
				flex: 1;
				min-width: 180px;
				border-radius: 10px;
				padding: 22px 28px;
				color: #fff;
				box-shadow: 0 4px 18px rgba(0,0,0,0.10);
				transition: transform 0.15s;
			}
			.acc-kpi-card:hover { transform: translateY(-2px); }
			.acc-kpi-card.income  { background: linear-gradient(135deg, #1a9e6c, #22c55e); }
			.acc-kpi-card.expense { background: linear-gradient(135deg, #c0392b, #e74c3c); }
			.acc-kpi-card.net.kpi-positive { background: linear-gradient(135deg, #2563eb, #60a5fa); }
			.acc-kpi-card.net.kpi-negative { background: linear-gradient(135deg, #7c3aed, #a78bfa); }
			.acc-kpi-label {
				font-size: 12px;
				font-weight: 600;
				letter-spacing: 0.08em;
				text-transform: uppercase;
				opacity: 0.85;
				margin-bottom: 6px;
			}
			.acc-kpi-value {
				font-size: 30px;
				font-weight: 700;
				line-height: 1.1;
			}
			.acc-kpi-sub {
				font-size: 12px;
				margin-top: 6px;
				opacity: 0.75;
			}
			.acc-section {
				background: var(--card-bg, #fff);
				border: 1px solid var(--border-color, #e9ecef);
				border-radius: 10px;
				padding: 20px 24px;
				margin-bottom: 22px;
				box-shadow: 0 2px 8px rgba(0,0,0,0.04);
			}
			.acc-section-title {
				font-size: 14px;
				font-weight: 600;
				color: var(--text-color, #333);
				margin-bottom: 14px;
				padding-bottom: 10px;
				border-bottom: 1px solid var(--border-color, #e9ecef);
			}
			.acc-table {
				width: 100%;
				border-collapse: collapse;
				font-size: 13px;
			}
			.acc-table th {
				text-align: left;
				color: var(--text-muted, #6c757d);
				font-weight: 600;
				font-size: 12px;
				padding: 6px 10px;
				border-bottom: 1px solid var(--border-color, #e9ecef);
			}
			.acc-table td {
				padding: 8px 10px;
				border-bottom: 1px solid var(--border-color, #f1f3f5);
				vertical-align: middle;
			}
			.acc-table tr:last-child td { border-bottom: none; }
			.acc-table tr:hover td { background: var(--control-bg, #f8f9fa); }
			.text-right { text-align: right !important; }
			.income-text { color: #16a34a; font-weight: 600; }
			.expense-text { color: #dc2626; font-weight: 600; }
			.acc-badge {
				display: inline-block;
				padding: 2px 10px;
				border-radius: 12px;
				font-size: 11px;
				font-weight: 600;
			}
			.acc-stage-badge {
				display: inline-block;
				padding: 2px 8px;
				border-radius: 6px;
				font-size: 11px;
				font-weight: 500;
				background: #f1f5f9;
				color: #334155;
				border: 1px solid #cbd5e1;
			}
			.badge-income  { background: #dcfce7; color: #15803d; }
			.badge-expense { background: #fee2e2; color: #b91c1c; }
			.acc-empty {
				text-align: center;
				color: var(--text-muted, #6c757d);
				padding: 40px;
				font-size: 14px;
			}
		`;
		document.head.appendChild(style);
	}

	root.innerHTML = kpi_html + stage_html + fee_type_html + per_applicant_html + recent_html;
}
