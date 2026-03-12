/* ========== NEXRAY Messaging Module — Inbox & Canned Responses ========== */

let inboxConversations = [];
let inboxChannels = [];
let activeConversationId = null;

const PLATFORM_COLORS = {
  messenger: { bg: 'rgba(24,119,242,0.15)', color: '#1877F2', label: 'Messenger' },
  instagram: { bg: 'rgba(167,139,250,0.15)', color: '#A78BFA', label: 'Instagram' },
  whatsapp:  { bg: 'rgba(37,211,102,0.15)',  color: '#25D366', label: 'WhatsApp' },
  viber:     { bg: 'rgba(121,92,174,0.15)',   color: '#795CAE', label: 'Viber' },
};

function platformBadge(platform) {
  const p = PLATFORM_COLORS[(platform || '').toLowerCase()] || { bg: 'var(--color-surface-2)', color: 'var(--color-text-muted)', label: platform || 'Unknown' };
  return `<span style="display:inline-block;padding:2px 8px;border-radius:var(--radius-full);font-size:var(--text-xs);font-weight:600;background:${p.bg};color:${p.color}">${esc(p.label)}</span>`;
}

function inboxStyles() {
  if (document.getElementById('inbox-styles')) return;
  const style = document.createElement('style');
  style.id = 'inbox-styles';
  style.textContent = `
    .inbox-container { display:grid; grid-template-columns:360px 1fr; height:calc(100vh - 140px); min-height:500px; border:1px solid var(--color-divider); border-radius:var(--radius-lg); overflow:hidden; background:var(--color-surface); }
    .inbox-list { border-right:1px solid var(--color-divider); display:flex; flex-direction:column; overflow:hidden; }
    .inbox-list-header { padding:var(--space-3) var(--space-4); border-bottom:1px solid var(--color-divider); display:flex; flex-direction:column; gap:var(--space-2); }
    .inbox-search { width:100%; padding:var(--space-2) var(--space-3); border:1px solid var(--color-border); border-radius:var(--radius-md); background:var(--color-surface-2); color:var(--color-text); font-size:var(--text-sm); }
    .inbox-filters { display:flex; gap:var(--space-2); }
    .inbox-filter-select { padding:var(--space-1) var(--space-2); border:1px solid var(--color-border); border-radius:var(--radius-sm); background:var(--color-surface-2); color:var(--color-text); font-size:var(--text-xs); flex:1; }
    .inbox-conversations { flex:1; overflow-y:auto; }
    .inbox-conv-row { display:flex; align-items:center; gap:var(--space-3); padding:var(--space-3) var(--space-4); border-bottom:1px solid var(--color-divider); cursor:pointer; transition:background var(--transition-interactive); }
    .inbox-conv-row:hover { background:var(--color-surface-2); }
    .inbox-conv-row.active { background:var(--color-primary-subtle); border-left:3px solid var(--color-primary); }
    .inbox-conv-info { flex:1; min-width:0; }
    .inbox-conv-name { font-weight:600; font-size:var(--text-sm); color:var(--color-text); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .inbox-conv-preview { font-size:var(--text-xs); color:var(--color-text-muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; margin-top:2px; }
    .inbox-conv-meta { display:flex; flex-direction:column; align-items:flex-end; gap:2px; flex-shrink:0; }
    .inbox-conv-time { font-size:10px; color:var(--color-text-faint); white-space:nowrap; }
    .inbox-unread-badge { background:var(--color-primary); color:#fff; font-size:10px; font-weight:700; padding:1px 6px; border-radius:var(--radius-full); }
    .inbox-thread { display:flex; flex-direction:column; overflow:hidden; }
    .inbox-thread-header { padding:var(--space-3) var(--space-4); border-bottom:1px solid var(--color-divider); display:flex; align-items:center; justify-content:space-between; gap:var(--space-3); }
    .inbox-thread-title { font-weight:600; font-size:var(--text-base); }
    .inbox-thread-actions { display:flex; gap:var(--space-2); align-items:center; }
    .inbox-messages { flex:1; overflow-y:auto; padding:var(--space-4); display:flex; flex-direction:column; gap:var(--space-3); }
    .msg-bubble { max-width:70%; padding:var(--space-3) var(--space-4); border-radius:var(--radius-lg); font-size:var(--text-sm); line-height:1.5; word-break:break-word; }
    .msg-bubble.incoming { align-self:flex-start; background:var(--color-surface-2); color:var(--color-text); border-bottom-left-radius:var(--radius-sm); }
    .msg-bubble.outgoing { align-self:flex-end; background:var(--color-primary); color:#fff; border-bottom-right-radius:var(--radius-sm); }
    .msg-bubble .msg-time { font-size:10px; opacity:0.65; margin-top:var(--space-1); display:block; }
    .msg-bubble.outgoing .msg-time { text-align:right; }
    .inbox-compose { padding:var(--space-3) var(--space-4); border-top:1px solid var(--color-divider); display:flex; gap:var(--space-2); align-items:flex-end; }
    .inbox-compose textarea { flex:1; resize:none; padding:var(--space-2) var(--space-3); border:1px solid var(--color-border); border-radius:var(--radius-md); background:var(--color-surface-2); color:var(--color-text); font-size:var(--text-sm); min-height:40px; max-height:120px; }
    .inbox-empty { display:flex; align-items:center; justify-content:center; height:100%; color:var(--color-text-faint); font-size:var(--text-sm); }
    @media (max-width:768px) {
      .inbox-container { grid-template-columns:1fr; height:auto; }
      .inbox-list { max-height:300px; }
    }
  `;
  document.head.appendChild(style);
}

// ===== INBOX =====

async function loadInbox() {
  inboxStyles();
  const el = document.getElementById('page-inbox');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(3);

  const [channelsRes, convsRes] = await Promise.all([
    api('/inbox_channels'),
    api('/conversations'),
  ]);

  inboxChannels = channelsRes?.channels || [];
  inboxConversations = convsRes?.conversations || [];
  activeConversationId = null;

  renderInbox(el);
}

function renderInbox(el) {
  el.innerHTML = `
    <div class="page-action-bar">
      <div class="page-action-bar-left">
        <span style="font-size:var(--text-xs);color:var(--color-text-muted)">${inboxConversations.length} conversations</span>
      </div>
      <div class="page-action-bar-right">
        <button class="btn btn-sm btn-ghost" onclick="showChannelsModal()">Channels</button>
      </div>
    </div>
    <div class="inbox-container">
      <div class="inbox-list">
        <div class="inbox-list-header">
          <input class="inbox-search" type="text" placeholder="Search conversations..." oninput="filterInboxConversations()" id="inboxSearch">
          <div class="inbox-filters">
            <select class="inbox-filter-select" id="inboxStatusFilter" onchange="filterInboxConversations()">
              <option value="">All Status</option>
              <option value="open" selected>Open</option>
              <option value="resolved">Resolved</option>
              <option value="archived">Archived</option>
            </select>
            <select class="inbox-filter-select" id="inboxChannelFilter" onchange="filterInboxConversations()">
              <option value="">All Channels</option>
              ${inboxChannels.map(ch => `<option value="${ch.id}">${esc(ch.channel_name)}</option>`).join('')}
            </select>
          </div>
        </div>
        <div class="inbox-conversations" id="inboxConvList"></div>
      </div>
      <div class="inbox-thread" id="inboxThread">
        <div class="inbox-empty">Select a conversation to view messages</div>
      </div>
    </div>
  `;

  filterInboxConversations();
}

async function filterInboxConversations() {
  const search = (document.getElementById('inboxSearch')?.value || '').trim();
  const status = document.getElementById('inboxStatusFilter')?.value || '';
  const channelId = document.getElementById('inboxChannelFilter')?.value || '';

  const params = {};
  if (search) params.search = search;
  if (status) params.status = status;
  if (channelId) params.channel_id = channelId;

  const data = await api('/conversations', params);
  inboxConversations = data?.conversations || [];
  renderConversationList();
}

function renderConversationList() {
  const listEl = document.getElementById('inboxConvList');
  if (!listEl) return;

  if (inboxConversations.length === 0) {
    listEl.innerHTML = '<div class="inbox-empty">No conversations found</div>';
    return;
  }

  listEl.innerHTML = inboxConversations.map(c => {
    const isActive = c.id === activeConversationId;
    const platform = (c.platform || '').toLowerCase();
    const unread = c.unread_count || 0;
    return `
      <div class="inbox-conv-row ${isActive ? 'active' : ''}" onclick="openConversation('${c.id}')">
        <div style="flex-shrink:0">${platformBadge(platform)}</div>
        <div class="inbox-conv-info">
          <div class="inbox-conv-name">${esc(c.customer_name || 'Unknown')}</div>
          <div class="inbox-conv-preview">${esc(c.last_message_preview || '')}</div>
        </div>
        <div class="inbox-conv-meta">
          <span class="inbox-conv-time">${fmtDate(c.last_message_at || c.updated_at)}</span>
          ${unread > 0 ? `<span class="inbox-unread-badge">${unread}</span>` : ''}
        </div>
      </div>
    `;
  }).join('');
}

async function openConversation(id) {
  activeConversationId = id;
  renderConversationList();

  const threadEl = document.getElementById('inboxThread');
  threadEl.innerHTML = '<div class="inbox-empty">Loading...</div>';

  const [convRes, msgsRes] = await Promise.all([
    api(`/conversations/${id}`),
    api(`/conversations/${id}/messages`),
  ]);

  if (!convRes) {
    threadEl.innerHTML = '<div class="inbox-empty">Failed to load conversation</div>';
    return;
  }

  const conv = convRes.conversation || convRes;
  const messages = msgsRes?.messages || [];
  const statusLabel = conv.status || 'open';

  threadEl.innerHTML = `
    <div class="inbox-thread-header">
      <div>
        <div class="inbox-thread-title">${esc(conv.customer_name || 'Unknown')} ${platformBadge(conv.platform)}</div>
        <div style="font-size:var(--text-xs);color:var(--color-text-muted);margin-top:2px">
          ${badge(statusLabel)}
          ${conv.priority ? `<span style="margin-left:var(--space-2)">${badge(conv.priority)}</span>` : ''}
          ${conv.assigned_to ? `<span style="margin-left:var(--space-2);font-size:var(--text-xs)">Assigned: ${esc(conv.assigned_to)}</span>` : ''}
        </div>
      </div>
      <div class="inbox-thread-actions">
        <button class="btn btn-sm btn-ghost" onclick="showAssignModal('${id}')">Assign</button>
        ${statusLabel === 'open'
          ? `<button class="btn btn-sm btn-primary" onclick="resolveConversation('${id}')">Resolve</button>`
          : `<button class="btn btn-sm btn-ghost" onclick="reopenConversation('${id}')">Reopen</button>`
        }
        <button class="btn btn-sm btn-ghost" onclick="showEditConversationModal('${id}')">Edit</button>
      </div>
    </div>
    <div class="inbox-messages" id="inboxMessages">
      ${messages.length === 0
        ? '<div class="inbox-empty">No messages yet</div>'
        : messages.map(m => renderMessageBubble(m)).join('')
      }
    </div>
    <div class="inbox-compose">
      <textarea id="inboxMsgInput" rows="1" placeholder="Type a message..." onkeydown="handleMsgKeydown(event, '${id}')"></textarea>
      <button class="btn btn-sm btn-ghost" onclick="aiDraftMessage('${id}')" title="AI Draft" style="color:var(--color-primary)">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a4 4 0 0 1 4 4v2a4 4 0 0 1-8 0V6a4 4 0 0 1 4-4z"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><path d="M9 18h6"/><path d="M12 22v-4"/></svg>
      </button>
      <button class="btn btn-sm btn-primary" onclick="sendMessage('${id}')">Send</button>
    </div>
  `;

  const msgsContainer = document.getElementById('inboxMessages');
  if (msgsContainer) msgsContainer.scrollTop = msgsContainer.scrollHeight;
}

function renderMessageBubble(m) {
  const isOutgoing = (m.sender_type || '').toLowerCase() === 'agent' || (m.sender_type || '').toLowerCase() === 'system';
  const cls = isOutgoing ? 'outgoing' : 'incoming';
  return `
    <div class="msg-bubble ${cls}">
      ${esc(m.content || '')}
      <span class="msg-time">${fmtDate(m.created_at)}</span>
    </div>
  `;
}

function handleMsgKeydown(e, convId) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage(convId);
  }
}

async function sendMessage(convId) {
  const input = document.getElementById('inboxMsgInput');
  if (!input) return;
  const content = input.value.trim();
  if (!content) return;

  input.value = '';
  const result = await apiPost(`/conversations/${convId}/messages`, {
    content,
    sender_type: 'agent',
  });

  if (result && (result.success || result.message)) {
    await openConversation(convId);
  }
}

async function aiDraftMessage(convId) {
  const input = document.getElementById('inboxMsgInput');
  if (!input) return;

  input.value = 'Generating AI draft...';
  input.disabled = true;

  const result = await apiPost(`/conversations/${convId}/messages/ai_draft`, {});
  input.disabled = false;

  if (result && result.draft) {
    input.value = result.draft;
  } else {
    input.value = '';
    toast('Failed to generate AI draft', 'error');
  }
}

async function resolveConversation(id) {
  const result = await apiPost(`/conversations/${id}/resolve`, {});
  if (result && result.success) {
    toast('Conversation resolved', 'success');
    await openConversation(id);
    filterInboxConversations();
  }
}

async function reopenConversation(id) {
  const result = await apiPost(`/conversations/${id}/reopen`, {});
  if (result && result.success) {
    toast('Conversation reopened', 'success');
    await openConversation(id);
    filterInboxConversations();
  }
}

function showAssignModal(convId) {
  openModal('Assign Conversation', `
    <div class="form-grid">
      <div class="form-group full">
        <label class="form-label">Assign to (username or ID)</label>
        <input type="text" class="form-input" id="assignToInput" placeholder="e.g. agent_name">
      </div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitAssign('${convId}')">Assign</button>
  `);
}

async function submitAssign(convId) {
  const assignedTo = document.getElementById('assignToInput').value.trim();
  if (!assignedTo) { toast('Please enter a name', 'warning'); return; }

  const result = await apiPost(`/conversations/${convId}/assign`, { assigned_to: assignedTo });
  if (result && result.success) {
    closeModal();
    toast('Conversation assigned', 'success');
    await openConversation(convId);
  }
}

function showEditConversationModal(convId) {
  const conv = inboxConversations.find(c => c.id === convId) || {};
  openModal('Edit Conversation', `
    <div class="form-grid">
      <div class="form-group">
        <label class="form-label">Customer Name</label>
        <input type="text" class="form-input" id="convEditName" value="${esc(conv.customer_name || '')}">
      </div>
      <div class="form-group">
        <label class="form-label">Priority</label>
        <select class="form-input" id="convEditPriority">
          <option value="">None</option>
          <option value="low" ${conv.priority === 'low' ? 'selected' : ''}>Low</option>
          <option value="medium" ${conv.priority === 'medium' ? 'selected' : ''}>Medium</option>
          <option value="high" ${conv.priority === 'high' ? 'selected' : ''}>High</option>
          <option value="urgent" ${conv.priority === 'urgent' ? 'selected' : ''}>Urgent</option>
        </select>
      </div>
      <div class="form-group full">
        <label class="form-label">Tags (comma-separated)</label>
        <input type="text" class="form-input" id="convEditTags" value="${esc(conv.tags_json || '')}" placeholder="vip, follow-up">
      </div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitEditConversation('${convId}')">Save</button>
  `);
}

async function submitEditConversation(convId) {
  const result = await apiPut(`/conversations/${convId}`, {
    customer_name: document.getElementById('convEditName').value.trim() || null,
    priority: document.getElementById('convEditPriority').value || null,
    tags_json: document.getElementById('convEditTags').value.trim() || null,
  });

  if (result && result.success) {
    closeModal();
    toast('Conversation updated', 'success');
    filterInboxConversations();
    await openConversation(convId);
  }
}

// ===== CHANNELS MODAL =====

function showChannelsModal() {
  openModal('Inbox Channels', `
    <div id="channelsModalBody"><div class="loading-skeleton skeleton-row"></div></div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Close</button>
    <button class="btn btn-primary" onclick="showCreateChannelModal()">+ Add Channel</button>
  `);
  loadChannelsInModal();
}

async function loadChannelsInModal() {
  const data = await api('/inbox_channels');
  const channels = data?.channels || [];
  const body = document.getElementById('channelsModalBody');
  if (!body) return;

  if (channels.length === 0) {
    body.innerHTML = '<p style="color:var(--color-text-muted);font-size:var(--text-sm)">No channels configured.</p>';
    return;
  }

  body.innerHTML = `
    <div class="table-wrapper">
      <table>
        <thead><tr><th>Platform</th><th>Name</th><th>Identifier</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>
          ${channels.map(ch => `<tr>
            <td>${platformBadge(ch.platform)}</td>
            <td style="font-weight:500">${esc(ch.channel_name)}</td>
            <td style="font-size:var(--text-xs);color:var(--color-text-muted)">${esc(ch.channel_identifier || '')}</td>
            <td>${ch.is_active ? '<span style="color:var(--color-success)">Active</span>' : '<span style="color:var(--color-text-faint)">Inactive</span>'}</td>
            <td>
              <button class="btn btn-sm btn-ghost" onclick="showEditChannelModal(${JSON.stringify(esc(JSON.stringify(ch))).slice(1,-1)})">Edit</button>
              <button class="btn btn-sm btn-ghost" style="color:var(--color-error)" onclick="deleteChannel('${ch.id}')">Delete</button>
            </td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function showCreateChannelModal() {
  closeModal();
  openModal('New Channel', `
    <div class="form-grid">
      <div class="form-group">
        <label class="form-label">Platform *</label>
        <select class="form-input" id="chPlatform">
          <option value="messenger">Messenger</option>
          <option value="instagram">Instagram</option>
          <option value="whatsapp">WhatsApp</option>
          <option value="viber">Viber</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Channel Name *</label>
        <input type="text" class="form-input" id="chName" placeholder="Main Page">
      </div>
      <div class="form-group">
        <label class="form-label">Identifier</label>
        <input type="text" class="form-input" id="chIdentifier" placeholder="page_id / phone">
      </div>
      <div class="form-group">
        <label class="form-label">Access Token</label>
        <input type="text" class="form-input" id="chToken" placeholder="token...">
      </div>
      <div class="form-group">
        <label class="form-label">Webhook Secret</label>
        <input type="text" class="form-input" id="chWebhook" placeholder="secret...">
      </div>
      <div class="form-group">
        <label class="form-label">Active</label>
        <select class="form-input" id="chActive">
          <option value="true">Yes</option>
          <option value="false">No</option>
        </select>
      </div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="showChannelsModal()">Back</button>
    <button class="btn btn-primary" onclick="submitCreateChannel()">Create</button>
  `);
}

async function submitCreateChannel() {
  const platform = document.getElementById('chPlatform').value;
  const channelName = document.getElementById('chName').value.trim();
  if (!channelName) { toast('Channel name is required', 'warning'); return; }

  const result = await apiPost('/inbox_channels', {
    platform,
    channel_name: channelName,
    channel_identifier: document.getElementById('chIdentifier').value.trim() || null,
    access_token: document.getElementById('chToken').value.trim() || null,
    webhook_secret: document.getElementById('chWebhook').value.trim() || null,
    is_active: document.getElementById('chActive').value === 'true',
  });

  if (result && result.success) {
    toast('Channel created', 'success');
    showChannelsModal();
  }
}

function showEditChannelModal(chJson) {
  const ch = JSON.parse(chJson);
  closeModal();
  openModal('Edit Channel', `
    <div class="form-grid">
      <div class="form-group">
        <label class="form-label">Platform *</label>
        <select class="form-input" id="chEditPlatform">
          ${['messenger','instagram','whatsapp','viber'].map(p =>
            `<option value="${p}" ${ch.platform === p ? 'selected' : ''}>${p.charAt(0).toUpperCase() + p.slice(1)}</option>`
          ).join('')}
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Channel Name *</label>
        <input type="text" class="form-input" id="chEditName" value="${esc(ch.channel_name || '')}">
      </div>
      <div class="form-group">
        <label class="form-label">Identifier</label>
        <input type="text" class="form-input" id="chEditIdentifier" value="${esc(ch.channel_identifier || '')}">
      </div>
      <div class="form-group">
        <label class="form-label">Access Token</label>
        <input type="text" class="form-input" id="chEditToken" value="${esc(ch.access_token || '')}">
      </div>
      <div class="form-group">
        <label class="form-label">Webhook Secret</label>
        <input type="text" class="form-input" id="chEditWebhook" value="${esc(ch.webhook_secret || '')}">
      </div>
      <div class="form-group">
        <label class="form-label">Active</label>
        <select class="form-input" id="chEditActive">
          <option value="true" ${ch.is_active ? 'selected' : ''}>Yes</option>
          <option value="false" ${!ch.is_active ? 'selected' : ''}>No</option>
        </select>
      </div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="showChannelsModal()">Back</button>
    <button class="btn btn-primary" onclick="submitEditChannel('${ch.id}')">Save</button>
  `);
}

async function submitEditChannel(id) {
  const result = await apiPut(`/inbox_channels/${id}`, {
    platform: document.getElementById('chEditPlatform').value,
    channel_name: document.getElementById('chEditName').value.trim(),
    channel_identifier: document.getElementById('chEditIdentifier').value.trim() || null,
    access_token: document.getElementById('chEditToken').value.trim() || null,
    webhook_secret: document.getElementById('chEditWebhook').value.trim() || null,
    is_active: document.getElementById('chEditActive').value === 'true',
  });

  if (result && result.success) {
    toast('Channel updated', 'success');
    showChannelsModal();
  }
}

async function deleteChannel(id) {
  if (!confirm('Delete this channel? This cannot be undone.')) return;
  const result = await apiDelete(`/inbox_channels/${id}`);
  if (result && result.success) {
    toast('Channel deleted', 'success');
    loadChannelsInModal();
  }
}

// ===== CANNED RESPONSES & MESSAGE TEMPLATES =====

async function loadCannedResponses() {
  const el = document.getElementById('page-canned-responses');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(3);

  const [cannedRes, templatesRes] = await Promise.all([
    api('/canned_responses'),
    api('/message_templates'),
  ]);

  const canned = cannedRes?.canned_responses || [];
  const templates = templatesRes?.templates || [];

  const categories = [...new Set(canned.map(c => c.category).filter(Boolean))];

  el.innerHTML = `
    <div class="page-action-bar">
      <div class="page-action-bar-left">
        <span style="font-size:var(--text-xs);color:var(--color-text-muted)">${canned.length} quick replies, ${templates.length} templates</span>
      </div>
      <div class="page-action-bar-right">
        <button class="btn btn-primary" onclick="showCreateCannedModal()">+ New Quick Reply</button>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div><div class="card-title">Quick Replies</div><div class="card-subtitle">Reusable response snippets with shortcuts</div></div>
        <div>
          <select class="form-input" id="cannedCategoryFilter" onchange="filterCannedTable()" style="font-size:var(--text-xs);padding:var(--space-1) var(--space-2)">
            <option value="">All Categories</option>
            ${categories.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join('')}
          </select>
        </div>
      </div>
      <div class="table-wrapper">
        <table id="cannedTable">
          <thead><tr><th>Shortcut</th><th>Title</th><th>Category</th><th>Content</th><th>Actions</th></tr></thead>
          <tbody>
            ${canned.length === 0
              ? '<tr><td colspan="5" style="text-align:center;color:var(--color-text-muted)">No quick replies yet</td></tr>'
              : canned.map(c => `<tr data-category="${esc(c.category || '')}">
                  <td><span class="mono" style="color:var(--color-primary)">${esc(c.shortcut || '')}</span></td>
                  <td style="font-weight:500">${esc(c.title)}</td>
                  <td>${c.category ? badge(c.category) : '\u2014'}</td>
                  <td style="font-size:var(--text-xs);color:var(--color-text-muted);max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc((c.content || '').substring(0, 100))}</td>
                  <td>
                    <button class="btn btn-sm btn-ghost" onclick="showEditCannedModal(${JSON.stringify(esc(JSON.stringify(c))).slice(1,-1)})">Edit</button>
                    <button class="btn btn-sm btn-ghost" style="color:var(--color-error)" onclick="deleteCanned('${c.id}')">Delete</button>
                  </td>
                </tr>`).join('')
            }
          </tbody>
        </table>
      </div>
    </div>

    <div class="card" style="margin-top:var(--space-6)">
      <div class="card-header">
        <div><div class="card-title">Message Templates</div><div class="card-subtitle">Platform-approved message templates</div></div>
        <div>
          <button class="btn btn-sm btn-primary" onclick="showCreateTemplateModal()">+ New Template</button>
        </div>
      </div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>Platform</th><th>Name</th><th>Content</th><th>Approved</th><th>Actions</th></tr></thead>
          <tbody>
            ${templates.length === 0
              ? '<tr><td colspan="5" style="text-align:center;color:var(--color-text-muted)">No templates yet</td></tr>'
              : templates.map(t => `<tr>
                  <td>${platformBadge(t.platform)}</td>
                  <td style="font-weight:500">${esc(t.template_name)}</td>
                  <td style="font-size:var(--text-xs);color:var(--color-text-muted);max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc((t.content || '').substring(0, 100))}</td>
                  <td>${t.is_approved ? '<span style="color:var(--color-success)">Approved</span>' : '<span style="color:var(--color-warning)">Pending</span>'}</td>
                  <td>
                    <button class="btn btn-sm btn-ghost" onclick="showEditTemplateModal(${JSON.stringify(esc(JSON.stringify(t))).slice(1,-1)})">Edit</button>
                  </td>
                </tr>`).join('')
            }
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function filterCannedTable() {
  const cat = document.getElementById('cannedCategoryFilter')?.value || '';
  const rows = document.querySelectorAll('#cannedTable tbody tr');
  rows.forEach(row => {
    if (!cat || row.dataset.category === cat) {
      row.style.display = '';
    } else {
      row.style.display = 'none';
    }
  });
}

// ===== CANNED CRUD =====

function showCreateCannedModal() {
  openModal('New Quick Reply', `
    <div class="form-grid">
      <div class="form-group">
        <label class="form-label">Title *</label>
        <input type="text" class="form-input" id="cannedTitle" placeholder="Greeting">
      </div>
      <div class="form-group">
        <label class="form-label">Shortcut</label>
        <input type="text" class="form-input" id="cannedShortcut" placeholder="/greet">
      </div>
      <div class="form-group">
        <label class="form-label">Category</label>
        <input type="text" class="form-input" id="cannedCategory" placeholder="general">
      </div>
      <div class="form-group">
        <label class="form-label">Language</label>
        <input type="text" class="form-input" id="cannedLang" placeholder="en" value="en">
      </div>
      <div class="form-group full">
        <label class="form-label">Content *</label>
        <textarea class="form-input" id="cannedContent" rows="4" placeholder="Hi! How can I help you today?"></textarea>
      </div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitCreateCanned()">Create</button>
  `);
}

async function submitCreateCanned() {
  const title = document.getElementById('cannedTitle').value.trim();
  const content = document.getElementById('cannedContent').value.trim();
  if (!title || !content) { toast('Title and content are required', 'warning'); return; }

  const result = await apiPost('/canned_responses', {
    title,
    content,
    shortcut: document.getElementById('cannedShortcut').value.trim() || null,
    category: document.getElementById('cannedCategory').value.trim() || null,
    language: document.getElementById('cannedLang').value.trim() || 'en',
  });

  if (result && result.success) {
    closeModal();
    toast('Quick reply created', 'success');
    loadCannedResponses();
  }
}

function showEditCannedModal(json) {
  const c = JSON.parse(json);
  openModal('Edit Quick Reply', `
    <div class="form-grid">
      <div class="form-group">
        <label class="form-label">Title *</label>
        <input type="text" class="form-input" id="cannedEditTitle" value="${esc(c.title || '')}">
      </div>
      <div class="form-group">
        <label class="form-label">Shortcut</label>
        <input type="text" class="form-input" id="cannedEditShortcut" value="${esc(c.shortcut || '')}">
      </div>
      <div class="form-group">
        <label class="form-label">Category</label>
        <input type="text" class="form-input" id="cannedEditCategory" value="${esc(c.category || '')}">
      </div>
      <div class="form-group">
        <label class="form-label">Language</label>
        <input type="text" class="form-input" id="cannedEditLang" value="${esc(c.language || 'en')}">
      </div>
      <div class="form-group full">
        <label class="form-label">Content *</label>
        <textarea class="form-input" id="cannedEditContent" rows="4">${esc(c.content || '')}</textarea>
      </div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitEditCanned('${c.id}')">Save</button>
  `);
}

async function submitEditCanned(id) {
  const title = document.getElementById('cannedEditTitle').value.trim();
  const content = document.getElementById('cannedEditContent').value.trim();
  if (!title || !content) { toast('Title and content are required', 'warning'); return; }

  const result = await apiPut(`/canned_responses/${id}`, {
    title,
    content,
    shortcut: document.getElementById('cannedEditShortcut').value.trim() || null,
    category: document.getElementById('cannedEditCategory').value.trim() || null,
    language: document.getElementById('cannedEditLang').value.trim() || 'en',
  });

  if (result && result.success) {
    closeModal();
    toast('Quick reply updated', 'success');
    loadCannedResponses();
  }
}

async function deleteCanned(id) {
  if (!confirm('Delete this quick reply?')) return;
  const result = await apiDelete(`/canned_responses/${id}`);
  if (result && result.success) {
    toast('Quick reply deleted', 'success');
    loadCannedResponses();
  }
}

// ===== TEMPLATE CRUD =====

function showCreateTemplateModal() {
  openModal('New Message Template', `
    <div class="form-grid">
      <div class="form-group">
        <label class="form-label">Platform *</label>
        <select class="form-input" id="tplPlatform">
          <option value="messenger">Messenger</option>
          <option value="instagram">Instagram</option>
          <option value="whatsapp">WhatsApp</option>
          <option value="viber">Viber</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Template Name *</label>
        <input type="text" class="form-input" id="tplName" placeholder="order_confirmation">
      </div>
      <div class="form-group full">
        <label class="form-label">Content *</label>
        <textarea class="form-input" id="tplContent" rows="4" placeholder="Hello {{name}}, your order #{{order_id}} has been confirmed."></textarea>
      </div>
      <div class="form-group">
        <label class="form-label">Variables (JSON array)</label>
        <input type="text" class="form-input" id="tplVars" placeholder='["name","order_id"]'>
      </div>
      <div class="form-group">
        <label class="form-label">Pre-approved</label>
        <select class="form-input" id="tplApproved">
          <option value="false">No</option>
          <option value="true">Yes</option>
        </select>
      </div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitCreateTemplate()">Create</button>
  `);
}

async function submitCreateTemplate() {
  const templateName = document.getElementById('tplName').value.trim();
  const content = document.getElementById('tplContent').value.trim();
  if (!templateName || !content) { toast('Name and content are required', 'warning'); return; }

  const result = await apiPost('/message_templates', {
    platform: document.getElementById('tplPlatform').value,
    template_name: templateName,
    content,
    variables_json: document.getElementById('tplVars').value.trim() || null,
    is_approved: document.getElementById('tplApproved').value === 'true',
  });

  if (result && result.success) {
    closeModal();
    toast('Template created', 'success');
    loadCannedResponses();
  }
}

function showEditTemplateModal(json) {
  const t = JSON.parse(json);
  openModal('Edit Message Template', `
    <div class="form-grid">
      <div class="form-group">
        <label class="form-label">Platform *</label>
        <select class="form-input" id="tplEditPlatform">
          ${['messenger','instagram','whatsapp','viber'].map(p =>
            `<option value="${p}" ${t.platform === p ? 'selected' : ''}>${p.charAt(0).toUpperCase() + p.slice(1)}</option>`
          ).join('')}
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Template Name *</label>
        <input type="text" class="form-input" id="tplEditName" value="${esc(t.template_name || '')}">
      </div>
      <div class="form-group full">
        <label class="form-label">Content *</label>
        <textarea class="form-input" id="tplEditContent" rows="4">${esc(t.content || '')}</textarea>
      </div>
      <div class="form-group">
        <label class="form-label">Variables (JSON array)</label>
        <input type="text" class="form-input" id="tplEditVars" value="${esc(t.variables_json || '')}">
      </div>
      <div class="form-group">
        <label class="form-label">Approved</label>
        <select class="form-input" id="tplEditApproved">
          <option value="false" ${!t.is_approved ? 'selected' : ''}>No</option>
          <option value="true" ${t.is_approved ? 'selected' : ''}>Yes</option>
        </select>
      </div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitEditTemplate('${t.id}')">Save</button>
  `);
}

async function submitEditTemplate(id) {
  const templateName = document.getElementById('tplEditName').value.trim();
  const content = document.getElementById('tplEditContent').value.trim();
  if (!templateName || !content) { toast('Name and content are required', 'warning'); return; }

  const result = await apiPut(`/message_templates/${id}`, {
    platform: document.getElementById('tplEditPlatform').value,
    template_name: templateName,
    content,
    variables_json: document.getElementById('tplEditVars').value.trim() || null,
    is_approved: document.getElementById('tplEditApproved').value === 'true',
  });

  if (result && result.success) {
    closeModal();
    toast('Template updated', 'success');
    loadCannedResponses();
  }
}
