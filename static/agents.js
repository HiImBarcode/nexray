/* ========== NEXRAY v3 — AI Agent System UI ========== */

// ===== AGENT DASHBOARD =====

async function loadAgentDashboard() {
  const el = document.getElementById('page-agent-dashboard');
  el.innerHTML = '<div class="kpi-grid">' +
    Array(4).fill('<div class="loading-skeleton skeleton-kpi"></div>').join('') +
    '</div>';

  const data = await api('/agents/dashboard');
  if (!data) {
    el.innerHTML = '<div class="empty-state"><p>Unable to load agent dashboard</p></div>';
    return;
  }

  const s = data.stats;
  const agents = data.agents || [];
  const reviews = data.pending_reviews || [];
  const decisions = data.recent_decisions || [];

  el.innerHTML = `
    <div class="kpi-grid">
      <div class="kpi-card accent">
        <div class="kpi-label">Decisions Today</div>
        <div class="kpi-value">${s.total_today}</div>
      </div>
      <div class="kpi-card success">
        <div class="kpi-label">Auto-Executed</div>
        <div class="kpi-value">${s.auto_executed}</div>
      </div>
      <div class="kpi-card ${s.escalated > 0 ? 'warning' : ''}">
        <div class="kpi-label">Escalated</div>
        <div class="kpi-value">${s.escalated}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Avg Confidence</div>
        <div class="kpi-value">${(s.avg_confidence * 100).toFixed(1)}%</div>
      </div>
    </div>

    <!-- Kill Switch Row -->
    <div class="card" style="margin-bottom:var(--space-4)">
      <div class="card-header" style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:var(--space-2)">
        <div>
          <div class="card-title">Agent Controls</div>
          <div class="card-subtitle">Cost today: $${s.total_cost_usd.toFixed(4)} &middot; Overridden: ${s.overridden}</div>
        </div>
        <div style="display:flex;gap:var(--space-2)">
          <button class="btn" onclick="agentResumeAll()"
            style="background:var(--color-success);color:#fff;font-weight:700">
            Resume All
          </button>
          <button class="btn" onclick="agentKillSwitch()"
            style="background:var(--color-error);color:#fff;font-weight:700;font-size:14px;padding:8px 20px;border:2px solid darkred">
            KILL SWITCH
          </button>
        </div>
      </div>
    </div>

    <!-- Agent Config Cards -->
    <div class="card" style="margin-bottom:var(--space-4)">
      <div class="card-header">
        <div><div class="card-title">Agent Configurations</div>
        <div class="card-subtitle">${agents.length} agent(s) configured</div></div>
      </div>
      <div class="detail-grid" style="padding:var(--space-4)">
        ${agents.map(a => _agentConfigCard(a)).join('')}
      </div>
    </div>

    <!-- Pending Reviews -->
    <div class="card" style="margin-bottom:var(--space-4)">
      <div class="card-header">
        <div><div class="card-title">Pending Reviews</div>
        <div class="card-subtitle">${reviews.length} item(s) awaiting human review</div></div>
      </div>
      ${reviews.length > 0 ? `<div class="table-wrapper"><table>
        <thead><tr><th>Agent</th><th>Proposed Action</th><th>Confidence</th><th>Context</th><th>Created</th><th>Actions</th></tr></thead>
        <tbody>${reviews.map(r => `<tr>
          <td>${badge(r.agent_type)}</td>
          <td>${esc(r.proposed_action || '\u2014')}</td>
          <td>${_confidencePill(r.confidence)}</td>
          <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(r.context_summary || r.reasoning || '\u2014')}</td>
          <td>${fmtDate(r.created_at)}</td>
          <td style="white-space:nowrap">
            <button class="btn btn-sm" style="background:var(--color-success);color:#fff" onclick="approveReview('${r.id}')">Approve</button>
            <button class="btn btn-sm" style="background:var(--color-error);color:#fff;margin-left:4px" onclick="rejectReviewPrompt('${r.id}')">Reject</button>
          </td>
        </tr>`).join('')}</tbody>
      </table></div>` : '<div style="padding:var(--space-4);text-align:center;color:var(--color-text-faint)">No pending reviews.</div>'}
    </div>

    <!-- Recent Decisions -->
    <div class="card">
      <div class="card-header">
        <div><div class="card-title">Recent Decisions</div>
        <div class="card-subtitle">Last 20 decisions across all agents</div></div>
      </div>
      ${decisions.length > 0 ? `<div class="table-wrapper"><table>
        <thead><tr><th>Time</th><th>Agent</th><th>Action</th><th>Confidence</th><th>Auto</th><th>Cost</th></tr></thead>
        <tbody>${decisions.map(d => `<tr style="cursor:pointer" onclick="showDecisionDetail('${d.id}')">
          <td>${fmtDate(d.created_at)}</td>
          <td>${badge(d.agent_type)}</td>
          <td>${esc(d.action_taken || '\u2014')}</td>
          <td>${_confidencePill(d.confidence)}</td>
          <td>${d.was_auto_executed ? '\u2705' : '\u274C'}</td>
          <td>${d.cost_usd != null ? '$' + Number(d.cost_usd).toFixed(4) : '\u2014'}</td>
        </tr>`).join('')}</tbody>
      </table></div>` : '<div style="padding:var(--space-4);text-align:center;color:var(--color-text-faint)">No decisions recorded yet.</div>'}
    </div>
  `;
}

function _agentConfigCard(a) {
  const active = !!a.is_active;
  const dot = `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${active ? 'var(--color-success)' : 'var(--color-error)'};margin-right:6px;vertical-align:middle"></span>`;
  const modeBadge = a.execution_mode === 'deep'
    ? '<span style="background:#f97316;color:#fff;padding:1px 6px;border-radius:4px;font-size:10px;margin-left:4px">deep</span>'
    : '<span style="background:var(--color-info);color:#fff;padding:1px 6px;border-radius:4px;font-size:10px;margin-left:4px">realtime</span>';
  return `
    <div class="info-card" style="cursor:pointer;position:relative" onclick="editAgentConfig('${esc(a.agent_type)}')">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--space-2)">
        <strong>${dot}${esc(a.display_name)}</strong>
        ${modeBadge}
      </div>
      <div style="font-size:12px;color:var(--color-text-muted);margin-bottom:var(--space-2)">${esc(a.description || '')}</div>
      <div class="info-row"><span class="label">Confidence Threshold</span><span class="value">${a.confidence_threshold != null ? (Number(a.confidence_threshold) * 100).toFixed(0) + '%' : '\u2014'}</span></div>
      <div class="info-row"><span class="label">Status</span><span class="value">${active ? 'Active' : 'Disabled'}</span></div>
      <div style="margin-top:var(--space-2)">
        <button class="btn btn-sm" onclick="event.stopPropagation();toggleAgent('${esc(a.agent_type)}')"
          style="background:${active ? 'var(--color-error)' : 'var(--color-success)'};color:#fff;font-size:11px">
          ${active ? 'Disable' : 'Enable'}
        </button>
      </div>
    </div>
  `;
}


// ===== AGENT CONFIG MODAL =====

async function editAgentConfig(agentType) {
  const data = await api('/agents/configs');
  if (!data) return;
  const cfg = (data.configs || []).find(c => c.agent_type === agentType);
  if (!cfg) { toast('Agent config not found', 'error'); return; }

  openModal(`Edit Agent: ${esc(cfg.display_name)}`, `
    <div class="form-grid">
      <div class="form-group">
        <label class="form-label">Display Name</label>
        <input type="text" class="form-input" id="agCfgName" value="${esc(cfg.display_name)}">
      </div>
      <div class="form-group">
        <label class="form-label">Description</label>
        <input type="text" class="form-input" id="agCfgDesc" value="${esc(cfg.description || '')}">
      </div>
      <div class="form-group">
        <label class="form-label">Model</label>
        <input type="text" class="form-input" id="agCfgModel" value="${esc(cfg.model || '')}">
      </div>
      <div class="form-group">
        <label class="form-label">Confidence Threshold (0-1)</label>
        <input type="number" class="form-input" id="agCfgThreshold" value="${cfg.confidence_threshold || 0.9}" step="0.01" min="0" max="1">
      </div>
      <div class="form-group">
        <label class="form-label">Max Tokens</label>
        <input type="number" class="form-input" id="agCfgMaxTokens" value="${cfg.max_tokens || 4096}">
      </div>
      <div class="form-group">
        <label class="form-label">Execution Mode</label>
        <select class="form-input" id="agCfgMode">
          <option value="realtime" ${cfg.execution_mode === 'realtime' ? 'selected' : ''}>Realtime</option>
          <option value="deep" ${cfg.execution_mode === 'deep' ? 'selected' : ''}>Deep</option>
        </select>
      </div>
      <div class="form-group" style="grid-column:1/-1">
        <label class="form-label">System Prompt</label>
        <textarea class="form-input" id="agCfgPrompt" rows="4" style="font-family:var(--font-mono);font-size:12px">${esc(cfg.system_prompt || '')}</textarea>
      </div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitAgentConfig('${esc(agentType)}')">Save</button>
  `);
}

async function submitAgentConfig(agentType) {
  const body = {
    display_name: document.getElementById('agCfgName').value.trim(),
    description: document.getElementById('agCfgDesc').value.trim(),
    model: document.getElementById('agCfgModel').value.trim(),
    confidence_threshold: parseFloat(document.getElementById('agCfgThreshold').value) || 0.9,
    max_tokens: parseInt(document.getElementById('agCfgMaxTokens').value) || 4096,
    execution_mode: document.getElementById('agCfgMode').value,
    system_prompt: document.getElementById('agCfgPrompt').value.trim() || null,
  };
  const result = await apiPut(`/agents/configs/${agentType}`, body);
  if (result) {
    closeModal();
    toast('Agent config updated', 'success');
    loadAgentDashboard();
  }
}

async function toggleAgent(agentType) {
  const result = await apiPost(`/agents/configs/${agentType}/toggle`, {});
  if (result) {
    toast(`Agent ${result.config.is_active ? 'enabled' : 'disabled'}`, 'success');
    loadAgentDashboard();
  }
}


// ===== KILL SWITCH / RESUME =====

async function agentKillSwitch() {
  if (!confirm('KILL SWITCH: This will immediately disable ALL agents. Continue?')) return;
  const result = await apiPost('/agents/kill_switch', {});
  if (result) {
    toast('All agents disabled', 'warning');
    loadAgentDashboard();
  }
}

async function agentResumeAll() {
  if (!confirm('Resume ALL agents?')) return;
  const result = await apiPost('/agents/resume_all', {});
  if (result) {
    toast('All agents resumed', 'success');
    loadAgentDashboard();
  }
}


// ===== REVIEW QUEUE =====

async function approveReview(reviewId) {
  const result = await apiPost(`/agents/review_queue/${reviewId}/approve`, {});
  if (result) {
    toast('Review approved', 'success');
    loadAgentDashboard();
  }
}

function rejectReviewPrompt(reviewId) {
  openModal('Reject Decision', `
    <div class="form-group">
      <label class="form-label">Rejection Reason (required)</label>
      <textarea class="form-input" id="rejectReason" rows="3" placeholder="Why is this decision being rejected?"></textarea>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn" style="background:var(--color-error);color:#fff" onclick="submitRejectReview('${reviewId}')">Reject</button>
  `);
}

async function submitRejectReview(reviewId) {
  const reason = document.getElementById('rejectReason').value.trim();
  if (!reason) { toast('Reason is required', 'error'); return; }
  const result = await apiPost(`/agents/review_queue/${reviewId}/reject`, { reason });
  if (result) {
    closeModal();
    toast('Review rejected', 'success');
    loadAgentDashboard();
  }
}


// ===== DECISION DETAIL =====

async function showDecisionDetail(decisionId) {
  const data = await api('/agents/decisions', { agent_type: '' });
  if (!data) return;
  const d = (data.decisions || []).find(x => x.id === decisionId);
  if (!d) { toast('Decision not found', 'error'); return; }

  openModal(`Decision: ${esc(d.action_taken || d.id.substring(0, 8))}`, `
    <div class="detail-grid">
      <div class="info-card">
        <div class="info-row"><span class="label">Agent</span><span class="value">${badge(d.agent_type)}</span></div>
        <div class="info-row"><span class="label">Action</span><span class="value">${esc(d.action_taken || '\u2014')}</span></div>
        <div class="info-row"><span class="label">Trigger</span><span class="value">${esc(d.trigger_type || '\u2014')} ${d.trigger_id ? mono(d.trigger_id) : ''}</span></div>
        <div class="info-row"><span class="label">Confidence</span><span class="value">${_confidencePill(d.confidence)}</span></div>
        <div class="info-row"><span class="label">Auto-Executed</span><span class="value">${d.was_auto_executed ? 'Yes' : 'No'}</span></div>
        <div class="info-row"><span class="label">Overridden</span><span class="value">${d.was_overridden ? 'Yes' : 'No'}</span></div>
        <div class="info-row"><span class="label">Tokens</span><span class="value">${d.tokens_used != null ? d.tokens_used.toLocaleString() : '\u2014'}</span></div>
        <div class="info-row"><span class="label">Cost</span><span class="value">${d.cost_usd != null ? '$' + Number(d.cost_usd).toFixed(4) : '\u2014'}</span></div>
        <div class="info-row"><span class="label">Execution</span><span class="value">${d.execution_ms != null ? d.execution_ms + 'ms' : '\u2014'}</span></div>
        <div class="info-row"><span class="label">Created</span><span class="value">${fmtDate(d.created_at)}</span></div>
      </div>
    </div>
    ${d.reasoning ? `<div style="margin-top:var(--space-3)"><strong>Reasoning</strong><pre style="background:var(--color-surface);padding:var(--space-3);border-radius:6px;font-size:12px;white-space:pre-wrap;max-height:200px;overflow-y:auto">${esc(d.reasoning)}</pre></div>` : ''}
    ${d.input_summary ? `<div style="margin-top:var(--space-3)"><strong>Input Summary</strong><pre style="background:var(--color-surface);padding:var(--space-3);border-radius:6px;font-size:12px;white-space:pre-wrap;max-height:200px;overflow-y:auto">${esc(d.input_summary)}</pre></div>` : ''}
    ${d.output_summary ? `<div style="margin-top:var(--space-3)"><strong>Output Summary</strong><pre style="background:var(--color-surface);padding:var(--space-3);border-radius:6px;font-size:12px;white-space:pre-wrap;max-height:200px;overflow-y:auto">${esc(d.output_summary)}</pre></div>` : ''}
    ${d.override_reason ? `<div style="margin-top:var(--space-3)"><strong>Override Reason</strong><pre style="background:var(--color-surface);padding:var(--space-3);border-radius:6px;font-size:12px;white-space:pre-wrap">${esc(d.override_reason)}</pre></div>` : ''}
  `, `<button class="btn btn-secondary" onclick="closeModal()">Close</button>`, 'modal-lg');
}


// ===== DEEP TASKS PAGE =====

async function loadAgentTasks() {
  const el = document.getElementById('page-agent-tasks');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(5);

  const [tasksData, configsData] = await Promise.all([
    api('/agents/tasks'),
    api('/agents/configs'),
  ]);
  if (!tasksData) { el.innerHTML = '<div class="empty-state"><p>Unable to load tasks</p></div>'; return; }

  const tasks = tasksData.tasks || [];
  const agentTypes = (configsData?.configs || []).map(c => c.agent_type);

  el.innerHTML = `
    <div class="card" style="margin-bottom:var(--space-4)">
      <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:var(--space-2)">
        <div><div class="card-title">Deep Tasks (OpenClaw)</div>
        <div class="card-subtitle">Agent task queue for background / deep-thinking operations</div></div>
        <button class="btn btn-primary" onclick="showCreateTaskModal()">+ New Task</button>
      </div>
      <div style="padding:var(--space-3);display:flex;gap:var(--space-2);flex-wrap:wrap">
        <select class="form-input" id="taskFilterStatus" onchange="filterAgentTasks()" style="width:auto">
          <option value="">All Statuses</option>
          <option value="queued">Queued</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
          <option value="cancelled">Cancelled</option>
        </select>
        <select class="form-input" id="taskFilterType" onchange="filterAgentTasks()" style="width:auto">
          <option value="">All Task Types</option>
        </select>
      </div>
      <div class="table-wrapper" id="agentTasksTable">
        ${_renderTasksTable(tasks)}
      </div>
    </div>
  `;

  // Store for filtering
  window._agentTasks = tasks;
  window._agentTypes = agentTypes;
}

function _renderTasksTable(tasks) {
  if (tasks.length === 0) {
    return '<div style="padding:var(--space-4);text-align:center;color:var(--color-text-faint)">No tasks found.</div>';
  }
  return `<table>
    <thead><tr><th>ID</th><th>Agent</th><th>Task Type</th><th>Status</th><th>Priority</th><th>Progress</th><th>Created</th><th>Actions</th></tr></thead>
    <tbody>${tasks.map(t => `<tr style="cursor:pointer" onclick="showTaskDetail('${t.id}')">
      <td>${mono(t.id ? t.id.substring(0, 8) : '\u2014')}</td>
      <td>${t.agent_type ? badge(t.agent_type) : '\u2014'}</td>
      <td>${esc(t.task_type)}</td>
      <td>${badge(t.status)}</td>
      <td>${t.priority || 0}</td>
      <td>${t.progress != null ? t.progress + '%' : '\u2014'}${t.progress_message ? ' <span style="font-size:11px;color:var(--color-text-muted)">' + esc(t.progress_message) + '</span>' : ''}</td>
      <td>${fmtDate(t.created_at)}</td>
      <td onclick="event.stopPropagation()">
        ${['queued', 'running'].includes(t.status)
          ? `<button class="btn btn-sm" style="background:var(--color-error);color:#fff" onclick="cancelAgentTask('${t.id}')">Cancel</button>`
          : ''}
      </td>
    </tr>`).join('')}</tbody>
  </table>`;
}

async function filterAgentTasks() {
  const status = document.getElementById('taskFilterStatus').value;
  const taskType = document.getElementById('taskFilterType').value;
  const params = {};
  if (status) params.status = status;
  if (taskType) params.task_type = taskType;

  const data = await api('/agents/tasks', params);
  if (!data) return;
  document.getElementById('agentTasksTable').innerHTML = _renderTasksTable(data.tasks || []);
}

async function showTaskDetail(taskId) {
  const data = await api(`/agents/tasks/${taskId}`);
  if (!data) return;
  const t = data.task;

  const resultStr = t.result ? JSON.stringify(typeof t.result === 'string' ? JSON.parse(t.result) : t.result, null, 2) : null;
  const paramsStr = t.params ? JSON.stringify(typeof t.params === 'string' ? JSON.parse(t.params) : t.params, null, 2) : null;

  openModal(`Task: ${esc(t.task_type)}`, `
    <div class="detail-grid">
      <div class="info-card">
        <div class="info-row"><span class="label">ID</span><span class="value">${mono(t.id)}</span></div>
        <div class="info-row"><span class="label">Agent Type</span><span class="value">${t.agent_type ? badge(t.agent_type) : '\u2014'}</span></div>
        <div class="info-row"><span class="label">Task Type</span><span class="value">${esc(t.task_type)}</span></div>
        <div class="info-row"><span class="label">Status</span><span class="value">${badge(t.status)}</span></div>
        <div class="info-row"><span class="label">Priority</span><span class="value">${t.priority || 0}</span></div>
        <div class="info-row"><span class="label">Progress</span><span class="value">${t.progress != null ? t.progress + '%' : '\u2014'}</span></div>
        <div class="info-row"><span class="label">Created</span><span class="value">${fmtDate(t.created_at)}</span></div>
        <div class="info-row"><span class="label">Started</span><span class="value">${fmtDate(t.started_at)}</span></div>
        <div class="info-row"><span class="label">Completed</span><span class="value">${fmtDate(t.completed_at)}</span></div>
      </div>
    </div>
    ${paramsStr ? `<div style="margin-top:var(--space-3)"><strong>Parameters</strong><pre style="background:var(--color-surface);padding:var(--space-3);border-radius:6px;font-size:12px;white-space:pre-wrap;max-height:200px;overflow-y:auto">${esc(paramsStr)}</pre></div>` : ''}
    ${resultStr ? `<div style="margin-top:var(--space-3)"><strong>Result</strong><pre style="background:var(--color-surface);padding:var(--space-3);border-radius:6px;font-size:12px;white-space:pre-wrap;max-height:200px;overflow-y:auto">${esc(resultStr)}</pre></div>` : ''}
    ${t.error_message ? `<div style="margin-top:var(--space-3)"><strong style="color:var(--color-error)">Error</strong><pre style="background:var(--color-surface);padding:var(--space-3);border-radius:6px;font-size:12px;white-space:pre-wrap;color:var(--color-error)">${esc(t.error_message)}</pre></div>` : ''}
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Close</button>
    ${['queued', 'running'].includes(t.status) ? `<button class="btn" style="background:var(--color-error);color:#fff" onclick="cancelAgentTask('${t.id}');closeModal()">Cancel Task</button>` : ''}
  `, 'modal-lg');
}

async function showCreateTaskModal() {
  const configsData = await api('/agents/configs');
  const types = (configsData?.configs || []);

  openModal('Create Agent Task', `
    <div class="form-grid">
      <div class="form-group">
        <label class="form-label">Agent Type</label>
        <select class="form-input" id="newTaskAgent">
          <option value="">None (unassigned)</option>
          ${types.map(c => `<option value="${esc(c.agent_type)}">${esc(c.display_name)}</option>`).join('')}
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Task Type</label>
        <input type="text" class="form-input" id="newTaskType" placeholder="e.g. reconcile_inventory">
      </div>
      <div class="form-group">
        <label class="form-label">Priority (0-10)</label>
        <input type="number" class="form-input" id="newTaskPriority" value="0" min="0" max="10">
      </div>
      <div class="form-group" style="grid-column:1/-1">
        <label class="form-label">Parameters (JSON)</label>
        <textarea class="form-input" id="newTaskParams" rows="4" style="font-family:var(--font-mono);font-size:12px" placeholder='{"key": "value"}'></textarea>
      </div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
    <button class="btn btn-primary" onclick="submitCreateTask()">Create Task</button>
  `);
}

async function submitCreateTask() {
  const taskType = document.getElementById('newTaskType').value.trim();
  if (!taskType) { toast('Task type is required', 'error'); return; }

  let params = null;
  const paramsRaw = document.getElementById('newTaskParams').value.trim();
  if (paramsRaw) {
    try { params = JSON.parse(paramsRaw); }
    catch (e) { toast('Invalid JSON in parameters', 'error'); return; }
  }

  const body = {
    task_type: taskType,
    agent_type: document.getElementById('newTaskAgent').value || null,
    priority: parseInt(document.getElementById('newTaskPriority').value) || 0,
    params,
  };

  const result = await apiPost('/agents/tasks', body);
  if (result) {
    closeModal();
    toast('Task created', 'success');
    loadAgentTasks();
  }
}

async function cancelAgentTask(taskId) {
  if (!confirm('Cancel this task?')) return;
  const result = await apiPost(`/agents/tasks/${taskId}/cancel`, {});
  if (result) {
    toast('Task cancelled', 'success');
    loadAgentTasks();
  }
}


// ===== DECISION LOG PAGE =====

async function loadAgentDecisions() {
  const el = document.getElementById('page-agent-decisions');
  el.innerHTML = '<div class="loading-skeleton skeleton-row"></div>'.repeat(5);

  const [decisionsData, statsData, configsData] = await Promise.all([
    api('/agents/decisions'),
    api('/agents/decisions/stats'),
    api('/agents/configs'),
  ]);
  if (!decisionsData) { el.innerHTML = '<div class="empty-state"><p>Unable to load decisions</p></div>'; return; }

  const decisions = decisionsData.decisions || [];
  const s = statsData?.stats || {};
  const agentTypes = (configsData?.configs || []).map(c => c.agent_type);

  el.innerHTML = `
    <!-- Stats Summary -->
    <div class="kpi-grid" style="margin-bottom:var(--space-4)">
      <div class="kpi-card accent">
        <div class="kpi-label">Total Today</div>
        <div class="kpi-value">${s.total_today || 0}</div>
      </div>
      <div class="kpi-card success">
        <div class="kpi-label">Auto-Executed</div>
        <div class="kpi-value">${s.auto_executed || 0}</div>
      </div>
      <div class="kpi-card warning">
        <div class="kpi-label">Escalated</div>
        <div class="kpi-value">${s.escalated || 0}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Avg Confidence</div>
        <div class="kpi-value">${s.avg_confidence != null ? (s.avg_confidence * 100).toFixed(1) + '%' : '\u2014'}</div>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div><div class="card-title">Decision Log</div>
        <div class="card-subtitle">Full audit trail of all agent decisions</div></div>
      </div>
      <div style="padding:var(--space-3);display:flex;gap:var(--space-2);flex-wrap:wrap;align-items:end">
        <div class="form-group" style="margin:0">
          <label class="form-label" style="font-size:11px">Agent Type</label>
          <select class="form-input" id="decFilterAgent" onchange="filterDecisions()" style="width:auto">
            <option value="">All Agents</option>
            ${agentTypes.map(t => `<option value="${esc(t)}">${esc(t)}</option>`).join('')}
          </select>
        </div>
        <div class="form-group" style="margin:0">
          <label class="form-label" style="font-size:11px">Auto-Executed</label>
          <select class="form-input" id="decFilterAuto" onchange="filterDecisions()" style="width:auto">
            <option value="">All</option>
            <option value="1">Yes</option>
            <option value="0">No</option>
          </select>
        </div>
        <div class="form-group" style="margin:0">
          <label class="form-label" style="font-size:11px">From</label>
          <input type="date" class="form-input" id="decFilterFrom" onchange="filterDecisions()" style="width:auto">
        </div>
        <div class="form-group" style="margin:0">
          <label class="form-label" style="font-size:11px">To</label>
          <input type="date" class="form-input" id="decFilterTo" onchange="filterDecisions()" style="width:auto">
        </div>
      </div>
      <div class="table-wrapper" id="decisionsTable">
        ${_renderDecisionsTable(decisions)}
      </div>
    </div>
  `;
}

function _renderDecisionsTable(decisions) {
  if (decisions.length === 0) {
    return '<div style="padding:var(--space-4);text-align:center;color:var(--color-text-faint)">No decisions found.</div>';
  }
  return `<table>
    <thead><tr><th>Timestamp</th><th>Agent</th><th>Action</th><th>Confidence</th><th>Auto</th><th>Trigger</th><th>Cost</th></tr></thead>
    <tbody>${decisions.map(d => `<tr style="cursor:pointer" onclick="showDecisionDetail('${d.id}')">
      <td>${fmtDate(d.created_at)}</td>
      <td>${badge(d.agent_type)}</td>
      <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(d.action_taken || '\u2014')}</td>
      <td>${_confidencePill(d.confidence)}</td>
      <td>${d.was_auto_executed ? '\u2705' : '\u274C'}</td>
      <td>${d.trigger_type ? esc(d.trigger_type) : '\u2014'}</td>
      <td>${d.cost_usd != null ? '$' + Number(d.cost_usd).toFixed(4) : '\u2014'}</td>
    </tr>`).join('')}</tbody>
  </table>`;
}

async function filterDecisions() {
  const params = {};
  const agent = document.getElementById('decFilterAgent').value;
  const auto = document.getElementById('decFilterAuto').value;
  const from = document.getElementById('decFilterFrom').value;
  const to = document.getElementById('decFilterTo').value;
  if (agent) params.agent_type = agent;
  if (auto !== '') params.was_auto_executed = auto;
  if (from) params.date_from = from;
  if (to) params.date_to = to;

  const data = await api('/agents/decisions', params);
  if (!data) return;
  document.getElementById('decisionsTable').innerHTML = _renderDecisionsTable(data.decisions || []);
}


// ===== SHARED HELPERS =====

function _confidencePill(confidence) {
  if (confidence == null) return '\u2014';
  const pct = Number(confidence) * 100;
  const color = pct >= 80 ? 'var(--color-success)' : pct >= 50 ? '#f59e0b' : 'var(--color-error)';
  return `<span style="display:inline-flex;align-items:center;gap:4px">
    <span style="display:inline-block;width:40px;height:6px;background:var(--color-border);border-radius:3px;overflow:hidden">
      <span style="display:block;width:${pct}%;height:100%;background:${color};border-radius:3px"></span>
    </span>
    <span style="font-size:12px;font-weight:600;color:${color}">${pct.toFixed(0)}%</span>
  </span>`;
}
