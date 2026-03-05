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

// ===== OUTBOUND =====
async function loadOutbound() {
  const el = document.getElementById('page-outbound');
  el.innerHTML = skeletonTable(10);
  const data = await api('/outbound_lines');
  if (!data?.lines?.length) { el.innerHTML = emptyState('No outbound lines'); return; }
  el.innerHTML = `
    <div class="card">
      <div class="card-header"><div class="card-title">Outbound Queue</div><div class="card-subtitle">${data.lines.length} lines</div></div>
      <div class="table-wrapper"><table>
        <thead><tr><th>SO #</th><th>Customer</th><th>Item</th><th>Ordered</th><th>Allocated</th><th>Status</th><th>Priority</th><th>Ship By</th></tr></thead>
        <tbody>${data.lines.map(l => `<tr>
          <td>${trackingId(l.so_number)}</td>
          <td>${l.customer_name || '—'}</td>
          <td>${l.item_name || '—'}</td>
          <td>${fmtQty(l.qty_ordered)}m</td>
          <td>${fmtQty(l.qty_allocated)}m</td>
          <td>${badge(l.status)}</td>
          <td>${badge(l.priority)}</td>
          <td>${fmtDate(l.ship_by_date)}</td>
        </tr>`).join('')}</tbody>
      </table></div>
    </div>`;
}

// ===== CUTS =====
async function loadCuts() {
  const el = document.getElementById('page-cuts');
  el.innerHTML = skeletonTable(10);
  const data = await api('/cuts');
  if (!data?.cuts?.length) { el.innerHTML = emptyState('No cut transactions'); return; }
  el.innerHTML = `
    <div class="card">
      <div class="card-header"><div class="card-title">Cut Transactions</div><div class="card-subtitle">${data.cuts.length} cuts</div></div>
      <div class="table-wrapper"><table>
        <thead><tr><th>Cut ID</th><th>Item</th><th>Lot</th><th>SO #</th><th>Qty Cut</th><th>Status</th><th>Cut By</th><th>Time</th></tr></thead>
        <tbody>${data.cuts.map(c => `<tr>
          <td>${trackingId(c.cut_id)}</td>
          <td>${c.item_name || '—'}</td>
          <td>${mono(c.lot_tracking)}</td>
          <td>${trackingId(c.so_number)}</td>
          <td>${fmtQty(c.qty_cut)}m</td>
          <td>${badge(c.status)}</td>
          <td>${mono(c.cut_by)}</td>
          <td>${fmtDate(c.cut_at)}</td>
        </tr>`).join('')}</tbody>
      </table></div>
    </div>`;
}

// ===== TAGS =====
async function loadTags() {
  const el = document.getElementById('page-tags');
  el.innerHTML = skeletonTable(10);
  const data = await api('/tags');
  if (!data?.tags?.length) { el.innerHTML = emptyState('No tags found'); return; }
  el.innerHTML = `
    <div class="card">
      <div class="card-header"><div class="card-title">Tags & Labels</div><div class="card-subtitle">${data.tags.length} tags</div></div>
      <div class="table-wrapper"><table>
        <thead><tr><th>Tag ID</th><th>Type</th><th>Lot</th><th>Item</th><th>Status</th><th>Printed By</th><th>Printed At</th></tr></thead>
        <tbody>${data.tags.map(t => `<tr>
          <td>${trackingId(t.tag_id)}</td>
          <td>${badge(t.tag_type)}</td>
          <td>${mono(t.lot_tracking)}</td>
          <td>${t.item_name || '—'}</td>
          <td>${badge(t.status)}</td>
          <td>${mono(t.printed_by)}</td>
          <td>${fmtDate(t.printed_at)}</td>
        </tr>`).join('')}</tbody>
      </table></div>
    </div>`;
}

// ===== INVENTORY =====
async function loadInventory() {
  const el = document.getElementById('page-inventory');
  el.innerHTML = skeletonTable(10);
  const data = await api('/inventory');
  if (!data?.lots?.length) { el.innerHTML = emptyState('No inventory'); return; }
  el.innerHTML = `
    <div class="card">
      <div class="card-header"><div class="card-title">Lots & Rolls</div><div class="card-subtitle">${data.lots.length} lots</div></div>
      <div class="table-wrapper"><table>
        <thead><tr><th>Lot ID</th><th>Item</th><th>On Hand</th><th>Reserved</th><th>Available</th><th>Location</th><th>Status</th></tr></thead>
        <tbody>${data.lots.map(l => `<tr>
          <td>${trackingId(l.lot_tracking)}</td>
          <td>${l.item_name || '—'}</td>
          <td>${fmtQty(l.qty_on_hand)}m</td>
          <td>${fmtQty(l.qty_reserved)}m</td>
          <td>${fmtQty(l.qty_available)}m</td>
          <td><span class="location-path">${l.location_path || '—'}</span></td>
          <td>${badge(l.status)}</td>
        </tr>`).join('')}</tbody>
      </table></div>
    </div>`;
}

// ===== WAREHOUSES =====
async function loadWarehouses() {
  const el = document.getElementById('page-warehouses');
  el.innerHTML = '<div class="loading-skeleton skeleton-kpi" style="height:200px"></div>';
  const data = await api('/warehouses');
  if (!data?.warehouses?.length) { el.innerHTML = emptyState('No warehouses'); return; }
  el.innerHTML = `
    <div class="warehouse-grid">${data.warehouses.map(w => `
      <div class="rack-card">
        <div class="rack-name">${w.location_path}</div>
        <div class="rack-stats">${w.total_lots} lots · ${fmtQty(w.total_qty)}m</div>
        <div class="rack-bar"><div class="rack-bar-fill" style="width:${Math.min(100,(w.total_qty/100)*100)}%"></div></div>
      </div>`).join('')}
    </div>`;
}

// ===== MOVEMENTS =====
async function loadMovements() {
  const el = document.getElementById('page-movements');
  el.innerHTML = skeletonTable(15);
  const data = await api('/movements');
  if (!data?.movements?.length) { el.innerHTML = emptyState('No movements'); return; }
  el.innerHTML = `
    <div class="card">
      <div class="card-header"><div class="card-title">Movement Ledger</div><div class="card-subtitle">${data.movements.length} entries</div></div>
      <div class="table-wrapper"><table>
        <thead><tr><th>Type</th><th>Item</th><th>Lot</th><th>Delta</th><th>Before</th><th>After</th><th>Location</th><th>By</th><th>Time</th></tr></thead>
        <tbody>${data.movements.map(m => `<tr>
          <td><span class="movement-type ${m.movement_type}">${m.movement_type}</span></td>
          <td>${m.item_name || '—'}</td>
          <td>${mono(m.lot_tracking)}</td>
          <td>${qtyDelta(m.qty_delta)}</td>
          <td>${fmtQty(m.qty_before)}</td>
          <td>${fmtQty(m.qty_after)}</td>
          <td><span class="location-path">${m.location_path || '—'}</span></td>
          <td>${mono(m.action_by)}</td>
          <td>${fmtDate(m.action_at)}</td>
        </tr>`).join('')}</tbody>
      </table></div>
    </div>`;
}

// ===== ADJUSTMENTS =====
async function loadAdjustments() {
  const el = document.getElementById('page-adjustments');
  el.innerHTML = skeletonTable(10);
  const data = await api('/adjustments');
  if (!data?.adjustments?.length) { el.innerHTML = emptyState('No pending approvals'); return; }
  el.innerHTML = `
    <div class="card">
      <div class="card-header"><div class="card-title">Adjustment Approvals</div><div class="card-subtitle">${data.adjustments.length} items</div></div>
      <div class="table-wrapper"><table>
        <thead><tr><th>Adj ID</th><th>Item</th><th>Lot</th><th>Delta</th><th>Reason</th><th>Status</th><th>Requested By</th><th>Time</th></tr></thead>
        <tbody>${data.adjustments.map(a => `<tr>
          <td>${trackingId(a.adjustment_id)}</td>
          <td>${a.item_name || '—'}</td>
          <td>${mono(a.lot_tracking)}</td>
          <td>${qtyDelta(a.qty_delta)}</td>
          <td>${a.reason || '—'}</td>
          <td>${badge(a.status)}</td>
          <td>${mono(a.requested_by)}</td>
          <td>${fmtDate(a.requested_at)}</td>
        </tr>`).join('')}</tbody>
      </table></div>
    </div>`;
}

// ===== FINDINGS =====
async function loadFindings() {
  const el = document.getElementById('page-findings');
  el.innerHTML = skeletonTable(10);
  const data = await api('/findings');
  if (!data?.findings?.length) { el.innerHTML = emptyState('No findings'); return; }
  el.innerHTML = `
    <div class="card">
      <div class="card-header"><div class="card-title">Reconciliation Findings</div><div class="card-subtitle">${data.findings.length} findings</div></div>
      <div class="table-wrapper"><table>
        <thead><tr><th>ID</th><th>Type</th><th>Severity</th><th>Description</th><th>Status</th><th>Lot</th><th>Created</th></tr></thead>
        <tbody>${data.findings.map(f => `<tr>
          <td>${trackingId(f.finding_id)}</td>
          <td>${badge(f.finding_type)}</td>
          <td>${badge(f.severity)}</td>
          <td style="max-width:350px">${f.description || '—'}</td>
          <td>${badge(f.resolution_status)}</td>
          <td>${mono(f.lot_tracking)}</td>
          <td>${fmtDate(f.created_at)}</td>
        </tr>`).join('')}</tbody>
      </table></div>
    </div>`;
}

// ===== INTEGRATIONS =====
async function loadIntegrations() {
  const el = document.getElementById('page-integrations');
  el.innerHTML = skeletonTable(5);
  const data = await api('/integrations');
  if (!data?.events?.length) { el.innerHTML = emptyState('No integration events'); return; }
  el.innerHTML = `
    <div class="card">
      <div class="card-header"><div class="card-title">QBD Integration Events</div><div class="card-subtitle">${data.events.length} events</div></div>
      <div class="table-wrapper"><table>
        <thead><tr><th>Event ID</th><th>Type</th><th>Direction</th><th>Status</th><th>Entity</th><th>Payload</th><th>Created</th></tr></thead>
        <tbody>${data.events.map(e => `<tr>
          <td>${trackingId(e.event_id)}</td>
          <td>${badge(e.event_type)}</td>
          <td>${badge(e.direction)}</td>
          <td>${badge(e.status)}</td>
          <td>${mono(e.entity_id)}</td>
          <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${e.payload || ''}">${e.payload ? e.payload.substring(0,60)+'…' : '—'}</td>
          <td>${fmtDate(e.created_at)}</td>
        </tr>`).join('')}</tbody>
      </table></div>
    </div>`;
}

// ===== USERS =====
async function loadUsers() {
  const el = document.getElementById('page-users');
  el.innerHTML = skeletonTable(5);
  const data = await api('/users');
  if (!data?.users?.length) { el.innerHTML = emptyState('No users'); return; }
  el.innerHTML = `
    <div class="card">
      <div class="card-header"><div class="card-title">Users & RBAC</div><div class="card-subtitle">${data.users.length} users</div></div>
      <div class="table-wrapper"><table>
        <thead><tr><th>User</th><th>Email</th><th>Role</th><th>Status</th><th>Entity</th><th>Last Login</th></tr></thead>
        <tbody>${data.users.map(u => `<tr>
          <td>${mono(u.username)}</td>
          <td>${u.email || '—'}</td>
          <td>${badge(u.role)}</td>
          <td>${statusDot(u.is_active)} ${u.is_active ? 'Active' : 'Inactive'}</td>
          <td>${mono(u.entity_id)}</td>
          <td>${fmtDate(u.last_login)}</td>
        </tr>`).join('')}</tbody>
      </table></div>
    </div>`;
}

// ===== AUDIT =====
async function loadAudit() {
  const el = document.getElementById('page-audit');
  el.innerHTML = skeletonTable(20);
  const data = await api('/audit');
  if (!data?.events?.length) { el.innerHTML = emptyState('No audit events'); return; }
  el.innerHTML = `
    <div class="card">
      <div class="card-header"><div class="card-title">Audit Log</div><div class="card-subtitle">${data.events.length} events</div></div>
      <div class="table-wrapper"><table>
        <thead><tr><th>Time</th><th>User</th><th>Action</th><th>Table</th><th>Record</th><th>Changes</th></tr></thead>
        <tbody>${data.events.map(e => `<tr>
          <td>${fmtDate(e.action_at)}</td>
          <td>${mono(e.action_by)}</td>
          <td>${badge(e.action_type)}</td>
          <td>${mono(e.table_name)}</td>
          <td>${mono(e.record_id)}</td>
          <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${e.changes_summary || ''}">${e.changes_summary ? e.changes_summary.substring(0,80) : '—'}</td>
        </tr>`).join('')}</tbody>
      </table></div>
    </div>`;
}

// ===== UI HELPERS =====
function skeletonTable(rows) {
  return `<div class="card"><div class="card-header"><div class="card-title loading-skeleton" style="width:160px;height:20px"></div></div>
    ${Array(rows).fill('<div class="loading-skeleton skeleton-row"></div>').join('')}</div>`;
}

function emptyState(msg) {
  return `<div class="empty-state"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><path d="M8 12h8M12 8v8"/></svg><p>${msg}</p></div>`;
}

// ===== INIT =====
navigate('dashboard');

// Reveal body after app init to prevent first-frame jitter
document.body.classList.add('ready');
