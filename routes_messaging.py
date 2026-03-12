"""
NEXRAY v3 — Unified Inbox / Messaging API Routes
Inbox channels, conversations, messages, canned responses, message templates, and webhooks.
"""

from fastapi import APIRouter, Request, HTTPException
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


# ========== SCHEMA INIT ==========

def init_messaging_db():
    """Create messaging tables if they don't exist."""
    with get_db() as db:
        with db.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS inbox_channels (
                id VARCHAR(36) PRIMARY KEY,
                platform VARCHAR(50) NOT NULL,
                account_name VARCHAR(200),
                account_id VARCHAR(200),
                access_token TEXT,
                webhook_secret VARCHAR(200),
                company_label VARCHAR(200),
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT NOW(),
                updated_at DATETIME DEFAULT NOW()
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id VARCHAR(36) PRIMARY KEY,
                inbox_channel_id VARCHAR(36) NOT NULL,
                platform VARCHAR(50) NOT NULL,
                platform_conversation_id VARCHAR(200),
                customer_name VARCHAR(300),
                customer_phone VARCHAR(100),
                customer_email VARCHAR(200),
                customer_platform_id VARCHAR(200),
                customer_avatar_url VARCHAR(500),
                ecommerce_order_id VARCHAR(36),
                status VARCHAR(30) DEFAULT 'open',
                assigned_to VARCHAR(36),
                priority VARCHAR(20) DEFAULT 'normal',
                tags JSON,
                last_message_at DATETIME,
                last_message_preview VARCHAR(500),
                unread_count INTEGER DEFAULT 0,
                company_label VARCHAR(200),
                created_at DATETIME DEFAULT NOW(),
                updated_at DATETIME DEFAULT NOW()
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id VARCHAR(36) PRIMARY KEY,
                conversation_id VARCHAR(36) NOT NULL,
                direction VARCHAR(10) NOT NULL,
                sender_type VARCHAR(20) NOT NULL,
                sender_name VARCHAR(200),
                sender_id VARCHAR(36),
                content TEXT NOT NULL,
                content_type VARCHAR(30) DEFAULT 'text',
                media_url VARCHAR(500),
                platform_message_id VARCHAR(200),
                is_ai_generated INTEGER DEFAULT 0,
                ai_confidence DECIMAL(5,2),
                metadata JSON,
                created_at DATETIME DEFAULT NOW()
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS canned_responses (
                id VARCHAR(36) PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                content TEXT NOT NULL,
                category VARCHAR(100),
                language VARCHAR(20) DEFAULT 'en',
                shortcut VARCHAR(50),
                company_label VARCHAR(200),
                is_active INTEGER DEFAULT 1,
                usage_count INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT NOW()
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS message_templates (
                id VARCHAR(36) PRIMARY KEY,
                platform VARCHAR(50),
                name VARCHAR(200) NOT NULL,
                content TEXT NOT NULL,
                variables JSON,
                status VARCHAR(30) DEFAULT 'draft',
                company_label VARCHAR(200),
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT NOW()
            )""")

            # Indexes
            index_stmts = [
                "CREATE INDEX idx_conv_channel ON conversations(inbox_channel_id)",
                "CREATE INDEX idx_conv_status ON conversations(status)",
                "CREATE INDEX idx_conv_platform ON conversations(platform)",
                "CREATE INDEX idx_conv_assigned ON conversations(assigned_to)",
                "CREATE INDEX idx_conv_last_msg ON conversations(last_message_at)",
                "CREATE INDEX idx_msg_conv ON messages(conversation_id)",
                "CREATE INDEX idx_msg_created ON messages(created_at)",
                "CREATE INDEX idx_canned_shortcut ON canned_responses(shortcut)",
            ]
            for stmt in index_stmts:
                try:
                    cur.execute(stmt)
                except Exception:
                    pass  # index already exists

        db.commit()


# ========== INBOX CHANNELS ==========

@router.get("/api/inbox_channels")
async def list_inbox_channels(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'manager', 'inventory_admin')
    with get_db() as db:
        channels = rows_to_list(fetchall(db,
            "SELECT * FROM inbox_channels ORDER BY created_at DESC"))
    return {'channels': channels}


@router.post("/api/inbox_channels")
async def create_inbox_channel(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'manager')
    body = await request.json()
    platform = (body.get('platform') or '').strip()
    if not platform:
        raise HTTPException(status_code=400, detail="platform is required")
    if platform not in ('messenger', 'instagram', 'whatsapp', 'viber'):
        raise HTTPException(status_code=400, detail="platform must be one of: messenger, instagram, whatsapp, viber")
    cid = str(uuid.uuid4())
    with get_db() as db:
        execute(db,
            "INSERT INTO inbox_channels (id, platform, account_name, account_id, access_token, "
            "webhook_secret, company_label, is_active) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (cid, platform, body.get('account_name'), body.get('account_id'),
             body.get('access_token'), body.get('webhook_secret'),
             body.get('company_label'), body.get('is_active', 1)))
        write_audit(db, user['uid'], 'create', 'inbox_channel', cid, None, body)
        db.commit()
    return {'id': cid, 'success': True}


@router.put("/api/inbox_channels/{channel_id}")
async def update_inbox_channel(request: Request, channel_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'manager')
    body = await request.json()
    with get_db() as db:
        before = dict_from_row(fetchone(db, "SELECT * FROM inbox_channels WHERE id=%s", (channel_id,)))
        if not before:
            raise HTTPException(status_code=404, detail="Inbox channel not found")
        allowed = ('platform', 'account_name', 'account_id', 'access_token',
                   'webhook_secret', 'company_label', 'is_active')
        fields = {k: v for k, v in body.items() if k in allowed}
        if fields:
            set_clause = ", ".join(f"{k}=%s" for k in fields)
            set_clause += ", updated_at=NOW()"
            execute(db, f"UPDATE inbox_channels SET {set_clause} WHERE id=%s",
                    list(fields.values()) + [channel_id])
        write_audit(db, user['uid'], 'update', 'inbox_channel', channel_id, before, fields)
        db.commit()
    return {'success': True}


@router.delete("/api/inbox_channels/{channel_id}")
async def delete_inbox_channel(request: Request, channel_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'manager')
    with get_db() as db:
        before = dict_from_row(fetchone(db, "SELECT * FROM inbox_channels WHERE id=%s", (channel_id,)))
        if not before:
            raise HTTPException(status_code=404, detail="Inbox channel not found")
        execute(db, "UPDATE inbox_channels SET is_active=0, updated_at=NOW() WHERE id=%s", (channel_id,))
        write_audit(db, user['uid'], 'deactivate', 'inbox_channel', channel_id,
                    {'is_active': 1}, {'is_active': 0})
        db.commit()
    return {'success': True}


# ========== CONVERSATIONS ==========

@router.get("/api/conversations")
async def list_conversations(request: Request,
                             platform: str = None,
                             status: str = None,
                             assigned_to: str = None,
                             company_label: str = None,
                             search: str = None):
    user = require_auth(request)
    require_role(user, 'system_admin', 'manager', 'inventory_admin', 'warehouse_lead')
    with get_db() as db:
        query = """SELECT c.*, ic.account_name as channel_account_name
                   FROM conversations c
                   LEFT JOIN inbox_channels ic ON c.inbox_channel_id = ic.id
                   WHERE 1=1"""
        args = []
        if platform:
            query += " AND c.platform=%s"; args.append(platform)
        if status:
            query += " AND c.status=%s"; args.append(status)
        if assigned_to:
            query += " AND c.assigned_to=%s"; args.append(assigned_to)
        if company_label:
            query += " AND c.company_label=%s"; args.append(company_label)
        if search:
            query += " AND (c.customer_name LIKE %s OR c.customer_email LIKE %s OR c.last_message_preview LIKE %s)"
            like = f"%{search}%"
            args.extend([like, like, like])
        query += " ORDER BY c.last_message_at DESC"
        conversations = rows_to_list(fetchall(db, query, args))
    return {'conversations': conversations}


@router.get("/api/conversations/{conversation_id}")
async def get_conversation(request: Request, conversation_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'manager', 'inventory_admin', 'warehouse_lead')
    with get_db() as db:
        conv = dict_from_row(fetchone(db, """
            SELECT c.*, ic.account_name as channel_account_name, ic.platform as channel_platform
            FROM conversations c
            LEFT JOIN inbox_channels ic ON c.inbox_channel_id = ic.id
            WHERE c.id=%s
        """, (conversation_id,)))
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        msgs = rows_to_list(fetchall(db,
            "SELECT * FROM messages WHERE conversation_id=%s ORDER BY created_at ASC",
            (conversation_id,)))
        conv['messages'] = msgs
    return conv


@router.put("/api/conversations/{conversation_id}")
async def update_conversation(request: Request, conversation_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'manager', 'inventory_admin', 'warehouse_lead')
    body = await request.json()
    with get_db() as db:
        before = dict_from_row(fetchone(db, "SELECT * FROM conversations WHERE id=%s", (conversation_id,)))
        if not before:
            raise HTTPException(status_code=404, detail="Conversation not found")
        allowed = ('status', 'assigned_to', 'priority', 'tags', 'company_label', 'ecommerce_order_id')
        fields = {}
        for k, v in body.items():
            if k in allowed:
                fields[k] = json.dumps(v) if k == 'tags' and isinstance(v, (list, dict)) else v
        if fields:
            set_clause = ", ".join(f"{k}=%s" for k in fields)
            set_clause += ", updated_at=NOW()"
            execute(db, f"UPDATE conversations SET {set_clause} WHERE id=%s",
                    list(fields.values()) + [conversation_id])
        write_audit(db, user['uid'], 'update', 'conversation', conversation_id, before, fields)
        db.commit()
    return {'success': True}


@router.post("/api/conversations/{conversation_id}/assign")
async def assign_conversation(request: Request, conversation_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'manager', 'inventory_admin', 'warehouse_lead')
    body = await request.json()
    assigned_to = body.get('assigned_to')
    if not assigned_to:
        raise HTTPException(status_code=400, detail="assigned_to is required")
    with get_db() as db:
        before = dict_from_row(fetchone(db, "SELECT * FROM conversations WHERE id=%s", (conversation_id,)))
        if not before:
            raise HTTPException(status_code=404, detail="Conversation not found")
        execute(db,
            "UPDATE conversations SET assigned_to=%s, status='assigned', updated_at=NOW() WHERE id=%s",
            (assigned_to, conversation_id))
        write_audit(db, user['uid'], 'assign', 'conversation', conversation_id,
                    {'assigned_to': before.get('assigned_to'), 'status': before.get('status')},
                    {'assigned_to': assigned_to, 'status': 'assigned'})
        db.commit()
    return {'success': True}


@router.post("/api/conversations/{conversation_id}/resolve")
async def resolve_conversation(request: Request, conversation_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'manager', 'inventory_admin', 'warehouse_lead')
    with get_db() as db:
        before = dict_from_row(fetchone(db, "SELECT * FROM conversations WHERE id=%s", (conversation_id,)))
        if not before:
            raise HTTPException(status_code=404, detail="Conversation not found")
        execute(db,
            "UPDATE conversations SET status='resolved', updated_at=NOW() WHERE id=%s",
            (conversation_id,))
        write_audit(db, user['uid'], 'resolve', 'conversation', conversation_id,
                    {'status': before.get('status')}, {'status': 'resolved'})
        db.commit()
    return {'success': True}


@router.post("/api/conversations/{conversation_id}/reopen")
async def reopen_conversation(request: Request, conversation_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'manager', 'inventory_admin', 'warehouse_lead')
    with get_db() as db:
        before = dict_from_row(fetchone(db, "SELECT * FROM conversations WHERE id=%s", (conversation_id,)))
        if not before:
            raise HTTPException(status_code=404, detail="Conversation not found")
        execute(db,
            "UPDATE conversations SET status='open', updated_at=NOW() WHERE id=%s",
            (conversation_id,))
        write_audit(db, user['uid'], 'reopen', 'conversation', conversation_id,
                    {'status': before.get('status')}, {'status': 'open'})
        db.commit()
    return {'success': True}


# ========== MESSAGES ==========

@router.get("/api/conversations/{conversation_id}/messages")
async def list_messages(request: Request, conversation_id: str,
                        limit: int = 50, offset: int = 0):
    user = require_auth(request)
    require_role(user, 'system_admin', 'manager', 'inventory_admin', 'warehouse_lead')
    with get_db() as db:
        conv = fetchone(db, "SELECT id FROM conversations WHERE id=%s", (conversation_id,))
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        total_row = fetchone(db,
            "SELECT COUNT(*) as c FROM messages WHERE conversation_id=%s", (conversation_id,))
        total = total_row['c'] if total_row else 0
        msgs = rows_to_list(fetchall(db,
            "SELECT * FROM messages WHERE conversation_id=%s ORDER BY created_at ASC LIMIT %s OFFSET %s",
            (conversation_id, limit, offset)))
    return {'messages': msgs, 'total': total, 'limit': limit, 'offset': offset}


@router.post("/api/conversations/{conversation_id}/messages")
async def send_message(request: Request, conversation_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'manager', 'inventory_admin', 'warehouse_lead')
    body = await request.json()
    content = (body.get('content') or '').strip()
    if not content:
        raise HTTPException(status_code=400, detail="content is required")
    with get_db() as db:
        conv = dict_from_row(fetchone(db, "SELECT * FROM conversations WHERE id=%s", (conversation_id,)))
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        mid = str(uuid.uuid4())
        now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        execute(db,
            "INSERT INTO messages (id, conversation_id, direction, sender_type, sender_name, sender_id, "
            "content, content_type, media_url, is_ai_generated, metadata, created_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (mid, conversation_id, 'outbound', body.get('sender_type', 'agent'),
             user.get('display_name', user.get('username')), user['uid'],
             content, body.get('content_type', 'text'), body.get('media_url'),
             body.get('is_ai_generated', 0),
             json.dumps(body.get('metadata')) if body.get('metadata') else None,
             now_str))
        preview = content[:500] if len(content) > 500 else content
        execute(db,
            "UPDATE conversations SET last_message_at=%s, last_message_preview=%s, updated_at=NOW() WHERE id=%s",
            (now_str, preview, conversation_id))
        db.commit()
    return {'id': mid, 'success': True}


@router.post("/api/conversations/{conversation_id}/messages/ai_draft")
async def ai_draft_message(request: Request, conversation_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'manager', 'inventory_admin', 'warehouse_lead')
    with get_db() as db:
        conv = dict_from_row(fetchone(db, "SELECT * FROM conversations WHERE id=%s", (conversation_id,)))
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
    # Stub: return a placeholder draft
    return {
        'draft': 'Thank you for reaching out! Let me look into this for you and get back to you shortly.',
        'confidence': 0.0,
        'is_stub': True,
    }


# ========== CANNED RESPONSES ==========

@router.get("/api/canned_responses")
async def list_canned_responses(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'manager', 'inventory_admin', 'warehouse_lead')
    with get_db() as db:
        responses = rows_to_list(fetchall(db,
            "SELECT * FROM canned_responses WHERE is_active=1 ORDER BY usage_count DESC, title ASC"))
    return {'canned_responses': responses}


@router.post("/api/canned_responses")
async def create_canned_response(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'manager')
    body = await request.json()
    title = (body.get('title') or '').strip()
    content = (body.get('content') or '').strip()
    if not title or not content:
        raise HTTPException(status_code=400, detail="title and content are required")
    cid = str(uuid.uuid4())
    with get_db() as db:
        execute(db,
            "INSERT INTO canned_responses (id, title, content, category, language, shortcut, "
            "company_label, is_active) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (cid, title, content, body.get('category'), body.get('language', 'en'),
             body.get('shortcut'), body.get('company_label'), body.get('is_active', 1)))
        write_audit(db, user['uid'], 'create', 'canned_response', cid, None, body)
        db.commit()
    return {'id': cid, 'success': True}


@router.put("/api/canned_responses/{response_id}")
async def update_canned_response(request: Request, response_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'manager')
    body = await request.json()
    with get_db() as db:
        before = dict_from_row(fetchone(db, "SELECT * FROM canned_responses WHERE id=%s", (response_id,)))
        if not before:
            raise HTTPException(status_code=404, detail="Canned response not found")
        allowed = ('title', 'content', 'category', 'language', 'shortcut', 'company_label', 'is_active')
        fields = {k: v for k, v in body.items() if k in allowed}
        if fields:
            set_clause = ", ".join(f"{k}=%s" for k in fields)
            execute(db, f"UPDATE canned_responses SET {set_clause} WHERE id=%s",
                    list(fields.values()) + [response_id])
        write_audit(db, user['uid'], 'update', 'canned_response', response_id, before, fields)
        db.commit()
    return {'success': True}


@router.delete("/api/canned_responses/{response_id}")
async def delete_canned_response(request: Request, response_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'manager')
    with get_db() as db:
        before = dict_from_row(fetchone(db, "SELECT * FROM canned_responses WHERE id=%s", (response_id,)))
        if not before:
            raise HTTPException(status_code=404, detail="Canned response not found")
        execute(db, "UPDATE canned_responses SET is_active=0 WHERE id=%s", (response_id,))
        write_audit(db, user['uid'], 'deactivate', 'canned_response', response_id,
                    {'is_active': 1}, {'is_active': 0})
        db.commit()
    return {'success': True}


# ========== MESSAGE TEMPLATES ==========

@router.get("/api/message_templates")
async def list_message_templates(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'manager', 'inventory_admin', 'warehouse_lead')
    with get_db() as db:
        templates = rows_to_list(fetchall(db,
            "SELECT * FROM message_templates WHERE is_active=1 ORDER BY name ASC"))
    return {'templates': templates}


@router.post("/api/message_templates")
async def create_message_template(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'manager')
    body = await request.json()
    name = (body.get('name') or '').strip()
    content = (body.get('content') or '').strip()
    if not name or not content:
        raise HTTPException(status_code=400, detail="name and content are required")
    tid = str(uuid.uuid4())
    with get_db() as db:
        execute(db,
            "INSERT INTO message_templates (id, platform, name, content, variables, status, "
            "company_label, is_active) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (tid, body.get('platform'), name, content,
             json.dumps(body.get('variables')) if body.get('variables') else None,
             body.get('status', 'draft'), body.get('company_label'), body.get('is_active', 1)))
        write_audit(db, user['uid'], 'create', 'message_template', tid, None, body)
        db.commit()
    return {'id': tid, 'success': True}


@router.put("/api/message_templates/{template_id}")
async def update_message_template(request: Request, template_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'manager')
    body = await request.json()
    with get_db() as db:
        before = dict_from_row(fetchone(db, "SELECT * FROM message_templates WHERE id=%s", (template_id,)))
        if not before:
            raise HTTPException(status_code=404, detail="Message template not found")
        allowed = ('platform', 'name', 'content', 'variables', 'status', 'company_label', 'is_active')
        fields = {}
        for k, v in body.items():
            if k in allowed:
                fields[k] = json.dumps(v) if k == 'variables' and isinstance(v, (list, dict)) else v
        if fields:
            set_clause = ", ".join(f"{k}=%s" for k in fields)
            execute(db, f"UPDATE message_templates SET {set_clause} WHERE id=%s",
                    list(fields.values()) + [template_id])
        write_audit(db, user['uid'], 'update', 'message_template', template_id, before, fields)
        db.commit()
    return {'success': True}


# ========== WEBHOOKS (platform stubs) ==========

def _process_webhook(platform: str, payload: dict):
    """
    Generic webhook processor stub.
    Expects payload: {sender_id, sender_name, message_text, platform}
    Finds or creates a conversation, creates a message record, updates conversation metadata.
    """
    sender_id = (payload.get('sender_id') or '').strip()
    sender_name = payload.get('sender_name') or 'Unknown'
    message_text = (payload.get('message_text') or '').strip()

    if not sender_id or not message_text:
        raise HTTPException(status_code=400, detail="sender_id and message_text are required")

    with get_db() as db:
        # Find an active inbox channel for this platform
        channel = dict_from_row(fetchone(db,
            "SELECT * FROM inbox_channels WHERE platform=%s AND is_active=1 LIMIT 1",
            (platform,)))

        # If no channel configured, create a placeholder so messages aren't lost
        if not channel:
            channel_id = str(uuid.uuid4())
            execute(db,
                "INSERT INTO inbox_channels (id, platform, account_name, is_active) VALUES (%s,%s,%s,%s)",
                (channel_id, platform, f'{platform}_default', 1))
            channel = {'id': channel_id}
        else:
            channel_id = channel['id']

        # Find existing conversation by customer_platform_id + channel
        conv = dict_from_row(fetchone(db,
            "SELECT * FROM conversations WHERE inbox_channel_id=%s AND customer_platform_id=%s",
            (channel_id, sender_id)))

        now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

        if not conv:
            conv_id = str(uuid.uuid4())
            execute(db,
                "INSERT INTO conversations (id, inbox_channel_id, platform, customer_name, "
                "customer_platform_id, status, last_message_at, last_message_preview, "
                "unread_count, created_at, updated_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (conv_id, channel_id, platform, sender_name, sender_id,
                 'open', now_str, message_text[:500], 1, now_str, now_str))
        else:
            conv_id = conv['id']
            new_unread = (conv.get('unread_count') or 0) + 1
            execute(db,
                "UPDATE conversations SET last_message_at=%s, last_message_preview=%s, "
                "unread_count=%s, updated_at=NOW() WHERE id=%s",
                (now_str, message_text[:500], new_unread, conv_id))

        # Create message record
        mid = str(uuid.uuid4())
        execute(db,
            "INSERT INTO messages (id, conversation_id, direction, sender_type, sender_name, "
            "content, content_type, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (mid, conv_id, 'inbound', 'customer', sender_name,
             message_text, 'text', now_str))

        db.commit()

    return {'conversation_id': conv_id, 'message_id': mid}


@router.post("/api/webhooks/messenger")
async def webhook_messenger(request: Request):
    body = await request.json()
    payload = {**body, 'platform': 'messenger'}
    result = _process_webhook('messenger', payload)
    return result


@router.post("/api/webhooks/instagram")
async def webhook_instagram(request: Request):
    body = await request.json()
    payload = {**body, 'platform': 'instagram'}
    result = _process_webhook('instagram', payload)
    return result


@router.post("/api/webhooks/whatsapp")
async def webhook_whatsapp(request: Request):
    body = await request.json()
    payload = {**body, 'platform': 'whatsapp'}
    result = _process_webhook('whatsapp', payload)
    return result


@router.post("/api/webhooks/viber")
async def webhook_viber(request: Request):
    body = await request.json()
    payload = {**body, 'platform': 'viber'}
    result = _process_webhook('viber', payload)
    return result
