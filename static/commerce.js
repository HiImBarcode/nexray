/* ========== NEXRAY Commerce Hub — Frontend Module ========== */

const PLATFORM_COLORS = { shopee: '#ee4d2d', lazada: '#0f146d', tiktok: '#111', shopify: '#96bf48' };

function platformBadge(p) {
  if (!p) return '\u2014';
  const color = PLATFORM_COLORS[p.toLowerCase()] || '#666';
  return `<span class="badge" style="background:${color};color:#fff">${esc(p)}</span>`;
}

function fmtPrice(val) {
  return val != null ? '\u20B1' + Number(val).toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '\u2014';
}

/* ===== PRODUCTS & LISTINGS ===== */

async function loadProducts() {
  const el = document.getElementById('page-products');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(5);
  const data = await api('/products');
  if (!data) { el.innerHTML = '<div class="empty-state"><p>Unable to load products</p></div>'; return; }
  const products = data.products || data || [];

  el.innerHTML = `
    <div class="page-action-bar">
      <div class="page-action-bar-left">
        <input type="text" class="form-input" id="prodSearch" placeholder="Search products\u2026" style="width:240px" oninput="filterProductsTable()">
        <select class="form-select" id="prodCatFilter" style="width:160px" onchange="filterProductsTable()">
          <option value="">All Categories</option>
          ${[...new Set(products.map(p => p.category).filter(Boolean))].map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join('')}
        </select>
      </div>
      <div class="page-action-bar-right">
        <button class="btn btn-sm btn-secondary" onclick="showBulkPublishModal()">Bulk Publish</button>
        <button class="btn btn-primary" onclick="showCreateProductModal()">+ New Product</button>
      </div>
    </div>
    <div class="card">
      <div class="card-header">
        <div><div class="card-title">Product Catalog</div><div class="card-subtitle">${products.length} products</div></div>
      </div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>SKU</th><th>Name</th><th>Category</th><th>Base Price</th><th>Cost</th><th>Weight</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody id="products-tbody">
            ${products.map(p => `<tr data-cat="${esc(p.category || '')}" data-name="${esc((p.name || '') + ' ' + (p.sku || ''))}">
              <td>${mono(p.sku)}</td>
              <td>${esc(p.name)}</td>
              <td>${esc(p.category || '\u2014')}</td>
              <td>${fmtPrice(p.base_price)}</td>
              <td>${fmtPrice(p.cost_price)}</td>
              <td>${p.weight_kg != null ? p.weight_kg + ' kg' : '\u2014'}</td>
              <td>${badge(p.status || 'draft')}</td>
              <td>
                <button class="btn btn-xs btn-secondary" onclick="showEditProductModal(${p.id})">Edit</button>
                <button class="btn btn-xs btn-secondary" onclick="showPublishProductModal(${p.id}, '${esc(p.name)}')">Publish</button>
                <button class="btn btn-xs btn-secondary" onclick="showProductListings(${p.id}, '${esc(p.name)}')">Listings</button>
              </td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function filterProductsTable() {
  const q = (document.getElementById('prodSearch').value || '').toLowerCase();
  const cat = document.getElementById('prodCatFilter').value;
  document.querySelectorAll('#products-tbody tr').forEach(r => {
    const matchName = !q || (r.dataset.name || '').toLowerCase().includes(q);
    const matchCat = !cat || r.dataset.cat === cat;
    r.style.display = matchName && matchCat ? '' : 'none';
  });
}

function showCreateProductModal() {
  openModal('New Product', `
    <div class="form-grid">
      <div class="form-group"><label class="form-label">Name *</label><input type="text" class="form-input" id="prodName"></div>
      <div class="form-group"><label class="form-label">SKU *</label><input type="text" class="form-input" id="prodSku"></div>
      <div class="form-group"><label class="form-label">Category</label><input type="text" class="form-input" id="prodCategory"></div>
      <div class="form-group"><label class="form-label">Base Price</label><input type="number" class="form-input" id="prodBasePrice" step="0.01"></div>
      <div class="form-group"><label class="form-label">Cost Price</label><input type="number" class="form-input" id="prodCostPrice" step="0.01"></div>
      <div class="form-group"><label class="form-label">Weight (kg)</label><input type="number" class="form-input" id="prodWeight" step="0.01"></div>
      <div class="form-group full"><label class="form-label">Description</label><textarea class="form-textarea" id="prodDesc" rows="2"></textarea></div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitCreateProduct()">Create</button>
  `);
}

async function submitCreateProduct() {
  const name = document.getElementById('prodName').value.trim();
  const sku = document.getElementById('prodSku').value.trim();
  if (!name || !sku) { toast('Name and SKU are required', 'warning'); return; }
  const result = await apiPost('/products', {
    name, sku,
    category: document.getElementById('prodCategory').value.trim() || null,
    base_price: parseFloat(document.getElementById('prodBasePrice').value) || null,
    cost_price: parseFloat(document.getElementById('prodCostPrice').value) || null,
    weight_kg: parseFloat(document.getElementById('prodWeight').value) || null,
    description: document.getElementById('prodDesc').value.trim() || null
  });
  if (result && (result.success || result.id)) { closeModal(); toast('Product created', 'success'); loadProducts(); }
}

async function showEditProductModal(id) {
  const p = await api(`/products/${id}`);
  if (!p) return;
  const prod = p.product || p;
  openModal('Edit Product', `
    <div class="form-grid">
      <div class="form-group"><label class="form-label">Name *</label><input type="text" class="form-input" id="prodEditName" value="${esc(prod.name)}"></div>
      <div class="form-group"><label class="form-label">SKU *</label><input type="text" class="form-input" id="prodEditSku" value="${esc(prod.sku)}"></div>
      <div class="form-group"><label class="form-label">Category</label><input type="text" class="form-input" id="prodEditCategory" value="${esc(prod.category || '')}"></div>
      <div class="form-group"><label class="form-label">Base Price</label><input type="number" class="form-input" id="prodEditBasePrice" step="0.01" value="${prod.base_price || ''}"></div>
      <div class="form-group"><label class="form-label">Cost Price</label><input type="number" class="form-input" id="prodEditCostPrice" step="0.01" value="${prod.cost_price || ''}"></div>
      <div class="form-group"><label class="form-label">Weight (kg)</label><input type="number" class="form-input" id="prodEditWeight" step="0.01" value="${prod.weight_kg || ''}"></div>
      <div class="form-group full"><label class="form-label">Description</label><textarea class="form-textarea" id="prodEditDesc" rows="2">${esc(prod.description || '')}</textarea></div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitEditProduct(${id})">Save</button>
  `);
}

async function submitEditProduct(id) {
  const name = document.getElementById('prodEditName').value.trim();
  const sku = document.getElementById('prodEditSku').value.trim();
  if (!name || !sku) { toast('Name and SKU are required', 'warning'); return; }
  const result = await apiPut(`/products/${id}`, {
    name, sku,
    category: document.getElementById('prodEditCategory').value.trim() || null,
    base_price: parseFloat(document.getElementById('prodEditBasePrice').value) || null,
    cost_price: parseFloat(document.getElementById('prodEditCostPrice').value) || null,
    weight_kg: parseFloat(document.getElementById('prodEditWeight').value) || null,
    description: document.getElementById('prodEditDesc').value.trim() || null
  });
  if (result && (result.success || result.id)) { closeModal(); toast('Product updated', 'success'); loadProducts(); }
}

function showPublishProductModal(id, name) {
  openModal(`Publish: ${name}`, `
    <div class="form-grid">
      <div class="form-group"><label class="form-label">Platform *</label>
        <select class="form-select" id="pubPlatform">
          <option value="shopee">Shopee</option><option value="lazada">Lazada</option>
          <option value="tiktok">TikTok</option><option value="shopify">Shopify</option>
        </select>
      </div>
      <div class="form-group"><label class="form-label">Platform Price</label><input type="number" class="form-input" id="pubPrice" step="0.01"></div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitPublishProduct(${id})">Publish</button>
  `);
}

async function submitPublishProduct(id) {
  const platform = document.getElementById('pubPlatform').value;
  const price = parseFloat(document.getElementById('pubPrice').value) || null;
  const result = await apiPost(`/products/${id}/publish`, { platform, platform_data: { price } });
  if (result && (result.success || result.id)) { closeModal(); toast('Published to ' + platform, 'success'); }
}

function showBulkPublishModal() {
  openModal('Bulk Publish', `
    <div class="form-grid">
      <div class="form-group full"><label class="form-label">Product IDs (comma-separated) *</label><input type="text" class="form-input" id="bulkPubIds" placeholder="1, 2, 3"></div>
      <div class="form-group"><label class="form-label">Platform *</label>
        <select class="form-select" id="bulkPubPlatform">
          <option value="shopee">Shopee</option><option value="lazada">Lazada</option>
          <option value="tiktok">TikTok</option><option value="shopify">Shopify</option>
        </select>
      </div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitBulkPublish()">Publish All</button>
  `);
}

async function submitBulkPublish() {
  const ids = document.getElementById('bulkPubIds').value.split(',').map(s => parseInt(s.trim())).filter(Boolean);
  if (!ids.length) { toast('Enter at least one product ID', 'warning'); return; }
  const platform = document.getElementById('bulkPubPlatform').value;
  const result = await apiPost('/products/bulk_publish', { product_ids: ids, platform, platform_data: {} });
  if (result && (result.success || result.published)) { closeModal(); toast(`Published ${ids.length} products to ${platform}`, 'success'); }
}

async function showProductListings(productId, name) {
  const data = await api('/platform_listings', { product_id: productId });
  if (!data) return;
  const listings = data.listings || data || [];
  const rows = listings.length > 0
    ? listings.map(l => `<tr>
        <td>${platformBadge(l.platform)}</td>
        <td>${mono(l.platform_sku || l.platform_listing_id)}</td>
        <td>${fmtPrice(l.platform_price)}</td>
        <td>${badge(l.sync_status || l.status || 'unknown')}</td>
        <td>${fmtDate(l.last_synced_at)}</td>
        <td>
          <button class="btn btn-xs btn-secondary" onclick="syncListing(${l.id})">Sync</button>
        </td>
      </tr>`).join('')
    : '<tr><td colspan="6" class="empty-state"><p>No listings yet</p></td></tr>';

  openModal(`Listings: ${name}`, `
    <div class="table-wrapper"><table>
      <thead><tr><th>Platform</th><th>Platform SKU</th><th>Price</th><th>Status</th><th>Last Sync</th><th>Actions</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>
  `, `<button class="btn btn-secondary" onclick="closeModal()">Close</button>`, 'modal-lg');
}

async function syncListing(id) {
  const result = await apiPost(`/platform_listings/${id}/sync`, {});
  if (result && (result.success || result.id)) { toast('Listing synced', 'success'); }
}

/* ===== E-COMMERCE ORDERS ===== */

async function loadEcomOrders() {
  const el = document.getElementById('page-ecom-orders');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(5);

  const statuses = ['all', 'pending', 'confirmed', 'shipped', 'delivered', 'cancelled'];
  const platforms = ['all', 'shopee', 'lazada', 'tiktok', 'shopify'];

  el.innerHTML = `
    <div class="page-action-bar">
      <div class="page-action-bar-left">
        <div class="tab-bar" id="ecomStatusTabs">
          ${statuses.map(s => `<button class="tab-btn ${s === 'all' ? 'active' : ''}" onclick="filterEcomOrders(this)" data-status="${s}">${s === 'all' ? 'All' : s.replace(/_/g, ' ')}</button>`).join('')}
        </div>
      </div>
      <div class="page-action-bar-right">
        <select class="form-select" id="ecomPlatformFilter" style="width:140px" onchange="reloadEcomOrders()">
          ${platforms.map(p => `<option value="${p === 'all' ? '' : p}">${p === 'all' ? 'All Platforms' : p}</option>`).join('')}
        </select>
        <input type="text" class="form-input" id="ecomSearch" placeholder="Search orders\u2026" style="width:200px">
        <button class="btn btn-sm btn-secondary" onclick="reloadEcomOrders()">Search</button>
        <button class="btn btn-sm btn-secondary" onclick="syncEcomOrders()">Sync Orders</button>
      </div>
    </div>
    <div class="page-action-bar">
      <div class="page-action-bar-left">
        <button class="btn btn-sm btn-secondary" onclick="bulkEcomAction('confirm')">Bulk Confirm</button>
        <button class="btn btn-sm btn-secondary" onclick="bulkEcomAction('ship')">Bulk Ship</button>
        <button class="btn btn-sm btn-secondary" onclick="bulkEcomAction('cancel')">Bulk Cancel</button>
      </div>
    </div>
    <div class="card">
      <div class="table-wrapper">
        <table>
          <thead><tr><th><input type="checkbox" id="ecomSelectAll" onchange="toggleEcomSelectAll(this)"></th><th>Order #</th><th>Platform</th><th>Customer</th><th>Total</th><th>Items</th><th>Status</th><th>Ordered</th><th>Actions</th></tr></thead>
          <tbody id="ecom-orders-tbody"><tr><td colspan="9"><div class="loading-skeleton"></div></td></tr></tbody>
        </table>
      </div>
    </div>
  `;
  await reloadEcomOrders();
}

async function reloadEcomOrders() {
  const params = {};
  const activeTab = document.querySelector('#ecomStatusTabs .tab-btn.active');
  const status = activeTab ? activeTab.dataset.status : 'all';
  if (status && status !== 'all') params.status = status;
  const platform = document.getElementById('ecomPlatformFilter')?.value;
  if (platform) params.platform = platform;
  const search = document.getElementById('ecomSearch')?.value?.trim();
  if (search) params.search = search;

  const data = await api('/ecommerce_orders', params);
  const orders = (data && (data.orders || data)) || [];
  const tbody = document.getElementById('ecom-orders-tbody');
  if (!tbody) return;

  tbody.innerHTML = orders.length > 0
    ? orders.map(o => `<tr>
        <td><input type="checkbox" class="ecom-order-cb" value="${o.id}"></td>
        <td>${mono(o.platform_order_id || o.id)}</td>
        <td>${platformBadge(o.platform)}</td>
        <td>${esc(o.customer_name || '\u2014')}</td>
        <td>${fmtPrice(o.total_amount)}</td>
        <td>${o.item_count || o.items_count || '\u2014'}</td>
        <td>${badge(o.status)}</td>
        <td>${fmtDate(o.ordered_at || o.created_at)}</td>
        <td>
          <button class="btn btn-xs btn-secondary" onclick="showEcomOrderDetail(${o.id})">View</button>
          ${o.status === 'pending' ? `<button class="btn btn-xs btn-primary" onclick="confirmEcomOrder(${o.id})">Confirm</button>` : ''}
          ${o.status === 'confirmed' ? `<button class="btn btn-xs btn-primary" onclick="showShipEcomOrderModal(${o.id})">Ship</button>` : ''}
        </td>
      </tr>`).join('')
    : '<tr><td colspan="9" class="empty-state"><p>No orders found</p></td></tr>';
}

function filterEcomOrders(btn) {
  document.querySelectorAll('#ecomStatusTabs .tab-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  reloadEcomOrders();
}

function toggleEcomSelectAll(cb) {
  document.querySelectorAll('.ecom-order-cb').forEach(c => { c.checked = cb.checked; });
}

function getSelectedEcomOrderIds() {
  return [...document.querySelectorAll('.ecom-order-cb:checked')].map(c => parseInt(c.value));
}

async function syncEcomOrders() {
  const result = await apiPost('/ecommerce_orders/sync', {});
  if (result && (result.success || result.synced != null)) { toast(`Synced ${result.synced || 0} orders`, 'success'); reloadEcomOrders(); }
}

async function confirmEcomOrder(id) {
  const result = await apiPost(`/ecommerce_orders/${id}/confirm`, {});
  if (result && (result.success || result.id)) { toast('Order confirmed', 'success'); reloadEcomOrders(); }
}

function showShipEcomOrderModal(id) {
  openModal('Ship Order', `
    <div class="form-grid">
      <div class="form-group"><label class="form-label">Tracking Number *</label><input type="text" class="form-input" id="shipTracking"></div>
      <div class="form-group"><label class="form-label">Carrier</label><input type="text" class="form-input" id="shipCarrier" placeholder="e.g. J&T, LBC"></div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitShipEcomOrder(${id})">Ship</button>
  `);
}

async function submitShipEcomOrder(id) {
  const tracking = document.getElementById('shipTracking').value.trim();
  if (!tracking) { toast('Tracking number required', 'warning'); return; }
  const carrier = document.getElementById('shipCarrier').value.trim() || null;
  const result = await apiPost(`/ecommerce_orders/${id}/ship`, { tracking_number: tracking, carrier });
  if (result && (result.success || result.id)) { closeModal(); toast('Order shipped', 'success'); reloadEcomOrders(); }
}

async function showEcomOrderDetail(id) {
  const data = await api(`/ecommerce_orders/${id}`);
  if (!data) return;
  const o = data.order || data;
  const items = o.items || data.items || [];
  openModal(`Order: ${o.platform_order_id || o.id}`, `
    <div class="detail-grid">
      <div class="info-card">
        <h4>Order Info</h4>
        <div class="info-row"><span class="label">Platform</span><span class="value">${platformBadge(o.platform)}</span></div>
        <div class="info-row"><span class="label">Status</span><span class="value">${badge(o.status)}</span></div>
        <div class="info-row"><span class="label">Customer</span><span class="value">${esc(o.customer_name || '\u2014')}</span></div>
        <div class="info-row"><span class="label">Total</span><span class="value">${fmtPrice(o.total_amount)}</span></div>
        <div class="info-row"><span class="label">Ordered</span><span class="value">${fmtDate(o.ordered_at || o.created_at)}</span></div>
        ${o.tracking_number ? `<div class="info-row"><span class="label">Tracking</span><span class="value">${trackingId(o.tracking_number)}</span></div>` : ''}
      </div>
    </div>
    <h4 style="margin:12px 0 6px">Items</h4>
    <div class="table-wrapper"><table>
      <thead><tr><th>Product</th><th>SKU</th><th>Qty</th><th>Unit Price</th><th>Subtotal</th></tr></thead>
      <tbody>
        ${items.map(i => `<tr>
          <td>${esc(i.product_name || i.name || '\u2014')}</td>
          <td>${mono(i.sku)}</td>
          <td>${i.qty || i.quantity || 0}</td>
          <td>${fmtPrice(i.unit_price)}</td>
          <td>${fmtPrice(i.subtotal || (i.unit_price * (i.qty || i.quantity || 0)))}</td>
        </tr>`).join('')}
      </tbody>
    </table></div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Close</button>
    ${o.status === 'pending' ? `<button class="btn btn-primary" onclick="confirmEcomOrder(${o.id}); closeModal();">Confirm</button>` : ''}
    ${o.status === 'confirmed' ? `<button class="btn btn-primary" onclick="closeModal(); showShipEcomOrderModal(${o.id});">Ship</button>` : ''}
    ${['pending','confirmed'].includes(o.status) ? `<button class="btn btn-danger" onclick="cancelEcomOrder(${o.id})">Cancel</button>` : ''}
  `, 'modal-lg');
}

async function cancelEcomOrder(id) {
  const reason = prompt('Cancellation reason:');
  if (reason === null) return;
  const result = await apiPost(`/ecommerce_orders/${id}/cancel`, { reason });
  if (result && (result.success || result.id)) { closeModal(); toast('Order cancelled', 'success'); reloadEcomOrders(); }
}

async function bulkEcomAction(action) {
  const ids = getSelectedEcomOrderIds();
  if (!ids.length) { toast('Select at least one order', 'warning'); return; }

  if (action === 'confirm') {
    const result = await apiPost('/ecommerce_orders/bulk_confirm', { order_ids: ids });
    if (result) { toast(`Confirmed ${ids.length} orders`, 'success'); reloadEcomOrders(); }
  } else if (action === 'ship') {
    openModal('Bulk Ship', `
      <p>Shipping ${ids.length} order(s). Provide tracking numbers (one per line, matching order selection order).</p>
      <div class="form-group"><label class="form-label">Tracking Numbers</label><textarea class="form-textarea" id="bulkShipTrackings" rows="4" placeholder="One per line"></textarea></div>
    `, `
      <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="submitBulkShip([${ids}])">Ship All</button>
    `);
  } else if (action === 'cancel') {
    const reason = prompt('Cancellation reason for all selected orders:');
    if (reason === null) return;
    const result = await apiPost('/ecommerce_orders/bulk_cancel', { order_ids: ids, reason });
    if (result) { toast(`Cancelled ${ids.length} orders`, 'success'); reloadEcomOrders(); }
  }
}

async function submitBulkShip(ids) {
  const trackings = document.getElementById('bulkShipTrackings').value.split('\n').map(s => s.trim()).filter(Boolean);
  const result = await apiPost('/ecommerce_orders/bulk_ship', { order_ids: ids, tracking_numbers: trackings });
  if (result) { closeModal(); toast(`Shipped ${ids.length} orders`, 'success'); reloadEcomOrders(); }
}

/* ===== FULFILLMENT ===== */

async function loadFulfillment() {
  const el = document.getElementById('page-fulfillment');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(4);

  const [printData, pickData] = await Promise.all([
    api('/print_queue'),
    api('/pick_lists')
  ]);
  const printJobs = (printData && (printData.jobs || printData)) || [];
  const pickLists = (pickData && (pickData.pick_lists || pickData)) || [];

  el.innerHTML = `
    <div class="page-action-bar">
      <div class="page-action-bar-left">
        <div class="tab-bar" id="fulfillTabs">
          <button class="tab-btn active" onclick="toggleFulfillTab('print', this)">Print Queue</button>
          <button class="tab-btn" onclick="toggleFulfillTab('pick', this)">Pick Lists</button>
        </div>
      </div>
      <div class="page-action-bar-right">
        <button class="btn btn-primary" onclick="showCreatePrintJobModal()">+ Print Job</button>
        <button class="btn btn-sm btn-secondary" onclick="showGeneratePickListModal()">Generate Pick List</button>
      </div>
    </div>

    <div id="fulfillPrintSection" class="card">
      <div class="card-header"><div><div class="card-title">Print Queue</div><div class="card-subtitle">${printJobs.length} jobs</div></div></div>
      <div class="table-wrapper"><table>
        <thead><tr><th>ID</th><th>Job Type</th><th>Reference</th><th>Copies</th><th>Printer</th><th>Status</th><th>Created</th><th>Actions</th></tr></thead>
        <tbody>
          ${printJobs.length > 0 ? printJobs.map(j => `<tr>
            <td>${mono(j.id)}</td>
            <td>${badge(j.job_type)}</td>
            <td>${mono(j.reference_id)}</td>
            <td>${j.copies || 1}</td>
            <td>${esc(j.printer_name || '\u2014')}</td>
            <td>${badge(j.status)}</td>
            <td>${fmtDate(j.created_at)}</td>
            <td>${j.status === 'pending' || j.status === 'queued' ? `<button class="btn btn-xs btn-primary" onclick="markPrinted(${j.id})">Mark Printed</button>` : '\u2014'}</td>
          </tr>`).join('') : '<tr><td colspan="8" class="empty-state"><p>No print jobs</p></td></tr>'}
        </tbody>
      </table></div>
    </div>

    <div id="fulfillPickSection" class="card" style="display:none">
      <div class="card-header"><div><div class="card-title">Pick Lists</div><div class="card-subtitle">${pickLists.length} lists</div></div></div>
      <div class="table-wrapper"><table>
        <thead><tr><th>ID</th><th>Orders</th><th>Lines</th><th>Status</th><th>Created</th><th>Actions</th></tr></thead>
        <tbody>
          ${pickLists.length > 0 ? pickLists.map(p => `<tr>
            <td>${mono(p.id)}</td>
            <td>${p.order_count || '\u2014'}</td>
            <td>${p.line_count || '\u2014'}</td>
            <td>${badge(p.status)}</td>
            <td>${fmtDate(p.created_at)}</td>
            <td>
              <button class="btn btn-xs btn-secondary" onclick="showPickListDetail(${p.id})">View</button>
              ${p.status !== 'completed' ? `<button class="btn btn-xs btn-primary" onclick="completePickList(${p.id})">Complete</button>` : ''}
            </td>
          </tr>`).join('') : '<tr><td colspan="6" class="empty-state"><p>No pick lists</p></td></tr>'}
        </tbody>
      </table></div>
    </div>
  `;
}

function toggleFulfillTab(tab, btn) {
  document.querySelectorAll('#fulfillTabs .tab-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('fulfillPrintSection').style.display = tab === 'print' ? '' : 'none';
  document.getElementById('fulfillPickSection').style.display = tab === 'pick' ? '' : 'none';
}

function showCreatePrintJobModal() {
  openModal('New Print Job', `
    <div class="form-grid">
      <div class="form-group"><label class="form-label">Job Type *</label>
        <select class="form-select" id="pjType"><option value="shipping_label">Shipping Label</option><option value="invoice">Invoice</option><option value="packing_slip">Packing Slip</option><option value="pick_list">Pick List</option></select>
      </div>
      <div class="form-group"><label class="form-label">Reference ID *</label><input type="text" class="form-input" id="pjRefId"></div>
      <div class="form-group"><label class="form-label">Reference Type</label><input type="text" class="form-input" id="pjRefType" placeholder="order, pick_list"></div>
      <div class="form-group"><label class="form-label">Copies</label><input type="number" class="form-input" id="pjCopies" value="1" min="1"></div>
      <div class="form-group"><label class="form-label">Printer</label><input type="text" class="form-input" id="pjPrinter" placeholder="Optional"></div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitCreatePrintJob()">Create</button>
  `);
}

async function submitCreatePrintJob() {
  const refId = document.getElementById('pjRefId').value.trim();
  if (!refId) { toast('Reference ID required', 'warning'); return; }
  const result = await apiPost('/print_queue', {
    job_type: document.getElementById('pjType').value,
    reference_id: refId,
    reference_type: document.getElementById('pjRefType').value.trim() || null,
    copies: parseInt(document.getElementById('pjCopies').value) || 1,
    printer_name: document.getElementById('pjPrinter').value.trim() || null
  });
  if (result && (result.success || result.id)) { closeModal(); toast('Print job created', 'success'); loadFulfillment(); }
}

async function markPrinted(id) {
  const result = await apiPost(`/print_queue/${id}/mark_printed`, {});
  if (result && (result.success || result.id)) { toast('Marked as printed', 'success'); loadFulfillment(); }
}

function showGeneratePickListModal() {
  openModal('Generate Pick List', `
    <div class="form-group"><label class="form-label">Order IDs (comma-separated) *</label><input type="text" class="form-input" id="pickOrderIds" placeholder="1, 2, 3"></div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitGeneratePickList()">Generate</button>
  `);
}

async function submitGeneratePickList() {
  const ids = document.getElementById('pickOrderIds').value.split(',').map(s => parseInt(s.trim())).filter(Boolean);
  if (!ids.length) { toast('Enter at least one order ID', 'warning'); return; }
  const result = await apiPost('/pick_lists/generate', { order_ids: ids });
  if (result && (result.success || result.id)) { closeModal(); toast('Pick list generated', 'success'); loadFulfillment(); }
}

async function showPickListDetail(id) {
  toast('Loading pick list...', 'info');
  // Pick list detail view would show lines with picked_qty inputs
  // For now, display in modal
  openModal(`Pick List #${id}`, `
    <p>Pick list detail for ID ${id}. Use the "Complete" action when all items are picked.</p>
  `, `<button class="btn btn-secondary" onclick="closeModal()">Close</button>`);
}

async function completePickList(id) {
  const result = await apiPost(`/pick_lists/${id}/complete`, {});
  if (result && (result.success || result.id)) { toast('Pick list completed', 'success'); loadFulfillment(); }
}

/* ===== E-COMMERCE RETURNS ===== */

async function loadEcomReturns() {
  const el = document.getElementById('page-ecom-returns');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(4);

  const statuses = ['all', 'requested', 'approved', 'received', 'refunded', 'rejected'];

  el.innerHTML = `
    <div class="page-action-bar">
      <div class="page-action-bar-left">
        <div class="tab-bar" id="ecomReturnTabs">
          ${statuses.map(s => `<button class="tab-btn ${s === 'all' ? 'active' : ''}" onclick="filterEcomReturns(this)" data-status="${s}">${s === 'all' ? 'All' : s}</button>`).join('')}
        </div>
      </div>
      <div class="page-action-bar-right">
        <button class="btn btn-primary" onclick="showCreateEcomReturnModal()">+ New Return</button>
      </div>
    </div>
    <div class="card" id="ecom-returns-card">
      <div class="table-wrapper"><table>
        <thead><tr><th>ID</th><th>Order</th><th>Product</th><th>Qty</th><th>Reason</th><th>Status</th><th>Created</th><th>Actions</th></tr></thead>
        <tbody id="ecom-returns-tbody"><tr><td colspan="8"><div class="loading-skeleton"></div></td></tr></tbody>
      </table></div>
    </div>
  `;
  await reloadEcomReturns();
}

async function reloadEcomReturns() {
  const params = {};
  const activeTab = document.querySelector('#ecomReturnTabs .tab-btn.active');
  const status = activeTab ? activeTab.dataset.status : 'all';
  if (status && status !== 'all') params.status = status;

  const data = await api('/ecommerce_returns', params);
  const returns = (data && (data.returns || data)) || [];
  const tbody = document.getElementById('ecom-returns-tbody');
  if (!tbody) return;

  tbody.innerHTML = returns.length > 0
    ? returns.map(r => `<tr>
        <td>${mono(r.id)}</td>
        <td>${mono(r.order_id || r.platform_order_id)}</td>
        <td>${esc(r.product_name || '\u2014')}</td>
        <td>${r.qty || r.quantity || 0}</td>
        <td>${esc(r.reason || '\u2014')}</td>
        <td>${badge(r.status)}</td>
        <td>${fmtDate(r.created_at)}</td>
        <td>
          ${r.status === 'requested' ? `<button class="btn btn-xs btn-primary" onclick="approveEcomReturn(${r.id})">Approve</button><button class="btn btn-xs btn-danger" onclick="rejectEcomReturn(${r.id})">Reject</button>` : ''}
          ${r.status === 'approved' ? `<button class="btn btn-xs btn-primary" onclick="receiveEcomReturn(${r.id})">Receive</button>` : ''}
          ${r.status === 'received' ? `<button class="btn btn-xs btn-primary" onclick="showRefundEcomReturnModal(${r.id})">Refund</button>` : ''}
        </td>
      </tr>`).join('')
    : '<tr><td colspan="8" class="empty-state"><p>No returns found</p></td></tr>';
}

function filterEcomReturns(btn) {
  document.querySelectorAll('#ecomReturnTabs .tab-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  reloadEcomReturns();
}

function showCreateEcomReturnModal() {
  openModal('New Return Request', `
    <div class="form-grid">
      <div class="form-group"><label class="form-label">Order ID *</label><input type="number" class="form-input" id="retOrderId"></div>
      <div class="form-group"><label class="form-label">Order Item ID</label><input type="number" class="form-input" id="retItemId"></div>
      <div class="form-group"><label class="form-label">Quantity *</label><input type="number" class="form-input" id="retQty" value="1" min="1"></div>
      <div class="form-group"><label class="form-label">Reason *</label>
        <select class="form-select" id="retReason">
          <option value="defective">Defective</option><option value="wrong_item">Wrong Item</option>
          <option value="not_as_described">Not As Described</option><option value="change_of_mind">Change of Mind</option>
          <option value="damaged_in_transit">Damaged in Transit</option>
        </select>
      </div>
      <div class="form-group full"><label class="form-label">Customer Note</label><textarea class="form-textarea" id="retNote" rows="2"></textarea></div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitCreateEcomReturn()">Submit</button>
  `);
}

async function submitCreateEcomReturn() {
  const orderId = parseInt(document.getElementById('retOrderId').value);
  const qty = parseInt(document.getElementById('retQty').value);
  if (!orderId || !qty) { toast('Order ID and quantity required', 'warning'); return; }
  const result = await apiPost('/ecommerce_returns', {
    order_id: orderId,
    order_item_id: parseInt(document.getElementById('retItemId').value) || null,
    reason: document.getElementById('retReason').value,
    qty,
    customer_note: document.getElementById('retNote').value.trim() || null
  });
  if (result && (result.success || result.id)) { closeModal(); toast('Return created', 'success'); reloadEcomReturns(); }
}

async function approveEcomReturn(id) {
  const result = await apiPost(`/ecommerce_returns/${id}/approve`, {});
  if (result && (result.success || result.id)) { toast('Return approved', 'success'); reloadEcomReturns(); }
}

async function rejectEcomReturn(id) {
  const reason = prompt('Rejection reason:');
  if (reason === null) return;
  const result = await apiPost(`/ecommerce_returns/${id}/reject`, { rejection_reason: reason });
  if (result && (result.success || result.id)) { toast('Return rejected', 'success'); reloadEcomReturns(); }
}

async function receiveEcomReturn(id) {
  const condition = prompt('Item condition (good, damaged, unsellable):') || 'good';
  const result = await apiPost(`/ecommerce_returns/${id}/receive`, { condition });
  if (result && (result.success || result.id)) { toast('Return received', 'success'); reloadEcomReturns(); }
}

function showRefundEcomReturnModal(id) {
  openModal('Process Refund', `
    <div class="form-grid">
      <div class="form-group"><label class="form-label">Refund Amount *</label><input type="number" class="form-input" id="refundAmt" step="0.01"></div>
      <div class="form-group"><label class="form-label">Refund Method</label>
        <select class="form-select" id="refundMethod">
          <option value="original_payment">Original Payment</option><option value="store_credit">Store Credit</option><option value="bank_transfer">Bank Transfer</option>
        </select>
      </div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitRefundEcomReturn(${id})">Refund</button>
  `);
}

async function submitRefundEcomReturn(id) {
  const amt = parseFloat(document.getElementById('refundAmt').value);
  if (!amt) { toast('Refund amount required', 'warning'); return; }
  const result = await apiPost(`/ecommerce_returns/${id}/refund`, {
    refund_amount: amt,
    refund_method: document.getElementById('refundMethod').value
  });
  if (result && (result.success || result.id)) { closeModal(); toast('Refund processed', 'success'); reloadEcomReturns(); }
}

/* ===== AFFILIATES ===== */

async function loadAffiliates() {
  const el = document.getElementById('page-affiliates');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(4);
  const data = await api('/affiliates');
  if (!data) { el.innerHTML = '<div class="empty-state"><p>Unable to load affiliates</p></div>'; return; }
  const affiliates = data.affiliates || data || [];

  el.innerHTML = `
    <div class="page-action-bar">
      <div class="page-action-bar-left">
        <input type="text" class="form-input" id="affSearch" placeholder="Search affiliates\u2026" style="width:240px" oninput="filterAffiliatesTable()">
      </div>
      <div class="page-action-bar-right">
        <button class="btn btn-sm btn-secondary" onclick="showCommissionsPanel()">Commissions</button>
        <button class="btn btn-primary" onclick="showCreateAffiliateModal()">+ New Affiliate</button>
      </div>
    </div>
    <div class="card">
      <div class="card-header"><div><div class="card-title">Affiliates</div><div class="card-subtitle">${affiliates.length} affiliates</div></div></div>
      <div class="table-wrapper"><table>
        <thead><tr><th>Name</th><th>Email</th><th>Platform</th><th>Handle</th><th>Commission</th><th>Tier</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody id="affiliates-tbody">
          ${affiliates.length > 0 ? affiliates.map(a => `<tr data-name="${esc((a.name || '') + ' ' + (a.email || '') + ' ' + (a.social_handle || ''))}">
            <td>${esc(a.name)}</td>
            <td>${esc(a.email || '\u2014')}</td>
            <td>${platformBadge(a.platform)}</td>
            <td>${mono(a.social_handle)}</td>
            <td>${a.commission_rate != null ? (a.commission_rate * 100).toFixed(1) + '%' : '\u2014'}</td>
            <td>${badge(a.tier || 'standard')}</td>
            <td>${badge(a.status || 'active')}</td>
            <td>
              <button class="btn btn-xs btn-secondary" onclick="showEditAffiliateModal(${a.id})">Edit</button>
              <button class="btn btn-xs btn-secondary" onclick="showAffiliateCommissions(${a.id}, '${esc(a.name)}')">Commissions</button>
              <button class="btn btn-xs btn-secondary" onclick="showAffiliateSamples(${a.id}, '${esc(a.name)}')">Samples</button>
            </td>
          </tr>`).join('') : '<tr><td colspan="8" class="empty-state"><p>No affiliates yet</p></td></tr>'}
        </tbody>
      </table></div>
    </div>
  `;
}

function filterAffiliatesTable() {
  const q = (document.getElementById('affSearch').value || '').toLowerCase();
  document.querySelectorAll('#affiliates-tbody tr').forEach(r => {
    r.style.display = !q || (r.dataset.name || '').toLowerCase().includes(q) ? '' : 'none';
  });
}

function showCreateAffiliateModal() {
  openModal('New Affiliate', `
    <div class="form-grid">
      <div class="form-group"><label class="form-label">Name *</label><input type="text" class="form-input" id="affName"></div>
      <div class="form-group"><label class="form-label">Email *</label><input type="email" class="form-input" id="affEmail"></div>
      <div class="form-group"><label class="form-label">Phone</label><input type="text" class="form-input" id="affPhone"></div>
      <div class="form-group"><label class="form-label">Social Handle</label><input type="text" class="form-input" id="affHandle" placeholder="@handle"></div>
      <div class="form-group"><label class="form-label">Platform</label>
        <select class="form-select" id="affPlatform">
          <option value="tiktok">TikTok</option><option value="shopee">Shopee</option>
          <option value="lazada">Lazada</option><option value="instagram">Instagram</option><option value="facebook">Facebook</option>
        </select>
      </div>
      <div class="form-group"><label class="form-label">Commission Rate</label><input type="number" class="form-input" id="affCommission" step="0.01" placeholder="0.10 = 10%"></div>
      <div class="form-group"><label class="form-label">Tier</label>
        <select class="form-select" id="affTier"><option value="standard">Standard</option><option value="silver">Silver</option><option value="gold">Gold</option><option value="vip">VIP</option></select>
      </div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitCreateAffiliate()">Create</button>
  `);
}

async function submitCreateAffiliate() {
  const name = document.getElementById('affName').value.trim();
  const email = document.getElementById('affEmail').value.trim();
  if (!name || !email) { toast('Name and email required', 'warning'); return; }
  const result = await apiPost('/affiliates', {
    name, email,
    phone: document.getElementById('affPhone').value.trim() || null,
    social_handle: document.getElementById('affHandle').value.trim() || null,
    platform: document.getElementById('affPlatform').value,
    commission_rate: parseFloat(document.getElementById('affCommission').value) || 0.1,
    tier: document.getElementById('affTier').value
  });
  if (result && (result.success || result.id)) { closeModal(); toast('Affiliate created', 'success'); loadAffiliates(); }
}

async function showEditAffiliateModal(id) {
  const data = await api(`/affiliates`);
  if (!data) return;
  const affiliates = data.affiliates || data || [];
  const a = affiliates.find(x => x.id === id);
  if (!a) { toast('Affiliate not found', 'error'); return; }
  openModal('Edit Affiliate', `
    <div class="form-grid">
      <div class="form-group"><label class="form-label">Name *</label><input type="text" class="form-input" id="affEditName" value="${esc(a.name)}"></div>
      <div class="form-group"><label class="form-label">Email *</label><input type="email" class="form-input" id="affEditEmail" value="${esc(a.email || '')}"></div>
      <div class="form-group"><label class="form-label">Phone</label><input type="text" class="form-input" id="affEditPhone" value="${esc(a.phone || '')}"></div>
      <div class="form-group"><label class="form-label">Social Handle</label><input type="text" class="form-input" id="affEditHandle" value="${esc(a.social_handle || '')}"></div>
      <div class="form-group"><label class="form-label">Commission Rate</label><input type="number" class="form-input" id="affEditCommission" step="0.01" value="${a.commission_rate || ''}"></div>
      <div class="form-group"><label class="form-label">Tier</label>
        <select class="form-select" id="affEditTier">
          ${['standard','silver','gold','vip'].map(t => `<option value="${t}" ${a.tier === t ? 'selected' : ''}>${t}</option>`).join('')}
        </select>
      </div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitEditAffiliate(${id})">Save</button>
  `);
}

async function submitEditAffiliate(id) {
  const name = document.getElementById('affEditName').value.trim();
  const email = document.getElementById('affEditEmail').value.trim();
  if (!name || !email) { toast('Name and email required', 'warning'); return; }
  const result = await apiPut(`/affiliates/${id}`, {
    name, email,
    phone: document.getElementById('affEditPhone').value.trim() || null,
    social_handle: document.getElementById('affEditHandle').value.trim() || null,
    commission_rate: parseFloat(document.getElementById('affEditCommission').value) || null,
    tier: document.getElementById('affEditTier').value
  });
  if (result && (result.success || result.id)) { closeModal(); toast('Affiliate updated', 'success'); loadAffiliates(); }
}

async function showAffiliateCommissions(id, name) {
  const data = await api(`/affiliates/${id}/commissions`);
  const commissions = (data && (data.commissions || data)) || [];
  const rows = commissions.length > 0
    ? commissions.map(c => `<tr>
        <td>${mono(c.id)}</td>
        <td>${mono(c.order_id || '\u2014')}</td>
        <td>${fmtPrice(c.sale_amount)}</td>
        <td>${fmtPrice(c.commission_amount)}</td>
        <td>${badge(c.status)}</td>
        <td>${fmtDate(c.created_at)}</td>
      </tr>`).join('')
    : '<tr><td colspan="6" class="empty-state"><p>No commissions</p></td></tr>';

  openModal(`Commissions: ${name}`, `
    <div class="table-wrapper"><table>
      <thead><tr><th>ID</th><th>Order</th><th>Sale</th><th>Commission</th><th>Status</th><th>Date</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>
  `, `<button class="btn btn-secondary" onclick="closeModal()">Close</button>`, 'modal-lg');
}

async function showAffiliateSamples(id, name) {
  const data = await api(`/affiliates/${id}/samples`);
  const samples = (data && (data.samples || data)) || [];
  const rows = samples.length > 0
    ? samples.map(s => `<tr>
        <td>${mono(s.id)}</td>
        <td>${esc(s.product_name || s.product_id)}</td>
        <td>${s.qty || 0}</td>
        <td>${badge(s.status)}</td>
        <td>${s.tracking_number ? trackingId(s.tracking_number) : '\u2014'}</td>
        <td>
          ${s.status === 'pending' ? `<button class="btn btn-xs btn-primary" onclick="approveSample(${s.id}, ${id}, '${esc(name)}')">Approve</button>` : ''}
          ${s.status === 'approved' ? `<button class="btn btn-xs btn-primary" onclick="shipSample(${s.id}, ${id}, '${esc(name)}')">Ship</button>` : ''}
        </td>
      </tr>`).join('')
    : '<tr><td colspan="6" class="empty-state"><p>No samples</p></td></tr>';

  openModal(`Samples: ${name}`, `
    <div style="margin-bottom:12px"><button class="btn btn-sm btn-primary" onclick="closeModal(); showCreateSampleModal(${id}, '${esc(name)}')">+ Request Sample</button></div>
    <div class="table-wrapper"><table>
      <thead><tr><th>ID</th><th>Product</th><th>Qty</th><th>Status</th><th>Tracking</th><th>Actions</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>
  `, `<button class="btn btn-secondary" onclick="closeModal()">Close</button>`, 'modal-lg');
}

function showCreateSampleModal(affiliateId, name) {
  openModal(`New Sample for ${name}`, `
    <div class="form-grid">
      <div class="form-group"><label class="form-label">Product ID *</label><input type="number" class="form-input" id="smpProductId"></div>
      <div class="form-group"><label class="form-label">Quantity *</label><input type="number" class="form-input" id="smpQty" value="1" min="1"></div>
      <div class="form-group full"><label class="form-label">Notes</label><textarea class="form-textarea" id="smpNotes" rows="2"></textarea></div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitCreateSample(${affiliateId})">Submit</button>
  `);
}

async function submitCreateSample(affiliateId) {
  const productId = parseInt(document.getElementById('smpProductId').value);
  const qty = parseInt(document.getElementById('smpQty').value);
  if (!productId || !qty) { toast('Product ID and quantity required', 'warning'); return; }
  const result = await apiPost('/affiliate_samples', {
    affiliate_id: affiliateId, product_id: productId, qty,
    notes: document.getElementById('smpNotes').value.trim() || null
  });
  if (result && (result.success || result.id)) { closeModal(); toast('Sample request created', 'success'); }
}

async function approveSample(sampleId, affId, name) {
  const result = await apiPost(`/affiliate_samples/${sampleId}/approve`, {});
  if (result && (result.success || result.id)) { toast('Sample approved', 'success'); showAffiliateSamples(affId, name); }
}

async function shipSample(sampleId, affId, name) {
  const tracking = prompt('Tracking number:');
  if (!tracking) return;
  const result = await apiPost(`/affiliate_samples/${sampleId}/ship`, { tracking_number: tracking });
  if (result && (result.success || result.id)) { toast('Sample shipped', 'success'); showAffiliateSamples(affId, name); }
}

async function showCommissionsPanel() {
  const data = await api('/affiliate_commissions');
  const commissions = (data && (data.commissions || data)) || [];
  const unpaid = commissions.filter(c => c.status === 'pending' || c.status === 'unpaid');

  const rows = commissions.length > 0
    ? commissions.map(c => `<tr>
        <td><input type="checkbox" class="comm-cb" value="${c.id}" ${c.status === 'pending' || c.status === 'unpaid' ? '' : 'disabled'}></td>
        <td>${mono(c.id)}</td>
        <td>${esc(c.affiliate_name || c.affiliate_id)}</td>
        <td>${fmtPrice(c.commission_amount)}</td>
        <td>${badge(c.status)}</td>
        <td>${fmtDate(c.created_at)}</td>
      </tr>`).join('')
    : '<tr><td colspan="6" class="empty-state"><p>No commissions</p></td></tr>';

  openModal('All Commissions', `
    <div style="margin-bottom:12px">
      <button class="btn btn-sm btn-primary" onclick="bulkPayCommissions()">Bulk Pay Selected</button>
      <span style="margin-left:8px;opacity:0.7">${unpaid.length} unpaid</span>
    </div>
    <div class="table-wrapper"><table>
      <thead><tr><th><input type="checkbox" onchange="document.querySelectorAll('.comm-cb:not(:disabled)').forEach(c=>c.checked=this.checked)"></th><th>ID</th><th>Affiliate</th><th>Amount</th><th>Status</th><th>Date</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>
  `, `<button class="btn btn-secondary" onclick="closeModal()">Close</button>`, 'modal-lg');
}

async function bulkPayCommissions() {
  const ids = [...document.querySelectorAll('.comm-cb:checked')].map(c => parseInt(c.value));
  if (!ids.length) { toast('Select commissions to pay', 'warning'); return; }
  const result = await apiPost('/affiliate_commissions/bulk_pay', { commission_ids: ids });
  if (result && (result.success || result.paid)) { toast(`Paid ${ids.length} commissions`, 'success'); showCommissionsPanel(); }
}

/* ===== STOCK SYNC ===== */

async function loadStockSync() {
  const el = document.getElementById('page-stock-sync');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(4);

  const data = await api('/stock_sync/rules');
  if (!data) { el.innerHTML = '<div class="empty-state"><p>Unable to load stock sync rules</p></div>'; return; }
  const rules = data.rules || data || [];

  el.innerHTML = `
    <div class="page-action-bar">
      <div class="page-action-bar-left">
        <input type="text" class="form-input" id="syncSearch" placeholder="Search rules\u2026" style="width:240px" oninput="filterSyncTable()">
      </div>
      <div class="page-action-bar-right">
        <button class="btn btn-sm btn-secondary" onclick="triggerStockSync()">Push Sync Now</button>
        <button class="btn btn-primary" onclick="showCreateSyncRuleModal()">+ New Rule</button>
      </div>
    </div>
    <div class="card">
      <div class="card-header"><div><div class="card-title">Sync Rules</div><div class="card-subtitle">${rules.length} rules</div></div></div>
      <div class="table-wrapper"><table>
        <thead><tr><th>ID</th><th>Item</th><th>Platform</th><th>Platform SKU</th><th>Sync Mode</th><th>Buffer Qty</th><th>Status</th><th>Last Sync</th><th>Actions</th></tr></thead>
        <tbody id="sync-rules-tbody">
          ${rules.length > 0 ? rules.map(r => `<tr data-name="${esc((r.item_name || '') + ' ' + (r.platform_sku || ''))}">
            <td>${mono(r.id)}</td>
            <td>${esc(r.item_name || r.item_id)}</td>
            <td>${platformBadge(r.platform)}</td>
            <td>${mono(r.platform_sku)}</td>
            <td>${badge(r.sync_mode || 'auto')}</td>
            <td>${r.buffer_qty != null ? r.buffer_qty : '\u2014'}</td>
            <td>${badge(r.status || 'active')}</td>
            <td>${fmtDate(r.last_synced_at)}</td>
            <td>
              <button class="btn btn-xs btn-secondary" onclick="showEditSyncRuleModal(${r.id})">Edit</button>
              <button class="btn btn-xs btn-secondary" onclick="showSyncLogs(${r.id})">Logs</button>
            </td>
          </tr>`).join('') : '<tr><td colspan="9" class="empty-state"><p>No sync rules</p></td></tr>'}
        </tbody>
      </table></div>
    </div>
  `;
}

function filterSyncTable() {
  const q = (document.getElementById('syncSearch').value || '').toLowerCase();
  document.querySelectorAll('#sync-rules-tbody tr').forEach(r => {
    r.style.display = !q || (r.dataset.name || '').toLowerCase().includes(q) ? '' : 'none';
  });
}

function showCreateSyncRuleModal() {
  openModal('New Sync Rule', `
    <div class="form-grid">
      <div class="form-group"><label class="form-label">Item ID *</label><input type="number" class="form-input" id="syncItemId"></div>
      <div class="form-group"><label class="form-label">Platform *</label>
        <select class="form-select" id="syncPlatform">
          <option value="shopee">Shopee</option><option value="lazada">Lazada</option>
          <option value="tiktok">TikTok</option><option value="shopify">Shopify</option>
        </select>
      </div>
      <div class="form-group"><label class="form-label">Platform SKU *</label><input type="text" class="form-input" id="syncPlatformSku"></div>
      <div class="form-group"><label class="form-label">Sync Mode</label>
        <select class="form-select" id="syncMode"><option value="auto">Auto</option><option value="manual">Manual</option></select>
      </div>
      <div class="form-group"><label class="form-label">Buffer Qty</label><input type="number" class="form-input" id="syncBuffer" value="0" min="0"></div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitCreateSyncRule()">Create</button>
  `);
}

async function submitCreateSyncRule() {
  const itemId = parseInt(document.getElementById('syncItemId').value);
  const platformSku = document.getElementById('syncPlatformSku').value.trim();
  if (!itemId || !platformSku) { toast('Item ID and Platform SKU required', 'warning'); return; }
  const result = await apiPost('/stock_sync/rules', {
    item_id: itemId,
    platform: document.getElementById('syncPlatform').value,
    platform_sku: platformSku,
    sync_mode: document.getElementById('syncMode').value,
    buffer_qty: parseInt(document.getElementById('syncBuffer').value) || 0
  });
  if (result && (result.success || result.id)) { closeModal(); toast('Sync rule created', 'success'); loadStockSync(); }
}

async function showEditSyncRuleModal(id) {
  const data = await api('/stock_sync/rules');
  if (!data) return;
  const rules = data.rules || data || [];
  const r = rules.find(x => x.id === id);
  if (!r) { toast('Rule not found', 'error'); return; }
  openModal('Edit Sync Rule', `
    <div class="form-grid">
      <div class="form-group"><label class="form-label">Platform SKU</label><input type="text" class="form-input" id="syncEditSku" value="${esc(r.platform_sku || '')}"></div>
      <div class="form-group"><label class="form-label">Sync Mode</label>
        <select class="form-select" id="syncEditMode">
          <option value="auto" ${r.sync_mode === 'auto' ? 'selected' : ''}>Auto</option>
          <option value="manual" ${r.sync_mode === 'manual' ? 'selected' : ''}>Manual</option>
        </select>
      </div>
      <div class="form-group"><label class="form-label">Buffer Qty</label><input type="number" class="form-input" id="syncEditBuffer" value="${r.buffer_qty || 0}" min="0"></div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitEditSyncRule(${id})">Save</button>
  `);
}

async function submitEditSyncRule(id) {
  const result = await apiPut(`/stock_sync/rules/${id}`, {
    platform_sku: document.getElementById('syncEditSku').value.trim(),
    sync_mode: document.getElementById('syncEditMode').value,
    buffer_qty: parseInt(document.getElementById('syncEditBuffer').value) || 0
  });
  if (result && (result.success || result.id)) { closeModal(); toast('Rule updated', 'success'); loadStockSync(); }
}

async function triggerStockSync() {
  const result = await apiPost('/stock_sync/push', {});
  if (result && (result.success || result.synced != null)) { toast(`Stock sync complete: ${result.synced || 0} updated`, 'success'); loadStockSync(); }
}

async function showSyncLogs(ruleId) {
  const data = await api('/stock_sync/logs', { rule_id: ruleId });
  const logs = (data && (data.logs || data)) || [];
  const rows = logs.length > 0
    ? logs.map(l => `<tr>
        <td>${fmtDate(l.created_at || l.synced_at)}</td>
        <td>${badge(l.status || l.result)}</td>
        <td>${l.qty_pushed != null ? l.qty_pushed : '\u2014'}</td>
        <td>${esc(l.error_message || l.message || '\u2014')}</td>
      </tr>`).join('')
    : '<tr><td colspan="4" class="empty-state"><p>No sync logs</p></td></tr>';

  openModal(`Sync Logs (Rule #${ruleId})`, `
    <div class="table-wrapper"><table>
      <thead><tr><th>Time</th><th>Status</th><th>Qty Pushed</th><th>Message</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>
  `, `<button class="btn btn-secondary" onclick="closeModal()">Close</button>`, 'modal-lg');
}
