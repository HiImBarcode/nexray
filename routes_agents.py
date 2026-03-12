"""
NEXRAY v3 — AI Agent System Routes
Agent configs, task queue, decision audit, review queue, dashboard, and kill switch.
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
import uuid
import json

from db import (
    get_db, fetchone, fetchall, execute,
    rows_to_list, dict_from_row,
    require_auth, require_role,
    write_audit,
)

router = APIRouter()


# ========== AGENT CONFIG ==========

@router.get("/api/agents/configs")
async def list_agent_configs(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    with get_db() as db:
        configs = rows_to_list(fetchall(db,
            "SELECT * FROM agent_configs ORDER BY display_name"))
    return {'configs': configs}


@router.put("/api/agents/configs/{agent_type}")
async def update_agent_config(request: Request, agent_type: str):
    user = require_auth(request)
    require_role(user, 'system_admin')
    body = await request.json()

    allowed_fields = {
        'display_name', 'description', 'model', 'system_prompt',
        'tools', 'confidence_threshold', 'max_tokens', 'is_active', 'execution_mode',
    }
    updates = {k: v for k, v in body.items() if k in allowed_fields}
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    with get_db() as db:
        existing = fetchone(db, "SELECT * FROM agent_configs WHERE agent_type=%s", (agent_type,))
        if not existing:
            raise HTTPException(status_code=404, detail=f"Agent config '{agent_type}' not found")

        set_clauses = []
        args = []
        for field, value in updates.items():
            if field == 'tools' and not isinstance(value, str):
                value = json.dumps(value)
            set_clauses.append(f"{field}=%s")
            args.append(value)
        set_clauses.append("updated_at=NOW()")
        args.append(agent_type)

        execute(db,
            f"UPDATE agent_configs SET {', '.join(set_clauses)} WHERE agent_type=%s",
            tuple(args))
        write_audit(db, user['uid'], 'update_agent_config', 'agent_config', existing['id'],
                    before_json=existing, after_json=updates)
        db.commit()

        updated = dict_from_row(fetchone(db, "SELECT * FROM agent_configs WHERE agent_type=%s", (agent_type,)))
    return {'config': updated}


@router.post("/api/agents/configs/{agent_type}/toggle")
async def toggle_agent_config(request: Request, agent_type: str):
    user = require_auth(request)
    require_role(user, 'system_admin')
    with get_db() as db:
        existing = fetchone(db, "SELECT * FROM agent_configs WHERE agent_type=%s", (agent_type,))
        if not existing:
            raise HTTPException(status_code=404, detail=f"Agent config '{agent_type}' not found")

        new_active = 0 if existing['is_active'] else 1
        execute(db,
            "UPDATE agent_configs SET is_active=%s, updated_at=NOW() WHERE agent_type=%s",
            (new_active, agent_type))
        write_audit(db, user['uid'], 'toggle_agent', 'agent_config', existing['id'],
                    before_json={'is_active': existing['is_active']},
                    after_json={'is_active': new_active})
        db.commit()

        updated = dict_from_row(fetchone(db, "SELECT * FROM agent_configs WHERE agent_type=%s", (agent_type,)))
    return {'config': updated}


# ========== AGENT TASKS (Deep Tasks for OpenClaw) ==========

@router.get("/api/agents/tasks")
async def list_agent_tasks(request: Request, status: str = None, task_type: str = None):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    with get_db() as db:
        query = "SELECT * FROM agent_tasks WHERE 1=1"
        args = []
        if status:
            query += " AND status=%s"; args.append(status)
        if task_type:
            query += " AND task_type=%s"; args.append(task_type)
        query += " ORDER BY created_at DESC LIMIT 100"
        tasks = rows_to_list(fetchall(db, query, args))
    return {'tasks': tasks}


@router.post("/api/agents/tasks")
async def create_agent_task(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    body = await request.json()

    task_type = body.get("task_type", "").strip()
    if not task_type:
        raise HTTPException(status_code=400, detail="task_type is required")

    task_id = str(uuid.uuid4())
    agent_type = body.get("agent_type")
    priority = body.get("priority", 0)
    params = body.get("params")
    params_json = json.dumps(params) if params and not isinstance(params, str) else params

    with get_db() as db:
        execute(db,
            "INSERT INTO agent_tasks (id, task_type, agent_type, status, priority, params, created_by, created_at) "
            "VALUES (%s,%s,%s,'queued',%s,%s,%s,NOW())",
            (task_id, task_type, agent_type, priority, params_json, user['uid']))
        write_audit(db, user['uid'], 'create_agent_task', 'agent_task', task_id,
                    after_json={'task_type': task_type, 'agent_type': agent_type, 'priority': priority})
        db.commit()

        task = dict_from_row(fetchone(db, "SELECT * FROM agent_tasks WHERE id=%s", (task_id,)))
    return {'task': task}


@router.get("/api/agents/tasks/next")
async def poll_next_task(request: Request):
    """Poll endpoint for OpenClaw to pick up the next queued task and mark it as running."""
    user = require_auth(request)
    require_role(user, 'system_admin')
    with get_db() as db:
        task = fetchone(db,
            "SELECT * FROM agent_tasks WHERE status='queued' ORDER BY priority DESC, created_at ASC LIMIT 1")
        if not task:
            return {'task': None}

        now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        execute(db,
            "UPDATE agent_tasks SET status='running', started_at=%s WHERE id=%s AND status='queued'",
            (now_str, task['id']))
        db.commit()

        updated = dict_from_row(fetchone(db, "SELECT * FROM agent_tasks WHERE id=%s", (task['id'],)))
    return {'task': updated}


@router.get("/api/agents/tasks/{task_id}")
async def get_agent_task(request: Request, task_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    with get_db() as db:
        task = dict_from_row(fetchone(db, "SELECT * FROM agent_tasks WHERE id=%s", (task_id,)))
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
    return {'task': task}


@router.post("/api/agents/tasks/{task_id}/cancel")
async def cancel_agent_task(request: Request, task_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    with get_db() as db:
        task = fetchone(db, "SELECT * FROM agent_tasks WHERE id=%s", (task_id,))
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        if task['status'] not in ('queued', 'running'):
            raise HTTPException(status_code=400, detail=f"Cannot cancel task in '{task['status']}' status")

        execute(db,
            "UPDATE agent_tasks SET status='cancelled' WHERE id=%s", (task_id,))
        write_audit(db, user['uid'], 'cancel_agent_task', 'agent_task', task_id,
                    before_json={'status': task['status']}, after_json={'status': 'cancelled'})
        db.commit()

        updated = dict_from_row(fetchone(db, "SELECT * FROM agent_tasks WHERE id=%s", (task_id,)))
    return {'task': updated}


# ========== AGENT DECISIONS (Audit) ==========

@router.get("/api/agents/decisions")
async def list_agent_decisions(request: Request, agent_type: str = None,
                                was_auto_executed: int = None,
                                date_from: str = None, date_to: str = None):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    with get_db() as db:
        query = "SELECT * FROM agent_decisions WHERE 1=1"
        args = []
        if agent_type:
            query += " AND agent_type=%s"; args.append(agent_type)
        if was_auto_executed is not None:
            query += " AND was_auto_executed=%s"; args.append(was_auto_executed)
        if date_from:
            query += " AND created_at >= %s"; args.append(date_from)
        if date_to:
            query += " AND created_at <= %s"; args.append(date_to)
        query += " ORDER BY created_at DESC LIMIT 100"
        decisions = rows_to_list(fetchall(db, query, args))
    return {'decisions': decisions}


@router.get("/api/agents/decisions/stats")
async def get_decision_stats(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    with get_db() as db:
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        total_today = fetchone(db,
            "SELECT COUNT(*) as c FROM agent_decisions WHERE DATE(created_at)=%s", (today,))['c']
        auto_executed = fetchone(db,
            "SELECT COUNT(*) as c FROM agent_decisions WHERE DATE(created_at)=%s AND was_auto_executed=1",
            (today,))['c']
        escalated = fetchone(db,
            "SELECT COUNT(*) as c FROM agent_decisions WHERE DATE(created_at)=%s AND was_auto_executed=0",
            (today,))['c']
        overridden = fetchone(db,
            "SELECT COUNT(*) as c FROM agent_decisions WHERE DATE(created_at)=%s AND was_overridden=1",
            (today,))['c']
        avg_confidence = fetchone(db,
            "SELECT COALESCE(AVG(confidence),0) as avg_conf FROM agent_decisions WHERE DATE(created_at)=%s",
            (today,))['avg_conf']
        total_cost = fetchone(db,
            "SELECT COALESCE(SUM(cost_usd),0) as total FROM agent_decisions WHERE DATE(created_at)=%s",
            (today,))['total']

    return {
        'stats': {
            'date': today,
            'total_today': total_today,
            'auto_executed': auto_executed,
            'escalated': escalated,
            'overridden': overridden,
            'avg_confidence': round(float(avg_confidence), 4),
            'total_cost_usd': round(float(total_cost), 4),
        }
    }


# ========== REVIEW QUEUE ==========

@router.get("/api/agents/review_queue")
async def list_review_queue(request: Request, status: str = "pending"):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    with get_db() as db:
        query = """SELECT rq.*, ad.reasoning, ad.input_summary, ad.output_summary,
                   ad.trigger_type, ad.trigger_id
                   FROM agent_review_queue rq
                   LEFT JOIN agent_decisions ad ON rq.decision_id = ad.id
                   WHERE 1=1"""
        args = []
        if status:
            query += " AND rq.status=%s"; args.append(status)
        query += " ORDER BY rq.created_at DESC LIMIT 100"
        reviews = rows_to_list(fetchall(db, query, args))
    return {'reviews': reviews}


@router.post("/api/agents/review_queue/{review_id}/approve")
async def approve_review(request: Request, review_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    with get_db() as db:
        review = fetchone(db, "SELECT * FROM agent_review_queue WHERE id=%s", (review_id,))
        if not review:
            raise HTTPException(status_code=404, detail="Review item not found")
        if review['status'] != 'pending':
            raise HTTPException(status_code=400, detail=f"Review already in '{review['status']}' status")

        now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        execute(db,
            "UPDATE agent_review_queue SET status='approved', reviewed_by=%s, reviewed_at=%s WHERE id=%s",
            (user['uid'], now_str, review_id))
        write_audit(db, user['uid'], 'approve_agent_decision', 'agent_review_queue', review_id,
                    after_json={'status': 'approved', 'decision_id': review['decision_id']})
        db.commit()

        updated = dict_from_row(fetchone(db, "SELECT * FROM agent_review_queue WHERE id=%s", (review_id,)))
    return {'review': updated}


@router.post("/api/agents/review_queue/{review_id}/reject")
async def reject_review(request: Request, review_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    body = await request.json()
    reason = body.get("reason", "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")

    with get_db() as db:
        review = fetchone(db, "SELECT * FROM agent_review_queue WHERE id=%s", (review_id,))
        if not review:
            raise HTTPException(status_code=404, detail="Review item not found")
        if review['status'] != 'pending':
            raise HTTPException(status_code=400, detail=f"Review already in '{review['status']}' status")

        now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        execute(db,
            "UPDATE agent_review_queue SET status='rejected', reviewed_by=%s, reviewed_at=%s WHERE id=%s",
            (user['uid'], now_str, review_id))

        # Also mark the decision as overridden
        execute(db,
            "UPDATE agent_decisions SET was_overridden=1, override_by=%s, override_reason=%s WHERE id=%s",
            (user['uid'], reason, review['decision_id']))

        write_audit(db, user['uid'], 'reject_agent_decision', 'agent_review_queue', review_id,
                    after_json={'status': 'rejected', 'reason': reason, 'decision_id': review['decision_id']})
        db.commit()

        updated = dict_from_row(fetchone(db, "SELECT * FROM agent_review_queue WHERE id=%s", (review_id,)))
    return {'review': updated}


# ========== AGENT DASHBOARD ==========

@router.get("/api/agents/dashboard")
async def agent_dashboard(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    with get_db() as db:
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

        # Active agents
        active_agents = rows_to_list(fetchall(db,
            "SELECT id, agent_type, display_name, description, execution_mode, is_active, confidence_threshold, updated_at "
            "FROM agent_configs ORDER BY display_name"))

        # Today's stats
        total_today = fetchone(db,
            "SELECT COUNT(*) as c FROM agent_decisions WHERE DATE(created_at)=%s", (today,))['c']
        auto_executed = fetchone(db,
            "SELECT COUNT(*) as c FROM agent_decisions WHERE DATE(created_at)=%s AND was_auto_executed=1",
            (today,))['c']
        escalated = fetchone(db,
            "SELECT COUNT(*) as c FROM agent_decisions WHERE DATE(created_at)=%s AND was_auto_executed=0",
            (today,))['c']
        overridden = fetchone(db,
            "SELECT COUNT(*) as c FROM agent_decisions WHERE DATE(created_at)=%s AND was_overridden=1",
            (today,))['c']
        avg_confidence = fetchone(db,
            "SELECT COALESCE(AVG(confidence),0) as avg_conf FROM agent_decisions WHERE DATE(created_at)=%s",
            (today,))['avg_conf']
        total_cost = fetchone(db,
            "SELECT COALESCE(SUM(cost_usd),0) as total FROM agent_decisions WHERE DATE(created_at)=%s",
            (today,))['total']

        stats = {
            'date': today,
            'total_today': total_today,
            'auto_executed': auto_executed,
            'escalated': escalated,
            'overridden': overridden,
            'avg_confidence': round(float(avg_confidence), 4),
            'total_cost_usd': round(float(total_cost), 4),
        }

        # Pending reviews
        pending_reviews = rows_to_list(fetchall(db,
            "SELECT rq.*, ad.reasoning, ad.trigger_type, ad.trigger_id "
            "FROM agent_review_queue rq "
            "LEFT JOIN agent_decisions ad ON rq.decision_id = ad.id "
            "WHERE rq.status='pending' ORDER BY rq.created_at DESC LIMIT 20"))

        # Recent decisions
        recent_decisions = rows_to_list(fetchall(db,
            "SELECT * FROM agent_decisions ORDER BY created_at DESC LIMIT 20"))

        # Running tasks
        running_tasks = rows_to_list(fetchall(db,
            "SELECT * FROM agent_tasks WHERE status IN ('queued','running') ORDER BY priority DESC, created_at ASC LIMIT 20"))

    return {
        'agents': active_agents,
        'stats': stats,
        'pending_reviews': pending_reviews,
        'recent_decisions': recent_decisions,
        'running_tasks': running_tasks,
    }


# ========== KILL SWITCH ==========

@router.post("/api/agents/kill_switch")
async def kill_switch(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin')
    with get_db() as db:
        execute(db, "UPDATE agent_configs SET is_active=0, updated_at=NOW()")
        write_audit(db, user['uid'], 'kill_switch_activated', 'agent_config', 'ALL',
                    after_json={'is_active': 0, 'scope': 'all_agents'})
        db.commit()

        configs = rows_to_list(fetchall(db, "SELECT * FROM agent_configs ORDER BY display_name"))
    return {'message': 'All agents paused', 'configs': configs}


@router.post("/api/agents/resume_all")
async def resume_all(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin')
    with get_db() as db:
        execute(db, "UPDATE agent_configs SET is_active=1, updated_at=NOW()")
        write_audit(db, user['uid'], 'resume_all_agents', 'agent_config', 'ALL',
                    after_json={'is_active': 1, 'scope': 'all_agents'})
        db.commit()

        configs = rows_to_list(fetchall(db, "SELECT * FROM agent_configs ORDER BY display_name"))
    return {'message': 'All agents resumed', 'configs': configs}


# ========== DB INIT ==========

def init_agents_db():
    """Create agent tables and seed default configs."""
    with get_db() as db:
        with db.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS agent_configs (
                id VARCHAR(36) PRIMARY KEY,
                agent_type VARCHAR(50) NOT NULL UNIQUE,
                display_name VARCHAR(200) NOT NULL,
                description TEXT,
                model VARCHAR(100) DEFAULT 'claude-sonnet-4-6-20250514',
                system_prompt TEXT,
                tools JSON,
                confidence_threshold DECIMAL(5,2) DEFAULT 0.90,
                max_tokens INTEGER DEFAULT 4096,
                is_active INTEGER DEFAULT 1,
                execution_mode VARCHAR(20) DEFAULT 'realtime',
                created_at DATETIME DEFAULT NOW(),
                updated_at DATETIME DEFAULT NOW()
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS agent_tasks (
                id VARCHAR(36) PRIMARY KEY,
                task_type VARCHAR(100) NOT NULL,
                agent_type VARCHAR(50),
                status VARCHAR(30) DEFAULT 'queued',
                priority INTEGER DEFAULT 0,
                params JSON,
                result JSON,
                error_message TEXT,
                progress INTEGER DEFAULT 0,
                progress_message VARCHAR(500),
                created_by VARCHAR(36),
                started_at DATETIME,
                completed_at DATETIME,
                created_at DATETIME DEFAULT NOW()
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS agent_decisions (
                id VARCHAR(36) PRIMARY KEY,
                agent_type VARCHAR(50) NOT NULL,
                trigger_type VARCHAR(50),
                trigger_id VARCHAR(200),
                action_taken VARCHAR(200),
                confidence DECIMAL(5,2),
                reasoning TEXT,
                was_auto_executed INTEGER DEFAULT 0,
                was_overridden INTEGER DEFAULT 0,
                override_by VARCHAR(36),
                override_reason TEXT,
                input_summary TEXT,
                output_summary TEXT,
                tokens_used INTEGER,
                cost_usd DECIMAL(8,4),
                execution_ms INTEGER,
                created_at DATETIME DEFAULT NOW()
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS agent_review_queue (
                id VARCHAR(36) PRIMARY KEY,
                decision_id VARCHAR(36) NOT NULL,
                agent_type VARCHAR(50) NOT NULL,
                proposed_action VARCHAR(200),
                context_summary TEXT,
                confidence DECIMAL(5,2),
                status VARCHAR(30) DEFAULT 'pending',
                reviewed_by VARCHAR(36),
                reviewed_at DATETIME,
                created_at DATETIME DEFAULT NOW()
            )""")

            # Indexes
            index_stmts = [
                "CREATE INDEX idx_agent_tasks_status ON agent_tasks(status)",
                "CREATE INDEX idx_agent_tasks_type ON agent_tasks(task_type)",
                "CREATE INDEX idx_agent_decisions_type ON agent_decisions(agent_type)",
                "CREATE INDEX idx_agent_decisions_created ON agent_decisions(created_at)",
                "CREATE INDEX idx_agent_review_status ON agent_review_queue(status)",
                "CREATE INDEX idx_agent_review_decision ON agent_review_queue(decision_id)",
            ]
            for stmt in index_stmts:
                try:
                    cur.execute(stmt)
                except Exception:
                    pass  # index already exists

        db.commit()

        # Seed default agent configs if empty
        count = fetchone(db, "SELECT COUNT(*) as c FROM agent_configs")
        if count and count['c'] == 0:
            _seed_agent_configs(db)
            db.commit()


def _seed_agent_configs(db):
    agents = [
        ('order_processor', 'Order Processor', 'Auto-confirms orders, flags fraud, creates outbound lines', 'realtime'),
        ('message_responder', 'Message Responder', 'Auto-replies to customer messages, escalates complex issues', 'realtime'),
        ('stock_sync', 'Stock Sync Agent', 'Pushes inventory levels to all connected platforms', 'realtime'),
        ('fulfillment_coordinator', 'Fulfillment Coordinator', 'Batches orders, generates pick lists, triggers print jobs', 'deep'),
        ('returns_handler', 'Returns Handler', 'Auto-approves eligible returns, processes refunds', 'realtime'),
        ('affiliate_manager', 'Affiliate Manager', 'Tracks performance, approves samples, identifies top performers', 'deep'),
    ]
    for agent_type, display_name, description, execution_mode in agents:
        execute(db,
            "INSERT INTO agent_configs (id, agent_type, display_name, description, execution_mode, created_at, updated_at) "
            "VALUES (%s,%s,%s,%s,%s,NOW(),NOW())",
            (str(uuid.uuid4()), agent_type, display_name, description, execution_mode))
