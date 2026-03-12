/* ========== NEXRAY App v3 — Full Feature UI ========== */

const API = '/api';
let currentPage = 'dashboard';
let dashboardData = null;
let currentUser = null;

// ===== THEME TOGGLE =====
(function () {
  const toggle = document.querySelector('[data-theme-toggle]');
  const root = document.documentElement;
  let theme = localStorage.getItem('nexray_theme') ||
    (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  root.setAttribute('data-theme', theme);
  if (toggle) {
    updateToggleIcon(toggle, theme);
    toggle.addEventListener('click', () => {
      theme = theme === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', theme);
      localStorage.setItem('nexray_theme', theme);
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

// ===== API CLIENT =====
function getToken() { return localStorage.getItem('nexray_token'); }

function authHeaders() {
  const tok = getToken();
  const h = { 'Content-Type': 'application/json' };
  if (tok) h['Authorization'] = 'Bearer ' + tok;
  return h;
}

async function api(endpoint, params = {}) {
  const qs = new URLSearchParams(params).toString();
  try {
    const res = await fetch(`${API}${endpoint}?${qs}`, {
      headers: { 'Authorization': 'Bearer ' + (getToken() || '') }
    });
    if (res.status === 401) { showLogin(); return null; }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: `Error ${res.status}` }));
      toast(err.detail || `Request failed (${res.status})`, 'error');
      return null;
    }
    return await res.json();
  } catch (e) {
    console.error('API Error:', e);
    toast('Network error: ' + (e.message || 'Connection failed'), 'error');
    return null;
  }
}

async function apiPost(endpoint, body) {
  try {
    const res = await fetch(`${API}${endpoint}`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(body)
    });
    if (res.status === 401) { showLogin(); return null; }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: `Error ${res.status}` }));
      toast(err.detail || `Request failed (${res.status})`, 'error');
      return null;
    }
    return await res.json();
  } catch (e) {
    console.error('API Error:', e);
    toast('Network error: ' + (e.message || 'Connection failed'), 'error');
    return null;
  }
}

async function apiPut(endpoint, body) {
  try {
    const res = await fetch(`${API}${endpoint}`, {
      method: 'PUT',
      headers: authHeaders(),
      body: JSON.stringify(body)
    });
    if (res.status === 401) { showLogin(); return null; }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: `Error ${res.status}` }));
      toast(err.detail || `Request failed (${res.status})`, 'error');
      return null;
    }
    return await res.json();
  } catch (e) {
    console.error('API Error:', e);
    toast('Network error: ' + (e.message || 'Connection failed'), 'error');
    return null;
  }
}

async function apiDelete(endpoint) {
  try {
    const res = await fetch(`${API}${endpoint}`, {
      method: 'DELETE',
      headers: authHeaders()
    });
    if (res.status === 401) { showLogin(); return null; }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: `Error ${res.status}` }));
      toast(err.detail || `Request failed (${res.status})`, 'error');
      return null;
    }
    return await res.json();
  } catch (e) {
    console.error('API Error:', e);
    toast('Network error: ' + (e.message || 'Connection failed'), 'error');
    return null;
  }
}

// ===== AUTH =====
function showLogin() {
  document.getElementById('loginScreen').style.display = '';
  document.getElementById('appContainer').style.display = 'none';
}

function showApp() {
  document.getElementById('loginScreen').style.display = 'none';
  document.getElementById('appContainer').style.display = 'grid';
}

async function handleLogin(e) {
  e.preventDefault();
  const username = document.getElementById('loginUsername').value.trim();
  const password = document.getElementById('loginPassword').value.trim();
  const btn = document.getElementById('loginBtn');
  const errEl = document.getElementById('loginError');

  btn.disabled = true;
  btn.textContent = 'Signing in…';
  errEl.classList.remove('visible');

  try {
    const res = await fetch(`${API}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    const data = await res.json();
    if (!res.ok) {
      errEl.textContent = data.detail || 'Invalid credentials.';
      errEl.classList.add('visible');
      btn.disabled = false;
      btn.textContent = 'Sign In';
      return;
    }
    localStorage.setItem('nexray_token', data.token);
    currentUser = data.user;
    updateSidebarUser(currentUser);
    showApp();
    navigate('dashboard');
    document.body.classList.add('ready');
  } catch (err) {
    errEl.textContent = 'Connection error. Please try again.';
    errEl.classList.add('visible');
    btn.disabled = false;
    btn.textContent = 'Sign In';
  }
}

async function handleLogout() {
  try {
    await apiPost('/auth/logout', {});
  } catch (_) {}
  localStorage.removeItem('nexray_token');
  currentUser = null;
  document.body.classList.remove('ready');
  showLogin();
  setTimeout(() => document.body.classList.add('ready'), 50);
}

function updateSidebarUser(user) {
  if (!user) return;
  const initials = user.display_name
    .split(' ')
    .map(w => w[0])
    .join('')
    .substring(0, 2)
    .toUpperCase();
  const el = document.getElementById('sidebarAvatar');
  const nm = document.getElementById('sidebarUserName');
  const rl = document.getElementById('sidebarUserRole');
  if (el) el.textContent = initials;
  if (nm) nm.textContent = user.display_name;
  if (rl) rl.textContent = user.role.replace(/_/g, ' ');
}

async function getWarehouseOptions() {
  const data = await api('/warehouses');
  if (!data || !data.warehouses) return '<option value="">No warehouses</option>';
  return data.warehouses.map(w =>
    `<option value="${w.id}">${esc(w.name)} (${esc(w.code)})</option>`
  ).join('');
}

// ===== INIT (auth check) =====
async function initApp() {
  const token = getToken();
  if (!token) {
    showLogin();
    document.body.classList.add('ready');
    return;
  }
  // Validate token with /api/auth/me
  try {
    const res = await fetch(`${API}/auth/me`, {
      headers: { 'Authorization': 'Bearer ' + token }
    });
    if (!res.ok) {
      localStorage.removeItem('nexray_token');
      showLogin();
      document.body.classList.add('ready');
      return;
    }
    const user = await res.json();
    currentUser = user;
    updateSidebarUser(user);
    showApp();
    navigate('dashboard');
  } catch (e) {
    showLogin();
  }
  document.body.classList.add('ready');
}

// ===== NAVIGATION =====
const pageTitles = {
  dashboard:   ['Dashboard', 'NEXRAY \u203A Home'],
  outbound:    ['Outbound Queue', 'NEXRAY \u203A Orders \u203A Outbound'],
  cuts:        ['Cut Transactions', 'NEXRAY \u203A Execution \u203A Cuts'],
  tags:        ['Tags & Labels', 'NEXRAY \u203A Execution \u203A Tags'],
  inbound:     ['Inbound Orders', 'NEXRAY \u203A Orders \u203A Inbound'],
  receiving:   ['Receiving Sessions', 'NEXRAY \u203A Orders \u203A Receiving'],
  channels:    ['Channel Connections', 'NEXRAY \u203A Orders \u203A Channels'],
  inventory:   ['Lots & Rolls', 'NEXRAY \u203A Warehouse \u203A Inventory'],
  warehouses:  ['Warehouses', 'NEXRAY \u203A Warehouse \u203A Locations'],
  movements:   ['Movement Ledger', 'NEXRAY \u203A Warehouse \u203A Ledger'],
  putaway:     ['Putaway', 'NEXRAY \u203A Warehouse \u203A Putaway'],
  adjustments: ['Approvals', 'NEXRAY \u203A Controls \u203A Approvals'],
  findings:    ['Reconciliation Findings', 'NEXRAY \u203A Controls \u203A Findings'],
  integrations:['Integrations', 'NEXRAY \u203A System \u203A Integrations'],
  items:       ['Items', 'NEXRAY \u203A System \u203A Items'],
  suppliers:   ['Suppliers', 'NEXRAY \u203A System \u203A Suppliers'],
  customers:   ['Customers', 'NEXRAY \u203A System \u203A Customers'],
  users:       ['Users & RBAC', 'NEXRAY \u203A System \u203A Access Control'],
  audit:       ['Audit Log', 'NEXRAY \u203A System \u203A Audit'],
  reservations:['Reservations', 'NEXRAY \u203A Controls \u203A Reservations'],
  returns:     ['Returns', 'NEXRAY \u203A Controls \u203A Returns'],
  // Commerce
  products:         ['Products & Listings', 'NEXRAY \u203A Commerce \u203A Products'],
  'ecom-orders':    ['E-Commerce Orders', 'NEXRAY \u203A Commerce \u203A Orders'],
  fulfillment:      ['Fulfillment', 'NEXRAY \u203A Commerce \u203A Fulfillment'],
  'ecom-returns':   ['E-Com Returns', 'NEXRAY \u203A Commerce \u203A Returns'],
  affiliates:       ['Affiliates', 'NEXRAY \u203A Commerce \u203A Affiliates'],
  'stock-sync':     ['Stock Sync', 'NEXRAY \u203A Commerce \u203A Stock Sync'],
  // Messaging
  inbox:            ['Unified Inbox', 'NEXRAY \u203A Messaging \u203A Inbox'],
  'canned-responses':['Quick Replies', 'NEXRAY \u203A Messaging \u203A Quick Replies'],
  // AI Agents
  'agent-dashboard':['Agent Dashboard', 'NEXRAY \u203A AI Agents \u203A Dashboard'],
  'agent-tasks':    ['Deep Tasks', 'NEXRAY \u203A AI Agents \u203A Tasks'],
  'agent-decisions':['Decision Log', 'NEXRAY \u203A AI Agents \u203A Decisions'],
};

function navigate(page) {
  currentPage = page;
  document.querySelectorAll('.page-section').forEach(s => s.classList.remove('active'));
  const section = document.getElementById(`page-${page}`);
  if (section) section.classList.add('active');
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.querySelector(`.nav-item[data-page="${page}"]`)?.classList.add('active');
  const [title, breadcrumb] = pageTitles[page] || [page, ''];
  document.getElementById('page-title').textContent = title;
  document.getElementById('page-breadcrumb').textContent = breadcrumb;
  // Loading bar
  const main = document.getElementById('mainContent');
  let bar = main.querySelector('.loading-bar');
  if (!bar) { bar = document.createElement('div'); bar.className = 'loading-bar'; main.appendChild(bar); }
  bar.style.display = 'block';
  const loadDone = () => { if (bar) bar.style.display = 'none'; };
  Promise.resolve(loadPage(page)).then(loadDone).catch(loadDone);
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('mobileOverlay').classList.remove('active');
}

// ===== HELPERS =====
function badge(status) {
  if (!status) return '';
  const cls = `badge badge-${status.replace(/\s/g, '_')}`;
  return `<span class="${cls}">${status.replace(/_/g, ' ')}</span>`;
}

function trackingId(id) { return id ? `<span class="tracking-id">${id}</span>` : '\u2014'; }
function mono(val) { return val ? `<span class="mono">${val}</span>` : '\u2014'; }
function fmtQty(val) { return val != null ? Number(val).toFixed(2) : '\u2014'; }
function fmtDate(d) {
  if (!d) return '\u2014';
  const dt = new Date(d + (d.includes('T') ? '' : 'Z'));
  return dt.toLocaleDateString('en-PH', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}
function statusDot(active) { return `<span class="status-dot ${active ? 'active' : 'inactive'}"></span>`; }

function qtyDelta(val) {
  if (val == null) return '\u2014';
  const n = Number(val);
  const cls = n > 0 ? 'qty-positive' : n < 0 ? 'qty-negative' : '';
  return `<span class="${cls}">${n > 0 ? '+' : ''}${n.toFixed(2)}</span>`;
}

function esc(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ===== TOAST =====
function toast(msg, type = 'info') {
  const container = document.getElementById('toastContainer');
  const t = document.createElement('div');
  t.className = `toast toast-${type}`;
  t.textContent = msg;
  container.appendChild(t);
  setTimeout(() => {
    t.style.opacity = '0';
    t.style.transition = 'opacity 200ms';
    setTimeout(() => t.remove(), 200);
  }, 3500);
}

// ===== MODAL SYSTEM =====
function openModal(title, bodyHtml, footerHtml, sizeClass = '') {
  const overlay = document.getElementById('modalOverlay');
  const modal = document.getElementById('modalContainer');
  document.getElementById('modalTitle').textContent = title;
  document.getElementById('modalBody').innerHTML = bodyHtml;
  document.getElementById('modalFooter').innerHTML = footerHtml;
  modal.className = `modal${sizeClass ? ' ' + sizeClass : ''}`;
  overlay.classList.add('open');
}

function closeModal() {
  document.getElementById('modalOverlay').classList.remove('open');
  document.getElementById('modalBody').innerHTML = '';
  document.getElementById('modalFooter').innerHTML = '';
}

// ===== PAGE LOADERS =====
async function loadPage(page) {
  const loaders = {
    dashboard:    loadDashboard,
    outbound:     loadOutbound,
    cuts:         loadCuts,
    tags:         loadTags,
    inbound:      loadInbound,
    receiving:    loadReceiving,
    channels:     loadChannels,
    inventory:    loadInventory,
    warehouses:   loadWarehouses,
    movements:    loadMovements,
    putaway:      loadPutaway,
    adjustments:  loadAdjustments,
    findings:     loadFindings,
    integrations: loadIntegrations,
    items:        loadItems,
    suppliers:    loadSuppliers,
    customers:    loadCustomers,
    users:        loadUsers,
    audit:        loadAudit,
    reservations: loadReservations,
    returns:      loadReturns,
    // Commerce (commerce.js)
    products:         loadProducts,
    'ecom-orders':    loadEcomOrders,
    fulfillment:      loadFulfillment,
    'ecom-returns':   loadEcomReturns,
    affiliates:       loadAffiliates,
    'stock-sync':     loadStockSync,
    // Messaging (messaging.js)
    inbox:            loadInbox,
    'canned-responses': loadCannedResponses,
    // AI Agents (agents.js)
    'agent-dashboard': loadAgentDashboard,
    'agent-tasks':     loadAgentTasks,
    'agent-decisions': loadAgentDecisions,
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

  const pb = document.getElementById('nav-pending-badge');
  if (pb) { pb.textContent = k.pending_lines > 0 ? k.pending_lines : ''; pb.style.display = k.pending_lines > 0 ? 'flex' : 'none'; }
  const ab = document.getElementById('nav-approval-badge');
  if (ab) { ab.textContent = k.pending_adjustments > 0 ? k.pending_adjustments : ''; ab.style.display = k.pending_adjustments > 0 ? 'flex' : 'none'; }
  const fb = document.getElementById('nav-findings-badge');
  if (fb) { fb.textContent = k.open_findings > 0 ? k.open_findings : ''; fb.style.display = k.open_findings > 0 ? 'flex' : 'none'; }

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
              <td>${m.item_name || '\u2014'}</td>
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
        <button class="btn btn-sm btn-secondary" onclick="runReconciliation()">Run Reconciliation</button>
      </div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>Type</th><th>Severity</th><th>Description</th><th>Status</th><th>Created</th></tr></thead>
          <tbody>
            ${data.recent_findings.length > 0 ? data.recent_findings.map(f => `<tr>
              <td>${badge(f.finding_type)}</td>
              <td>${badge(f.severity)}</td>
              <td style="max-width:400px">${f.description || '\u2014'}</td>
              <td>${badge(f.resolution_status)}</td>
              <td>${fmtDate(f.created_at)}</td>
            </tr>`).join('') : '<tr><td colspan="5" class="empty-state"><p>No active findings</p></td></tr>'}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

async function runReconciliation() {
  const btn = event.target;
  btn.disabled = true;
  btn.textContent = 'Running\u2026';
  const result = await apiPost('/reconciliation/run', { run_type: 'manual' });
  btn.disabled = false;
  btn.textContent = 'Run Reconciliation';
  if (result && result.success) {
    toast(`Reconciliation complete: ${result.findings_count} finding(s) found`, result.findings_count > 0 ? 'warning' : 'success');
    loadDashboard();
  } else {
    toast('Reconciliation failed', 'error');
  }
}

// ===== OUTBOUND QUEUE =====
async function loadOutbound() {
  const el = document.getElementById('page-outbound');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(5);
  const data = await api('/outbound');
  if (!data) return;
  const lines = data.lines;
  const statuses = ['all','pending','allocated','in_progress','cut_complete','closed','needs_approval','cancelled'];

  el.innerHTML = `
    <div class="page-action-bar">
      <div class="page-action-bar-left">
        <div class="tab-bar">
          ${statuses.map(s => `<button class="tab-btn ${s === 'all' ? 'active' : ''}" onclick="filterOutbound('${s}', this)">${s === 'all' ? 'All' : s.replace(/_/g,' ')}</button>`).join('')}
        </div>
      </div>
      <div class="page-action-bar-right">
        <button class="btn btn-primary" onclick="showCreateOutboundBatchModal()">+ Import Batch</button>
      </div>
    </div>
    <div class="card">
      <div class="card-header">
        <div><div class="card-title">Outbound Request Lines</div><div class="card-subtitle">${lines.length} total lines</div></div>
      </div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>Line</th><th>Company</th><th>Ref</th><th>Item</th><th>SKU</th><th>Requested</th><th>Allocated</th><th>Fulfilled</th><th>Variance</th><th>Status</th><th>Claimed By</th><th>Actions</th></tr></thead>
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
  const actions = [];
  if (l.status === 'pending') {
    actions.push(`<button class="btn btn-sm btn-primary" onclick="fifoAllocate('${l.id}')">FIFO Allocate</button>`);
  }
  if (l.status === 'allocated') {
    actions.push(`<button class="btn btn-sm btn-primary" onclick="claimLine('${l.id}')">Claim Line</button>`);
  }
  if (l.status === 'in_progress') {
    actions.push(`<button class="btn btn-sm btn-secondary" onclick="showRecordCutModal('${l.id}','${esc(l.item_name)}','${esc(l.qty_requested)}')">Record Cut</button>`);
  }
  if (l.status === 'cut_complete') {
    actions.push(`<button class="btn btn-sm btn-success" onclick="closeLine('${l.id}')">Close Line</button>`);
  }

  return `<tr data-status="${l.status}">
    <td>${mono('#' + l.line_no)}</td>
    <td>${l.company_label ? `<span style="font-size:11px;font-weight:500">${esc(l.company_label)}</span>` : '\u2014'}</td>
    <td>${l.reference_no || '\u2014'}</td>
    <td>${l.item_name || '\u2014'}</td>
    <td>${mono(l.sku)}</td>
    <td>${fmtQty(l.qty_requested)}</td>
    <td>${fmtQty(l.qty_allocated)}</td>
    <td>${fmtQty(l.qty_fulfilled)}</td>
    <td><span class="${varClass}">${l.qty_variance !== 0 ? (l.qty_variance > 0 ? '+' : '') + Number(l.qty_variance).toFixed(2) : '0.00'}</span></td>
    <td>${badge(l.status)}</td>
    <td>${mono(l.claimed_by || '\u2014')}</td>
    <td style="white-space:nowrap">${actions.join(' ')}</td>
  </tr>`;
}

function filterOutbound(status, btn) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('#outbound-tbody tr').forEach(tr => {
    tr.style.display = (status === 'all' || tr.dataset.status === status) ? '' : 'none';
  });
}

async function fifoAllocate(lineId) {
  const result = await apiPost('/outbound/allocate', { line_id: lineId });
  if (result && result.success) {
    toast(`Allocated ${fmtQty(result.total_allocated)}m across ${result.reservations.length} lot(s)`, 'success');
    loadOutbound();
  } else {
    toast(result?.detail || 'Allocation failed', 'error');
  }
}

async function claimLine(lineId) {
  const result = await apiPost('/outbound/claim_line', { line_id: lineId });
  if (result && result.success) {
    toast('Line claimed \u2014 now in progress', 'success');
    loadOutbound();
  } else {
    toast(result?.detail || 'Claim failed', 'error');
  }
}

async function closeLine(lineId) {
  const result = await apiPost('/outbound/close_line', { line_id: lineId });
  if (result && result.success) {
    toast('Line closed successfully', 'success');
    loadOutbound();
  } else {
    toast(result?.detail || 'Close failed \u2014 check gate conditions', 'error');
  }
}

function showRecordCutModal(lineId, itemName, qtyRequested) {
  // Calculate remaining qty (requested - fulfilled so far)
  const remaining = parseFloat(qtyRequested) || 0;

  openModal('Record Cut', `
    <p style="font-size:var(--text-xs);color:var(--color-text-muted);margin-bottom:var(--space-2)">Item: <strong>${esc(itemName)}</strong> \u2014 Requested: <strong>${fmtQty(qtyRequested)}m</strong></p>
    <div class="form-group" style="margin-top:var(--space-3)">
      <label class="form-label">Tracking ID (scan or type)</label>
      <input type="text" class="form-input" id="cutTrackingId" placeholder="Scan barcode or type tracking ID" autofocus>
    </div>
    <div class="form-grid">
      <div class="form-group">
        <label class="form-label">Qty Requested</label>
        <input type="number" class="form-input" id="cutQtyReq" value="${qtyRequested}" step="0.01" min="0">
      </div>
      <div class="form-group">
        <label class="form-label">Qty Actual (cut)</label>
        <input type="number" class="form-input" id="cutQtyActual" value="${remaining.toFixed(2)}" step="0.01" min="0">
      </div>
    </div>
    <div class="form-group">
      <label class="form-label">Variance Reason (if applicable)</label>
      <input type="text" class="form-input" id="cutVarianceReason" placeholder="e.g. edge defect, customer request">
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitRecordCut('${lineId}')">Record Cut</button>
  `);
}

async function submitRecordCut(lineId) {
  const trackingIdVal = document.getElementById('cutTrackingId').value.trim();
  const qtyReq = parseFloat(document.getElementById('cutQtyReq').value);
  const qtyActual = parseFloat(document.getElementById('cutQtyActual').value);
  const varianceReason = document.getElementById('cutVarianceReason').value.trim();

  if (!trackingIdVal) { toast('Enter or scan a tracking ID', 'warning'); return; }
  if (!qtyActual || qtyActual <= 0) { toast('Enter a valid actual qty', 'warning'); return; }

  const result = await apiPost('/outbound/record_cut', {
    line_id: lineId,
    tracking_id: trackingIdVal,
    qty_requested: qtyReq,
    qty_actual: qtyActual,
    variance_reason: varianceReason || null
  });

  if (result && result.success) {
    closeModal();
    const msg = result.needs_approval
      ? `Cut recorded \u2014 tag ${result.tag_code} generated. NEEDS APPROVAL (variance >5%)`
      : `Cut recorded \u2014 tag ${result.tag_code} generated`;
    toast(msg, result.needs_approval ? 'warning' : 'success');
    loadOutbound();
  } else {
    toast(result?.detail || 'Cut failed', 'error');
  }
}

async function showCreateOutboundBatchModal() {
  const whOpts = await getWarehouseOptions();
  openModal('Import Outbound Batch', `
    <div class="form-group">
      <label class="form-label">Batch Code (auto-generated if empty)</label>
      <input type="text" class="form-input" id="obBatchCode" placeholder="ORB-2024-001">
    </div>
    <div class="form-group">
      <label class="form-label">Company</label>
      <select class="form-select" id="obCompany">
        <option value="">— Select —</option>
        <option value="Larry's Hitex Division Inc.">Larry's Hitex Division Inc.</option>
        <option value="Fabric Life">Fabric Life</option>
        <option value="Casa Finds">Casa Finds</option>
      </select>
    </div>
    <div class="form-group">
      <label class="form-label">Reference No</label>
      <input type="text" class="form-input" id="obRefNo" placeholder="PO-CUST-001">
    </div>
    <div class="form-group">
      <label class="form-label">Warehouse</label>
      <select class="form-select" id="obWarehouse">${whOpts}</select>
    </div>
    <div class="form-group">
      <label class="form-label">Lines</label>
      <div class="lines-table-wrap">
        <table>
          <thead><tr><th>Item ID / Name</th><th>Qty (m)</th><th>UOM</th><th></th></tr></thead>
          <tbody id="obLinesTbody">
            <tr>
              <td><input class="form-input" style="min-width:180px" placeholder="item id or name"></td>
              <td><input type="number" class="form-input" style="width:80px" placeholder="0.00" step="0.01" min="0"></td>
              <td><select class="form-select" style="width:80px"><option>meter</option><option>piece</option><option>pack</option></select></td>
              <td><button class="btn btn-sm btn-error" onclick="this.closest('tr').remove()">✕</button></td>
            </tr>
          </tbody>
        </table>
        <div class="lines-table-actions">
          <button class="btn btn-sm btn-secondary" onclick="addOutboundLine()">+ Add Line</button>
        </div>
      </div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitCreateOutboundBatch()">Create Batch</button>
  `, 'modal-lg');
}

function addOutboundLine() {
  const tbody = document.getElementById('obLinesTbody');
  if (!tbody) return;
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td><input class="form-input" style="min-width:180px" placeholder="item id or name"></td>
    <td><input type="number" class="form-input" style="width:80px" placeholder="0.00" step="0.01" min="0"></td>
    <td><select class="form-select" style="width:80px"><option>meter</option><option>piece</option><option>pack</option></select></td>
    <td><button class="btn btn-sm btn-error" onclick="this.closest('tr').remove()">✕</button></td>
  `;
  tbody.appendChild(tr);
}

async function submitCreateOutboundBatch() {
  const batchCode = document.getElementById('obBatchCode').value.trim() || null;
  const refNo = document.getElementById('obRefNo').value.trim();
  const warehouseId = document.getElementById('obWarehouse').value;

  const rows = document.querySelectorAll('#obLinesTbody tr');
  const lines = [];
  rows.forEach(r => {
    const inputs = r.querySelectorAll('input, select');
    const itemVal = inputs[0].value.trim();
    const qty = parseFloat(inputs[1].value);
    const uom = inputs[2].value;
    if (itemVal && qty > 0) {
      const lineData = { qty, uom };
      // Try to determine if it's an ID or a name
      if (itemVal.startsWith('itm-')) {
        lineData.item_id = itemVal;
      } else {
        lineData.item_name_raw = itemVal;
      }
      lines.push(lineData);
    }
  });

  if (!lines.length) { toast('Add at least one line', 'warning'); return; }

  const companyLabel = document.getElementById('obCompany').value.trim() || null;

  const body = {
    batch_code: batchCode,
    company_label: companyLabel,
    warehouse_id: warehouseId,
    reference_no: refNo || null,
    lines
  };

  const result = await apiPost('/outbound_requests', body);
  if (result && result.success) {
    closeModal();
    toast(`Batch created: ${result.batch_code} (${result.total_lines} lines)`, 'success');
    loadOutbound();
  } else {
    toast(result?.detail || 'Batch creation failed', 'error');
  }
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
          <thead><tr><th>ID</th><th>Item</th><th>Tracking ID</th><th>Requested</th><th>Actual</th><th>Variance</th><th>Status</th><th>Reason</th><th>Cut By</th><th>Time</th></tr></thead>
          <tbody>
            ${data.cuts.map(c => `<tr>
              <td>${mono(c.id.substring(0,8))}</td>
              <td>${c.item_name || '\u2014'}</td>
              <td>${trackingId(c.tracking_id)}</td>
              <td>${fmtQty(c.qty_requested)}</td>
              <td>${fmtQty(c.qty_actual)}</td>
              <td>${qtyDelta(c.qty_variance)}</td>
              <td>${badge(c.status)}</td>
              <td style="max-width:200px;font-size:11px">${c.variance_reason || '\u2014'}</td>
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
              <td>${t.item_name || '\u2014'}</td>
              <td>${trackingId(t.lot_tracking)}</td>
              <td>${fmtQty(t.cut_qty)}</td>
              <td>${badge(t.tag_status)}</td>
              <td>${t.printed_at ? fmtDate(t.printed_at) : '\u2014'}</td>
              <td>${t.scanned_at ? fmtDate(t.scanned_at) : '\u2014'}</td>
              <td>${fmtDate(t.created_at)}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// ===== INBOUND =====
async function loadInbound() {
  const el = document.getElementById('page-inbound');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(3);
  const data = await api('/supplier_orders');
  if (!data) return;

  el.innerHTML = `
    <div class="page-action-bar">
      <div class="page-action-bar-left"><span style="font-size:var(--text-xs);color:var(--color-text-muted)">${data.orders.length} supplier orders</span></div>
      <div class="page-action-bar-right">
        <button class="btn btn-secondary" onclick="showExcelImportModal()">Excel Import</button>
        <button class="btn btn-primary" onclick="showCreateSupplierOrderModal()">+ Create Order</button>
      </div>
    </div>
    <div class="card">
      <div class="card-header">
        <div><div class="card-title">Supplier Orders (Inbound)</div><div class="card-subtitle">Import receipts and validation</div></div>
      </div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>Batch Code</th><th>Company</th><th>Supplier</th><th>Status</th><th>Lines</th><th>Errors</th><th>Notes</th><th>Created</th><th>Actions</th></tr></thead>
          <tbody>
            ${data.orders.length > 0 ? data.orders.map(o => `<tr>
              <td>${mono(o.batch_code)}</td>
              <td>${o.company_label ? `<span style="font-size:11px;font-weight:500">${esc(o.company_label)}</span>` : '\u2014'}</td>
              <td>${o.supplier_name || '\u2014'}</td>
              <td>${badge(o.status)}</td>
              <td>${o.total_lines}</td>
              <td>${o.error_count > 0 ? `<span class="qty-negative">${o.error_count}</span>` : '0'}</td>
              <td style="max-width:200px;font-size:11px">${o.notes || '\u2014'}</td>
              <td>${fmtDate(o.created_at)}</td>
              <td style="white-space:nowrap">
                <button class="btn btn-sm btn-ghost" onclick="showOrderDetail('${o.id}')">View</button>
                ${o.status === 'draft' || o.status === 'failed_with_errors' ? `<button class="btn btn-sm btn-secondary" onclick="validateSupplierOrder('${o.id}')">Validate</button>` : ''}
                ${o.status === 'validated' ? `<button class="btn btn-sm btn-primary" onclick="showStartReceivingModal('${o.id}','${esc(o.batch_code)}')">Start Receiving</button>` : ''}
              </td>
            </tr>`).join('') : '<tr><td colspan="9" class="empty-state"><p>No supplier orders yet</p></td></tr>'}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

async function validateSupplierOrder(solId) {
  const result = await apiPost(`/supplier_orders/${solId}/validate`, {});
  if (result) {
    const msg = result.error_count > 0
      ? `Validation complete: ${result.error_count} error(s) found`
      : 'Validation passed \u2014 all lines valid';
    toast(msg, result.error_count > 0 ? 'warning' : 'success');
    loadInbound();
  } else {
    toast('Validation failed', 'error');
  }
}

function showCreateSupplierOrderModal() {
  // Build supplier options
  api('/suppliers').then(supData => {
    const suppliers = supData ? supData.suppliers : [];
    const supOptions = `<option value="">No supplier</option>` +
      suppliers.map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join('');

    openModal('Create Supplier Order (Import)', `
      <div class="form-grid">
        <div class="form-group">
          <label class="form-label">Supplier</label>
          <select class="form-select" id="solSupplier">${supOptions}</select>
        </div>
        <div class="form-group">
          <label class="form-label">Company</label>
          <select class="form-select" id="solCompany">
            <option value="">— Select —</option>
            <option value="Larry's Hitex Division Inc.">Larry's Hitex Division Inc.</option>
            <option value="Fabric Life">Fabric Life</option>
            <option value="Casa Finds">Casa Finds</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Batch Code (auto if empty)</label>
          <input type="text" class="form-input" id="solBatchCode" placeholder="SOL-2024-001">
        </div>
        <div class="form-group full">
          <label class="form-label">Notes</label>
          <input type="text" class="form-input" id="solNotes" placeholder="Optional notes">
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">Order Lines</label>
        <div class="lines-table-wrap">
          <table>
            <thead><tr><th>Item ID/Name</th><th>Qty Expected</th><th>UOM</th><th>Lot Info</th><th>Shade</th><th></th></tr></thead>
            <tbody id="solLinesTbody">
              <tr>
                <td><input class="form-input" style="min-width:140px" placeholder="item id or name"></td>
                <td><input type="number" class="form-input" style="width:80px" placeholder="0.00" step="0.01"></td>
                <td><select class="form-select" style="width:70px"><option>meter</option><option>piece</option></select></td>
                <td><input class="form-input" style="width:90px" placeholder="LOT-A1"></td>
                <td><input class="form-input" style="width:80px" placeholder="IVR-01"></td>
                <td><button class="btn btn-sm btn-error" onclick="this.closest('tr').remove()">✕</button></td>
              </tr>
            </tbody>
          </table>
          <div class="lines-table-actions">
            <button class="btn btn-sm btn-secondary" onclick="addSolLine()">+ Add Line</button>
          </div>
        </div>
      </div>
    `, `
      <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="submitCreateSupplierOrder()">Create Order</button>
    `, 'modal-xl');
  });
}

function addSolLine() {
  const tbody = document.getElementById('solLinesTbody');
  if (!tbody) return;
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td><input class="form-input" style="min-width:140px" placeholder="item id or name"></td>
    <td><input type="number" class="form-input" style="width:80px" placeholder="0.00" step="0.01"></td>
    <td><select class="form-select" style="width:70px"><option>meter</option><option>piece</option></select></td>
    <td><input class="form-input" style="width:90px" placeholder="LOT-A1"></td>
    <td><input class="form-input" style="width:80px" placeholder="IVR-01"></td>
    <td><button class="btn btn-sm btn-error" onclick="this.closest('tr').remove()">✕</button></td>
  `;
  tbody.appendChild(tr);
}

async function submitCreateSupplierOrder() {
  const supplierId = document.getElementById('solSupplier').value;
  const batchCode = document.getElementById('solBatchCode').value.trim() || null;
  const notes = document.getElementById('solNotes').value.trim() || null;

  const rows = document.querySelectorAll('#solLinesTbody tr');
  const lines = [];
  rows.forEach(r => {
    const inputs = r.querySelectorAll('input, select');
    const itemVal = inputs[0].value.trim();
    const qty = parseFloat(inputs[1].value);
    const uom = inputs[2].value;
    const lotInfo = inputs[3].value.trim() || null;
    const shadeInfo = inputs[4].value.trim() || null;
    if (itemVal && qty > 0) {
      const lineData = { qty_expected: qty, uom, lot_info: lotInfo, shade_info: shadeInfo };
      if (itemVal.startsWith('itm-')) lineData.item_id = itemVal;
      else lineData.item_name_raw = itemVal;
      lines.push(lineData);
    }
  });

  if (!lines.length) { toast('Add at least one line', 'warning'); return; }

  const companyLabel = document.getElementById('solCompany').value.trim() || null;

  const result = await apiPost('/supplier_orders', {
    supplier_id: supplierId || null,
    company_label: companyLabel,
    batch_code: batchCode,
    notes,
    lines
  });

  if (result && result.success) {
    closeModal();
    toast(`Supplier order created: ${result.batch_code}`, 'success');
    loadInbound();
  } else {
    toast(result?.detail || 'Creation failed', 'error');
  }
}

async function showStartReceivingModal(solId, batchCode) {
  const whOpts = await getWarehouseOptions();
  openModal('Start Receiving Session', `
    <p style="font-size:var(--text-xs);color:var(--color-text-muted)">Starting receiving for: <strong>${esc(batchCode)}</strong></p>
    <div class="form-group">
      <label class="form-label">Warehouse</label>
      <select class="form-select" id="recvWarehouse">
        ${whOpts}
      </select>
    </div>
    <div class="form-group">
      <label class="form-label">Notes</label>
      <input type="text" class="form-input" id="recvNotes" placeholder="Optional notes">
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitStartReceiving('${solId}')">Start Receiving</button>
  `);
}

async function submitStartReceiving(solId) {
  const warehouseId = document.getElementById('recvWarehouse').value;
  const notes = document.getElementById('recvNotes').value.trim() || null;

  const result = await apiPost('/receivings', {
    warehouse_id: warehouseId,
    supplier_order_list_id: solId,
    notes
  });

  if (result && result.success) {
    closeModal();
    toast('Receiving session started', 'success');
    navigate('receiving');
  } else {
    toast(result?.detail || 'Failed to start receiving', 'error');
  }
}

// ===== RECEIVING (Odoo-style) =====
async function loadReceiving() {
  const el = document.getElementById('page-receiving');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(3);

  const [ordersData, movData] = await Promise.all([
    api('/supplier_orders'),
    api('/movements')
  ]);
  if (!ordersData && !movData) { el.innerHTML = '<div class="empty-state"><p>Unable to load</p></div>'; return; }

  const validatedOrders = ordersData ? (ordersData.orders || []).filter(o => o.status === 'validated' || o.status === 'receiving') : [];
  const receivingMovs = movData ? movData.movements.filter(m => m.movement_type === 'receive') : [];

  el.innerHTML = `
    <div class="page-action-bar">
      <div class="page-action-bar-left"><span style="font-size:var(--text-xs);color:var(--color-text-muted)">${validatedOrders.length} order(s) ready to receive</span></div>
      <div class="page-action-bar-right">
        <button class="btn btn-primary" onclick="showQuickReceiveModal()">Quick Receive (no order)</button>
      </div>
    </div>

    ${validatedOrders.length > 0 ? `
    <div class="card" style="margin-bottom:var(--space-4)">
      <div class="card-header">
        <div><div class="card-title">Orders Ready to Receive</div><div class="card-subtitle">Pre-filled from supplier order — review quantities, then confirm</div></div>
      </div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>Batch Code</th><th>Supplier</th><th>Lines</th><th>Status</th><th>Created</th><th></th></tr></thead>
          <tbody>
            ${validatedOrders.map(o => `<tr>
              <td>${mono(o.batch_code)}</td>
              <td>${esc(o.supplier_name || '\u2014')}</td>
              <td>${o.total_lines}</td>
              <td>${badge(o.status)}</td>
              <td>${fmtDate(o.created_at)}</td>
              <td><button class="btn btn-sm btn-primary" onclick="startOdooReceiving('${o.id}','${esc(o.batch_code)}')">Receive</button></td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>
    ` : ''}

    <div class="card">
      <div class="card-header">
        <div><div class="card-title">Recent Receiving Events</div><div class="card-subtitle">Lots received into inventory</div></div>
      </div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>Tracking ID</th><th>Item</th><th>Qty</th><th>Warehouse</th><th>Received By</th><th>Time</th></tr></thead>
          <tbody>
            ${receivingMovs.length > 0 ? receivingMovs.map(m => `<tr>
              <td>${trackingId(m.lot_tracking || m.tracking_id)}</td>
              <td>${m.item_name || '\u2014'}</td>
              <td>${fmtQty(m.qty_delta)}</td>
              <td>${mono(m.warehouse_to_id)}</td>
              <td>${mono(m.action_by)}</td>
              <td>${fmtDate(m.action_at)}</td>
            </tr>`).join('') : '<tr><td colspan="6" class="empty-state"><p>No receiving events yet</p></td></tr>'}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

async function startOdooReceiving(solId, batchCode) {
  const [linesData, whData] = await Promise.all([
    api(`/supplier_orders/${solId}/lines`),
    api('/warehouses')
  ]);
  const lines = linesData ? linesData.lines : [];
  const warehouses = whData ? whData.warehouses : [];
  const whOptions = warehouses.map(w => `<option value="${w.id}">${esc(w.name)}</option>`).join('');

  openModal(`Receive: ${esc(batchCode)}`, `
    <div class="form-group">
      <label class="form-label">Warehouse *</label>
      <select class="form-select" id="odooRecvWh">${whOptions}</select>
    </div>
    <div class="result-banner info">Review and adjust quantities. Pre-filled from supplier order.</div>
    <div class="table-wrapper" style="margin-top:var(--space-3)">
      <table>
        <thead><tr><th>Item</th><th>Expected</th><th>Received Qty</th><th>Shade</th><th>Confidence</th></tr></thead>
        <tbody id="odooRecvLines">
          ${lines.map((l, i) => `<tr>
            <td>${esc(l.item_name || l.item_name_raw || 'Line ' + (i+1))}<input type="hidden" class="odoo-item-id" value="${l.item_id || ''}"></td>
            <td>${fmtQty(l.qty_expected)}</td>
            <td><input type="number" class="form-input odoo-qty" value="${l.qty_expected || ''}" step="0.01" min="0" style="width:100px"></td>
            <td><input type="text" class="form-input odoo-shade" value="${esc(l.shade_info || '')}" style="width:80px"></td>
            <td><select class="form-select odoo-confidence" style="width:130px">
              <option value="supplier_reported" selected>Supplier Reported</option>
              <option value="measured">Measured</option>
            </select></td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitOdooReceiving('${solId}')">Confirm & Receive All</button>
  `, 'modal-xl');
}

async function submitOdooReceiving(solId) {
  const warehouseId = document.getElementById('odooRecvWh').value;
  if (!warehouseId) { toast('Select a warehouse', 'warning'); return; }

  const recvResult = await apiPost('/receivings', {
    warehouse_id: warehouseId,
    supplier_order_list_id: solId
  });
  if (!recvResult || !recvResult.success) { toast('Failed to create receiving session', 'error'); return; }
  const receivingId = recvResult.id;

  const rows = document.querySelectorAll('#odooRecvLines tr');
  let successCount = 0;
  for (const row of rows) {
    const itemId = row.querySelector('.odoo-item-id')?.value;
    const qty = parseFloat(row.querySelector('.odoo-qty')?.value);
    const shade = row.querySelector('.odoo-shade')?.value.trim() || null;
    const confidence = row.querySelector('.odoo-confidence')?.value || 'supplier_reported';
    if (!itemId || !qty || qty <= 0) continue;

    const lotResult = await apiPost(`/receivings/${receivingId}/receive_lot`, {
      item_id: itemId,
      qty_original: qty,
      shade_code: shade,
      qty_confidence: confidence
    });
    if (lotResult && lotResult.success) successCount++;
  }

  await apiPost(`/receivings/${receivingId}/confirm`, {});
  await apiPost(`/receivings/${receivingId}/complete`, {});
  closeModal();
  toast(`Received ${successCount} lot(s) successfully`, 'success');
  loadReceiving();
}

function showQuickReceiveModal() {
  Promise.all([api('/items'), api('/warehouses'), api('/locations')]).then(([itemsData, whData, locData]) => {
    const items = itemsData ? itemsData.items : [];
    const warehouses = whData ? whData.warehouses : [];
    const locs = locData ? locData.locations : [];

    const itemOptions = `<option value="">Select item\u2026</option>` +
      items.map(i => `<option value="${i.id}">${esc(i.name)} (${esc(i.sku)})</option>`).join('');
    const whOptions = warehouses.map(w => `<option value="${w.id}">${esc(w.name)}</option>`).join('');
    const locOptions = `<option value="">No location</option>` +
      locs.map(l => `<option value="${l.id}">${esc(l.location_barcode || l.rack_code)}</option>`).join('');

    openModal('Quick Receive Lot', `
      <div class="form-group">
        <label class="form-label">Item *</label>
        <select class="form-select" id="rlItem">${itemOptions}</select>
      </div>
      <div class="form-grid">
        <div class="form-group">
          <label class="form-label">Tracking ID (auto if empty)</label>
          <input type="text" class="form-input" id="rlTrackingId" placeholder="TRK-2024-XXXX">
        </div>
        <div class="form-group">
          <label class="form-label">Qty *</label>
          <input type="number" class="form-input" id="rlQty" placeholder="0.00" step="0.01" min="0">
        </div>
        <div class="form-group">
          <label class="form-label">Shade Code</label>
          <input type="text" class="form-input" id="rlShade" placeholder="IVR-01">
        </div>
        <div class="form-group">
          <label class="form-label">Width (cm)</label>
          <input type="number" class="form-input" id="rlWidth" placeholder="137" step="1">
        </div>
        <div class="form-group">
          <label class="form-label">Confidence</label>
          <select class="form-select" id="rlConfidence">
            <option value="supplier_reported">Supplier Reported</option>
            <option value="measured">Measured</option>
          </select>
        </div>
      </div>
      <div class="form-grid">
        <div class="form-group">
          <label class="form-label">Warehouse *</label>
          <select class="form-select" id="rlWarehouse" onchange="loadReceivingLocations(this.value)">${whOptions}</select>
        </div>
        <div class="form-group">
          <label class="form-label">Location</label>
          <select class="form-select" id="rlLocation">${locOptions}</select>
        </div>
      </div>
    `, `
      <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="submitReceiveLot()">Receive Lot</button>
    `, 'modal-lg');
  });
}

async function loadReceivingLocations(warehouseId) {
  const locData = await api('/locations', { warehouse_id: warehouseId });
  const sel = document.getElementById('rlLocation');
  if (sel && locData) {
    sel.innerHTML = `<option value="">No location</option>` +
      locData.locations.map(l => `<option value="${l.id}">${esc(l.location_barcode || l.rack_code)}</option>`).join('');
  }
}

async function submitReceiveLot() {
  const itemId = document.getElementById('rlItem').value;
  const qty = parseFloat(document.getElementById('rlQty').value);
  const warehouseId = document.getElementById('rlWarehouse').value;

  if (!itemId) { toast('Select an item', 'warning'); return; }
  if (!qty || qty <= 0) { toast('Enter a valid quantity', 'warning'); return; }

  const recvResult = await apiPost('/receivings', { warehouse_id: warehouseId });
  if (!recvResult || !recvResult.success) { toast('Failed to create receiving session', 'error'); return; }

  const receivingId = recvResult.id;
  const result = await apiPost(`/receivings/${receivingId}/receive_lot`, {
    item_id: itemId,
    tracking_id: document.getElementById('rlTrackingId').value.trim() || null,
    shade_code: document.getElementById('rlShade').value.trim() || null,
    width_value: parseFloat(document.getElementById('rlWidth').value) || null,
    qty_original: qty,
    location_id: document.getElementById('rlLocation').value || null,
    qty_confidence: document.getElementById('rlConfidence').value
  });

  if (result && result.success) {
    await apiPost(`/receivings/${receivingId}/complete`, {});
    closeModal();
    toast(`Lot received: ${result.tracking_id} (${fmtQty(qty)}m)`, 'success');
    loadReceiving();
  } else {
    toast(result?.detail || 'Receiving failed', 'error');
  }
}

// ===== CHANNELS =====
async function loadChannels() {
  const el = document.getElementById('page-channels');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(3);
  const data = await api('/channels');
  if (!data) return;

  const mappingsData = await api('/channel_mappings');
  const mappings = mappingsData ? mappingsData.mappings : [];

  el.innerHTML = `
    <div class="page-action-bar">
      <div class="page-action-bar-left"><span style="font-size:var(--text-xs);color:var(--color-text-muted)">${data.channels.length} channel(s)</span></div>
      <div class="page-action-bar-right">
        <button class="btn btn-primary" onclick="showAddChannelModal()">+ Add Channel</button>
      </div>
    </div>
    <div class="channel-grid">
      ${data.channels.map(ch => `
        <div class="channel-card">
          <div class="channel-card-header">
            <div>
              <span class="channel-type-badge ${ch.channel_type}">${ch.channel_type}</span>
              <div style="font-size:var(--text-sm);font-weight:600;margin-top:var(--space-2)">${esc(ch.shop_name || 'Unnamed Channel')}</div>
              <div style="font-size:11px;color:var(--color-text-faint);margin-top:2px">${esc(ch.shop_url || '\u2014')}</div>
            </div>
            ${statusDot(ch.is_active)}
          </div>
          <div class="info-row" style="margin-top:var(--space-2)">
            <span class="label">Region</span>
            <span class="value">${ch.region || '\u2014'}</span>
          </div>
          <div class="info-row">
            <span class="label">Last Sync</span>
            <span class="value">${ch.last_sync_at ? fmtDate(ch.last_sync_at) : 'Never'}</span>
          </div>
          <div class="channel-actions">
            <button class="btn btn-sm btn-secondary" onclick="syncOrders('${ch.id}')">Sync Orders</button>
            <button class="btn btn-sm btn-secondary" onclick="pushInventory('${ch.id}')">Push Inventory</button>
            <button class="btn btn-sm btn-ghost" onclick="showAddMappingModal('${ch.id}')">+ Mapping</button>
          </div>
        </div>
      `).join('')}
      ${data.channels.length === 0 ? '<div class="empty-state" style="grid-column:1/-1"><p>No channels connected yet</p></div>' : ''}
    </div>

    ${mappings.length > 0 ? `
    <div class="card">
      <div class="card-header">
        <div><div class="card-title">Product Mappings</div><div class="card-subtitle">Channel SKU to NEXRAY item links</div></div>
      </div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>Channel</th><th>Shop</th><th>Channel SKU</th><th>NEXRAY Item</th><th>NEXRAY SKU</th><th>Active</th></tr></thead>
          <tbody>
            ${mappings.map(m => `<tr>
              <td>${badge(m.channel_type)}</td>
              <td>${esc(m.shop_name)}</td>
              <td>${mono(m.channel_sku)}</td>
              <td>${esc(m.item_name)}</td>
              <td>${mono(m.sku)}</td>
              <td>${statusDot(m.is_active)}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>
    ` : ''}
  `;
}

async function syncOrders(channelId) {
  const result = await apiPost(`/channels/${channelId}/sync_orders`, {});
  if (result && result.success) {
    toast(result.message, 'success');
    loadChannels();
  } else {
    toast(result?.detail || 'Sync failed', 'error');
  }
}

async function pushInventory(channelId) {
  const result = await apiPost(`/channels/${channelId}/push_inventory`, {});
  if (result && result.success) {
    toast(result.message, 'success');
  } else {
    toast(result?.detail || 'Push failed', 'error');
  }
}

function showAddChannelModal() {
  openModal('Add Channel Connection', `
    <div class="form-grid">
      <div class="form-group">
        <label class="form-label">Channel Type *</label>
        <select class="form-select" id="chType">
          <option value="shopify">Shopify</option>
          <option value="shopee">Shopee</option>
          <option value="lazada">Lazada</option>
          <option value="tiktokshop">TikTok Shop</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Shop Name *</label>
        <input type="text" class="form-input" id="chShopName" placeholder="My Shopify Store">
      </div>
      <div class="form-group full">
        <label class="form-label">Shop URL</label>
        <input type="text" class="form-input" id="chShopUrl" placeholder="https://mystore.myshopify.com">
      </div>
      <div class="form-group">
        <label class="form-label">API Key</label>
        <input type="text" class="form-input" id="chApiKey" placeholder="sk_live_\u2026">
      </div>
      <div class="form-group">
        <label class="form-label">Region</label>
        <select class="form-select" id="chRegion">
          <option value="PH">Philippines</option>
          <option value="SG">Singapore</option>
          <option value="MY">Malaysia</option>
          <option value="TH">Thailand</option>
          <option value="ID">Indonesia</option>
        </select>
      </div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitAddChannel()">Connect Channel</button>
  `);
}

async function submitAddChannel() {
  const shopName = document.getElementById('chShopName').value.trim();
  if (!shopName) { toast('Shop name is required', 'warning'); return; }

  const result = await apiPost('/channels', {
    channel_type: document.getElementById('chType').value,
    shop_name: shopName,
    shop_url: document.getElementById('chShopUrl').value.trim() || null,
    api_key: document.getElementById('chApiKey').value.trim() || null,
    region: document.getElementById('chRegion').value
  });

  if (result && result.success) {
    closeModal();
    toast('Channel connected', 'success');
    loadChannels();
  } else {
    toast(result?.detail || 'Failed to add channel', 'error');
  }
}

function showAddMappingModal(channelId) {
  api('/items').then(itemsData => {
    const items = itemsData ? itemsData.items : [];
    const itemOptions = `<option value="">Select item\u2026</option>` +
      items.map(i => `<option value="${i.id}">${esc(i.name)} (${esc(i.sku)})</option>`).join('');

    openModal('Add Product Mapping', `
      <div class="form-group">
        <label class="form-label">NEXRAY Item *</label>
        <select class="form-select" id="mapItem">${itemOptions}</select>
      </div>
      <div class="form-grid">
        <div class="form-group">
          <label class="form-label">Channel SKU</label>
          <input type="text" class="form-input" id="mapChannelSku" placeholder="FAB-BLK-GREY">
        </div>
        <div class="form-group">
          <label class="form-label">Channel Product ID</label>
          <input type="text" class="form-input" id="mapChannelProductId" placeholder="shopify-prod-123">
        </div>
      </div>
    `, `
      <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="submitAddMapping('${channelId}')">Add Mapping</button>
    `);
  });
}

async function submitAddMapping(channelId) {
  const itemId = document.getElementById('mapItem').value;
  if (!itemId) { toast('Select an item', 'warning'); return; }

  const result = await apiPost('/channel_mappings', {
    channel_connection_id: channelId,
    nexray_item_id: itemId,
    channel_sku: document.getElementById('mapChannelSku').value.trim() || null,
    channel_product_id: document.getElementById('mapChannelProductId').value.trim() || null
  });

  if (result && result.success) {
    closeModal();
    toast('Product mapping added', 'success');
    loadChannels();
  } else {
    toast(result?.detail || 'Failed to add mapping', 'error');
  }
}

// ===== INVENTORY =====
let _inventoryLots = [];

async function loadInventory() {
  const el = document.getElementById('page-inventory');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(5);
  const data = await api('/inventory');
  if (!data) return;
  _inventoryLots = data.lots || [];

  const totalOnHand = _inventoryLots.reduce((s, l) => s + (l.qty_on_hand || 0), 0);
  const totalAvail = _inventoryLots.reduce((s, l) => s + (l.qty_available || 0), 0);

  el.innerHTML = `
    <div class="page-action-bar">
      <div class="page-action-bar-left">
        <input type="text" class="form-input" id="invSearch" placeholder="Search tracking ID, item, warehouse\u2026" style="min-width:300px" oninput="filterInventory()">
      </div>
      <div class="page-action-bar-right">
        <span style="font-size:var(--text-xs);color:var(--color-text-muted)">${_inventoryLots.length} lots &middot; ${fmtQty(totalOnHand)}m on hand &middot; ${fmtQty(totalAvail)}m available</span>
      </div>
    </div>
    <div class="card">
      <div class="card-header">
        <div><div class="card-title">Lots & Rolls</div><div class="card-subtitle">8-column view, grouped by item with warehouse totals</div></div>
      </div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>Tracking ID</th><th>Item</th><th>On Hand</th><th>Available</th><th>Warehouse</th><th>Location</th><th>Status</th><th>Confidence</th><th></th></tr></thead>
          <tbody id="inv-tbody">
          </tbody>
        </table>
      </div>
    </div>
  `;
  renderInventoryTable(_inventoryLots);
}

function filterInventory() {
  const q = (document.getElementById('invSearch')?.value || '').toLowerCase();
  if (!q) { renderInventoryTable(_inventoryLots); return; }
  const filtered = _inventoryLots.filter(l =>
    (l.tracking_id || '').toLowerCase().includes(q) ||
    (l.item_name || '').toLowerCase().includes(q) ||
    (l.warehouse_code || '').toLowerCase().includes(q) ||
    (l.location_barcode || '').toLowerCase().includes(q)
  );
  renderInventoryTable(filtered);
}

function renderInventoryTable(lots) {
  const tbody = document.getElementById('inv-tbody');
  if (!tbody) return;

  // Group by item
  const groups = {};
  lots.forEach(l => {
    const key = l.item_name || 'Unknown';
    if (!groups[key]) groups[key] = [];
    groups[key].push(l);
  });

  let html = '';
  for (const [itemName, itemLots] of Object.entries(groups)) {
    const groupOnHand = itemLots.reduce((s, l) => s + (l.qty_on_hand || 0), 0);
    const groupAvail = itemLots.reduce((s, l) => s + (l.qty_available || 0), 0);
    html += `<tr class="group-header"><td colspan="9" style="font-weight:600;background:var(--color-bg-subtle);padding:var(--space-2) var(--space-3)">${esc(itemName)} <span style="font-weight:400;font-size:var(--text-xs);color:var(--color-text-muted)">${itemLots.length} lots &middot; ${fmtQty(groupOnHand)}m on hand &middot; ${fmtQty(groupAvail)}m avail</span></td></tr>`;
    for (const l of itemLots) {
      html += `<tr>
        <td>${trackingId(l.tracking_id)}</td>
        <td>${l.item_name || '\u2014'}</td>
        <td style="font-weight:600">${fmtQty(l.qty_on_hand)}</td>
        <td style="font-weight:600;color:var(--color-success)">${fmtQty(l.qty_available)}</td>
        <td>${mono(l.warehouse_code)}</td>
        <td>${l.location_barcode ? `<span class="location-path">${l.location_barcode}</span>` : '\u2014'}</td>
        <td>${badge(l.status)}</td>
        <td>${badge(l.qty_confidence)}</td>
        <td><button class="btn btn-sm btn-ghost" onclick="showMeasureModal('${esc(l.tracking_id)}','${esc(l.item_name || '')}',${l.qty_on_hand || 0})">Measure</button></td>
      </tr>`;
    }
  }
  tbody.innerHTML = html || '<tr><td colspan="9" class="empty-state"><p>No lots found</p></td></tr>';
}

function showMeasureModal(tid, itemName, currentQty) {
  openModal('Manual Measure', `
    <p style="font-size:var(--text-xs);color:var(--color-text-muted)">Tracking ID: <strong>${esc(tid)}</strong> &mdash; ${esc(itemName)}</p>
    <p style="font-size:var(--text-xs);color:var(--color-text-muted)">Current On Hand: <strong>${fmtQty(currentQty)}m</strong></p>
    <div class="form-group" style="margin-top:var(--space-3)">
      <label class="form-label">Measured Quantity *</label>
      <input type="number" class="form-input" id="measureQty" placeholder="0.00" step="0.01" min="0" autofocus>
    </div>
    <div class="form-group">
      <label class="form-label">Notes</label>
      <input type="text" class="form-input" id="measureNotes" placeholder="Optional notes">
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitMeasure('${esc(tid)}')">Update Measurement</button>
  `);
}

async function submitMeasure(tid) {
  const qty = parseFloat(document.getElementById('measureQty').value);
  const notes = document.getElementById('measureNotes').value.trim() || null;
  if (!qty || qty < 0) { toast('Enter a valid measured quantity', 'warning'); return; }

  const result = await apiPost('/inventory/measure', { tracking_id: tid, measured_qty: qty, notes });
  if (result && result.success) {
    closeModal();
    toast(`Measurement updated: ${fmtQty(qty)}m (confidence: measured)`, 'success');
    loadInventory();
  } else {
    toast(result?.detail || 'Measurement failed', 'error');
  }
}

// ===== WAREHOUSES =====
async function loadWarehouses() {
  const el = document.getElementById('page-warehouses');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(3);
  const whData = await api('/warehouses', {  });
  if (!whData) return;

  el.innerHTML = `
    <div class="page-action-bar">
      <div class="page-action-bar-left"></div>
      <div class="page-action-bar-right">
        <button class="btn btn-primary" onclick="showCreateWarehouseModal()">+ New Warehouse</button>
      </div>
    </div>
    <div class="kpi-grid">
      ${whData.warehouses.map(w => `
        <div class="kpi-card">
          <div class="kpi-label">${w.name} ${statusDot(w.is_active)}</div>
          <div class="kpi-value">${w.active_lots} lots</div>
          <div style="font-size:var(--text-xs);color:var(--color-text-muted);margin-top:var(--space-1)">${fmtQty(w.total_stock)}m in stock &middot; ${w.code}</div>
          <div style="margin-top:var(--space-2)">
            <button class="btn btn-sm btn-ghost" onclick="showEditWarehouseModal('${w.id}','${esc(w.name)}','${esc(w.code)}','${esc(w.address || '')}')">Edit</button>
            <button class="btn btn-sm btn-ghost" onclick="loadLocationsForWarehouse('${w.id}','${esc(w.name)}')">View Locations</button>
          </div>
        </div>
      `).join('')}
    </div>
    <div id="warehouse-locations"></div>
  `;

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
        <div><div class="card-title">Locations \u2014 ${esc(whName)}</div><div class="card-subtitle">Rack/bin hierarchy</div></div>
        <button class="btn btn-sm btn-secondary" onclick="showCreateLocationModal('${whId}')">+ Add Location</button>
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

function showCreateWarehouseModal() {
  openModal('New Warehouse', `
    <div class="form-grid">
      <div class="form-group">
        <label class="form-label">Name *</label>
        <input type="text" class="form-input" id="whName" placeholder="Manila Warehouse">
      </div>
      <div class="form-group">
        <label class="form-label">Code *</label>
        <input type="text" class="form-input" id="whCode" placeholder="MNL-01">
      </div>
      <div class="form-group full">
        <label class="form-label">Address</label>
        <input type="text" class="form-input" id="whAddress" placeholder="123 Main St, Manila">
      </div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitCreateWarehouse()">Create</button>
  `);
}

async function submitCreateWarehouse() {
  const name = document.getElementById('whName').value.trim();
  const code = document.getElementById('whCode').value.trim();
  if (!name || !code) { toast('Name and code are required', 'warning'); return; }

  const result = await apiPost('/warehouses', {
        name,
    code,
    address: document.getElementById('whAddress').value.trim() || null
  });

  if (result && result.success) {
    closeModal();
    toast('Warehouse created', 'success');
    loadWarehouses();
  } else {
    toast(result?.detail || 'Failed', 'error');
  }
}

function showEditWarehouseModal(id, name, code, address) {
  openModal('Edit Warehouse', `
    <div class="form-grid">
      <div class="form-group">
        <label class="form-label">Name *</label>
        <input type="text" class="form-input" id="whEditName" value="${esc(name)}">
      </div>
      <div class="form-group">
        <label class="form-label">Code *</label>
        <input type="text" class="form-input" id="whEditCode" value="${esc(code)}">
      </div>
      <div class="form-group full">
        <label class="form-label">Address</label>
        <input type="text" class="form-input" id="whEditAddress" value="${esc(address)}">
      </div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitEditWarehouse('${id}')">Save</button>
  `);
}

async function submitEditWarehouse(id) {
  const result = await apiPut(`/warehouses/${id}`, {
    name: document.getElementById('whEditName').value.trim(),
    code: document.getElementById('whEditCode').value.trim(),
    address: document.getElementById('whEditAddress').value.trim() || null
  });
  if (result && result.success) {
    closeModal();
    toast('Warehouse updated', 'success');
    loadWarehouses();
  } else {
    toast(result?.detail || 'Failed', 'error');
  }
}

function showCreateLocationModal(warehouseId) {
  openModal('New Location', `
    <div class="form-grid">
      <div class="form-group">
        <label class="form-label">Rack Code *</label>
        <input type="text" class="form-input" id="locRack" placeholder="R01">
      </div>
      <div class="form-group">
        <label class="form-label">Location Barcode</label>
        <input type="text" class="form-input" id="locBarcode" placeholder="MNL-A1-R01-1-B01">
      </div>
      <div class="form-group">
        <label class="form-label">Zone</label>
        <input type="text" class="form-input" id="locZone" placeholder="A">
      </div>
      <div class="form-group">
        <label class="form-label">Aisle</label>
        <input type="text" class="form-input" id="locAisle" placeholder="1">
      </div>
      <div class="form-group">
        <label class="form-label">Level</label>
        <input type="text" class="form-input" id="locLevel" placeholder="1">
      </div>
      <div class="form-group">
        <label class="form-label">Type</label>
        <select class="form-select" id="locType">
          <option value="rack">Rack</option>
          <option value="bin">Bin</option>
          <option value="staging">Staging</option>
          <option value="dispatch">Dispatch</option>
          <option value="overflow">Overflow</option>
        </select>
      </div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitCreateLocation('${warehouseId}')">Create</button>
  `);
}

async function submitCreateLocation(warehouseId) {
  const rack = document.getElementById('locRack').value.trim();
  if (!rack) { toast('Rack code required', 'warning'); return; }

  const result = await apiPost('/locations', {
    warehouse_id: warehouseId,
    rack_code: rack,
    location_barcode: document.getElementById('locBarcode').value.trim() || null,
    zone_code: document.getElementById('locZone').value.trim() || null,
    aisle_code: document.getElementById('locAisle').value.trim() || null,
    level_code: document.getElementById('locLevel').value.trim() || null,
    location_type: document.getElementById('locType').value
  });

  if (result && result.success) {
    closeModal();
    toast('Location created', 'success');
    loadWarehouses();
  } else {
    toast(result?.detail || 'Failed', 'error');
  }
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
              <td>${mono(m.id.substring(0, 8))}</td>
              <td><span class="movement-type ${m.movement_type}">${m.movement_type}</span></td>
              <td>${m.item_name || '\u2014'}</td>
              <td>${trackingId(m.lot_tracking || m.tracking_id)}</td>
              <td>${qtyDelta(m.qty_delta)}</td>
              <td>${fmtQty(m.qty_before)}</td>
              <td>${fmtQty(m.qty_after)}</td>
              <td>${m.reason_code || '\u2014'}</td>
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

// ===== PUTAWAY =====
async function loadPutaway() {
  const el = document.getElementById('page-putaway');

  // Load all locations across all warehouses
  const locData = await api('/locations');
  const locs = locData ? locData.locations : [];

  el.innerHTML = `
    <div class="card" style="margin-bottom:var(--space-6)">
      <div class="card-header">
        <div><div class="card-title">Putaway Lot</div><div class="card-subtitle">Scan tracking ID and assign to a storage location</div></div>
      </div>
      <div style="padding:var(--space-5)">
        <div class="putaway-form-wrap">
          <div class="form-group">
            <label class="form-label">Tracking ID (scan or type) *</label>
            <input type="text" class="form-input" id="putawayTrackingId" placeholder="Scan barcode or type tracking ID" autofocus>
          </div>
          <div class="form-group">
            <label class="form-label">Target Location *</label>
            <select class="form-select" id="putawayLoc">
              <option value="">Select location\u2026</option>
              ${locs.map(l => `<option value="${l.id}">${esc(l.location_barcode || l.rack_code)} \u2014 ${l.lot_count} lots</option>`).join('')}
            </select>
          </div>
          <div class="form-group" style="display:flex;align-items:flex-end">
            <button class="btn btn-primary" onclick="submitPutaway()" style="width:100%;justify-content:center">Execute Putaway</button>
          </div>
        </div>
        <div id="putawayResult"></div>
      </div>
    </div>
  `;
}

async function submitPutaway() {
  const tid = document.getElementById('putawayTrackingId').value.trim();
  const locationId = document.getElementById('putawayLoc').value;
  const resultEl = document.getElementById('putawayResult');

  if (!tid) { toast('Enter or scan a tracking ID', 'warning'); return; }
  if (!locationId) { toast('Select a target location', 'warning'); return; }

  const result = await apiPost('/putaway', { tracking_id: tid, location_id: locationId });
  if (result && result.success) {
    resultEl.innerHTML = `<div class="result-banner success" style="margin-top:var(--space-4)">Putaway complete \u2014 lot moved successfully.</div>`;
    toast('Putaway completed', 'success');
    document.getElementById('putawayTrackingId').value = '';
    document.getElementById('putawayTrackingId').focus();
  } else {
    resultEl.innerHTML = `<div class="result-banner error" style="margin-top:var(--space-4)">${esc(result?.detail || 'Putaway failed')}</div>`;
    toast(result?.detail || 'Putaway failed', 'error');
  }
}

// ===== ADJUSTMENTS / APPROVALS =====
async function loadAdjustments() {
  const el = document.getElementById('page-adjustments');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(3);
  const data = await api('/adjustments');
  if (!data) return;

  el.innerHTML = `
    <div class="page-action-bar">
      <div class="page-action-bar-left">
        <div class="tab-bar">
          <button class="tab-btn active" onclick="filterAdj('all',this)">All</button>
          <button class="tab-btn" onclick="filterAdj('pending',this)">Pending</button>
          <button class="tab-btn" onclick="filterAdj('approved',this)">Approved</button>
          <button class="tab-btn" onclick="filterAdj('rejected',this)">Rejected</button>
        </div>
      </div>
      <div class="page-action-bar-right">
        <button class="btn btn-secondary" onclick="showWriteOffModal()">Write-Off</button>
        <button class="btn btn-secondary" onclick="showSplitRollModal()">Split Roll</button>
      </div>
    </div>
    <div class="card">
      <div class="card-header">
        <div><div class="card-title">Adjustment Requests</div><div class="card-subtitle">Write-offs, split rolls, and approval-gated controls</div></div>
      </div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>ID</th><th>Type</th><th>Qty Before</th><th>Qty After</th><th>Reason</th><th>Notes</th><th>Status</th><th>Requested By</th><th>Approved By</th><th>Actions</th></tr></thead>
          <tbody id="adj-tbody">
            ${data.adjustments.map(a => `<tr data-status="${a.status}">
              <td>${mono(a.id.substring(0, 8))}</td>
              <td>${badge(a.adjustment_type)}</td>
              <td>${fmtQty(a.qty_before)}</td>
              <td>${fmtQty(a.qty_after)}</td>
              <td>${mono(a.reason_code)}</td>
              <td style="max-width:200px;font-size:11px">${a.notes || '\u2014'}</td>
              <td>${badge(a.status)}</td>
              <td>${mono(a.requested_by)}</td>
              <td>${mono(a.approved_by || '\u2014')}</td>
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

async function approveAdj(id) {
  const result = await apiPost('/approve_adjustment', { id });
  if (result && result.success) {
    toast('Adjustment approved', 'success');
    loadAdjustments();
  } else {
    toast('Failed to approve', 'error');
  }
}

async function rejectAdj(id) {
  const result = await apiPost('/reject_adjustment', { id });
  if (result && result.success) {
    toast('Adjustment rejected', 'warning');
    loadAdjustments();
  } else {
    toast('Failed to reject', 'error');
  }
}

// ===== FINDINGS =====
async function loadFindings() {
  const el = document.getElementById('page-findings');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(3);
  const data = await api('/findings');
  if (!data) return;

  el.innerHTML = `
    <div class="page-action-bar">
      <div class="page-action-bar-left">
        <div class="tab-bar">
          <button class="tab-btn active" onclick="filterFindings('all',this)">All</button>
          <button class="tab-btn" onclick="filterFindings('open',this)">Open</button>
          <button class="tab-btn" onclick="filterFindings('resolved',this)">Resolved</button>
        </div>
      </div>
      <div class="page-action-bar-right">
        <button class="btn btn-secondary" onclick="runReconciliationFromFindings()">Run Reconciliation</button>
      </div>
    </div>
    <div id="reconResult"></div>
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
              <td style="max-width:350px;font-size:11px">${f.description || '\u2014'}</td>
              <td>${mono(f.resource_type ? f.resource_type + ':' + (f.resource_id || '').substring(0, 8) : '\u2014')}</td>
              <td>${badge(f.resolution_status)}</td>
              <td>${mono(f.resolved_by || '\u2014')}</td>
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

async function resolveFinding(id) {
  const result = await apiPost('/resolve_finding', { id });
  if (result && result.success) {
    toast('Finding resolved', 'success');
    loadFindings();
  }
}

async function runReconciliationFromFindings() {
  const btn = event.target;
  btn.disabled = true;
  btn.textContent = 'Running\u2026';
  const result = await apiPost('/reconciliation/run', { run_type: 'manual' });
  btn.disabled = false;
  btn.textContent = 'Run Reconciliation';
  const resEl = document.getElementById('reconResult');
  if (result && result.success) {
    if (resEl) resEl.innerHTML = `<div class="result-banner ${result.findings_count > 0 ? 'warning' : 'success'}">Reconciliation complete: ${result.findings_count} finding(s) found</div>`;
    loadFindings();
  } else {
    if (resEl) resEl.innerHTML = '<div class="result-banner error">Reconciliation failed</div>';
  }
}

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
        <div class="info-row"><span class="label">Last Sync</span><span class="value">\u2014</span></div>
      </div>
      <div class="info-card">
        <h4>Integration Health</h4>
        <div class="info-row"><span class="label">Pending Events</span><span class="value">${data.events.filter(e => e.status === 'pending').length}</span></div>
        <div class="info-row"><span class="label">Applied</span><span class="value">${data.events.filter(e => e.status === 'applied').length}</span></div>
        <div class="info-row"><span class="label">Failed</span><span class="value">${data.events.filter(e => e.status === 'failed').length}</span></div>
        <div class="info-row"><span class="label">Dead Letter</span><span class="value">${data.events.filter(e => e.status === 'dead_letter').length}</span></div>
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
              <td>${mono(e.id.substring(0, 8))}</td>
              <td>${mono(e.event_type)}</td>
              <td>${badge(e.direction)}</td>
              <td>${badge(e.status)}</td>
              <td>${e.retry_count}</td>
              <td style="max-width:200px;font-size:11px">${e.error_message || '\u2014'}</td>
              <td>${fmtDate(e.created_at)}</td>
              <td>${e.processed_at ? fmtDate(e.processed_at) : '\u2014'}</td>
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

async function retryIntegration(id) {
  const result = await apiPost('/retry_integration', { id });
  if (result && result.success) {
    toast('Integration event queued for retry', 'info');
    loadIntegrations();
  }
}

// ===== ITEMS =====
async function loadItems() {
  const el = document.getElementById('page-items');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(3);
  const data = await api('/items');
  if (!data) return;

  el.innerHTML = `
    <div class="page-action-bar">
      <div class="page-action-bar-left"><span style="font-size:var(--text-xs);color:var(--color-text-muted)">${data.items.length} items</span></div>
      <div class="page-action-bar-right">
        <button class="btn btn-primary" onclick="showCreateItemModal()">+ New Item</button>
      </div>
    </div>
    <div class="card">
      <div class="card-header">
        <div><div class="card-title">Items</div><div class="card-subtitle">Master item catalog</div></div>
      </div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>SKU</th><th>Name</th><th>Type</th><th>UOM</th><th>Category</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody>
            ${data.items.map(i => `<tr>
              <td>${mono(i.sku)}</td>
              <td style="font-weight:500">${i.name}</td>
              <td>${badge(i.item_type)}</td>
              <td>${i.base_uom || '\u2014'}</td>
              <td>${i.category || '\u2014'}</td>
              <td>${statusDot(i.is_active)} ${i.is_active ? 'Active' : 'Inactive'}</td>
              <td>
                <button class="btn btn-sm btn-ghost" onclick="showEditItemModal('${i.id}','${esc(i.sku)}','${esc(i.name)}','${i.item_type}','${i.base_uom || 'meter'}','${esc(i.category || '')}')">Edit</button>
              </td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function showCreateItemModal() {
  openModal('New Item', `
    <div class="form-grid">
      <div class="form-group">
        <label class="form-label">SKU *</label>
        <input type="text" class="form-input" id="itmSku" placeholder="FAB-BLK-001">
      </div>
      <div class="form-group">
        <label class="form-label">Name *</label>
        <input type="text" class="form-input" id="itmName" placeholder="Blackout Fabric - Ivory">
      </div>
      <div class="form-group">
        <label class="form-label">Item Type *</label>
        <select class="form-select" id="itmType">
          <option value="fabric">Fabric</option>
          <option value="component">Component</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Base UOM</label>
        <select class="form-select" id="itmUom">
          <option value="meter">Meter</option>
          <option value="piece">Piece</option>
          <option value="pack">Pack</option>
          <option value="pair">Pair</option>
          <option value="yard">Yard</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Category</label>
        <input type="text" class="form-input" id="itmCategory" placeholder="Curtains">
      </div>
      <div class="form-group full">
        <label class="form-label">Description</label>
        <textarea class="form-textarea" id="itmDesc" placeholder="Optional description" rows="2"></textarea>
      </div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitCreateItem()">Create Item</button>
  `);
}

async function submitCreateItem() {
  const sku = document.getElementById('itmSku').value.trim();
  const name = document.getElementById('itmName').value.trim();
  if (!sku || !name) { toast('SKU and name are required', 'warning'); return; }

  const result = await apiPost('/items', {
        sku,
    name,
    item_type: document.getElementById('itmType').value,
    base_uom: document.getElementById('itmUom').value,
    category: document.getElementById('itmCategory').value.trim() || null,
    description: document.getElementById('itmDesc').value.trim() || null
  });

  if (result && result.success) {
    closeModal();
    toast('Item created', 'success');
    loadItems();
  } else {
    toast(result?.detail || 'Failed to create item', 'error');
  }
}

function showEditItemModal(id, sku, name, type, uom, category) {
  openModal('Edit Item', `
    <div class="form-grid">
      <div class="form-group">
        <label class="form-label">SKU *</label>
        <input type="text" class="form-input" id="itmEditSku" value="${esc(sku)}">
      </div>
      <div class="form-group">
        <label class="form-label">Name *</label>
        <input type="text" class="form-input" id="itmEditName" value="${esc(name)}">
      </div>
      <div class="form-group">
        <label class="form-label">Item Type *</label>
        <select class="form-select" id="itmEditType">
          <option value="fabric" ${type === 'fabric' ? 'selected' : ''}>Fabric</option>
          <option value="component" ${type === 'component' ? 'selected' : ''}>Component</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Base UOM</label>
        <select class="form-select" id="itmEditUom">
          <option value="meter" ${uom === 'meter' ? 'selected' : ''}>Meter</option>
          <option value="piece" ${uom === 'piece' ? 'selected' : ''}>Piece</option>
          <option value="pack" ${uom === 'pack' ? 'selected' : ''}>Pack</option>
          <option value="pair" ${uom === 'pair' ? 'selected' : ''}>Pair</option>
          <option value="yard" ${uom === 'yard' ? 'selected' : ''}>Yard</option>
        </select>
      </div>
      <div class="form-group full">
        <label class="form-label">Category</label>
        <input type="text" class="form-input" id="itmEditCategory" value="${esc(category)}">
      </div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitEditItem('${id}')">Save</button>
  `);
}

async function submitEditItem(id) {
  const result = await apiPut(`/items/${id}`, {
    sku: document.getElementById('itmEditSku').value.trim(),
    name: document.getElementById('itmEditName').value.trim(),
    item_type: document.getElementById('itmEditType').value,
    base_uom: document.getElementById('itmEditUom').value,
    category: document.getElementById('itmEditCategory').value.trim() || null
  });

  if (result && result.success) {
    closeModal();
    toast('Item updated', 'success');
    loadItems();
  } else {
    toast(result?.detail || 'Failed', 'error');
  }
}

// ===== SUPPLIERS =====
async function loadSuppliers() {
  const el = document.getElementById('page-suppliers');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(3);
  const data = await api('/suppliers');
  if (!data) return;

  el.innerHTML = `
    <div class="page-action-bar">
      <div class="page-action-bar-left"><span style="font-size:var(--text-xs);color:var(--color-text-muted)">${data.suppliers.length} suppliers</span></div>
      <div class="page-action-bar-right">
        <button class="btn btn-primary" onclick="showCreateSupplierModal()">+ New Supplier</button>
      </div>
    </div>
    <div class="card">
      <div class="card-header">
        <div><div class="card-title">Suppliers</div><div class="card-subtitle">Supplier master list</div></div>
      </div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>Code</th><th>Name</th><th>Contact</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody>
            ${data.suppliers.map(s => `<tr>
              <td>${mono(s.code)}</td>
              <td style="font-weight:500">${esc(s.name)}</td>
              <td style="font-size:11px">${s.contact_info || '\u2014'}</td>
              <td>${statusDot(s.is_active)} ${s.is_active ? 'Active' : 'Inactive'}</td>
              <td>
                <button class="btn btn-sm btn-ghost" onclick="showEditSupplierModal('${s.id}','${esc(s.name)}','${esc(s.code || '')}','${esc(s.contact_info || '')}')">Edit</button>
              </td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function showCreateSupplierModal() {
  openModal('New Supplier', `
    <div class="form-grid">
      <div class="form-group">
        <label class="form-label">Name *</label>
        <input type="text" class="form-input" id="supName" placeholder="Guangzhou Textile Co.">
      </div>
      <div class="form-group">
        <label class="form-label">Code</label>
        <input type="text" class="form-input" id="supCode" placeholder="GZ-TEX">
      </div>
      <div class="form-group full">
        <label class="form-label">Contact Info</label>
        <input type="text" class="form-input" id="supContact" placeholder="contact@supplier.com / +86-\u2026">
      </div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitCreateSupplier()">Create</button>
  `);
}

async function submitCreateSupplier() {
  const name = document.getElementById('supName').value.trim();
  if (!name) { toast('Name is required', 'warning'); return; }

  const result = await apiPost('/suppliers', {
        name,
    code: document.getElementById('supCode').value.trim() || null,
    contact_info: document.getElementById('supContact').value.trim() || null
  });

  if (result && result.success) {
    closeModal();
    toast('Supplier created', 'success');
    loadSuppliers();
  } else {
    toast(result?.detail || 'Failed', 'error');
  }
}

function showEditSupplierModal(id, name, code, contact) {
  openModal('Edit Supplier', `
    <div class="form-grid">
      <div class="form-group">
        <label class="form-label">Name *</label>
        <input type="text" class="form-input" id="supEditName" value="${esc(name)}">
      </div>
      <div class="form-group">
        <label class="form-label">Code</label>
        <input type="text" class="form-input" id="supEditCode" value="${esc(code)}">
      </div>
      <div class="form-group full">
        <label class="form-label">Contact Info</label>
        <input type="text" class="form-input" id="supEditContact" value="${esc(contact)}">
      </div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitEditSupplier('${id}')">Save</button>
  `);
}

async function submitEditSupplier(id) {
  const result = await apiPut(`/suppliers/${id}`, {
    name: document.getElementById('supEditName').value.trim(),
    code: document.getElementById('supEditCode').value.trim() || null,
    contact_info: document.getElementById('supEditContact').value.trim() || null
  });

  if (result && result.success) {
    closeModal();
    toast('Supplier updated', 'success');
    loadSuppliers();
  } else {
    toast(result?.detail || 'Failed', 'error');
  }
}

// ===== CUSTOMERS =====
async function loadCustomers() {
  const el = document.getElementById('page-customers');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(3);
  const data = await api('/customers');
  if (!data) return;

  el.innerHTML = `
    <div class="page-action-bar">
      <div class="page-action-bar-left"><span style="font-size:var(--text-xs);color:var(--color-text-muted)">${data.customers.length} customers</span></div>
      <div class="page-action-bar-right">
        <button class="btn btn-primary" onclick="showCreateCustomerModal()">+ New Customer</button>
      </div>
    </div>
    <div class="card">
      <div class="card-header">
        <div><div class="card-title">Customers</div><div class="card-subtitle">Customer master list</div></div>
      </div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>Code</th><th>Name</th><th>Contact</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody>
            ${data.customers.map(c => `<tr>
              <td>${mono(c.code)}</td>
              <td style="font-weight:500">${esc(c.name)}</td>
              <td style="font-size:11px">${c.contact_info || '\u2014'}</td>
              <td>${statusDot(c.is_active)} ${c.is_active ? 'Active' : 'Inactive'}</td>
              <td>
                <button class="btn btn-sm btn-ghost" onclick="showEditCustomerModal('${c.id}','${esc(c.name)}','${esc(c.code || '')}','${esc(c.contact_info || '')}')">Edit</button>
              </td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function showCreateCustomerModal() {
  openModal('New Customer', `
    <div class="form-grid">
      <div class="form-group">
        <label class="form-label">Name *</label>
        <input type="text" class="form-input" id="custName" placeholder="InterContinental Hotels">
      </div>
      <div class="form-group">
        <label class="form-label">Code</label>
        <input type="text" class="form-input" id="custCode" placeholder="ICH">
      </div>
      <div class="form-group full">
        <label class="form-label">Contact Info</label>
        <input type="text" class="form-input" id="custContact" placeholder="contact@customer.com / +63-\u2026">
      </div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitCreateCustomer()">Create</button>
  `);
}

async function submitCreateCustomer() {
  const name = document.getElementById('custName').value.trim();
  if (!name) { toast('Name is required', 'warning'); return; }

  const result = await apiPost('/customers', {
        name,
    code: document.getElementById('custCode').value.trim() || null,
    contact_info: document.getElementById('custContact').value.trim() || null
  });

  if (result && result.success) {
    closeModal();
    toast('Customer created', 'success');
    loadCustomers();
  } else {
    toast(result?.detail || 'Failed', 'error');
  }
}

function showEditCustomerModal(id, name, code, contact) {
  openModal('Edit Customer', `
    <div class="form-grid">
      <div class="form-group">
        <label class="form-label">Name *</label>
        <input type="text" class="form-input" id="custEditName" value="${esc(name)}">
      </div>
      <div class="form-group">
        <label class="form-label">Code</label>
        <input type="text" class="form-input" id="custEditCode" value="${esc(code)}">
      </div>
      <div class="form-group full">
        <label class="form-label">Contact Info</label>
        <input type="text" class="form-input" id="custEditContact" value="${esc(contact)}">
      </div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitEditCustomer('${id}')">Save</button>
  `);
}

async function submitEditCustomer(id) {
  const result = await apiPut(`/customers/${id}`, {
    name: document.getElementById('custEditName').value.trim(),
    code: document.getElementById('custEditCode').value.trim() || null,
    contact_info: document.getElementById('custEditContact').value.trim() || null
  });

  if (result && result.success) {
    closeModal();
    toast('Customer updated', 'success');
    loadCustomers();
  } else {
    toast(result?.detail || 'Failed', 'error');
  }
}

// ===== USERS & RBAC =====
async function loadUsers() {
  const el = document.getElementById('page-users');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(3);
  const data = await api('/users');
  if (!data) return;

  const roleMap = {
    system_admin:        { label: 'System Admin', desc: 'Full access, config, users, integrations' },
    inventory_admin:     { label: 'Inventory Admin', desc: 'Receiving, putaway, adjustments, cycle counts' },
    warehouse_operator:  { label: 'Warehouse Operator', desc: 'Pick, cut, scan, print within warehouse' },
    warehouse_lead:      { label: 'Warehouse Lead', desc: 'Approve variances, unlock lines, reprint' },
    manager:             { label: 'Manager', desc: 'Dashboards, reconciliation, high-level approvals' },
    accounting_operator: { label: 'Accounting / QBD', desc: 'Manage QBD sync, mapping approvals' },
  };

  const isAdmin = currentUser && currentUser.role === 'system_admin';

  el.innerHTML = `
    <div class="page-action-bar">
      <div class="page-action-bar-left"></div>
      <div class="page-action-bar-right">
        ${isAdmin ? `<button class="btn btn-primary" onclick="showCreateUserModal()">+ Create User</button>` : ''}
      </div>
    </div>
    <div class="detail-grid">
      <div class="info-card">
        <h4>RBAC Summary</h4>
        ${Object.entries(roleMap).map(([k, v]) => `
          <div class="info-row"><span class="label">${v.label}</span><span class="value">${data.users.filter(u => u.role === k).length}</span></div>
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
          <thead><tr><th>User</th><th>Username</th><th>Email</th><th>Role</th><th>Warehouse</th><th>Status</th>${isAdmin ? '<th>Actions</th>' : ''}</tr></thead>
          <tbody>
            ${data.users.map(u => `<tr>
              <td style="font-weight:500">${esc(u.display_name)}</td>
              <td>${mono(u.username)}</td>
              <td style="font-size:11px">${u.email || '\u2014'}</td>
              <td>${badge(u.role)}</td>
              <td>${u.warehouse_name || 'All'}</td>
              <td>${statusDot(u.is_active)} ${u.is_active ? 'Active' : 'Inactive'}</td>
              ${isAdmin ? `<td><button class="btn btn-sm btn-ghost" onclick="showEditUserModal('${u.id}','${esc(u.display_name)}','${esc(u.email || '')}','${u.role}')">Edit</button></td>` : ''}
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function showCreateUserModal() {
  const roles = ['system_admin','inventory_admin','warehouse_lead','warehouse_operator','manager','accounting_operator'];
  openModal('Create User', `
    <div class="form-grid">
      <div class="form-group">
        <label class="form-label">Username *</label>
        <input type="text" class="form-input" id="newUsername" placeholder="jsmith">
      </div>
      <div class="form-group">
        <label class="form-label">Display Name *</label>
        <input type="text" class="form-input" id="newDisplayName" placeholder="John Smith">
      </div>
      <div class="form-group">
        <label class="form-label">Email</label>
        <input type="email" class="form-input" id="newEmail" placeholder="jsmith@nexray.local">
      </div>
      <div class="form-group">
        <label class="form-label">Role *</label>
        <select class="form-select" id="newRole">
          ${roles.map(r => `<option value="${r}">${r.replace(/_/g,' ')}</option>`).join('')}
        </select>
      </div>
    </div>
    <div class="result-banner info" style="margin-top:0">Default password is the username. User should change on first login.</div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitCreateUser()">Create User</button>
  `);
}

async function submitCreateUser() {
  const username = document.getElementById('newUsername').value.trim();
  const displayName = document.getElementById('newDisplayName').value.trim();
  if (!username || !displayName) { toast('Username and display name required', 'warning'); return; }

  const result = await apiPost('/users', {
    username,
    display_name: displayName,
    email: document.getElementById('newEmail').value.trim() || null,
    role: document.getElementById('newRole').value
  });

  if (result && result.success) {
    closeModal();
    toast(`User created: ${username}`, 'success');
    loadUsers();
  } else {
    toast(result?.detail || 'Failed to create user', 'error');
  }
}

function showEditUserModal(id, displayName, email, role) {
  const roles = ['system_admin','inventory_admin','warehouse_lead','warehouse_operator','manager','accounting_operator'];
  openModal('Edit User', `
    <div class="form-grid">
      <div class="form-group">
        <label class="form-label">Display Name *</label>
        <input type="text" class="form-input" id="editDisplayName" value="${esc(displayName)}">
      </div>
      <div class="form-group">
        <label class="form-label">Email</label>
        <input type="email" class="form-input" id="editEmail" value="${esc(email)}">
      </div>
      <div class="form-group">
        <label class="form-label">Role *</label>
        <select class="form-select" id="editRole">
          ${roles.map(r => `<option value="${r}" ${r === role ? 'selected' : ''}>${r.replace(/_/g,' ')}</option>`).join('')}
        </select>
      </div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitEditUser('${id}')">Save</button>
  `);
}

async function submitEditUser(id) {
  const result = await apiPut(`/users/${id}`, {
    display_name: document.getElementById('editDisplayName').value.trim(),
    email: document.getElementById('editEmail').value.trim() || null,
    role: document.getElementById('editRole').value
  });

  if (result && result.success) {
    closeModal();
    toast('User updated', 'success');
    loadUsers();
  } else {
    toast(result?.detail || 'Failed', 'error');
  }
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
        <div><div class="card-title">Audit Trail</div><div class="card-subtitle">Who, what, when, why \u2014 for all operationally material events</div></div>
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
              <td>${mono(l.object_id ? l.object_id.substring(0, 8) : '\u2014')}</td>
              <td style="font-size:11px">${l.reason_code || '\u2014'}</td>
              <td>${badge(l.source_channel || 'web')}</td>
            </tr>`).join('') : '<tr><td colspan="7" style="text-align:center;padding:var(--space-8);color:var(--color-text-faint)">No audit log entries yet.</td></tr>'}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// ===== ORDER DETAIL =====
async function showOrderDetail(solId) {
  const [order, linesData] = await Promise.all([
    api(`/supplier_orders/${solId}`),
    api(`/supplier_orders/${solId}/lines`)
  ]);
  if (!order) return;
  const lines = linesData ? linesData.lines : [];

  openModal(`Order: ${esc(order.batch_code)}`, `
    <div class="detail-grid" style="margin-bottom:var(--space-4)">
      <div class="info-card">
        <div class="info-row"><span class="label">Supplier</span><span class="value">${esc(order.supplier_name || '\u2014')}</span></div>
        <div class="info-row"><span class="label">Status</span><span class="value">${badge(order.status)}</span></div>
        <div class="info-row"><span class="label">Created</span><span class="value">${fmtDate(order.created_at)}</span></div>
        <div class="info-row"><span class="label">Notes</span><span class="value">${esc(order.notes || '\u2014')}</span></div>
      </div>
    </div>
    <div class="table-wrapper">
      <table>
        <thead><tr><th>Line</th><th>Item</th><th>Qty Expected</th><th>UOM</th><th>Status</th><th>Error</th></tr></thead>
        <tbody>
          ${lines.map((l, i) => `<tr>
            <td>${i + 1}</td>
            <td>${esc(l.item_name || l.item_name_raw || '\u2014')}</td>
            <td>${fmtQty(l.qty_expected)}</td>
            <td>${l.uom || '\u2014'}</td>
            <td>${badge(l.status || 'pending')}</td>
            <td style="font-size:11px;color:var(--color-error)">${esc(l.error_message || '')}</td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Close</button>
    ${order.status === 'draft' ? `<button class="btn btn-primary" onclick="closeModal();showEditOrderModal('${solId}')">Edit Order</button>` : ''}
  `, 'modal-lg');
}

async function showEditOrderModal(solId) {
  const order = await api(`/supplier_orders/${solId}`);
  if (!order) return;

  openModal(`Edit Order: ${esc(order.batch_code)}`, `
    <div class="form-grid">
      <div class="form-group">
        <label class="form-label">Batch Code</label>
        <input type="text" class="form-input" id="editSolBatch" value="${esc(order.batch_code)}">
      </div>
      <div class="form-group">
        <label class="form-label">Notes</label>
        <input type="text" class="form-input" id="editSolNotes" value="${esc(order.notes || '')}">
      </div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitEditOrder('${solId}')">Save</button>
  `);
}

async function submitEditOrder(solId) {
  const result = await apiPut(`/supplier_orders/${solId}`, {
    batch_code: document.getElementById('editSolBatch').value.trim(),
    notes: document.getElementById('editSolNotes').value.trim() || null
  });
  if (result && result.success) {
    closeModal();
    toast('Order updated', 'success');
    loadInbound();
  } else {
    toast(result?.detail || 'Update failed', 'error');
  }
}

// ===== EXCEL IMPORT =====
function showExcelImportModal() {
  openModal('Import Supplier Order (Excel/CSV)', `
    <div class="form-group">
      <label class="form-label">Upload Excel or CSV file</label>
      <input type="file" class="form-input" id="excelFile" accept=".xlsx,.xls,.csv">
    </div>
    <div class="result-banner info" style="margin-top:var(--space-2)">
      Expected columns: Item (name or SKU), Qty Expected, UOM, Lot Info (optional), Shade (optional)
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitExcelImport()">Import</button>
  `);
}

async function submitExcelImport() {
  const fileInput = document.getElementById('excelFile');
  if (!fileInput.files.length) { toast('Select a file', 'warning'); return; }

  const formData = new FormData();
  formData.append('file', fileInput.files[0]);

  try {
    const res = await fetch(`${API}/supplier_orders/import`, {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + (getToken() || '') },
      body: formData
    });
    if (res.status === 401) { showLogin(); return; }
    const result = await res.json();
    if (res.ok && result.success) {
      closeModal();
      toast(`Imported: ${result.batch_code} (${result.total_lines} lines, ${result.error_count} errors)`,
        result.error_count > 0 ? 'warning' : 'success');
      loadInbound();
    } else {
      toast(result?.detail || 'Import failed', 'error');
    }
  } catch (e) {
    toast('Import error: ' + (e.message || 'Network error'), 'error');
  }
}

// ===== WRITE-OFF =====
function showWriteOffModal() {
  openModal('Write-Off (Perpendicular Damage)', `
    <div class="form-group">
      <label class="form-label">Tracking ID (scan or type) *</label>
      <input type="text" class="form-input" id="woTrackingId" placeholder="Scan barcode" autofocus>
    </div>
    <div class="form-group">
      <label class="form-label">Reason *</label>
      <input type="text" class="form-input" id="woReason" placeholder="e.g. perpendicular damage, water stain">
    </div>
    <div class="form-group">
      <label class="form-label">Notes</label>
      <input type="text" class="form-input" id="woNotes" placeholder="Optional details">
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-error" onclick="submitWriteOff()">Write Off Lot</button>
  `);
}

async function submitWriteOff() {
  const tid = document.getElementById('woTrackingId').value.trim();
  const reason = document.getElementById('woReason').value.trim();
  const notes = document.getElementById('woNotes').value.trim() || null;

  if (!tid) { toast('Enter a tracking ID', 'warning'); return; }
  if (!reason) { toast('Provide a reason', 'warning'); return; }

  const result = await apiPost('/adjustments', {
    tracking_id: tid,
    adjustment_type: 'write_off',
    reason_code: reason,
    notes
  });
  if (result && result.success) {
    closeModal();
    toast('Write-off submitted for approval', 'success');
    loadAdjustments();
  } else {
    toast(result?.detail || 'Write-off failed', 'error');
  }
}

// ===== SPLIT ROLL =====
function showSplitRollModal() {
  openModal('Split Roll (Parallel Damage)', `
    <div class="form-group">
      <label class="form-label">Tracking ID (scan or type) *</label>
      <input type="text" class="form-input" id="srTrackingId" placeholder="Scan barcode" autofocus>
    </div>
    <div class="form-grid">
      <div class="form-group">
        <label class="form-label">Keep Qty (good portion) *</label>
        <input type="number" class="form-input" id="srKeepQty" placeholder="0.00" step="0.01" min="0">
      </div>
      <div class="form-group">
        <label class="form-label">Split Qty (damaged portion) *</label>
        <input type="number" class="form-input" id="srSplitQty" placeholder="0.00" step="0.01" min="0">
      </div>
    </div>
    <div class="form-group">
      <label class="form-label">Reason *</label>
      <input type="text" class="form-input" id="srReason" placeholder="e.g. parallel damage, tear">
    </div>
    <div class="form-group">
      <label class="form-label">Notes</label>
      <input type="text" class="form-input" id="srNotes" placeholder="Optional details">
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitSplitRoll()">Split Roll</button>
  `);
}

async function submitSplitRoll() {
  const tid = document.getElementById('srTrackingId').value.trim();
  const keepQty = parseFloat(document.getElementById('srKeepQty').value);
  const splitQty = parseFloat(document.getElementById('srSplitQty').value);
  const reason = document.getElementById('srReason').value.trim();
  const notes = document.getElementById('srNotes').value.trim() || null;

  if (!tid) { toast('Enter a tracking ID', 'warning'); return; }
  if (!keepQty || keepQty <= 0) { toast('Enter a valid keep qty', 'warning'); return; }
  if (!splitQty || splitQty <= 0) { toast('Enter a valid split qty', 'warning'); return; }
  if (!reason) { toast('Provide a reason', 'warning'); return; }

  const result = await apiPost('/adjustments', {
    tracking_id: tid,
    adjustment_type: 'split_roll',
    keep_qty: keepQty,
    split_qty: splitQty,
    reason_code: reason,
    notes
  });
  if (result && result.success) {
    closeModal();
    toast(`Split roll submitted. New tracking ID: ${result.new_tracking_id || 'pending approval'}`, 'success');
    loadAdjustments();
  } else {
    toast(result?.detail || 'Split roll failed', 'error');
  }
}

// ===== RESERVATIONS =====
async function loadReservations() {
  const el = document.getElementById('page-reservations');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(3);
  const data = await api('/reservations');
  if (!data) return;
  const reservations = data.reservations || [];

  el.innerHTML = `
    <div class="page-action-bar">
      <div class="page-action-bar-left">
        <div class="tab-bar">
          <button class="tab-btn active" onclick="filterRes('all',this)">All</button>
          <button class="tab-btn" onclick="filterRes('pending_approval',this)">Pending</button>
          <button class="tab-btn" onclick="filterRes('approved',this)">Approved</button>
          <button class="tab-btn" onclick="filterRes('rejected',this)">Rejected</button>
        </div>
      </div>
      <div class="page-action-bar-right">
        <button class="btn btn-primary" onclick="showCreateReservationModal()">+ New Reservation</button>
      </div>
    </div>
    <div class="card">
      <div class="card-header">
        <div><div class="card-title">Reservations</div><div class="card-subtitle">Manual reservation requests with approval workflow</div></div>
      </div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>ID</th><th>Tracking ID</th><th>Item</th><th>Qty</th><th>Reason</th><th>Status</th><th>Requested By</th><th>Approved By</th><th>Created</th><th>Actions</th></tr></thead>
          <tbody id="res-tbody">
            ${reservations.map(r => `<tr data-status="${r.status}">
              <td>${mono(r.id.substring(0, 8))}</td>
              <td>${trackingId(r.tracking_id)}</td>
              <td>${r.item_name || '\u2014'}</td>
              <td>${fmtQty(r.qty_reserved)}</td>
              <td style="font-size:11px">${r.reason || '\u2014'}</td>
              <td>${badge(r.status)}</td>
              <td>${mono(r.requested_by || '\u2014')}</td>
              <td>${mono(r.approved_by || '\u2014')}</td>
              <td>${fmtDate(r.created_at)}</td>
              <td>
                ${r.status === 'pending_approval' ? `
                  <button class="btn btn-sm btn-success" onclick="approveReservation('${r.id}')">Approve</button>
                  <button class="btn btn-sm btn-error" onclick="rejectReservation('${r.id}')">Reject</button>
                ` : ''}
              </td>
            </tr>`).join('')}
            ${reservations.length === 0 ? '<tr><td colspan="10" class="empty-state"><p>No reservations</p></td></tr>' : ''}
          </tbody>
        </table>
      </div>
    </div>
  `;

  // Update badge
  const pending = reservations.filter(r => r.status === 'pending_approval').length;
  const rb = document.getElementById('nav-reservations-badge');
  if (rb) { rb.textContent = pending > 0 ? pending : ''; rb.style.display = pending > 0 ? 'flex' : 'none'; }
}

function filterRes(status, btn) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('#res-tbody tr').forEach(tr => {
    if (tr.classList.contains('empty-state')) return;
    tr.style.display = (status === 'all' || tr.dataset.status === status) ? '' : 'none';
  });
}

function showCreateReservationModal() {
  openModal('New Reservation', `
    <div class="form-group">
      <label class="form-label">Tracking ID (scan or type) *</label>
      <input type="text" class="form-input" id="resTrackingId" placeholder="Scan barcode" autofocus>
    </div>
    <div class="form-group">
      <label class="form-label">Qty to Reserve *</label>
      <input type="number" class="form-input" id="resQty" placeholder="0.00" step="0.01" min="0">
    </div>
    <div class="form-group">
      <label class="form-label">Reason *</label>
      <input type="text" class="form-input" id="resReason" placeholder="e.g. customer hold, sample request">
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitReservation()">Submit Reservation</button>
  `);
}

async function submitReservation() {
  const tid = document.getElementById('resTrackingId').value.trim();
  const qty = parseFloat(document.getElementById('resQty').value);
  const reason = document.getElementById('resReason').value.trim();

  if (!tid) { toast('Enter a tracking ID', 'warning'); return; }
  if (!qty || qty <= 0) { toast('Enter a valid qty', 'warning'); return; }
  if (!reason) { toast('Provide a reason', 'warning'); return; }

  const result = await apiPost('/reservations', { tracking_id: tid, qty_reserved: qty, reason });
  if (result && result.success) {
    closeModal();
    toast('Reservation submitted for approval', 'success');
    loadReservations();
  } else {
    toast(result?.detail || 'Reservation failed', 'error');
  }
}

async function approveReservation(id) {
  const result = await apiPost(`/reservations/${id}/approve`, {});
  if (result && result.success) {
    toast('Reservation approved', 'success');
    loadReservations();
  } else {
    toast(result?.detail || 'Approval failed', 'error');
  }
}

async function rejectReservation(id) {
  const result = await apiPost(`/reservations/${id}/reject`, {});
  if (result && result.success) {
    toast('Reservation rejected', 'warning');
    loadReservations();
  } else {
    toast(result?.detail || 'Rejection failed', 'error');
  }
}

// ===== RETURNS =====
async function loadReturns() {
  const el = document.getElementById('page-returns');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(3);
  const data = await api('/returns');
  if (!data) return;
  const returns = data.returns || [];

  el.innerHTML = `
    <div class="page-action-bar">
      <div class="page-action-bar-left"><span style="font-size:var(--text-xs);color:var(--color-text-muted)">${returns.length} return(s)</span></div>
      <div class="page-action-bar-right">
        <button class="btn btn-primary" onclick="showCreateReturnModal()">+ Process Return</button>
      </div>
    </div>
    <div class="card">
      <div class="card-header">
        <div><div class="card-title">Returns</div><div class="card-subtitle">Returned fabric generates new tracking ID and inventory lot</div></div>
      </div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>ID</th><th>Original Tracking</th><th>New Tracking</th><th>Item</th><th>Qty Returned</th><th>Reason</th><th>Returned By</th><th>Created</th></tr></thead>
          <tbody>
            ${returns.map(r => `<tr>
              <td>${mono(r.id.substring(0, 8))}</td>
              <td>${trackingId(r.original_tracking_id)}</td>
              <td>${trackingId(r.new_tracking_id)}</td>
              <td>${r.item_name || '\u2014'}</td>
              <td>${fmtQty(r.qty_returned)}</td>
              <td style="font-size:11px">${r.reason || '\u2014'}</td>
              <td>${mono(r.returned_by || '\u2014')}</td>
              <td>${fmtDate(r.created_at)}</td>
            </tr>`).join('')}
            ${returns.length === 0 ? '<tr><td colspan="8" class="empty-state"><p>No returns yet</p></td></tr>' : ''}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function showCreateReturnModal() {
  openModal('Process Return', `
    <div class="form-group">
      <label class="form-label">Original Tracking ID *</label>
      <input type="text" class="form-input" id="retOrigTrackingId" placeholder="Scan or type original tracking ID" autofocus>
    </div>
    <div class="form-group">
      <label class="form-label">Qty Returned *</label>
      <input type="number" class="form-input" id="retQty" placeholder="0.00" step="0.01" min="0">
    </div>
    <div class="form-group">
      <label class="form-label">Reason *</label>
      <input type="text" class="form-input" id="retReason" placeholder="e.g. customer return, excess cut">
    </div>
    <div class="form-group">
      <label class="form-label">Notes</label>
      <input type="text" class="form-input" id="retNotes" placeholder="Optional details">
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitReturn()">Process Return</button>
  `);
}

async function submitReturn() {
  const origTid = document.getElementById('retOrigTrackingId').value.trim();
  const qty = parseFloat(document.getElementById('retQty').value);
  const reason = document.getElementById('retReason').value.trim();
  const notes = document.getElementById('retNotes').value.trim() || null;

  if (!origTid) { toast('Enter the original tracking ID', 'warning'); return; }
  if (!qty || qty <= 0) { toast('Enter a valid return qty', 'warning'); return; }
  if (!reason) { toast('Provide a reason', 'warning'); return; }

  const result = await apiPost('/returns', {
    original_tracking_id: origTid,
    qty_returned: qty,
    reason,
    notes
  });
  if (result && result.success) {
    closeModal();
    toast(`Return processed. New tracking ID: ${result.new_tracking_id}`, 'success');
    loadReturns();
  } else {
    toast(result?.detail || 'Return failed', 'error');
  }
}

// ===== BOOT =====
initApp();
