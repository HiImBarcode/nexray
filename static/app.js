/* ========== NEXRAY App ========== */
const API = '/api';
let currentEntity = 'ent-01';
let currentPage = 'dashboard';
let dashboardData = null;

// ===== THEME TOGGLE =====
(function() {
  const toggle = document.querySelector('[data-theme-toggle]');
  const root = document.documentElement;
  let theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  root.setAttribute('data-theme', theme);
  if (toggle) {
    updateToggleIcon(toggle, theme);
    toggle.addEventListener('click', () => {
      theme = theme === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', theme);
      updateToggleIcon(toggle, theme);
    });
  }
  function updateToggleIcon(el, t) {
    el.innerHTML = t === 'dark'
      ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>'
      : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
    el.setAttribute('aria-label', `Switch to ${t === 'dark' ? 'light' : 'dark'} mode`);
  }
})();

// ===== SIDEBAR =====
function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
  document.getElementById('mobileOverlay').classList.toggle('active');
}

// ===== API =====
async function api(endpoint, params = {}) {
  params.entity_id = currentEntity;
  const qs = new URLSearchParams(params).toString();
  try {
    const res = await fetch(`${API}${endpoint}?${qs}`);
    return await res.json();
  } catch (e) {
    console.error('API Error:', e);
    return null;
  }
}

async function apiPost(endpoint, body) {
  try {
    const res = await fetch(`${API}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    return await res.json();
  } catch (e) {
    console.error('API Error:', e);
    return null;
  }
}

// ===== NAVIGATION =====
const pageTitles = {
  dashboard: ['Dashboard', 'NEXRAY › Operations'],
  outbound: ['Outbound Queue', 'NEXRAY › OMS › Outbound'],
  cuts: ['Cut Transactions', 'NEXRAY › Execution › Cuts'],
  tags: ['Tags & Labels', 'NEXRAY › Execution › Tags'],
  inventory: ['Lots & Rolls', 'NEXRAY › WMS › Inventory'],
  warehouses: ['Warehouses', 'NEXRAY › WMS › Locations'],
  movements: ['Movement Ledger', 'NEXRAY › WMS › Ledger'],
  adjustments: ['Approvals', 'NEXRAY › Controls › Approvals'],
  findings: ['Reconciliation Findings', 'NEXRAY › Controls › Findings'],
  integrations: ['Integrations', 'NEXRAY › System › QBD Integration'],
  users: ['Users & RBAC', 'NEXRAY › System › Access Control'],
  audit: ['Audit Log', 'NEXRAY › System › Audit'],
};

function navigate(page) {
  currentPage = page;
  document.querySelectorAll('.page-section').forEach(s => s.classList.remove('active'));
  document.getElementById(`page-${page}`).classList.add('active');
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.querySelector(`.nav-item[data-page="${page}"]`)?.classList.add('active');
  const [title, breadcrumb] = pageTitles[page] || [page, ''];
  document.getElementById('page-title').textContent = title;
  document.getElementById('page-breadcrumb').textContent = breadcrumb;
  loadPage(page);
  // Close mobile sidebar
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('mobileOverlay').classList.remove('active');
}

function switchEntity(eid) { currentEntity = eid; loadPage(currentPage); }

// ===== HELPERS =====
function badge(status) {
  if (!status) return '';
  const cls = `badge badge-${status.replace(/\s/g,'_')}`;
  return `<span class="${cls}">${status.replace(/_/g,' ')}</span>`;
}

function trackingId(id) { return id ? `<span class="tracking-id">${id}</span>` : '—'; }
function mono(val) { return val ? `<span class="mono">${val}</span>` : '—'; }
function fmtQty(val) { return val != null ? Number(val).toFixed(2) : '—'; }
function fmtDate(d) { if (!d) return '—'; const dt = new Date(d + 'Z'); return dt.toLocaleDateString('en-PH', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }); }
function statusDot(active) { return `<span class="status-dot ${active ? 'active' : 'inactive'}"></span>`; }

function qtyDelta(val) {
  if (val == null) return '—';
  const n = Number(val);
  const cls = n > 0 ? 'qty-positive' : n < 0 ? 'qty-negative' : '';
  return `<span class="${cls}">${n > 0 ? '+' : ''}${n.toFixed(2)}</span>`;
}

// ===== PAGE LOADERS =====
async function loadPage(page) {
  const loaders = {
    dashboard: loadDashboard,
    outbound: loadOutbound,
    cuts: loadCuts,
    tags: loadTags,
    inventory: loadInventory,
    warehouses: loadWarehouses,
    movements: loadMovements,
    adjustments: loadAdjustments,
    findings: loadFindings,
    integrations: loadIntegrations,
    users: loadUsers,
    audit: loadAudit,
  };
  if (loaders[page]) await loaders[page]();
}

// ===== DASHBOARD =====
async function loadDashboard() {
  const el = document.getElementById('page-dashboard');
  el.innerHTML = '<div class="kpi-grid">' + Array(8).fill('<div class="loading-skeleton skeleton-kpi"></div>').join('') + '</div>';

  const data = await api('/dashboard');
  if (!data) { el.innerHTML = '<div class="empty-state"><p>Unable to load dashboard</p></div>'; return; }
  dashboardData = data;
  const k = data.kpis;

  // Update nav badges
  const pb = document.getElementById('nav-pending-badge');
  if (pb) pb.textContent = k.pending_lines > 0 ? k.pending_lines : '';
  if (pb && k.pending_lines <= 0) pb.style.display = 'none'; else if (pb) pb.style.display = 'flex';

  const ab = document.getElementById('nav-approval-badge');
  if (ab) ab.textContent = k.pending_adjustments > 0 ? k.pending_adjustments : '';
  if (ab && k.pending_adjustments <= 0) ab.style.display = 'none'; else if (ab) ab.style.display = 'flex';

  const fb = document.getElementById('nav-findings-badge');
  if (fb) fb.textContent = k.open_findings > 0 ? k.open_findings : '';
  if (fb && k.open_findings <= 0) fb.style.display = 'none'; else if (fb) fb.style.display = 'flex';

  el.innerHTML = `
    <div class="kpi-grid">
      <div class="kpi-card accent"><div class="kpi-label">Active Lots</div><div class="kpi-value">${k.total_active_lots}</div></div>
      <div class="kpi-card"><div class="kpi-label">On Hand</div><div class="kpi-value">${fmtQty(k.total_on_hand)}m</div></div>
      <div class="kpi-card"><div class="kpi-label">Reserved</div><div class="kpi-value">${fmtQty(k.total_reserved)}m</div></div>
      <div class="kpi-card success"><div class="kpi-label">Available</div><div class="kpi-value">${fmtQty(k.total_available)}m</div></div>
      <div class="kpi-card ${k.low_stock_lots > 0 ? 'warning' : ''}"><div class="kpi-label">Low Stock Lots</div><div class="kpi-value">${k.low_stock_lots}</div></div>
      <div class="kpi-card"><div class="kpi-label">Pending Lines</div><div class="kpi-value">${k.pending_lines}</div></div>
      <div class="kpi-card ${k.needs_approval > 0 ? 'error' : ''}"><div class="kpi-label">Needs Approval</div><div class="kpi-value">${k.needs_approval}</div></div>
      <div class="kpi-card success"><div class="kpi-label">Closed Lines</div><div class="kpi-value">${k.closed_lines}</div></div>
    </div>

    <div class="detail-grid">
      <div class="info-card">
        <h4>Operational Status</h4>
        <div class="info-row"><span class="label">In Progress</span><span class="value">${k.in_progress_lines}</span></div>
        <div class="info-row"><span class="label">Pending Adjustments</span><span class="value">${k.pending_adjustments}</span></div>
        <div class="info-row"><span class="label">Open Findings</span><span class="value">${k.open_findings}</span></div>
        <div class="info-row"><span class="label">Pending Sync</span><span class="value">${k.pending_integrations}</span></div>
        <div class="info-row"><span class="label">Failed Prints</span><span class="value">${k.failed_prints}</span></div>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div><div class="card-title">Recent Inventory Movements</div><div class="card-subtitle">Last 10 ledger events</div></div>
      </div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>Type</th><th>Item</th><th>Tracking ID</th><th>Delta</th><th>Before</th><th>After</th><th>By</th><th>Time</th></tr></thead>
          <tbody>
            ${data.recent_movements.map(m => `<tr>
              <td><span class="movement-type ${m.movement_type}">${m.movement_type}</span></td>
              <td>${m.item_name || '—'}</td>
              <td>${trackingId(m.lot_tracking || m.tracking_id)}</td>
              <td>${qtyDelta(m.qty_delta)}</td>
              <td>${fmtQty(m.qty_before)}</td>
              <td>${fmtQty(m.qty_after)}</td>
              <td>${mono(m.action_by)}</td>
              <td>${fmtDate(m.action_at)}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div><div class="card-title">Active Findings</div><div class="card-subtitle">Reconciliation exceptions requiring attention</div></div>
      </div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>Type</th><th>Severity</th><th>Description</th><th>Status</th><th>Created</th></tr></thead>
          <tbody>
            ${data.recent_findings.length > 0 ? data.recent_findings.map(f => `<tr>
              <td>${badge(f.finding_type)}</td>
              <td>${badge(f.severity)}</td>
              <td style="max-width:400px">${f.description || '—'}</td>
              <td>${badge(f.resolution_status)}</td>
              <td>${fmtDate(f.created_at)}</td>
            </tr>`).join('') : '<tr><td colspan="5" class="empty-state"><p>No active findings</p></td></tr>'}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// ===== OUTBOUND QUEUE =====
async function loadOutbound() {
  const el = document.getElementById('page-outbound');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(5);
  const data = await api('/outbound');
  if (!data) return;
  const lines = data.lines;
  const statuses = ['all','pending','allocated','in_progress','cut_complete','tagged','closed','needs_approval','cancelled'];

  el.innerHTML = `
    <div class="tab-bar">
      ${statuses.map(s => `<button class="tab-btn ${s === 'all' ? 'active' : ''}" onclick="filterOutbound('${s}', this)">${s === 'all' ? 'All' : s.replace(/_/g,' ')}</button>`).join('')}
    </div>
    <div class="card">
      <div class="card-header">
        <div><div class="card-title">Outbound Request Lines</div><div class="card-subtitle">${lines.length} total lines</div></div>
      </div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>Line</th><th>Ref</th><th>Item</th><th>SKU</th><th>Requested</th><th>Allocated</th><th>Fulfilled</th><th>Variance</th><th>Status</th><th>Claimed By</th><th>Actions</th></tr></thead>
          <tbody id="outbound-tbody">
            ${lines.map(l => outboundRow(l)).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function outboundRow(l) {
  const varClass = l.qty_variance < 0 ? 'qty-negative' : l.qty_variance > 0 ? 'qty-positive' : '';
  return `<tr data-status="${l.status}">
    <td>${mono('#' + l.line_no)}</td>
    <td>${l.reference_no || '—'}</td>
    <td>${l.item_name || '—'}</td>
    <td>${mono(l.sku)}</td>
    <td>${fmtQty(l.qty_requested)}</td>
    <td>${fmtQty(l.qty_allocated)}</td>
    <td>${fmtQty(l.qty_fulfilled)}</td>
    <td><span class="${varClass}">${l.qty_variance !== 0 ? (l.qty_variance > 0 ? '+' : '') + Number(l.qty_variance).toFixed(2) : '0.00'}</span></td>
    <td>${badge(l.status)}</td>
    <td>${mono(l.claimed_by || '—')}</td>
    <td>
      ${l.status === 'pending' ? `<button class="btn btn-sm btn-primary" onclick="updateLineStatus('${l.id}','allocated')">Allocate</button>` : ''}
      ${l.status === 'allocated' ? `<button class="btn btn-sm btn-primary" onclick="updateLineStatus('${l.id}','in_progress')">Start</button>` : ''}
      ${l.status === 'tagged' ? `<button class="btn btn-sm btn-success" onclick="updateLineStatus('${l.id}','closed')">Close</button>` : ''}
    </td>
  </tr>`;
}

function filterOutbound(status, btn) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('#outbound-tbody tr').forEach(tr => {
    tr.style.display = (status === 'all' || tr.dataset.status === status) ? '' : 'none';
  });
}

async function updateLineStatus(id, status) {
  await apiPost('/update_line_status', { id, status });
  loadOutbound();
}

// ===== CUT TRANSACTIONS =====
async function loadCuts() {
  const el = document.getElementById('page-cuts');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(5);
  const data = await api('/cuts');
  if (!data) return;

  el.innerHTML = `
    <div class="card">
      <div class="card-header">
        <div><div class="card-title">Cut Transactions</div><div class="card-subtitle">Roll-level issuance records</div></div>
      </div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>ID</th><th>Item</th><th>Tracking ID</th><th>Lot</th><th>Requested</th><th>Actual</th><th>Variance</th><th>Status</th><th>Reason</th><th>Cut By</th><th>Time</th></tr></thead>
          <tbody>
            ${data.cuts.map(c => `<tr>
              <td>${mono(c.id.substring(0,8))}</td>
              <td>${c.item_name || '—'}</td>
              <td>${trackingId(c.tracking_id)}</td>
              <td>${mono(c.lot_no)}</td>
              <td>${fmtQty(c.qty_requested)}</td>
              <td>${fmtQty(c.qty_actual)}</td>
              <td>${qtyDelta(c.qty_variance)}</td>
              <td>${badge(c.status)}</td>
              <td style="max-width:200px;font-size:11px">${c.variance_reason || '—'}</td>
              <td>${mono(c.cut_by)}</td>
              <td>${fmtDate(c.cut_at)}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// ===== TAGS & LABELS =====
async function loadTags() {
  const el = document.getElementById('page-tags');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(5);
  const data = await api('/tags');
  if (!data) return;

  el.innerHTML = `
    <div class="card">
      <div class="card-header">
        <div><div class="card-title">Tag Labels</div><div class="card-subtitle">Print and scan tracking for execution evidence</div></div>
      </div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>Tag Code</th><th>Item</th><th>Tracking ID</th><th>Cut Qty</th><th>Status</th><th>Printed</th><th>Scanned</th><th>Created</th></tr></thead>
          <tbody>
            ${data.tags.map(t => `<tr>
              <td>${trackingId(t.tag_code)}</td>
              <td>${t.item_name || '—'}</td>
              <td>${trackingId(t.lot_tracking)}</td>
              <td>${fmtQty(t.cut_qty)}</td>
              <td>${badge(t.tag_status)}</td>
              <td>${t.printed_at ? fmtDate(t.printed_at) : '—'}</td>
              <td>${t.scanned_at ? fmtDate(t.scanned_at) : '—'}</td>
              <td>${fmtDate(t.created_at)}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// ===== INVENTORY =====
async function loadInventory() {
  const el = document.getElementById('page-inventory');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(5);
  const data = await api('/inventory');
  if (!data) return;

  el.innerHTML = `
    <div class="kpi-grid">
      <div class="kpi-card accent"><div class="kpi-label">Active Lots</div><div class="kpi-value">${data.lots.length}</div></div>
      <div class="kpi-card"><div class="kpi-label">Total On Hand</div><div class="kpi-value">${fmtQty(data.lots.reduce((s,l) => s + (l.qty_on_hand||0), 0))}m</div></div>
      <div class="kpi-card"><div class="kpi-label">Total Reserved</div><div class="kpi-value">${fmtQty(data.lots.reduce((s,l) => s + (l.qty_reserved||0), 0))}m</div></div>
      <div class="kpi-card success"><div class="kpi-label">Total Available</div><div class="kpi-value">${fmtQty(data.lots.reduce((s,l) => s + (l.qty_available||0), 0))}m</div></div>
    </div>
    <div class="card">
      <div class="card-header">
        <div><div class="card-title">Inventory Lots</div><div class="card-subtitle">Roll and lot-level inventory tracking</div></div>
      </div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>Tracking ID</th><th>Item</th><th>SKU</th><th>Type</th><th>Lot/Shade</th><th>Original</th><th>On Hand</th><th>Reserved</th><th>Available</th><th>Warehouse</th><th>Location</th><th>Status</th><th>Confidence</th></tr></thead>
          <tbody>
            ${data.lots.map(l => {
              const lowStock = l.qty_on_hand < 10 && l.status === 'active';
              return `<tr ${lowStock ? 'style="background:var(--color-warning-subtle)"' : ''}>
                <td>${trackingId(l.tracking_id)}</td>
                <td>${l.item_name || '—'}</td>
                <td>${mono(l.sku)}</td>
                <td>${badge(l.item_type)}</td>
                <td>${mono((l.lot_no || '') + (l.shade_code ? ' / ' + l.shade_code : ''))}</td>
                <td>${fmtQty(l.qty_original)}</td>
                <td style="font-weight:600">${fmtQty(l.qty_on_hand)}</td>
                <td>${fmtQty(l.qty_reserved)}</td>
                <td style="font-weight:600;color:var(--color-success)">${fmtQty(l.qty_available)}</td>
                <td>${mono(l.warehouse_code)}</td>
                <td>${l.location_barcode ? `<span class="location-path">${l.location_barcode}</span>` : '—'}</td>
                <td>${badge(l.status)}</td>
                <td>${badge(l.qty_confidence)}</td>
              </tr>`;
            }).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// ===== WAREHOUSES =====
async function loadWarehouses() {
  const el = document.getElementById('page-warehouses');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(3);
  const whData = await api('/warehouses', { entity_id: 'all' });
  if (!whData) return;

  el.innerHTML = `
    <div class="kpi-grid">
      ${whData.warehouses.map(w => `
        <div class="kpi-card">
          <div class="kpi-label">${w.name} ${statusDot(w.is_active)}</div>
          <div class="kpi-value">${w.active_lots} lots</div>
          <div style="font-size:var(--text-xs);color:var(--color-text-muted);margin-top:var(--space-1)">${fmtQty(w.total_stock)}m in stock &middot; ${w.code}</div>
        </div>
      `).join('')}
    </div>
    <div id="warehouse-locations"></div>
  `;

  // Load locations for first warehouse
  if (whData.warehouses.length > 0) {
    await loadLocationsForWarehouse(whData.warehouses[0].id, whData.warehouses[0].name);
  }
}

async function loadLocationsForWarehouse(whId, whName) {
  const locData = await api('/locations', { warehouse_id: whId });
  if (!locData) return;
  const container = document.getElementById('warehouse-locations');

  container.innerHTML = `
    <div class="card">
      <div class="card-header">
        <div><div class="card-title">Locations — ${whName}</div><div class="card-subtitle">Rack/bin hierarchy</div></div>
      </div>
      <div style="padding:var(--space-4)">
        <div class="warehouse-grid">
          ${locData.locations.map(l => {
            const pct = l.capacity_qty ? Math.min((l.total_qty / l.capacity_qty) * 100, 100) : (l.lot_count > 0 ? 50 : 0);
            return `<div class="rack-card">
              <div class="rack-name">${l.location_barcode || l.rack_code}</div>
              <div class="rack-stats">${l.lot_count} lots &middot; ${fmtQty(l.total_qty)}m</div>
              <div style="font-size:10px;color:var(--color-text-faint);margin-top:2px">${badge(l.location_type)}</div>
              <div class="rack-bar"><div class="rack-bar-fill" style="width:${pct}%"></div></div>
            </div>`;
          }).join('')}
        </div>
      </div>
    </div>
  `;
}

// ===== MOVEMENT LEDGER =====
async function loadMovements() {
  const el = document.getElementById('page-movements');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(5);
  const data = await api('/movements');
  if (!data) return;

  el.innerHTML = `
    <div class="card">
      <div class="card-header">
        <div><div class="card-title">Inventory Movement Ledger</div><div class="card-subtitle">Immutable, append-only record of all inventory changes</div></div>
      </div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>ID</th><th>Type</th><th>Item</th><th>Tracking ID</th><th>Delta</th><th>Before</th><th>After</th><th>Reason</th><th>By</th><th>Channel</th><th>Time</th></tr></thead>
          <tbody>
            ${data.movements.map(m => `<tr>
              <td>${mono(m.id.substring(0,8))}</td>
              <td><span class="movement-type ${m.movement_type}">${m.movement_type}</span></td>
              <td>${m.item_name || '—'}</td>
              <td>${trackingId(m.lot_tracking || m.tracking_id)}</td>
              <td>${qtyDelta(m.qty_delta)}</td>
              <td>${fmtQty(m.qty_before)}</td>
              <td>${fmtQty(m.qty_after)}</td>
              <td>${m.reason_code || '—'}</td>
              <td>${mono(m.action_by)}</td>
              <td>${badge(m.source_channel || 'web')}</td>
              <td>${fmtDate(m.action_at)}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// ===== ADJUSTMENTS / APPROVALS =====
async function loadAdjustments() {
  const el = document.getElementById('page-adjustments');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(3);
  const data = await api('/adjustments');
  if (!data) return;

  el.innerHTML = `
    <div class="tab-bar">
      <button class="tab-btn active" onclick="filterAdj('all',this)">All</button>
      <button class="tab-btn" onclick="filterAdj('pending',this)">Pending</button>
      <button class="tab-btn" onclick="filterAdj('approved',this)">Approved</button>
      <button class="tab-btn" onclick="filterAdj('rejected',this)">Rejected</button>
    </div>
    <div class="card">
      <div class="card-header">
        <div><div class="card-title">Adjustment Requests</div><div class="card-subtitle">Approval-gated operational controls</div></div>
      </div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>ID</th><th>Type</th><th>Qty Before</th><th>Qty After</th><th>Reason</th><th>Notes</th><th>Status</th><th>Requested By</th><th>Approved By</th><th>Actions</th></tr></thead>
          <tbody id="adj-tbody">
            ${data.adjustments.map(a => `<tr data-status="${a.status}">
              <td>${mono(a.id.substring(0,8))}</td>
              <td>${badge(a.adjustment_type)}</td>
              <td>${fmtQty(a.qty_before)}</td>
              <td>${fmtQty(a.qty_after)}</td>
              <td>${mono(a.reason_code)}</td>
              <td style="max-width:200px;font-size:11px">${a.notes || '—'}</td>
              <td>${badge(a.status)}</td>
              <td>${mono(a.requested_by)}</td>
              <td>${mono(a.approved_by || '—')}</td>
              <td>
                ${a.status === 'pending' ? `
                  <button class="btn btn-sm btn-success" onclick="approveAdj('${a.id}')">Approve</button>
                  <button class="btn btn-sm btn-error" onclick="rejectAdj('${a.id}')">Reject</button>
                ` : ''}
              </td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function filterAdj(status, btn) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('#adj-tbody tr').forEach(tr => {
    tr.style.display = (status === 'all' || tr.dataset.status === status) ? '' : 'none';
  });
}

async function approveAdj(id) { await apiPost('/approve_adjustment', { id }); loadAdjustments(); }
async function rejectAdj(id) { await apiPost('/reject_adjustment', { id }); loadAdjustments(); }

// ===== FINDINGS =====
async function loadFindings() {
  const el = document.getElementById('page-findings');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(3);
  const data = await api('/findings');
  if (!data) return;

  el.innerHTML = `
    <div class="tab-bar">
      <button class="tab-btn active" onclick="filterFindings('all',this)">All</button>
      <button class="tab-btn" onclick="filterFindings('open',this)">Open</button>
      <button class="tab-btn" onclick="filterFindings('resolved',this)">Resolved</button>
    </div>
    <div class="card">
      <div class="card-header">
        <div><div class="card-title">Reconciliation Findings</div><div class="card-subtitle">Exceptions requiring investigation</div></div>
      </div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>Type</th><th>Severity</th><th>Description</th><th>Resource</th><th>Status</th><th>Resolved By</th><th>Created</th><th>Actions</th></tr></thead>
          <tbody id="findings-tbody">
            ${data.findings.map(f => `<tr data-status="${f.resolution_status}">
              <td>${badge(f.finding_type)}</td>
              <td>${badge(f.severity)}</td>
              <td style="max-width:350px;font-size:11px">${f.description || '—'}</td>
              <td>${mono(f.resource_type ? f.resource_type + ':' + (f.resource_id || '').substring(0,8) : '—')}</td>
              <td>${badge(f.resolution_status)}</td>
              <td>${mono(f.resolved_by || '—')}</td>
              <td>${fmtDate(f.created_at)}</td>
              <td>
                ${f.resolution_status === 'open' ? `<button class="btn btn-sm btn-primary" onclick="resolveFinding('${f.id}')">Resolve</button>` : ''}
              </td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function filterFindings(status, btn) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('#findings-tbody tr').forEach(tr => {
    tr.style.display = (status === 'all' || tr.dataset.status === status) ? '' : 'none';
  });
}

async function resolveFinding(id) { await apiPost('/resolve_finding', { id }); loadFindings(); }

// ===== INTEGRATIONS =====
async function loadIntegrations() {
  const el = document.getElementById('page-integrations');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(3);
  const data = await api('/integration_events');
  if (!data) return;

  el.innerHTML = `
    <div class="detail-grid">
      <div class="info-card">
        <h4>QuickBooks Desktop 2024</h4>
        <div class="info-row"><span class="label">Connector Status</span><span class="value">${badge('active')}</span></div>
        <div class="info-row"><span class="label">Pattern</span><span class="value">Outbox Queue</span></div>
        <div class="info-row"><span class="label">Protocol</span><span class="value">QB SDK / QBFC</span></div>
        <div class="info-row"><span class="label">Last Sync</span><span class="value">—</span></div>
      </div>
      <div class="info-card">
        <h4>Integration Health</h4>
        <div class="info-row"><span class="label">Pending Events</span><span class="value">${data.events.filter(e=>e.status==='pending').length}</span></div>
        <div class="info-row"><span class="label">Applied</span><span class="value">${data.events.filter(e=>e.status==='applied').length}</span></div>
        <div class="info-row"><span class="label">Failed</span><span class="value">${data.events.filter(e=>e.status==='failed').length}</span></div>
        <div class="info-row"><span class="label">Dead Letter</span><span class="value">${data.events.filter(e=>e.status==='dead_letter').length}</span></div>
      </div>
    </div>
    <div class="card">
      <div class="card-header">
        <div><div class="card-title">Integration Event Queue</div><div class="card-subtitle">Outbox events for QuickBooks sync</div></div>
      </div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>ID</th><th>Type</th><th>Direction</th><th>Status</th><th>Retries</th><th>Error</th><th>Created</th><th>Processed</th><th>Actions</th></tr></thead>
          <tbody>
            ${data.events.map(e => `<tr>
              <td>${mono(e.id.substring(0,8))}</td>
              <td>${mono(e.event_type)}</td>
              <td>${badge(e.direction)}</td>
              <td>${badge(e.status)}</td>
              <td>${e.retry_count}</td>
              <td style="max-width:200px;font-size:11px">${e.error_message || '—'}</td>
              <td>${fmtDate(e.created_at)}</td>
              <td>${e.processed_at ? fmtDate(e.processed_at) : '—'}</td>
              <td>
                ${e.status === 'failed' || e.status === 'dead_letter' ? `<button class="btn btn-sm btn-secondary" onclick="retryIntegration('${e.id}')">Retry</button>` : ''}
              </td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

async function retryIntegration(id) { await apiPost('/retry_integration', { id }); loadIntegrations(); }

// ===== USERS & RBAC =====
async function loadUsers() {
  const el = document.getElementById('page-users');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(3);
  const data = await api('/users');
  if (!data) return;

  const roleMap = {
    system_admin: { label: 'System Admin', desc: 'Full access, config, users, integrations' },
    inventory_admin: { label: 'Inventory Admin', desc: 'Receiving, putaway, adjustments, cycle counts' },
    warehouse_operator: { label: 'Warehouse Operator', desc: 'Pick, cut, scan, print within warehouse' },
    warehouse_lead: { label: 'Warehouse Lead', desc: 'Approve variances, unlock lines, reprint' },
    manager: { label: 'Manager', desc: 'Dashboards, reconciliation, high-level approvals' },
    accounting_operator: { label: 'Accounting / QBD', desc: 'Manage QBD sync, mapping approvals' },
  };

  el.innerHTML = `
    <div class="detail-grid">
      <div class="info-card">
        <h4>RBAC Summary</h4>
        ${Object.entries(roleMap).map(([k,v]) => `
          <div class="info-row"><span class="label">${v.label}</span><span class="value">${data.users.filter(u=>u.role===k).length}</span></div>
        `).join('')}
      </div>
      <div class="info-card">
        <h4>Permission Matrix</h4>
        <div style="font-size:11px;color:var(--color-text-muted);line-height:1.6">
          <div><strong>Import Requests:</strong> Lead, Inv Admin, Manager, Sys Admin</div>
          <div><strong>Execute Pick/Cut:</strong> Operator, Lead, Inv Admin, Sys Admin</div>
          <div><strong>Approve Adjustments:</strong> Lead (limited), Inv Admin, Manager, Sys Admin</div>
          <div><strong>Force Close/Override:</strong> Lead, Inv Admin, Manager, Sys Admin</div>
          <div><strong>Run QBD Sync:</strong> Accounting, Sys Admin</div>
          <div><strong>Edit Mappings:</strong> Inv Admin, Accounting, Sys Admin</div>
        </div>
      </div>
    </div>
    <div class="card">
      <div class="card-header">
        <div><div class="card-title">System Users</div><div class="card-subtitle">${data.users.length} total users</div></div>
      </div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>User</th><th>Username</th><th>Email</th><th>Role</th><th>Entity</th><th>Warehouse</th><th>Status</th></tr></thead>
          <tbody>
            ${data.users.map(u => `<tr>
              <td style="font-weight:500">${u.display_name}</td>
              <td>${mono(u.username)}</td>
              <td style="font-size:11px">${u.email || '—'}</td>
              <td>${badge(u.role)}</td>
              <td>${u.entity_name || '—'}</td>
              <td>${u.warehouse_name || 'All'}</td>
              <td>${statusDot(u.is_active)} ${u.is_active ? 'Active' : 'Inactive'}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// ===== AUDIT LOG =====
async function loadAudit() {
  const el = document.getElementById('page-audit');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(5);
  const data = await api('/audit_log');
  if (!data) return;

  el.innerHTML = `
    <div class="card">
      <div class="card-header">
        <div><div class="card-title">Audit Trail</div><div class="card-subtitle">Who, what, when, why — for all operationally material events</div></div>
      </div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Object</th><th>Object ID</th><th>Reason</th><th>Channel</th></tr></thead>
          <tbody>
            ${data.logs.length > 0 ? data.logs.map(l => `<tr>
              <td>${fmtDate(l.created_at)}</td>
              <td>${l.actor_name || mono(l.actor_user_id)}</td>
              <td>${mono(l.action)}</td>
              <td>${badge(l.object_type)}</td>
              <td>${mono(l.object_id ? l.object_id.substring(0,8) : '—')}</td>
              <td style="font-size:11px">${l.reason_code || '—'}</td>
              <td>${badge(l.source_channel || 'web')}</td>
            </tr>`).join('') : '<tr><td colspan="7" style="text-align:center;padding:var(--space-8);color:var(--color-text-faint)">No audit log entries yet. Actions will be recorded as operations are performed.</td></tr>'}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// ===== INIT =====
navigate('dashboard');
