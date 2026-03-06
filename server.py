# NOTE: After renaming entities, delete nexray.db and restart to re-seed.
"""
NEXRAY — FastAPI Backend Server
Private internal operations platform for multi-entity warehouse and order operations.
Deploy on Railway, Render, or any cloud platform.
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import sqlite3
import hashlib
import uuid
import os
import json
import mimetypes
from datetime import datetime, timezone, timedelta
from contextlib import contextmanager

# ========== CONFIG ==========
DB_PATH = os.environ.get("NEXRAY_DB_PATH", "nexray.db")

app = FastAPI(title="NEXRAY Operations Platform", version="2.0.0")

# ========== CORS ==========
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== DATABASE ==========
@contextmanager
def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
    finally:
        db.close()

def rows_to_list(rows):
    return [dict(r) for r in rows]

def dict_from_row(row):
    return dict(row) if row else None

# ========== AUTH HELPERS ==========
def get_session_user(request: Request):
    """Extract and validate session from Authorization header. Returns user dict or None."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    with get_db() as db:
        row = db.execute(
            "SELECT s.*, u.id as uid, u.username, u.display_name, u.email, u.role, u.entity_id, u.warehouse_id, u.is_active "
            "FROM sessions s JOIN users u ON s.user_id = u.id "
            "WHERE s.token=? AND s.expires_at > ? AND u.is_active=1",
            (token, now)
        ).fetchone()
    return dict_from_row(row)

def require_auth(request: Request):
    """Raises 401 if not authenticated. Returns user dict."""
    user = get_session_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized: valid session required")
    return user

ROLE_HIERARCHY = {
    'system_admin': 100,
    'inventory_admin': 80,
    'warehouse_lead': 70,
    'manager': 60,
    'warehouse_operator': 50,
    'accounting_operator': 30,
}

def require_role(user: dict, *allowed_roles):
    """Raises 403 if user role not in allowed_roles. system_admin always passes."""
    if user['role'] == 'system_admin':
        return
    if user['role'] not in allowed_roles:
        raise HTTPException(status_code=403, detail=f"Forbidden: requires one of {allowed_roles}")

def resolve_entity_id(user: dict, requested_entity_id: str = None) -> str:
    """For system_admin, allow any entity_id. For others, force their own."""
    if user['role'] == 'system_admin' and requested_entity_id:
        return requested_entity_id
    return user.get('entity_id') or requested_entity_id or 'ent-01'

def write_audit(db, entity_id, actor_user_id, action, object_type, object_id,
                before_json=None, after_json=None, reason_code=None, notes=None, source_channel='web'):
    db.execute(
        "INSERT INTO audit_logs (id, entity_id, actor_user_id, action, object_type, object_id, "
        "before_json, after_json, reason_code, notes, source_channel) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (str(uuid.uuid4()), entity_id, actor_user_id, action, object_type, object_id,
         json.dumps(before_json) if before_json and not isinstance(before_json, str) else before_json,
         json.dumps(after_json) if after_json and not isinstance(after_json, str) else after_json,
         reason_code, notes, source_channel)
    )

# ========== DB INIT ==========
def init_db():
    with get_db() as db:
        db.executescript("""
        -- ========== IDENTITY & ACCESS ==========
        CREATE TABLE IF NOT EXISTS entities (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            name TEXT NOT NULL,
            code TEXT UNIQUE NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            username TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            email TEXT,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('system_admin','inventory_admin','warehouse_operator','warehouse_lead','manager','accounting_operator')),
            entity_id TEXT,
            warehouse_id TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        -- ========== MASTER DATA ==========
        CREATE TABLE IF NOT EXISTS warehouses (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            entity_id TEXT NOT NULL,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            address TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (entity_id) REFERENCES entities(id)
        );

        CREATE TABLE IF NOT EXISTS locations (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            warehouse_id TEXT NOT NULL,
            zone_code TEXT,
            aisle_code TEXT,
            rack_code TEXT NOT NULL,
            level_code TEXT,
            bin_code TEXT,
            location_barcode TEXT UNIQUE,
            location_type TEXT DEFAULT 'rack' CHECK(location_type IN ('rack','bin','staging','dispatch','overflow')),
            capacity_qty REAL,
            is_pickable INTEGER DEFAULT 1,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(id)
        );

        CREATE TABLE IF NOT EXISTS items (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            entity_id TEXT NOT NULL,
            sku TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            item_type TEXT NOT NULL CHECK(item_type IN ('fabric','component')),
            base_uom TEXT DEFAULT 'meter',
            category TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(entity_id, sku),
            FOREIGN KEY (entity_id) REFERENCES entities(id)
        );

        CREATE TABLE IF NOT EXISTS suppliers (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            entity_id TEXT NOT NULL,
            name TEXT NOT NULL,
            code TEXT,
            contact_info TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (entity_id) REFERENCES entities(id)
        );

        CREATE TABLE IF NOT EXISTS customers (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            entity_id TEXT NOT NULL,
            name TEXT NOT NULL,
            code TEXT,
            contact_info TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (entity_id) REFERENCES entities(id)
        );

        CREATE TABLE IF NOT EXISTS item_aliases (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            item_id TEXT NOT NULL,
            alias_name TEXT NOT NULL,
            branch_context TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (item_id) REFERENCES items(id)
        );

        -- ========== INBOUND ==========
        CREATE TABLE IF NOT EXISTS supplier_order_lists (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            entity_id TEXT NOT NULL,
            supplier_id TEXT,
            batch_code TEXT UNIQUE,
            import_hash TEXT,
            status TEXT DEFAULT 'draft' CHECK(status IN ('draft','validated','receiving','completed','failed_with_errors')),
            total_lines INTEGER DEFAULT 0,
            error_count INTEGER DEFAULT 0,
            notes TEXT,
            created_by TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (entity_id) REFERENCES entities(id)
        );

        CREATE TABLE IF NOT EXISTS supplier_order_list_lines (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            supplier_order_list_id TEXT NOT NULL,
            line_no INTEGER NOT NULL,
            item_id TEXT,
            item_name_raw TEXT,
            qty_expected REAL NOT NULL,
            uom TEXT DEFAULT 'meter',
            lot_info TEXT,
            shade_info TEXT,
            width_info TEXT,
            validation_status TEXT DEFAULT 'pending' CHECK(validation_status IN ('pending','valid','error')),
            validation_error TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (supplier_order_list_id) REFERENCES supplier_order_lists(id)
        );

        CREATE TABLE IF NOT EXISTS receivings (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            entity_id TEXT NOT NULL,
            warehouse_id TEXT NOT NULL,
            supplier_order_list_id TEXT,
            status TEXT DEFAULT 'in_progress' CHECK(status IN ('in_progress','completed','cancelled')),
            received_by TEXT,
            received_at TEXT DEFAULT (datetime('now')),
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (entity_id) REFERENCES entities(id),
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(id)
        );

        -- ========== INVENTORY ==========
        CREATE TABLE IF NOT EXISTS inventory_lots (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            entity_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            tracking_id TEXT UNIQUE NOT NULL,
            lot_no TEXT,
            batch_no TEXT,
            shade_code TEXT,
            width_value REAL,
            qty_original REAL NOT NULL,
            qty_on_hand REAL NOT NULL,
            qty_reserved REAL DEFAULT 0,
            warehouse_id TEXT NOT NULL,
            location_id TEXT,
            status TEXT DEFAULT 'active' CHECK(status IN ('active','quarantined','consumed','lost','archived')),
            qty_confidence TEXT DEFAULT 'measured' CHECK(qty_confidence IN ('measured','supplier_reported')),
            receiving_id TEXT,
            supplier_order_line_id TEXT,
            created_by TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (entity_id) REFERENCES entities(id),
            FOREIGN KEY (item_id) REFERENCES items(id),
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
            FOREIGN KEY (location_id) REFERENCES locations(id)
        );

        CREATE TABLE IF NOT EXISTS inventory_movements (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            event_idempotency_key TEXT UNIQUE NOT NULL,
            movement_type TEXT NOT NULL CHECK(movement_type IN ('receive','deduct','adjust_up','adjust_down','move','transfer_out','transfer_in','void')),
            entity_id TEXT NOT NULL,
            inventory_lot_id TEXT NOT NULL,
            tracking_id TEXT,
            sales_order_line_id TEXT,
            cut_transaction_id TEXT,
            qty_delta REAL NOT NULL,
            qty_before REAL NOT NULL,
            qty_after REAL NOT NULL,
            warehouse_from_id TEXT,
            location_from_id TEXT,
            warehouse_to_id TEXT,
            location_to_id TEXT,
            reason_code TEXT,
            action_by TEXT NOT NULL,
            action_at TEXT DEFAULT (datetime('now')),
            source_channel TEXT DEFAULT 'web',
            meta_json TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS inventory_reservations (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            entity_id TEXT NOT NULL,
            inventory_lot_id TEXT NOT NULL,
            outbound_request_line_id TEXT,
            qty_reserved REAL NOT NULL,
            status TEXT DEFAULT 'active' CHECK(status IN ('active','released','cancelled')),
            created_by TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        -- ========== OUTBOUND ==========
        CREATE TABLE IF NOT EXISTS outbound_request_batches (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            entity_id TEXT NOT NULL,
            batch_code TEXT UNIQUE,
            import_hash TEXT,
            status TEXT DEFAULT 'draft' CHECK(status IN ('draft','validated','processing','completed','failed_with_errors')),
            total_lines INTEGER DEFAULT 0,
            error_count INTEGER DEFAULT 0,
            file_name TEXT,
            created_by TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (entity_id) REFERENCES entities(id)
        );

        CREATE TABLE IF NOT EXISTS outbound_requests (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            batch_id TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            warehouse_id TEXT NOT NULL,
            customer_id TEXT,
            reference_no TEXT,
            priority INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (batch_id) REFERENCES outbound_request_batches(id),
            FOREIGN KEY (entity_id) REFERENCES entities(id)
        );

        CREATE TABLE IF NOT EXISTS outbound_request_lines (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            outbound_request_id TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            line_no INTEGER NOT NULL,
            item_id TEXT,
            item_name_raw TEXT,
            qty_requested REAL NOT NULL,
            qty_allocated REAL DEFAULT 0,
            qty_fulfilled REAL DEFAULT 0,
            qty_variance REAL DEFAULT 0,
            uom TEXT DEFAULT 'meter',
            variance_reason_code TEXT,
            variance_approved_by TEXT,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending','allocated','in_progress','cut_complete','tagged','closed','cancelled','blocked','needs_approval')),
            claimed_by TEXT,
            claimed_at TEXT,
            picked_by TEXT,
            picked_at TEXT,
            fulfilled_by TEXT,
            fulfilled_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (outbound_request_id) REFERENCES outbound_requests(id)
        );

        -- ========== EXECUTION ==========
        CREATE TABLE IF NOT EXISTS pick_tasks (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            entity_id TEXT NOT NULL,
            outbound_request_line_id TEXT NOT NULL,
            inventory_lot_id TEXT NOT NULL,
            warehouse_id TEXT NOT NULL,
            location_id TEXT,
            qty_to_pick REAL NOT NULL,
            qty_picked REAL DEFAULT 0,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending','in_progress','completed','cancelled')),
            assigned_to TEXT,
            started_at TEXT,
            completed_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (outbound_request_line_id) REFERENCES outbound_request_lines(id),
            FOREIGN KEY (inventory_lot_id) REFERENCES inventory_lots(id)
        );

        CREATE TABLE IF NOT EXISTS cut_transactions (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            entity_id TEXT NOT NULL,
            outbound_request_line_id TEXT NOT NULL,
            inventory_lot_id TEXT NOT NULL,
            tracking_id TEXT NOT NULL,
            qty_requested REAL NOT NULL,
            qty_actual REAL NOT NULL,
            qty_variance REAL GENERATED ALWAYS AS (qty_actual - qty_requested) STORED,
            variance_reason TEXT,
            variance_approved_by TEXT,
            status TEXT DEFAULT 'recorded' CHECK(status IN ('recorded','approved','rejected','voided')),
            cut_by TEXT NOT NULL,
            cut_at TEXT DEFAULT (datetime('now')),
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (outbound_request_line_id) REFERENCES outbound_request_lines(id),
            FOREIGN KEY (inventory_lot_id) REFERENCES inventory_lots(id)
        );

        CREATE TABLE IF NOT EXISTS tag_labels (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            tag_code TEXT UNIQUE NOT NULL,
            entity_id TEXT NOT NULL,
            cut_transaction_id TEXT,
            inventory_lot_id TEXT,
            outbound_request_line_id TEXT,
            tag_status TEXT DEFAULT 'generated' CHECK(tag_status IN ('generated','printed','scanned','invalidated','reprinted')),
            printed_at TEXT,
            printed_by TEXT,
            scanned_at TEXT,
            scanned_by TEXT,
            invalidated_at TEXT,
            invalidated_by TEXT,
            invalidate_reason TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (cut_transaction_id) REFERENCES cut_transactions(id)
        );

        CREATE TABLE IF NOT EXISTS print_jobs (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            entity_id TEXT NOT NULL,
            tag_label_id TEXT,
            job_type TEXT DEFAULT 'tag' CHECK(job_type IN ('tag','receiving_label','location_label')),
            status TEXT DEFAULT 'queued' CHECK(status IN ('queued','printing','printed','failed','retrying')),
            printer_id TEXT,
            retry_count INTEGER DEFAULT 0,
            error_message TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT,
            FOREIGN KEY (tag_label_id) REFERENCES tag_labels(id)
        );

        CREATE TABLE IF NOT EXISTS staging_batches (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            entity_id TEXT NOT NULL,
            batch_code TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'open' CHECK(status IN ('open','scanning','closed','cancelled')),
            created_by TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS staging_scans (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            staging_batch_id TEXT NOT NULL,
            outbound_request_line_id TEXT,
            inventory_lot_id TEXT,
            tracking_id TEXT,
            scanned_qty REAL,
            scan_result TEXT DEFAULT 'valid' CHECK(scan_result IN ('valid','duplicate','mismatch','blocked')),
            scanned_by TEXT,
            scanned_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (staging_batch_id) REFERENCES staging_batches(id)
        );

        CREATE TABLE IF NOT EXISTS putaway_events (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            entity_id TEXT NOT NULL,
            inventory_lot_id TEXT NOT NULL,
            from_location_id TEXT,
            to_location_id TEXT NOT NULL,
            qty_moved REAL NOT NULL,
            moved_by TEXT,
            moved_at TEXT DEFAULT (datetime('now')),
            status TEXT DEFAULT 'completed' CHECK(status IN ('pending','completed','cancelled')),
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (inventory_lot_id) REFERENCES inventory_lots(id)
        );

        -- ========== CONTROLS ==========
        CREATE TABLE IF NOT EXISTS adjustment_requests (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            entity_id TEXT NOT NULL,
            inventory_lot_id TEXT,
            outbound_request_line_id TEXT,
            adjustment_type TEXT NOT NULL CHECK(adjustment_type IN ('qty_correction','variance_approval','force_close','override','cycle_count')),
            qty_before REAL,
            qty_after REAL,
            reason_code TEXT NOT NULL,
            notes TEXT,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','cancelled')),
            requested_by TEXT NOT NULL,
            requested_at TEXT DEFAULT (datetime('now')),
            approved_by TEXT,
            approved_at TEXT,
            FOREIGN KEY (entity_id) REFERENCES entities(id)
        );

        CREATE TABLE IF NOT EXISTS reconciliation_runs (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            entity_id TEXT NOT NULL,
            run_type TEXT DEFAULT 'daily' CHECK(run_type IN ('daily','manual','cycle_count')),
            status TEXT DEFAULT 'running' CHECK(status IN ('running','completed','failed')),
            findings_count INTEGER DEFAULT 0,
            run_by TEXT,
            started_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT,
            FOREIGN KEY (entity_id) REFERENCES entities(id)
        );

        CREATE TABLE IF NOT EXISTS reconciliation_findings (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            reconciliation_run_id TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            finding_type TEXT NOT NULL CHECK(finding_type IN ('qty_mismatch','negative_balance','missing_tag','stuck_line','orphan_scan','unsync_event','low_remainder')),
            severity TEXT DEFAULT 'warning' CHECK(severity IN ('info','warning','critical')),
            description TEXT,
            resource_type TEXT,
            resource_id TEXT,
            resolution_status TEXT DEFAULT 'open' CHECK(resolution_status IN ('open','investigating','resolved','dismissed')),
            resolved_by TEXT,
            resolved_at TEXT,
            resolution_notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (reconciliation_run_id) REFERENCES reconciliation_runs(id)
        );

        -- ========== INTEGRATIONS ==========
        CREATE TABLE IF NOT EXISTS integration_events (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            entity_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_idempotency_key TEXT UNIQUE NOT NULL,
            payload_json TEXT,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending','processing','applied','failed','dead_letter')),
            direction TEXT DEFAULT 'outbound' CHECK(direction IN ('inbound','outbound')),
            retry_count INTEGER DEFAULT 0,
            error_message TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            processed_at TEXT
        );

        -- ========== AUDIT ==========
        CREATE TABLE IF NOT EXISTS audit_logs (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            entity_id TEXT,
            actor_user_id TEXT,
            action TEXT NOT NULL,
            object_type TEXT NOT NULL,
            object_id TEXT,
            before_json TEXT,
            after_json TEXT,
            reason_code TEXT,
            notes TEXT,
            source_channel TEXT DEFAULT 'web',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS automation_runs (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            automation_name TEXT NOT NULL,
            trigger_table TEXT,
            trigger_record_id TEXT,
            event_idempotency_key TEXT UNIQUE,
            run_status TEXT DEFAULT 'running' CHECK(run_status IN ('running','success','failed','retried','skipped')),
            error_message TEXT,
            started_at TEXT DEFAULT (datetime('now')),
            finished_at TEXT
        );

        CREATE TABLE IF NOT EXISTS workflow_locks (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            resource_type TEXT NOT NULL,
            resource_id TEXT NOT NULL,
            lock_owner TEXT NOT NULL,
            lock_acquired_at TEXT DEFAULT (datetime('now')),
            lock_expires_at TEXT,
            UNIQUE(resource_type, resource_id)
        );

        -- ========== NEW: SESSIONS ==========
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            user_id TEXT NOT NULL,
            token TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        -- ========== NEW: CHANNEL CONNECTIONS ==========
        CREATE TABLE IF NOT EXISTS channel_connections (
            id TEXT PRIMARY KEY,
            entity_id TEXT NOT NULL,
            channel_type TEXT NOT NULL CHECK(channel_type IN ('shopify','shopee','lazada','tiktokshop')),
            shop_name TEXT,
            api_key_encrypted TEXT,
            api_secret_encrypted TEXT,
            access_token_encrypted TEXT,
            refresh_token_encrypted TEXT,
            shop_url TEXT,
            region TEXT,
            is_active INTEGER DEFAULT 1,
            last_sync_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS channel_order_mappings (
            id TEXT PRIMARY KEY,
            channel_connection_id TEXT NOT NULL,
            channel_order_id TEXT NOT NULL,
            nexray_outbound_request_id TEXT,
            channel_status TEXT,
            sync_status TEXT DEFAULT 'pending' CHECK(sync_status IN ('pending','synced','error','skipped')),
            raw_order_json TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS channel_product_mappings (
            id TEXT PRIMARY KEY,
            channel_connection_id TEXT NOT NULL,
            channel_product_id TEXT,
            channel_sku TEXT,
            nexray_item_id TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );

        -- ========== INDEXES ==========
        CREATE INDEX IF NOT EXISTS idx_inv_lots_entity ON inventory_lots(entity_id);
        CREATE INDEX IF NOT EXISTS idx_inv_lots_warehouse ON inventory_lots(warehouse_id);
        CREATE INDEX IF NOT EXISTS idx_inv_lots_item ON inventory_lots(item_id);
        CREATE INDEX IF NOT EXISTS idx_inv_lots_tracking ON inventory_lots(tracking_id);
        CREATE INDEX IF NOT EXISTS idx_inv_lots_status ON inventory_lots(status);
        CREATE INDEX IF NOT EXISTS idx_inv_movements_lot ON inventory_movements(inventory_lot_id);
        CREATE INDEX IF NOT EXISTS idx_inv_movements_type ON inventory_movements(movement_type);
        CREATE INDEX IF NOT EXISTS idx_orl_status ON outbound_request_lines(status);
        CREATE INDEX IF NOT EXISTS idx_orl_entity ON outbound_request_lines(entity_id);
        CREATE INDEX IF NOT EXISTS idx_cut_txn_line ON cut_transactions(outbound_request_line_id);
        CREATE INDEX IF NOT EXISTS idx_tag_cut ON tag_labels(cut_transaction_id);
        CREATE INDEX IF NOT EXISTS idx_audit_object ON audit_logs(object_type, object_id);
        CREATE INDEX IF NOT EXISTS idx_integ_status ON integration_events(status);
        CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
        CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
        """)

        # Migration: add password_salt column if missing
        try:
            db.execute("ALTER TABLE users ADD COLUMN password_salt TEXT")
        except Exception:
            pass  # column already exists

        # Seed demo data if empty
        if db.execute("SELECT COUNT(*) FROM entities").fetchone()[0] == 0:
            seed_demo_data(db)

        db.commit()


def seed_demo_data(db):
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    entities = [
        ('ent-01', "Larry's Hitex Inc.", 'LHX'),
        ('ent-02', 'Fabric Life', 'FBL'),
        ('ent-03', 'CasaFinds', 'CSF'),
    ]
    for eid, name, code in entities:
        db.execute("INSERT INTO entities (id, name, code) VALUES (?,?,?)", (eid, name, code))

    users = [
        ('usr-01', 'admin', 'System Admin', 'admin@nexray.local', 'system_admin', 'ent-01', None),
        ('usr-02', 'warehouse1', 'Juan Cruz', 'juan@nexray.local', 'warehouse_operator', 'ent-01', 'wh-01'),
        ('usr-03', 'lead1', 'Maria Santos', 'maria@nexray.local', 'warehouse_lead', 'ent-01', 'wh-01'),
        ('usr-04', 'inv_admin', 'Carlos Reyes', 'carlos@nexray.local', 'inventory_admin', 'ent-01', None),
        ('usr-05', 'manager1', 'Ana Dela Cruz', 'ana@nexray.local', 'manager', 'ent-01', None),
        ('usr-06', 'acct1', 'Rose Lim', 'rose@nexray.local', 'accounting_operator', 'ent-01', None),
    ]
    for uid, uname, dname, email, role, eid, wid in users:
        # Default password = username; salted SHA256 hash
        salt = uuid.uuid4().hex[:16]
        phash = hashlib.sha256((salt + uname).encode()).hexdigest()
        db.execute("INSERT INTO users (id, username, display_name, email, password_hash, password_salt, role, entity_id, warehouse_id) VALUES (?,?,?,?,?,?,?,?,?)",
                   (uid, uname, dname, email, phash, salt, role, eid, wid))

    warehouses = [
        ('wh-01', 'ent-01', 'MNL-MAIN', 'Manila Design Center', 'Quezon City, Manila'),
        ('wh-02', 'ent-01', 'CEB-01', 'Cebu Distribution Hub', 'Mandaue, Cebu'),
        ('wh-03', 'ent-02', 'AUR-01', 'Aurora Storage Facility', 'Aurora, Quezon'),
    ]
    for wid, eid, code, name, addr in warehouses:
        db.execute("INSERT INTO warehouses (id, entity_id, code, name, address) VALUES (?,?,?,?,?)", (wid, eid, code, name, addr))

    locs = [
        ('loc-01', 'wh-01', 'A', '1', 'R01', '1', 'B01', 'MNL-A1-R01-1-B01', 'rack'),
        ('loc-02', 'wh-01', 'A', '1', 'R01', '2', 'B02', 'MNL-A1-R01-2-B02', 'rack'),
        ('loc-03', 'wh-01', 'A', '1', 'R02', '1', 'B01', 'MNL-A1-R02-1-B01', 'rack'),
        ('loc-04', 'wh-01', 'B', '1', 'R01', '1', 'B01', 'MNL-B1-R01-1-B01', 'bin'),
        ('loc-05', 'wh-01', None, None, 'STG', None, 'STG-01', 'MNL-STG-01', 'staging'),
        ('loc-06', 'wh-02', 'A', '1', 'R01', '1', 'B01', 'CEB-A1-R01-1-B01', 'rack'),
        ('loc-07', 'wh-03', 'A', '1', 'R01', '1', 'B01', 'AUR-A1-R01-1-B01', 'rack'),
    ]
    for lid, wid, zone, aisle, rack, level, binc, barcode, ltype in locs:
        db.execute("INSERT INTO locations (id, warehouse_id, zone_code, aisle_code, rack_code, level_code, bin_code, location_barcode, location_type) VALUES (?,?,?,?,?,?,?,?,?)",
                   (lid, wid, zone, aisle, rack, level, binc, barcode, ltype))

    items_data = [
        ('itm-01', 'ent-01', 'FAB-BLK-001', 'Blackout Curtain Fabric - Ivory', 'fabric', 'meter', 'Curtains'),
        ('itm-02', 'ent-01', 'FAB-SHR-001', 'Sheer Voile Fabric - White', 'fabric', 'meter', 'Curtains'),
        ('itm-03', 'ent-01', 'FAB-LIN-001', 'Linen Blend Fabric - Natural', 'fabric', 'meter', 'Curtains'),
        ('itm-04', 'ent-01', 'FAB-VEL-001', 'Velvet Fabric - Emerald', 'fabric', 'meter', 'Curtains'),
        ('itm-05', 'ent-01', 'CMP-ROD-001', 'Curtain Rod - Brushed Nickel 1.2m', 'component', 'piece', 'Hardware'),
        ('itm-06', 'ent-01', 'CMP-RNG-001', 'Curtain Rings - Pack of 10', 'component', 'pack', 'Hardware'),
        ('itm-07', 'ent-01', 'CMP-TIE-001', 'Tieback Hooks - Pair', 'component', 'pair', 'Hardware'),
        ('itm-08', 'ent-02', 'FAB-BLK-002', 'Blackout Fabric - Navy (B2B)', 'fabric', 'meter', 'Curtains'),
        ('itm-09', 'ent-03', 'FAB-THP-001', 'Thermal Curtain Fabric - Gray', 'fabric', 'meter', 'Curtains'),
    ]
    for row in items_data:
        db.execute("INSERT INTO items (id, entity_id, sku, name, item_type, base_uom, category) VALUES (?,?,?,?,?,?,?)", row)

    db.execute("INSERT INTO suppliers (id, entity_id, name, code) VALUES (?,?,?,?)", ('sup-01', 'ent-01', 'Guangzhou Textile Co.', 'GZ-TEX'))
    db.execute("INSERT INTO suppliers (id, entity_id, name, code) VALUES (?,?,?,?)", ('sup-02', 'ent-01', 'Shanghai Fabrics Ltd.', 'SH-FAB'))

    db.execute("INSERT INTO customers (id, entity_id, name, code) VALUES (?,?,?,?)", ('cust-01', 'ent-01', 'InterContinental Hotels', 'ICH'))
    db.execute("INSERT INTO customers (id, entity_id, name, code) VALUES (?,?,?,?)", ('cust-02', 'ent-01', 'Ayala Land Inc.', 'ALI'))
    db.execute("INSERT INTO customers (id, entity_id, name, code) VALUES (?,?,?,?)", ('cust-03', 'ent-03', 'Online Customer', 'WEB'))

    lots = [
        ('lot-01', 'ent-01', 'itm-01', 'TRK-2024-0001', 'LOT-A1', None, 'IVR-01', 137.0, 50.0, 92.5, 10.0, 'wh-01', 'loc-01', 'active', 'measured'),
        ('lot-02', 'ent-01', 'itm-01', 'TRK-2024-0002', 'LOT-A2', None, 'IVR-01', 137.0, 50.0, 120.0, 0.0, 'wh-01', 'loc-02', 'active', 'measured'),
        ('lot-03', 'ent-01', 'itm-02', 'TRK-2024-0003', 'LOT-B1', None, 'WHT-01', 137.0, 100.0, 85.5, 0.0, 'wh-01', 'loc-03', 'active', 'measured'),
        ('lot-04', 'ent-01', 'itm-03', 'TRK-2024-0004', 'LOT-C1', None, 'NAT-01', 137.0, 75.0, 75.0, 0.0, 'wh-01', 'loc-04', 'active', 'supplier_reported'),
        ('lot-05', 'ent-01', 'itm-04', 'TRK-2024-0005', 'LOT-D1', None, 'EMR-01', 137.0, 60.0, 15.2, 0.0, 'wh-01', 'loc-01', 'active', 'measured'),
        ('lot-06', 'ent-02', 'itm-08', 'TRK-2024-0006', 'LOT-E1', None, 'NVY-01', 137.0, 200.0, 180.0, 25.0, 'wh-03', 'loc-07', 'active', 'measured'),
        ('lot-07', 'ent-01', 'itm-01', 'TRK-2024-0007', 'LOT-A3', None, 'IVR-02', 137.0, 50.0, 8.5, 0.0, 'wh-01', 'loc-01', 'active', 'measured'),
    ]
    for lid, eid, iid, tid, lot, batch, shade, width, orig, onhand, reserved, wid, locid, status, conf in lots:
        db.execute("""INSERT INTO inventory_lots
            (id, entity_id, item_id, tracking_id, lot_no, batch_no, shade_code, width_value, qty_original, qty_on_hand, qty_reserved, warehouse_id, location_id, status, qty_confidence)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (lid, eid, iid, tid, lot, batch, shade, width, orig, onhand, reserved, wid, locid, status, conf))

    db.execute("""INSERT INTO outbound_request_batches (id, entity_id, batch_code, status, total_lines, file_name, created_by)
        VALUES (?,?,?,?,?,?,?)""", ('orb-01', 'ent-01', 'ORB-2024-001', 'processing', 4, 'warehouse_request_jan.xlsx', 'usr-05'))

    db.execute("""INSERT INTO outbound_requests (id, batch_id, entity_id, warehouse_id, customer_id, reference_no, status)
        VALUES (?,?,?,?,?,?,?)""", ('or-01', 'orb-01', 'ent-01', 'wh-01', 'cust-01', 'PO-ICH-2024-001', 'in_progress'))

    or_lines = [
        ('orl-01', 'or-01', 'ent-01', 1, 'itm-01', 25.0, 25.0, 25.0, 0.0, 'closed'),
        ('orl-02', 'or-01', 'ent-01', 2, 'itm-02', 15.0, 15.0, 14.5, -0.5, 'needs_approval'),
        ('orl-03', 'or-01', 'ent-01', 3, 'itm-03', 30.0, 30.0, 0.0, 0.0, 'allocated'),
        ('orl-04', 'or-01', 'ent-01', 4, 'itm-04', 10.0, 0.0, 0.0, 0.0, 'pending'),
    ]
    for lid, orid, eid, lno, iid, req, alloc, ful, var, status in or_lines:
        db.execute("""INSERT INTO outbound_request_lines
            (id, outbound_request_id, entity_id, line_no, item_id, qty_requested, qty_allocated, qty_fulfilled, qty_variance, status)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (lid, orid, eid, lno, iid, req, alloc, ful, var, status))

    db.execute("""INSERT INTO cut_transactions (id, entity_id, outbound_request_line_id, inventory_lot_id, tracking_id, qty_requested, qty_actual, cut_by, status)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        ('cut-01', 'ent-01', 'orl-01', 'lot-01', 'TRK-2024-0001', 25.0, 25.0, 'usr-02', 'approved'))
    db.execute("""INSERT INTO cut_transactions (id, entity_id, outbound_request_line_id, inventory_lot_id, tracking_id, qty_requested, qty_actual, cut_by, status, variance_reason)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ('cut-02', 'ent-01', 'orl-02', 'lot-03', 'TRK-2024-0003', 15.0, 14.5, 'usr-02', 'recorded', 'Material edge defect - 0.5m unusable'))

    db.execute("""INSERT INTO tag_labels (id, tag_code, entity_id, cut_transaction_id, inventory_lot_id, outbound_request_line_id, tag_status, printed_at, printed_by)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        ('tag-01', 'NXR-TAG-0001', 'ent-01', 'cut-01', 'lot-01', 'orl-01', 'printed', now, 'usr-02'))
    db.execute("""INSERT INTO tag_labels (id, tag_code, entity_id, cut_transaction_id, inventory_lot_id, outbound_request_line_id, tag_status)
        VALUES (?,?,?,?,?,?,?)""",
        ('tag-02', 'NXR-TAG-0002', 'ent-01', 'cut-02', 'lot-03', 'orl-02', 'generated'))

    movements = [
        ('mov-01', 'recv-lot01-init', 'receive', 'ent-01', 'lot-01', 'TRK-2024-0001', None, None, 50.0, 0.0, 50.0, None, None, 'wh-01', 'loc-01', 'usr-04'),
        ('mov-02', 'cut-01-deduct', 'deduct', 'ent-01', 'lot-01', 'TRK-2024-0001', 'orl-01', 'cut-01', -25.0, 117.5, 92.5, 'wh-01', 'loc-01', None, None, 'usr-02'),
        ('mov-03', 'cut-02-deduct', 'deduct', 'ent-01', 'lot-03', 'TRK-2024-0003', 'orl-02', 'cut-02', -14.5, 100.0, 85.5, 'wh-01', 'loc-03', None, None, 'usr-02'),
    ]
    for mid, ikey, mtype, eid, lotid, tid, solid, ctid, delta, before, after, wfrom, lfrom, wto, lto, actor in movements:
        db.execute("""INSERT INTO inventory_movements
            (id, event_idempotency_key, movement_type, entity_id, inventory_lot_id, tracking_id, sales_order_line_id, cut_transaction_id, qty_delta, qty_before, qty_after, warehouse_from_id, location_from_id, warehouse_to_id, location_to_id, action_by)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (mid, ikey, mtype, eid, lotid, tid, solid, ctid, delta, before, after, wfrom, lfrom, wto, lto, actor))

    db.execute("""INSERT INTO adjustment_requests (id, entity_id, outbound_request_line_id, adjustment_type, qty_before, qty_after, reason_code, notes, status, requested_by)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ('adj-01', 'ent-01', 'orl-02', 'variance_approval', 15.0, 14.5, 'material_defect', 'Edge defect on roll, 0.5m unusable section', 'pending', 'usr-02'))

    db.execute("""INSERT INTO integration_events (id, entity_id, event_type, event_idempotency_key, payload_json, status, direction)
        VALUES (?,?,?,?,?,?,?)""",
        ('ie-01', 'ent-01', 'fulfillment_complete', 'ful-orl01-complete', '{"line_id":"orl-01","qty":25.0}', 'pending', 'outbound'))

    db.execute("""INSERT INTO reconciliation_runs (id, entity_id, run_type, status, findings_count, run_by, completed_at)
        VALUES (?,?,?,?,?,?,?)""",
        ('rec-01', 'ent-01', 'daily', 'completed', 3, 'usr-04', now))

    findings = [
        ('rf-01', 'rec-01', 'ent-01', 'low_remainder', 'warning', 'Lot TRK-2024-0007 has only 8.5m remaining - below 10m threshold', 'inventory_lot', 'lot-07', 'open'),
        ('rf-02', 'rec-01', 'ent-01', 'missing_tag', 'critical', 'Cut transaction cut-02 has tag in generated state, not yet printed', 'cut_transaction', 'cut-02', 'open'),
        ('rf-03', 'rec-01', 'ent-01', 'stuck_line', 'warning', 'Line orl-02 in needs_approval state for >24h', 'outbound_request_line', 'orl-02', 'open'),
    ]
    for fid, rid, eid, ftype, sev, desc, rtype, resid, rstatus in findings:
        db.execute("""INSERT INTO reconciliation_findings
            (id, reconciliation_run_id, entity_id, finding_type, severity, description, resource_type, resource_id, resolution_status)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (fid, rid, eid, ftype, sev, desc, rtype, resid, rstatus))

    # ---- NEW: Seed channel connections ----
    db.execute("""INSERT INTO channel_connections
        (id, entity_id, channel_type, shop_name, shop_url, region, is_active, last_sync_at)
        VALUES (?,?,?,?,?,?,?,?)""",
        ('ch-01', 'ent-03', 'shopify', 'NEXRAY DTC Store', 'https://nexray-dtc.myshopify.com', 'PH', 1, now))
    db.execute("""INSERT INTO channel_connections
        (id, entity_id, channel_type, shop_name, shop_url, region, is_active, last_sync_at)
        VALUES (?,?,?,?,?,?,?,?)""",
        ('ch-02', 'ent-03', 'shopee', 'NEXRAY Shopee PH', 'https://shopee.ph/nexray_dtc', 'PH', 1, now))

    # Sample product mapping for Shopify
    db.execute("""INSERT INTO channel_product_mappings (id, channel_connection_id, channel_product_id, channel_sku, nexray_item_id, is_active)
        VALUES (?,?,?,?,?,?)""",
        ('cpm-01', 'ch-01', 'shopify-prod-001', 'FAB-THP-001-GRAY', 'itm-09', 1))


# ========== API ROUTES ==========

# ===== HEALTH CHECK (unauthenticated) =====
@app.get("/api/health")
async def health_check():
    try:
        with get_db() as db:
            db.execute("SELECT 1")
        return {"status": "ok", "service": "nexray", "version": "2.0.0"}
    except Exception as e:
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=503)


# ========== AUTH ENDPOINTS ==========

@app.post("/api/auth/login")
async def auth_login(request: Request):
    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password required")

    with get_db() as db:
        user = db.execute(
            "SELECT * FROM users WHERE username=? AND is_active=1", (username,)
        ).fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        salt = user["password_salt"] or ""
        expected_hash = hashlib.sha256((salt + password).encode()).hexdigest()
        if user["password_hash"] != expected_hash:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        token = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        expires_at = (now + timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
        now_str = now.strftime('%Y-%m-%d %H:%M:%S')

        db.execute(
            "INSERT INTO sessions (id, user_id, token, created_at, expires_at) VALUES (?,?,?,?,?)",
            (session_id, user["id"], token, now_str, expires_at)
        )
        write_audit(db, user["entity_id"], user["id"], "login", "user", user["id"])
        db.commit()

        return {
            "token": token,
            "expires_at": expires_at,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "display_name": user["display_name"],
                "email": user["email"],
                "role": user["role"],
                "entity_id": user["entity_id"],
                "warehouse_id": user["warehouse_id"],
            }
        }


@app.post("/api/auth/logout")
async def auth_logout(request: Request):
    user = require_auth(request)
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    with get_db() as db:
        db.execute("DELETE FROM sessions WHERE token=?", (token,))
        write_audit(db, user["entity_id"], user["uid"], "logout", "user", user["uid"])
        db.commit()
    return {"success": True}


@app.get("/api/auth/me")
async def auth_me(request: Request):
    user = require_auth(request)
    return {
        "id": user["uid"],
        "username": user["username"],
        "display_name": user["display_name"],
        "email": user["email"],
        "role": user["role"],
        "entity_id": user["entity_id"],
        "warehouse_id": user["warehouse_id"],
    }


# ========== EXISTING GET ENDPOINTS (now auth-gated) ==========

@app.get("/api/dashboard")
async def get_dashboard(request: Request, entity_id: str = "ent-01"):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead', 'manager', 'warehouse_operator')
    entity_id = resolve_entity_id(user, entity_id)
    with get_db() as db:
        k = {}
        k['total_active_lots'] = db.execute("SELECT COUNT(*) as c FROM inventory_lots WHERE entity_id=? AND status='active'", (entity_id,)).fetchone()['c']
        k['total_on_hand'] = round(db.execute("SELECT COALESCE(SUM(qty_on_hand),0) as s FROM inventory_lots WHERE entity_id=? AND status='active'", (entity_id,)).fetchone()['s'], 2)
        k['total_reserved'] = round(db.execute("SELECT COALESCE(SUM(qty_reserved),0) as s FROM inventory_lots WHERE entity_id=? AND status='active'", (entity_id,)).fetchone()['s'], 2)
        k['total_available'] = round(k['total_on_hand'] - k['total_reserved'], 2)
        k['low_stock_lots'] = db.execute("SELECT COUNT(*) as c FROM inventory_lots WHERE entity_id=? AND status='active' AND qty_on_hand < 10", (entity_id,)).fetchone()['c']
        k['pending_lines'] = db.execute("SELECT COUNT(*) as c FROM outbound_request_lines WHERE entity_id=? AND status='pending'", (entity_id,)).fetchone()['c']
        k['in_progress_lines'] = db.execute("SELECT COUNT(*) as c FROM outbound_request_lines WHERE entity_id=? AND status IN ('allocated','in_progress')", (entity_id,)).fetchone()['c']
        k['needs_approval'] = db.execute("SELECT COUNT(*) as c FROM outbound_request_lines WHERE entity_id=? AND status='needs_approval'", (entity_id,)).fetchone()['c']
        k['closed_lines'] = db.execute("SELECT COUNT(*) as c FROM outbound_request_lines WHERE entity_id=? AND status='closed'", (entity_id,)).fetchone()['c']
        k['pending_adjustments'] = db.execute("SELECT COUNT(*) as c FROM adjustment_requests WHERE entity_id=? AND status='pending'", (entity_id,)).fetchone()['c']
        k['open_findings'] = db.execute("SELECT COUNT(*) as c FROM reconciliation_findings WHERE entity_id=? AND resolution_status='open'", (entity_id,)).fetchone()['c']
        k['pending_integrations'] = db.execute("SELECT COUNT(*) as c FROM integration_events WHERE entity_id=? AND status='pending'", (entity_id,)).fetchone()['c']
        k['failed_prints'] = db.execute("SELECT COUNT(*) as c FROM print_jobs WHERE entity_id=? AND status='failed'", (entity_id,)).fetchone()['c']

        recent_movements = rows_to_list(db.execute("""
            SELECT im.*, il.tracking_id as lot_tracking, i.name as item_name
            FROM inventory_movements im
            LEFT JOIN inventory_lots il ON im.inventory_lot_id = il.id
            LEFT JOIN items i ON il.item_id = i.id
            WHERE im.entity_id=? ORDER BY im.action_at DESC LIMIT 10
        """, (entity_id,)).fetchall())

        recent_findings = rows_to_list(db.execute(
            "SELECT * FROM reconciliation_findings WHERE entity_id=? ORDER BY created_at DESC LIMIT 10", (entity_id,)
        ).fetchall())

    return {'kpis': k, 'recent_movements': recent_movements, 'recent_findings': recent_findings}


@app.get("/api/inventory")
async def get_inventory(request: Request, entity_id: str = "ent-01", warehouse_id: str = None, status: str = "active", item_type: str = None):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead', 'warehouse_operator', 'manager')
    entity_id = resolve_entity_id(user, entity_id)
    with get_db() as db:
        query = """SELECT il.*, i.sku, i.name as item_name, i.item_type, i.base_uom,
                   w.code as warehouse_code, w.name as warehouse_name,
                   l.rack_code, l.level_code, l.bin_code, l.location_barcode
                   FROM inventory_lots il
                   LEFT JOIN items i ON il.item_id = i.id LEFT JOIN warehouses w ON il.warehouse_id = w.id
                   LEFT JOIN locations l ON il.location_id = l.id WHERE il.entity_id=?"""
        args = [entity_id]
        if status: query += " AND il.status=?"; args.append(status)
        if warehouse_id: query += " AND il.warehouse_id=?"; args.append(warehouse_id)
        if item_type: query += " AND i.item_type=?"; args.append(item_type)
        query += " ORDER BY il.created_at DESC"
        lots = rows_to_list(db.execute(query, args).fetchall())
        for lot in lots:
            lot['qty_available'] = round((lot['qty_on_hand'] or 0) - (lot['qty_reserved'] or 0), 2)
    return {'lots': lots}


@app.get("/api/outbound")
async def get_outbound(request: Request, entity_id: str = "ent-01", status: str = None):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead', 'warehouse_operator', 'manager')
    entity_id = resolve_entity_id(user, entity_id)
    with get_db() as db:
        query = """SELECT orl.*, i.sku, i.name as item_name, orq.reference_no, orq.warehouse_id, w.code as warehouse_code
                   FROM outbound_request_lines orl LEFT JOIN outbound_requests orq ON orl.outbound_request_id = orq.id
                   LEFT JOIN items i ON orl.item_id = i.id LEFT JOIN warehouses w ON orq.warehouse_id = w.id WHERE orl.entity_id=?"""
        args = [entity_id]
        if status: query += " AND orl.status=?"; args.append(status)
        query += " ORDER BY orl.created_at DESC"
        return {'lines': rows_to_list(db.execute(query, args).fetchall())}


@app.get("/api/cuts")
async def get_cuts(request: Request, entity_id: str = "ent-01"):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead', 'warehouse_operator', 'manager')
    entity_id = resolve_entity_id(user, entity_id)
    with get_db() as db:
        cuts = rows_to_list(db.execute("""
            SELECT ct.*, i.name as item_name, i.sku, il.tracking_id as lot_tracking, il.lot_no,
                   orl.qty_requested as line_qty_requested, orl.status as line_status
            FROM cut_transactions ct LEFT JOIN inventory_lots il ON ct.inventory_lot_id = il.id
            LEFT JOIN items i ON il.item_id = i.id LEFT JOIN outbound_request_lines orl ON ct.outbound_request_line_id = orl.id
            WHERE ct.entity_id=? ORDER BY ct.cut_at DESC
        """, (entity_id,)).fetchall())
    return {'cuts': cuts}


@app.get("/api/tags")
async def get_tags(request: Request, entity_id: str = "ent-01"):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead', 'warehouse_operator', 'manager')
    entity_id = resolve_entity_id(user, entity_id)
    with get_db() as db:
        tags = rows_to_list(db.execute("""
            SELECT tl.*, ct.qty_actual as cut_qty, il.tracking_id as lot_tracking, i.name as item_name
            FROM tag_labels tl LEFT JOIN cut_transactions ct ON tl.cut_transaction_id = ct.id
            LEFT JOIN inventory_lots il ON tl.inventory_lot_id = il.id LEFT JOIN items i ON il.item_id = i.id
            WHERE tl.entity_id=? ORDER BY tl.created_at DESC
        """, (entity_id,)).fetchall())
    return {'tags': tags}


@app.get("/api/warehouses")
async def get_warehouses(request: Request, entity_id: str = "ent-01"):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead', 'warehouse_operator', 'manager')
    entity_id = resolve_entity_id(user, entity_id)
    with get_db() as db:
        whs = rows_to_list(db.execute("""
            SELECT w.*, e.name as entity_name,
                (SELECT COUNT(*) FROM inventory_lots il WHERE il.warehouse_id=w.id AND il.status='active') as active_lots,
                (SELECT COALESCE(SUM(il.qty_on_hand),0) FROM inventory_lots il WHERE il.warehouse_id=w.id AND il.status='active') as total_stock
            FROM warehouses w LEFT JOIN entities e ON w.entity_id = e.id
            WHERE w.entity_id=? OR ?='all' ORDER BY w.name
        """, (entity_id, entity_id)).fetchall())
    return {'warehouses': whs}


@app.get("/api/locations")
async def get_locations(request: Request, warehouse_id: str = "wh-01"):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead', 'warehouse_operator', 'manager')
    with get_db() as db:
        locs = rows_to_list(db.execute("""
            SELECT l.*,
                (SELECT COUNT(*) FROM inventory_lots il WHERE il.location_id=l.id AND il.status='active') as lot_count,
                (SELECT COALESCE(SUM(il.qty_on_hand),0) FROM inventory_lots il WHERE il.location_id=l.id AND il.status='active') as total_qty
            FROM locations l WHERE l.warehouse_id=? ORDER BY l.zone_code, l.aisle_code, l.rack_code, l.level_code
        """, (warehouse_id,)).fetchall())
    return {'locations': locs}


@app.get("/api/adjustments")
async def get_adjustments(request: Request, entity_id: str = "ent-01", status: str = None):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead', 'manager')
    entity_id = resolve_entity_id(user, entity_id)
    with get_db() as db:
        query = "SELECT * FROM adjustment_requests WHERE entity_id=?"
        args = [entity_id]
        if status: query += " AND status=?"; args.append(status)
        query += " ORDER BY requested_at DESC"
        return {'adjustments': rows_to_list(db.execute(query, args).fetchall())}


@app.get("/api/findings")
async def get_findings(request: Request, entity_id: str = "ent-01", resolution_status: str = None):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead', 'manager')
    entity_id = resolve_entity_id(user, entity_id)
    with get_db() as db:
        query = "SELECT * FROM reconciliation_findings WHERE entity_id=?"
        args = [entity_id]
        if resolution_status: query += " AND resolution_status=?"; args.append(resolution_status)
        query += " ORDER BY created_at DESC"
        return {'findings': rows_to_list(db.execute(query, args).fetchall())}


@app.get("/api/movements")
async def get_movements(request: Request, entity_id: str = "ent-01", lot_id: str = None):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead', 'warehouse_operator', 'manager')
    entity_id = resolve_entity_id(user, entity_id)
    with get_db() as db:
        query = """SELECT im.*, il.tracking_id as lot_tracking, i.name as item_name
                   FROM inventory_movements im LEFT JOIN inventory_lots il ON im.inventory_lot_id = il.id
                   LEFT JOIN items i ON il.item_id = i.id WHERE im.entity_id=?"""
        args = [entity_id]
        if lot_id: query += " AND im.inventory_lot_id=?"; args.append(lot_id)
        query += " ORDER BY im.action_at DESC LIMIT 100"
        return {'movements': rows_to_list(db.execute(query, args).fetchall())}


@app.get("/api/integration_events")
async def get_integration_events(request: Request, entity_id: str = "ent-01", status: str = None):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager', 'accounting_operator')
    entity_id = resolve_entity_id(user, entity_id)
    with get_db() as db:
        query = "SELECT * FROM integration_events WHERE entity_id=?"
        args = [entity_id]
        if status: query += " AND status=?"; args.append(status)
        query += " ORDER BY created_at DESC"
        return {'events': rows_to_list(db.execute(query, args).fetchall())}


@app.get("/api/users")
async def get_users(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'manager')
    with get_db() as db:
        users = rows_to_list(db.execute("""
            SELECT u.id, u.username, u.display_name, u.email, u.role, u.entity_id, u.warehouse_id, u.is_active,
                   e.name as entity_name, w.name as warehouse_name
            FROM users u LEFT JOIN entities e ON u.entity_id = e.id LEFT JOIN warehouses w ON u.warehouse_id = w.id
            ORDER BY u.role, u.display_name
        """).fetchall())
    return {'users': users}


@app.get("/api/entities")
async def get_entities(request: Request):
    user = require_auth(request)
    with get_db() as db:
        return {'entities': rows_to_list(db.execute("SELECT * FROM entities ORDER BY name").fetchall())}


@app.get("/api/audit_log")
async def get_audit_log(request: Request, entity_id: str = "ent-01"):
    user = require_auth(request)
    require_role(user, 'system_admin', 'manager', 'inventory_admin')
    entity_id = resolve_entity_id(user, entity_id)
    with get_db() as db:
        logs = rows_to_list(db.execute("""
            SELECT al.*, u.display_name as actor_name FROM audit_logs al
            LEFT JOIN users u ON al.actor_user_id = u.id
            WHERE al.entity_id=? OR al.entity_id IS NULL ORDER BY al.created_at DESC LIMIT 50
        """, (entity_id,)).fetchall())
    return {'logs': logs}


@app.get("/api/supplier_orders")
async def get_supplier_orders(request: Request, entity_id: str = "ent-01"):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead', 'manager')
    entity_id = resolve_entity_id(user, entity_id)
    with get_db() as db:
        orders = rows_to_list(db.execute("""
            SELECT sol.*, s.name as supplier_name FROM supplier_order_lists sol
            LEFT JOIN suppliers s ON sol.supplier_id = s.id WHERE sol.entity_id=? ORDER BY sol.created_at DESC
        """, (entity_id,)).fetchall())
    return {'orders': orders}


@app.get("/api/print_jobs")
async def get_print_jobs(request: Request, entity_id: str = "ent-01"):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead', 'warehouse_operator', 'manager')
    entity_id = resolve_entity_id(user, entity_id)
    with get_db() as db:
        jobs = rows_to_list(db.execute("""
            SELECT pj.*, tl.tag_code FROM print_jobs pj
            LEFT JOIN tag_labels tl ON pj.tag_label_id = tl.id WHERE pj.entity_id=? ORDER BY pj.created_at DESC
        """, (entity_id,)).fetchall())
    return {'jobs': jobs}


# ========== NEW: Items & Suppliers & Customers GET ==========

@app.get("/api/items")
async def get_items(request: Request, entity_id: str = "ent-01", item_type: str = None, is_active: int = 1):
    user = require_auth(request)
    entity_id = resolve_entity_id(user, entity_id)
    with get_db() as db:
        query = "SELECT * FROM items WHERE entity_id=? AND is_active=?"
        args = [entity_id, is_active]
        if item_type: query += " AND item_type=?"; args.append(item_type)
        query += " ORDER BY name"
        return {'items': rows_to_list(db.execute(query, args).fetchall())}


@app.get("/api/items/{item_id}")
async def get_item(request: Request, item_id: str):
    user = require_auth(request)
    with get_db() as db:
        item = dict_from_row(db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone())
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        aliases = rows_to_list(db.execute("SELECT * FROM item_aliases WHERE item_id=?", (item_id,)).fetchall())
        item['aliases'] = aliases
    return item


@app.get("/api/suppliers")
async def get_suppliers(request: Request, entity_id: str = "ent-01"):
    user = require_auth(request)
    entity_id = resolve_entity_id(user, entity_id)
    with get_db() as db:
        return {'suppliers': rows_to_list(db.execute(
            "SELECT * FROM suppliers WHERE entity_id=? ORDER BY name", (entity_id,)
        ).fetchall())}


@app.get("/api/customers")
async def get_customers(request: Request, entity_id: str = "ent-01"):
    user = require_auth(request)
    entity_id = resolve_entity_id(user, entity_id)
    with get_db() as db:
        return {'customers': rows_to_list(db.execute(
            "SELECT * FROM customers WHERE entity_id=? ORDER BY name", (entity_id,)
        ).fetchall())}


# ========== EXISTING POST ENDPOINTS (now auth-gated) ==========

@app.post("/api/approve_adjustment")
async def approve_adjustment(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead', 'manager')
    body = await request.json()
    with get_db() as db:
        before = dict_from_row(db.execute("SELECT * FROM adjustment_requests WHERE id=?", (body['id'],)).fetchone())
        db.execute("UPDATE adjustment_requests SET status='approved', approved_by=?, approved_at=datetime('now') WHERE id=?",
                   (user['uid'], body['id']))
        write_audit(db, before['entity_id'] if before else None, user['uid'],
                    'approve', 'adjustment_request', body['id'], before, {'status': 'approved'})
        db.commit()
    return {'success': True}


@app.post("/api/reject_adjustment")
async def reject_adjustment(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead', 'manager')
    body = await request.json()
    with get_db() as db:
        before = dict_from_row(db.execute("SELECT * FROM adjustment_requests WHERE id=?", (body['id'],)).fetchone())
        db.execute("UPDATE adjustment_requests SET status='rejected', approved_by=?, approved_at=datetime('now') WHERE id=?",
                   (user['uid'], body['id']))
        write_audit(db, before['entity_id'] if before else None, user['uid'],
                    'reject', 'adjustment_request', body['id'], before, {'status': 'rejected'})
        db.commit()
    return {'success': True}


@app.post("/api/resolve_finding")
async def resolve_finding(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead', 'manager')
    body = await request.json()
    with get_db() as db:
        db.execute("UPDATE reconciliation_findings SET resolution_status='resolved', resolved_by=?, resolved_at=datetime('now'), resolution_notes=? WHERE id=?",
                   (user['uid'], body.get('notes', ''), body['id']))
        db.commit()
    return {'success': True}


@app.post("/api/update_line_status")
async def update_line_status(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead', 'warehouse_operator', 'manager')
    body = await request.json()
    with get_db() as db:
        before = dict_from_row(db.execute("SELECT * FROM outbound_request_lines WHERE id=?", (body['id'],)).fetchone())
        db.execute("UPDATE outbound_request_lines SET status=?, updated_at=datetime('now') WHERE id=?",
                   (body['status'], body['id']))
        write_audit(db, before['entity_id'] if before else None, user['uid'],
                    'update_status', 'outbound_request_line', body['id'],
                    {'status': before['status'] if before else None}, {'status': body['status']})
        db.commit()
    return {'success': True}


@app.post("/api/retry_integration")
async def retry_integration(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager', 'accounting_operator')
    body = await request.json()
    with get_db() as db:
        db.execute("UPDATE integration_events SET status='pending', retry_count=retry_count+1 WHERE id=?", (body['id'],))
        db.commit()
    return {'success': True}


# ========== CRUD: ENTITIES ==========

@app.post("/api/entities")
async def create_entity(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin')
    body = await request.json()
    eid = str(uuid.uuid4())
    with get_db() as db:
        db.execute(
            "INSERT INTO entities (id, name, code, is_active) VALUES (?,?,?,?)",
            (eid, body['name'], body['code'], body.get('is_active', 1))
        )
        write_audit(db, eid, user['uid'], 'create', 'entity', eid, None, body)
        db.commit()
    return {'id': eid, 'success': True}


@app.put("/api/entities/{entity_id}")
async def update_entity(request: Request, entity_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin')
    body = await request.json()
    with get_db() as db:
        before = dict_from_row(db.execute("SELECT * FROM entities WHERE id=?", (entity_id,)).fetchone())
        if not before:
            raise HTTPException(status_code=404, detail="Entity not found")
        fields = {k: v for k, v in body.items() if k in ('name', 'code', 'is_active')}
        if fields:
            set_clause = ", ".join(f"{k}=?" for k in fields)
            set_clause += ", updated_at=datetime('now')"
            db.execute(f"UPDATE entities SET {set_clause} WHERE id=?", list(fields.values()) + [entity_id])
        write_audit(db, entity_id, user['uid'], 'update', 'entity', entity_id, before, fields)
        db.commit()
    return {'success': True}


# ========== CRUD: WAREHOUSES ==========

@app.post("/api/warehouses")
async def create_warehouse(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin')
    body = await request.json()
    wid = str(uuid.uuid4())
    with get_db() as db:
        db.execute(
            "INSERT INTO warehouses (id, entity_id, code, name, address, is_active) VALUES (?,?,?,?,?,?)",
            (wid, body['entity_id'], body['code'], body['name'], body.get('address'), body.get('is_active', 1))
        )
        write_audit(db, body['entity_id'], user['uid'], 'create', 'warehouse', wid, None, body)
        db.commit()
    return {'id': wid, 'success': True}


@app.put("/api/warehouses/{warehouse_id}")
async def update_warehouse(request: Request, warehouse_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin')
    body = await request.json()
    with get_db() as db:
        before = dict_from_row(db.execute("SELECT * FROM warehouses WHERE id=?", (warehouse_id,)).fetchone())
        if not before:
            raise HTTPException(status_code=404, detail="Warehouse not found")
        fields = {k: v for k, v in body.items() if k in ('code', 'name', 'address', 'is_active')}
        if fields:
            set_clause = ", ".join(f"{k}=?" for k in fields)
            set_clause += ", updated_at=datetime('now')"
            db.execute(f"UPDATE warehouses SET {set_clause} WHERE id=?", list(fields.values()) + [warehouse_id])
        write_audit(db, before['entity_id'], user['uid'], 'update', 'warehouse', warehouse_id, before, fields)
        db.commit()
    return {'success': True}


# ========== CRUD: LOCATIONS ==========

@app.post("/api/locations")
async def create_location(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin')
    body = await request.json()
    lid = str(uuid.uuid4())
    with get_db() as db:
        wh = dict_from_row(db.execute("SELECT entity_id FROM warehouses WHERE id=?", (body['warehouse_id'],)).fetchone())
        db.execute(
            "INSERT INTO locations (id, warehouse_id, zone_code, aisle_code, rack_code, level_code, bin_code, location_barcode, location_type, capacity_qty, is_pickable, is_active) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (lid, body['warehouse_id'], body.get('zone_code'), body.get('aisle_code'), body['rack_code'],
             body.get('level_code'), body.get('bin_code'), body.get('location_barcode'),
             body.get('location_type', 'rack'), body.get('capacity_qty'), body.get('is_pickable', 1), body.get('is_active', 1))
        )
        write_audit(db, wh['entity_id'] if wh else None, user['uid'], 'create', 'location', lid, None, body)
        db.commit()
    return {'id': lid, 'success': True}


@app.put("/api/locations/{location_id}")
async def update_location(request: Request, location_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin')
    body = await request.json()
    with get_db() as db:
        before = dict_from_row(db.execute("SELECT * FROM locations WHERE id=?", (location_id,)).fetchone())
        if not before:
            raise HTTPException(status_code=404, detail="Location not found")
        fields = {k: v for k, v in body.items() if k in ('zone_code', 'aisle_code', 'rack_code', 'level_code', 'bin_code', 'location_barcode', 'location_type', 'capacity_qty', 'is_pickable', 'is_active')}
        if fields:
            set_clause = ", ".join(f"{k}=?" for k in fields)
            db.execute(f"UPDATE locations SET {set_clause} WHERE id=?", list(fields.values()) + [location_id])
        wh = dict_from_row(db.execute("SELECT entity_id FROM warehouses WHERE id=?", (before['warehouse_id'],)).fetchone())
        write_audit(db, wh['entity_id'] if wh else None, user['uid'], 'update', 'location', location_id, before, fields)
        db.commit()
    return {'success': True}


# ========== CRUD: ITEMS ==========

@app.post("/api/items")
async def create_item(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin')
    body = await request.json()
    iid = str(uuid.uuid4())
    with get_db() as db:
        db.execute(
            "INSERT INTO items (id, entity_id, sku, name, description, item_type, base_uom, category, is_active) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (iid, body['entity_id'], body['sku'], body['name'], body.get('description'),
             body['item_type'], body.get('base_uom', 'meter'), body.get('category'), body.get('is_active', 1))
        )
        write_audit(db, body['entity_id'], user['uid'], 'create', 'item', iid, None, body)
        db.commit()
    return {'id': iid, 'success': True}


@app.put("/api/items/{item_id}")
async def update_item(request: Request, item_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin')
    body = await request.json()
    with get_db() as db:
        before = dict_from_row(db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone())
        if not before:
            raise HTTPException(status_code=404, detail="Item not found")
        fields = {k: v for k, v in body.items() if k in ('sku', 'name', 'description', 'item_type', 'base_uom', 'category', 'is_active')}
        if fields:
            set_clause = ", ".join(f"{k}=?" for k in fields)
            set_clause += ", updated_at=datetime('now')"
            db.execute(f"UPDATE items SET {set_clause} WHERE id=?", list(fields.values()) + [item_id])
        write_audit(db, before['entity_id'], user['uid'], 'update', 'item', item_id, before, fields)
        db.commit()
    return {'success': True}


# ========== CRUD: SUPPLIERS ==========

@app.post("/api/suppliers")
async def create_supplier(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    body = await request.json()
    sid = str(uuid.uuid4())
    with get_db() as db:
        db.execute(
            "INSERT INTO suppliers (id, entity_id, name, code, contact_info, is_active) VALUES (?,?,?,?,?,?)",
            (sid, body['entity_id'], body['name'], body.get('code'), body.get('contact_info'), body.get('is_active', 1))
        )
        write_audit(db, body['entity_id'], user['uid'], 'create', 'supplier', sid, None, body)
        db.commit()
    return {'id': sid, 'success': True}


@app.put("/api/suppliers/{supplier_id}")
async def update_supplier(request: Request, supplier_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    body = await request.json()
    with get_db() as db:
        before = dict_from_row(db.execute("SELECT * FROM suppliers WHERE id=?", (supplier_id,)).fetchone())
        if not before:
            raise HTTPException(status_code=404, detail="Supplier not found")
        fields = {k: v for k, v in body.items() if k in ('name', 'code', 'contact_info', 'is_active')}
        if fields:
            set_clause = ", ".join(f"{k}=?" for k in fields)
            db.execute(f"UPDATE suppliers SET {set_clause} WHERE id=?", list(fields.values()) + [supplier_id])
        write_audit(db, before['entity_id'], user['uid'], 'update', 'supplier', supplier_id, before, fields)
        db.commit()
    return {'success': True}


# ========== CRUD: CUSTOMERS ==========

@app.post("/api/customers")
async def create_customer(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    body = await request.json()
    cid = str(uuid.uuid4())
    with get_db() as db:
        db.execute(
            "INSERT INTO customers (id, entity_id, name, code, contact_info, is_active) VALUES (?,?,?,?,?,?)",
            (cid, body['entity_id'], body['name'], body.get('code'), body.get('contact_info'), body.get('is_active', 1))
        )
        write_audit(db, body['entity_id'], user['uid'], 'create', 'customer', cid, None, body)
        db.commit()
    return {'id': cid, 'success': True}


@app.put("/api/customers/{customer_id}")
async def update_customer(request: Request, customer_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    body = await request.json()
    with get_db() as db:
        before = dict_from_row(db.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone())
        if not before:
            raise HTTPException(status_code=404, detail="Customer not found")
        fields = {k: v for k, v in body.items() if k in ('name', 'code', 'contact_info', 'is_active')}
        if fields:
            set_clause = ", ".join(f"{k}=?" for k in fields)
            db.execute(f"UPDATE customers SET {set_clause} WHERE id=?", list(fields.values()) + [customer_id])
        write_audit(db, before['entity_id'], user['uid'], 'update', 'customer', customer_id, before, fields)
        db.commit()
    return {'success': True}


# ========== CRUD: USERS ==========

@app.post("/api/users")
async def create_user(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin')
    body = await request.json()
    uid = str(uuid.uuid4())
    username = body['username']
    password = body.get('password', username)  # default password = username
    salt = uuid.uuid4().hex[:16]
    phash = hashlib.sha256((salt + password).encode()).hexdigest()
    with get_db() as db:
        db.execute(
            "INSERT INTO users (id, username, display_name, email, password_hash, password_salt, role, entity_id, warehouse_id, is_active) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (uid, username, body['display_name'], body.get('email'), phash, salt,
             body['role'], body.get('entity_id'), body.get('warehouse_id'), body.get('is_active', 1))
        )
        safe_body = {k: v for k, v in body.items() if k != 'password'}
        write_audit(db, body.get('entity_id'), user['uid'], 'create', 'user', uid, None, safe_body)
        db.commit()
    return {'id': uid, 'success': True}


@app.put("/api/users/{user_id}")
async def update_user(request: Request, user_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin')
    body = await request.json()
    with get_db() as db:
        before = dict_from_row(db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())
        if not before:
            raise HTTPException(status_code=404, detail="User not found")
        fields = {k: v for k, v in body.items() if k in ('display_name', 'email', 'role', 'entity_id', 'warehouse_id', 'is_active')}
        if fields:
            set_clause = ", ".join(f"{k}=?" for k in fields)
            set_clause += ", updated_at=datetime('now')"
            db.execute(f"UPDATE users SET {set_clause} WHERE id=?", list(fields.values()) + [user_id])
        safe_before = {k: v for k, v in before.items() if k != 'password_hash'}
        write_audit(db, before.get('entity_id'), user['uid'], 'update', 'user', user_id, safe_before, fields)
        db.commit()
    return {'success': True}


# ========== INBOUND WORKFLOW ==========

@app.post("/api/supplier_orders")
async def create_supplier_order(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead', 'manager')
    body = await request.json()
    sol_id = str(uuid.uuid4())
    batch_code = body.get('batch_code') or f"SOL-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    lines = body.get('lines', [])
    with get_db() as db:
        db.execute(
            "INSERT INTO supplier_order_lists (id, entity_id, supplier_id, batch_code, status, total_lines, notes, created_by) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (sol_id, body['entity_id'], body.get('supplier_id'), batch_code, 'draft', len(lines),
             body.get('notes'), user['uid'])
        )
        for idx, line in enumerate(lines, 1):
            line_id = str(uuid.uuid4())
            db.execute(
                "INSERT INTO supplier_order_list_lines (id, supplier_order_list_id, line_no, item_id, item_name_raw, qty_expected, uom, lot_info, shade_info, width_info) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (line_id, sol_id, idx, line.get('item_id'), line.get('item_name_raw'),
                 line['qty_expected'], line.get('uom', 'meter'), line.get('lot_info'),
                 line.get('shade_info'), line.get('width_info'))
            )
        write_audit(db, body['entity_id'], user['uid'], 'create', 'supplier_order_list', sol_id, None,
                    {'batch_code': batch_code, 'lines': len(lines)})
        db.commit()
    return {'id': sol_id, 'batch_code': batch_code, 'success': True}


@app.post("/api/supplier_orders/{sol_id}/validate")
async def validate_supplier_order(request: Request, sol_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead')
    with get_db() as db:
        sol = dict_from_row(db.execute("SELECT * FROM supplier_order_lists WHERE id=?", (sol_id,)).fetchone())
        if not sol:
            raise HTTPException(status_code=404, detail="Supplier order not found")
        lines = rows_to_list(db.execute("SELECT * FROM supplier_order_list_lines WHERE supplier_order_list_id=?", (sol_id,)).fetchall())
        error_count = 0
        for line in lines:
            err = None
            if not line['item_id']:
                # Try to resolve item by name
                item = db.execute("SELECT id FROM items WHERE name=? AND entity_id=?",
                                  (line['item_name_raw'], sol['entity_id'])).fetchone()
                if item:
                    db.execute("UPDATE supplier_order_list_lines SET item_id=? WHERE id=?", (item['id'], line['id']))
                else:
                    err = f"Item not found: '{line['item_name_raw']}'"
            if line['qty_expected'] is None or line['qty_expected'] <= 0:
                err = "qty_expected must be > 0"
            if sol.get('supplier_id'):
                sup = db.execute("SELECT id FROM suppliers WHERE id=?", (sol['supplier_id'],)).fetchone()
                if not sup:
                    err = f"Supplier {sol['supplier_id']} not found"
            if err:
                error_count += 1
                db.execute("UPDATE supplier_order_list_lines SET validation_status='error', validation_error=? WHERE id=?",
                           (err, line['id']))
            else:
                db.execute("UPDATE supplier_order_list_lines SET validation_status='valid', validation_error=NULL WHERE id=?",
                           (line['id'],))
        new_status = 'validated' if error_count == 0 else 'failed_with_errors'
        db.execute("UPDATE supplier_order_lists SET status=?, error_count=?, updated_at=datetime('now') WHERE id=?",
                   (new_status, error_count, sol_id))
        write_audit(db, sol['entity_id'], user['uid'], 'validate', 'supplier_order_list', sol_id,
                    {'status': sol['status']}, {'status': new_status, 'error_count': error_count})
        db.commit()
    return {'success': True, 'status': new_status, 'error_count': error_count}


@app.post("/api/receivings")
async def create_receiving(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead', 'warehouse_operator')
    body = await request.json()
    rid = str(uuid.uuid4())
    with get_db() as db:
        db.execute(
            "INSERT INTO receivings (id, entity_id, warehouse_id, supplier_order_list_id, status, received_by, notes) "
            "VALUES (?,?,?,?,?,?,?)",
            (rid, body['entity_id'], body['warehouse_id'], body.get('supplier_order_list_id'),
             'in_progress', user['uid'], body.get('notes'))
        )
        # If linked to SOL, update its status to receiving
        if body.get('supplier_order_list_id'):
            db.execute("UPDATE supplier_order_lists SET status='receiving', updated_at=datetime('now') WHERE id=?",
                       (body['supplier_order_list_id'],))
        write_audit(db, body['entity_id'], user['uid'], 'create', 'receiving', rid, None, body)
        db.commit()
    return {'id': rid, 'success': True}


@app.post("/api/receivings/{receiving_id}/receive_lot")
async def receive_lot(request: Request, receiving_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead', 'warehouse_operator')
    body = await request.json()
    with get_db() as db:
        recv = dict_from_row(db.execute("SELECT * FROM receivings WHERE id=?", (receiving_id,)).fetchone())
        if not recv:
            raise HTTPException(status_code=404, detail="Receiving session not found")
        if recv['status'] != 'in_progress':
            raise HTTPException(status_code=400, detail="Receiving session is not in progress")

        lot_id = str(uuid.uuid4())
        tracking_id = body.get('tracking_id') or f"TRK-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{lot_id[:6].upper()}"
        qty = float(body['qty_original'])

        db.execute(
            "INSERT INTO inventory_lots (id, entity_id, item_id, tracking_id, lot_no, batch_no, shade_code, width_value, "
            "qty_original, qty_on_hand, qty_reserved, warehouse_id, location_id, status, qty_confidence, receiving_id, supplier_order_line_id, created_by) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (lot_id, recv['entity_id'], body['item_id'], tracking_id, body.get('lot_no'),
             body.get('batch_no'), body.get('shade_code'), body.get('width_value'),
             qty, qty, 0.0, recv['warehouse_id'], body.get('location_id'),
             'active', body.get('qty_confidence', 'supplier_reported'),
             receiving_id, body.get('supplier_order_line_id'), user['uid'])
        )

        # Create inventory movement (receive)
        mov_id = str(uuid.uuid4())
        ikey = f"recv-{lot_id}"
        db.execute(
            "INSERT INTO inventory_movements (id, event_idempotency_key, movement_type, entity_id, inventory_lot_id, "
            "tracking_id, qty_delta, qty_before, qty_after, warehouse_to_id, location_to_id, action_by) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (mov_id, ikey, 'receive', recv['entity_id'], lot_id, tracking_id,
             qty, 0.0, qty, recv['warehouse_id'], body.get('location_id'), user['uid'])
        )

        # Update supplier_order_line if linked
        if body.get('supplier_order_line_id'):
            db.execute(
                "UPDATE supplier_order_list_lines SET validation_status='valid' WHERE id=?",
                (body['supplier_order_line_id'],)
            )

        write_audit(db, recv['entity_id'], user['uid'], 'receive_lot', 'inventory_lot', lot_id,
                    None, {'tracking_id': tracking_id, 'qty': qty})
        db.commit()
    return {'lot_id': lot_id, 'tracking_id': tracking_id, 'success': True}


@app.post("/api/receivings/{receiving_id}/complete")
async def complete_receiving(request: Request, receiving_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead')
    with get_db() as db:
        recv = dict_from_row(db.execute("SELECT * FROM receivings WHERE id=?", (receiving_id,)).fetchone())
        if not recv:
            raise HTTPException(status_code=404, detail="Receiving session not found")
        db.execute("UPDATE receivings SET status='completed' WHERE id=?", (receiving_id,))
        if recv.get('supplier_order_list_id'):
            db.execute("UPDATE supplier_order_lists SET status='completed', updated_at=datetime('now') WHERE id=?",
                       (recv['supplier_order_list_id'],))
        write_audit(db, recv['entity_id'], user['uid'], 'complete', 'receiving', receiving_id,
                    {'status': 'in_progress'}, {'status': 'completed'})
        db.commit()
    return {'success': True}


@app.post("/api/putaway")
async def putaway_lot(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead', 'warehouse_operator')
    body = await request.json()
    tracking_id = body.get('tracking_id')
    location_id = body.get('location_id')
    if not tracking_id or not location_id:
        raise HTTPException(status_code=400, detail="tracking_id and location_id required")
    with get_db() as db:
        lot = dict_from_row(db.execute("SELECT * FROM inventory_lots WHERE tracking_id=?", (tracking_id,)).fetchone())
        if not lot:
            raise HTTPException(status_code=404, detail="Lot not found")
        loc = dict_from_row(db.execute("SELECT * FROM locations WHERE id=?", (location_id,)).fetchone())
        if not loc:
            raise HTTPException(status_code=404, detail="Location not found")

        from_location_id = lot['location_id']
        pe_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO putaway_events (id, entity_id, inventory_lot_id, from_location_id, to_location_id, qty_moved, moved_by, status) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (pe_id, lot['entity_id'], lot['id'], from_location_id, location_id, lot['qty_on_hand'], user['uid'], 'completed')
        )
        db.execute("UPDATE inventory_lots SET location_id=?, updated_at=datetime('now') WHERE id=?",
                   (location_id, lot['id']))

        mov_id = str(uuid.uuid4())
        ikey = f"putaway-{pe_id}"
        db.execute(
            "INSERT INTO inventory_movements (id, event_idempotency_key, movement_type, entity_id, inventory_lot_id, "
            "tracking_id, qty_delta, qty_before, qty_after, warehouse_from_id, location_from_id, warehouse_to_id, location_to_id, action_by) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (mov_id, ikey, 'move', lot['entity_id'], lot['id'], tracking_id,
             0.0, lot['qty_on_hand'], lot['qty_on_hand'],
             lot['warehouse_id'], from_location_id, lot['warehouse_id'], location_id, user['uid'])
        )
        write_audit(db, lot['entity_id'], user['uid'], 'putaway', 'inventory_lot', lot['id'],
                    {'location_id': from_location_id}, {'location_id': location_id})
        db.commit()
    return {'putaway_event_id': pe_id, 'success': True}


# ========== OUTBOUND WORKFLOW ==========

@app.post("/api/outbound_batches")
async def create_outbound_batch(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead', 'manager')
    body = await request.json()
    batch_id = str(uuid.uuid4())
    batch_code = body.get('batch_code') or f"ORB-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    requests_list = body.get('requests', [])
    total_lines = 0
    with get_db() as db:
        db.execute(
            "INSERT INTO outbound_request_batches (id, entity_id, batch_code, status, total_lines, file_name, created_by) "
            "VALUES (?,?,?,?,?,?,?)",
            (batch_id, body['entity_id'], batch_code, 'draft', 0, body.get('file_name'), user['uid'])
        )
        for req in requests_list:
            or_id = str(uuid.uuid4())
            db.execute(
                "INSERT INTO outbound_requests (id, batch_id, entity_id, warehouse_id, customer_id, reference_no, status) "
                "VALUES (?,?,?,?,?,?,?)",
                (or_id, batch_id, body['entity_id'], req['warehouse_id'], req.get('customer_id'),
                 req.get('reference_no'), 'pending')
            )
            lines = req.get('lines', [])
            for idx, line in enumerate(lines, 1):
                line_id = str(uuid.uuid4())
                db.execute(
                    "INSERT INTO outbound_request_lines (id, outbound_request_id, entity_id, line_no, item_id, item_name_raw, qty_requested, uom, status) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (line_id, or_id, body['entity_id'], idx, line.get('item_id'), line.get('item_name_raw'),
                     line['qty'], line.get('uom', 'meter'), 'pending')
                )
                total_lines += 1
        db.execute("UPDATE outbound_request_batches SET total_lines=? WHERE id=?", (total_lines, batch_id))
        write_audit(db, body['entity_id'], user['uid'], 'create', 'outbound_request_batch', batch_id,
                    None, {'batch_code': batch_code, 'total_lines': total_lines})
        db.commit()
    return {'id': batch_id, 'batch_code': batch_code, 'total_lines': total_lines, 'success': True}


@app.post("/api/outbound_batches/{batch_id}/validate")
async def validate_outbound_batch(request: Request, batch_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead', 'manager')
    with get_db() as db:
        batch = dict_from_row(db.execute("SELECT * FROM outbound_request_batches WHERE id=?", (batch_id,)).fetchone())
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        lines = rows_to_list(db.execute(
            "SELECT orl.* FROM outbound_request_lines orl "
            "JOIN outbound_requests orq ON orl.outbound_request_id = orq.id "
            "WHERE orq.batch_id=?", (batch_id,)
        ).fetchall())
        error_count = 0
        for line in lines:
            err = None
            if not line.get('item_id'):
                item = db.execute("SELECT id FROM items WHERE name=? AND entity_id=?",
                                  (line.get('item_name_raw'), batch['entity_id'])).fetchone()
                if item:
                    db.execute("UPDATE outbound_request_lines SET item_id=? WHERE id=?", (item['id'], line['id']))
                else:
                    err = f"Item not found: '{line.get('item_name_raw')}'"
                    error_count += 1
            if not line.get('qty_requested') or float(line.get('qty_requested', 0)) <= 0:
                err = "qty_requested must be > 0"
                error_count += 1
            if err:
                db.execute("UPDATE outbound_request_lines SET status='blocked' WHERE id=?", (line['id'],))
        new_status = 'validated' if error_count == 0 else 'failed_with_errors'
        db.execute("UPDATE outbound_request_batches SET status=?, error_count=?, updated_at=datetime('now') WHERE id=?",
                   (new_status, error_count, batch_id))
        write_audit(db, batch['entity_id'], user['uid'], 'validate', 'outbound_request_batch', batch_id,
                    {'status': batch['status']}, {'status': new_status, 'error_count': error_count})
        db.commit()
    return {'success': True, 'status': new_status, 'error_count': error_count}


@app.post("/api/outbound/allocate")
async def allocate_outbound_line(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead')
    body = await request.json()
    line_id = body['line_id']
    with get_db() as db:
        line = dict_from_row(db.execute(
            "SELECT orl.*, orq.warehouse_id, orq.entity_id as req_entity_id "
            "FROM outbound_request_lines orl JOIN outbound_requests orq ON orl.outbound_request_id = orq.id "
            "WHERE orl.id=?", (line_id,)
        ).fetchone())
        if not line:
            raise HTTPException(status_code=404, detail="Line not found")
        qty_needed = float(line['qty_requested']) - float(line.get('qty_allocated') or 0)
        if qty_needed <= 0:
            return {'success': True, 'message': 'Already fully allocated'}

        # FIFO: oldest active lots with available qty for this item in the warehouse
        lots = rows_to_list(db.execute(
            "SELECT * FROM inventory_lots WHERE item_id=? AND warehouse_id=? AND status='active' "
            "AND (qty_on_hand - qty_reserved) > 0 ORDER BY created_at ASC",
            (line['item_id'], line['warehouse_id'])
        ).fetchall())

        total_allocated = 0.0
        reservations_made = []
        for lot in lots:
            if qty_needed <= 0:
                break
            available = float(lot['qty_on_hand']) - float(lot.get('qty_reserved') or 0)
            if available <= 0:
                continue
            reserve_qty = min(available, qty_needed)
            res_id = str(uuid.uuid4())
            db.execute(
                "INSERT INTO inventory_reservations (id, entity_id, inventory_lot_id, outbound_request_line_id, qty_reserved, status, created_by) "
                "VALUES (?,?,?,?,?,?,?)",
                (res_id, line['entity_id'], lot['id'], line_id, reserve_qty, 'active', user['uid'])
            )
            db.execute("UPDATE inventory_lots SET qty_reserved = qty_reserved + ?, updated_at=datetime('now') WHERE id=?",
                       (reserve_qty, lot['id']))
            total_allocated += reserve_qty
            qty_needed -= reserve_qty
            reservations_made.append({'lot_id': lot['id'], 'qty': reserve_qty})

        db.execute(
            "UPDATE outbound_request_lines SET qty_allocated = qty_allocated + ?, status='allocated', updated_at=datetime('now') WHERE id=?",
            (total_allocated, line_id)
        )
        write_audit(db, line['entity_id'], user['uid'], 'allocate', 'outbound_request_line', line_id,
                    {'qty_allocated': line.get('qty_allocated', 0)},
                    {'qty_allocated': float(line.get('qty_allocated', 0)) + total_allocated, 'reservations': reservations_made})
        db.commit()
    return {'success': True, 'total_allocated': total_allocated, 'reservations': reservations_made}


@app.post("/api/outbound/claim_line")
async def claim_outbound_line(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead', 'warehouse_operator')
    body = await request.json()
    line_id = body['line_id']
    with get_db() as db:
        line = dict_from_row(db.execute("SELECT * FROM outbound_request_lines WHERE id=?", (line_id,)).fetchone())
        if not line:
            raise HTTPException(status_code=404, detail="Line not found")
        # Check for existing lock
        lock = db.execute(
            "SELECT * FROM workflow_locks WHERE resource_type='outbound_request_line' AND resource_id=?", (line_id,)
        ).fetchone()
        if lock:
            raise HTTPException(status_code=409, detail=f"Line already claimed by {lock['lock_owner']}")

        now = datetime.now(timezone.utc)
        expires_at = (now + timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
        lock_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO workflow_locks (id, resource_type, resource_id, lock_owner, lock_expires_at) VALUES (?,?,?,?,?)",
            (lock_id, 'outbound_request_line', line_id, user['uid'], expires_at)
        )
        db.execute(
            "UPDATE outbound_request_lines SET claimed_by=?, claimed_at=datetime('now'), status='in_progress', updated_at=datetime('now') WHERE id=?",
            (user['uid'], line_id)
        )
        write_audit(db, line['entity_id'], user['uid'], 'claim', 'outbound_request_line', line_id,
                    {'status': line['status']}, {'status': 'in_progress', 'claimed_by': user['uid']})
        db.commit()
    return {'success': True, 'lock_id': lock_id, 'expires_at': expires_at}


@app.post("/api/outbound/record_cut")
async def record_cut(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead', 'warehouse_operator')
    body = await request.json()
    line_id = body['line_id']
    lot_id = body['lot_id']
    qty_requested = float(body['qty_requested'])
    qty_actual = float(body['qty_actual'])
    cut_by = body.get('cut_by', user['uid'])

    with get_db() as db:
        line = dict_from_row(db.execute("SELECT * FROM outbound_request_lines WHERE id=?", (line_id,)).fetchone())
        if not line:
            raise HTTPException(status_code=404, detail="Line not found")
        lot = dict_from_row(db.execute("SELECT * FROM inventory_lots WHERE id=?", (lot_id,)).fetchone())
        if not lot:
            raise HTTPException(status_code=404, detail="Lot not found")

        cut_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO cut_transactions (id, entity_id, outbound_request_line_id, inventory_lot_id, tracking_id, "
            "qty_requested, qty_actual, variance_reason, cut_by, status) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (cut_id, line['entity_id'], line_id, lot_id, lot['tracking_id'],
             qty_requested, qty_actual, body.get('variance_reason'), cut_by, 'recorded')
        )

        # Deduct inventory movement
        qty_before = float(lot['qty_on_hand'])
        qty_after = round(qty_before - qty_actual, 4)
        mov_id = str(uuid.uuid4())
        ikey = f"cut-{cut_id}-deduct"
        db.execute(
            "INSERT INTO inventory_movements (id, event_idempotency_key, movement_type, entity_id, inventory_lot_id, "
            "tracking_id, sales_order_line_id, cut_transaction_id, qty_delta, qty_before, qty_after, "
            "warehouse_from_id, location_from_id, action_by) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (mov_id, ikey, 'deduct', line['entity_id'], lot_id, lot['tracking_id'],
             line_id, cut_id, -qty_actual, qty_before, qty_after,
             lot['warehouse_id'], lot.get('location_id'), cut_by)
        )
        db.execute("UPDATE inventory_lots SET qty_on_hand=?, updated_at=datetime('now') WHERE id=?",
                   (qty_after, lot_id))

        # Auto-generate tag_label and print_job
        tag_id = str(uuid.uuid4())
        tag_count = db.execute("SELECT COUNT(*) FROM tag_labels WHERE entity_id=?", (line['entity_id'],)).fetchone()[0]
        tag_code = f"NXR-TAG-{(tag_count + 1):04d}"
        db.execute(
            "INSERT INTO tag_labels (id, tag_code, entity_id, cut_transaction_id, inventory_lot_id, outbound_request_line_id, tag_status) "
            "VALUES (?,?,?,?,?,?,?)",
            (tag_id, tag_code, line['entity_id'], cut_id, lot_id, line_id, 'generated')
        )
        pj_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO print_jobs (id, entity_id, tag_label_id, job_type, status) VALUES (?,?,?,?,?)",
            (pj_id, line['entity_id'], tag_id, 'tag', 'queued')
        )

        # Check variance: if abs variance > 5%, flag for approval
        variance_pct = abs(qty_actual - qty_requested) / qty_requested if qty_requested > 0 else 0
        line_needs_approval = variance_pct > 0.05
        if line_needs_approval:
            adj_id = str(uuid.uuid4())
            db.execute(
                "INSERT INTO adjustment_requests (id, entity_id, inventory_lot_id, outbound_request_line_id, "
                "adjustment_type, qty_before, qty_after, reason_code, notes, status, requested_by) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (adj_id, line['entity_id'], lot_id, line_id, 'variance_approval',
                 qty_requested, qty_actual, 'cut_variance',
                 f"Cut variance {variance_pct*100:.1f}% exceeds 5% threshold", 'pending', cut_by)
            )
            db.execute("UPDATE outbound_request_lines SET status='needs_approval', updated_at=datetime('now') WHERE id=?",
                       (line_id,))
        else:
            db.execute("UPDATE outbound_request_lines SET qty_fulfilled=qty_fulfilled+?, status='cut_complete', updated_at=datetime('now') WHERE id=?",
                       (qty_actual, line_id))

        write_audit(db, line['entity_id'], user['uid'], 'record_cut', 'cut_transaction', cut_id,
                    None, {'qty_requested': qty_requested, 'qty_actual': qty_actual, 'tag_code': tag_code})
        db.commit()
    return {
        'cut_id': cut_id, 'tag_id': tag_id, 'tag_code': tag_code, 'print_job_id': pj_id,
        'needs_approval': line_needs_approval, 'success': True
    }


@app.post("/api/outbound/close_line")
async def close_line(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead', 'manager')
    body = await request.json()
    line_id = body['line_id']
    with get_db() as db:
        line = dict_from_row(db.execute("SELECT * FROM outbound_request_lines WHERE id=?", (line_id,)).fetchone())
        if not line:
            raise HTTPException(status_code=404, detail="Line not found")
        # GATE CHECK: all cut tags must be printed or scanned
        tags = rows_to_list(db.execute(
            "SELECT tl.tag_status FROM tag_labels tl WHERE tl.outbound_request_line_id=?", (line_id,)
        ).fetchall())
        unprinted = [t for t in tags if t['tag_status'] not in ('printed', 'scanned')]
        if unprinted:
            raise HTTPException(status_code=400,
                detail=f"Gate check failed: {len(unprinted)} tag(s) not yet printed or scanned")

        # Release reservations
        db.execute(
            "UPDATE inventory_reservations SET status='released' WHERE outbound_request_line_id=? AND status='active'",
            (line_id,)
        )
        # Release workflow lock
        db.execute("DELETE FROM workflow_locks WHERE resource_type='outbound_request_line' AND resource_id=?", (line_id,))

        db.execute(
            "UPDATE outbound_request_lines SET status='closed', fulfilled_by=?, fulfilled_at=datetime('now'), updated_at=datetime('now') WHERE id=?",
            (user['uid'], line_id)
        )

        # Create integration event for QBD sync
        ie_id = str(uuid.uuid4())
        ikey = f"close-line-{line_id}"
        payload = json.dumps({'line_id': line_id, 'qty_fulfilled': line.get('qty_fulfilled', 0)})
        try:
            db.execute(
                "INSERT INTO integration_events (id, entity_id, event_type, event_idempotency_key, payload_json, status, direction) "
                "VALUES (?,?,?,?,?,?,?)",
                (ie_id, line['entity_id'], 'fulfillment_complete', ikey, payload, 'pending', 'outbound')
            )
        except Exception:
            pass  # Idempotency key already exists

        write_audit(db, line['entity_id'], user['uid'], 'close', 'outbound_request_line', line_id,
                    {'status': line['status']}, {'status': 'closed'})
        db.commit()
    return {'success': True, 'integration_event_id': ie_id}


# ========== APPROVALS & RECONCILIATION ==========

@app.post("/api/adjustments")
async def create_adjustment(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead', 'warehouse_operator', 'manager')
    body = await request.json()
    adj_id = str(uuid.uuid4())
    with get_db() as db:
        db.execute(
            "INSERT INTO adjustment_requests (id, entity_id, inventory_lot_id, outbound_request_line_id, "
            "adjustment_type, qty_before, qty_after, reason_code, notes, status, requested_by) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (adj_id, body['entity_id'], body.get('inventory_lot_id'), body.get('outbound_request_line_id'),
             body['adjustment_type'], body.get('qty_before'), body.get('qty_after'),
             body['reason_code'], body.get('notes'), 'pending', user['uid'])
        )
        write_audit(db, body['entity_id'], user['uid'], 'create', 'adjustment_request', adj_id, None, body)
        db.commit()
    return {'id': adj_id, 'success': True}


@app.put("/api/adjustments/{adj_id}/approve")
async def approve_adjustment_v2(request: Request, adj_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead', 'manager')
    body = await request.json() if request.headers.get('content-length', '0') != '0' else {}
    with get_db() as db:
        adj = dict_from_row(db.execute("SELECT * FROM adjustment_requests WHERE id=?", (adj_id,)).fetchone())
        if not adj:
            raise HTTPException(status_code=404, detail="Adjustment not found")
        if adj['status'] != 'pending':
            raise HTTPException(status_code=400, detail="Adjustment is not pending")
        db.execute(
            "UPDATE adjustment_requests SET status='approved', approved_by=?, approved_at=datetime('now') WHERE id=?",
            (user['uid'], adj_id)
        )
        # If qty_correction, apply movement
        if adj['adjustment_type'] == 'qty_correction' and adj.get('inventory_lot_id') and adj.get('qty_after') is not None:
            lot = dict_from_row(db.execute("SELECT * FROM inventory_lots WHERE id=?", (adj['inventory_lot_id'],)).fetchone())
            if lot:
                qty_before = float(lot['qty_on_hand'])
                qty_after = float(adj['qty_after'])
                delta = qty_after - qty_before
                mtype = 'adjust_up' if delta >= 0 else 'adjust_down'
                mov_id = str(uuid.uuid4())
                ikey = f"adj-{adj_id}-apply"
                try:
                    db.execute(
                        "INSERT INTO inventory_movements (id, event_idempotency_key, movement_type, entity_id, inventory_lot_id, "
                        "tracking_id, qty_delta, qty_before, qty_after, action_by) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (mov_id, ikey, mtype, lot['entity_id'], lot['id'], lot['tracking_id'],
                         delta, qty_before, qty_after, user['uid'])
                    )
                    db.execute("UPDATE inventory_lots SET qty_on_hand=?, updated_at=datetime('now') WHERE id=?",
                               (qty_after, adj['inventory_lot_id']))
                except Exception:
                    pass
        write_audit(db, adj['entity_id'], user['uid'], 'approve', 'adjustment_request', adj_id,
                    {'status': 'pending'}, {'status': 'approved'})
        db.commit()
    return {'success': True}


@app.put("/api/adjustments/{adj_id}/reject")
async def reject_adjustment_v2(request: Request, adj_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'warehouse_lead', 'manager')
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    with get_db() as db:
        adj = dict_from_row(db.execute("SELECT * FROM adjustment_requests WHERE id=?", (adj_id,)).fetchone())
        if not adj:
            raise HTTPException(status_code=404, detail="Adjustment not found")
        db.execute(
            "UPDATE adjustment_requests SET status='rejected', approved_by=?, approved_at=datetime('now') WHERE id=?",
            (user['uid'], adj_id)
        )
        write_audit(db, adj['entity_id'], user['uid'], 'reject', 'adjustment_request', adj_id,
                    {'status': 'pending'}, {'status': 'rejected', 'notes': body.get('notes')})
        db.commit()
    return {'success': True}


@app.post("/api/reconciliation/run")
async def run_reconciliation(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    entity_id = body.get('entity_id', user.get('entity_id', 'ent-01'))
    run_type = body.get('run_type', 'manual')

    with get_db() as db:
        run_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO reconciliation_runs (id, entity_id, run_type, status, run_by) VALUES (?,?,?,?,?)",
            (run_id, entity_id, run_type, 'running', user['uid'])
        )
        db.commit()

        findings = []

        # 1. Negative balances
        neg_lots = rows_to_list(db.execute(
            "SELECT * FROM inventory_lots WHERE entity_id=? AND qty_on_hand < 0 AND status='active'", (entity_id,)
        ).fetchall())
        for lot in neg_lots:
            findings.append(('negative_balance', 'critical',
                f"Lot {lot['tracking_id']} has negative balance: {lot['qty_on_hand']}", 'inventory_lot', lot['id']))

        # 2. Stuck lines >24h
        stuck = rows_to_list(db.execute(
            "SELECT * FROM outbound_request_lines WHERE entity_id=? AND status IN ('needs_approval','in_progress','allocated') "
            "AND datetime(updated_at) < datetime('now', '-24 hours')", (entity_id,)
        ).fetchall())
        for line in stuck:
            findings.append(('stuck_line', 'warning',
                f"Line {line['id']} in '{line['status']}' state for >24h", 'outbound_request_line', line['id']))

        # 3. Low remainder lots < 10m
        low_lots = rows_to_list(db.execute(
            "SELECT * FROM inventory_lots WHERE entity_id=? AND status='active' AND qty_on_hand < 10 AND qty_on_hand > 0",
            (entity_id,)
        ).fetchall())
        for lot in low_lots:
            findings.append(('low_remainder', 'warning',
                f"Lot {lot['tracking_id']} has only {lot['qty_on_hand']}m remaining - below 10m threshold",
                'inventory_lot', lot['id']))

        # 4. Missing/unprinted tags (cut transactions without printed tags)
        unprinted = rows_to_list(db.execute(
            "SELECT ct.id, ct.tracking_id FROM cut_transactions ct "
            "LEFT JOIN tag_labels tl ON ct.id = tl.cut_transaction_id "
            "WHERE ct.entity_id=? AND (tl.id IS NULL OR tl.tag_status = 'generated')", (entity_id,)
        ).fetchall())
        for ct in unprinted:
            findings.append(('missing_tag', 'critical',
                f"Cut transaction {ct['id']} has tag in generated state, not yet printed",
                'cut_transaction', ct['id']))

        # 5. Pending integration events
        pending_ie = rows_to_list(db.execute(
            "SELECT * FROM integration_events WHERE entity_id=? AND status='pending' AND datetime(created_at) < datetime('now', '-1 hour')",
            (entity_id,)
        ).fetchall())
        for ie in pending_ie:
            findings.append(('unsync_event', 'warning',
                f"Integration event {ie['id']} ({ie['event_type']}) pending for >1h",
                'integration_event', ie['id']))

        # Insert findings
        for ftype, sev, desc, rtype, rid in findings:
            fid = str(uuid.uuid4())
            db.execute(
                "INSERT INTO reconciliation_findings (id, reconciliation_run_id, entity_id, finding_type, severity, description, resource_type, resource_id, resolution_status) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (fid, run_id, entity_id, ftype, sev, desc, rtype, rid, 'open')
            )

        db.execute(
            "UPDATE reconciliation_runs SET status='completed', findings_count=?, completed_at=datetime('now') WHERE id=?",
            (len(findings), run_id)
        )
        write_audit(db, entity_id, user['uid'], 'run_reconciliation', 'reconciliation_run', run_id,
                    None, {'findings_count': len(findings), 'run_type': run_type})
        db.commit()
    return {'run_id': run_id, 'findings_count': len(findings), 'success': True}


# ========== E-COMMERCE CHANNELS ==========

@app.get("/api/channels")
async def get_channels(request: Request, entity_id: str = None):
    user = require_auth(request)
    entity_id = resolve_entity_id(user, entity_id)
    with get_db() as db:
        if entity_id:
            channels = rows_to_list(db.execute(
                "SELECT * FROM channel_connections WHERE entity_id=? ORDER BY created_at DESC", (entity_id,)
            ).fetchall())
        else:
            channels = rows_to_list(db.execute(
                "SELECT * FROM channel_connections ORDER BY created_at DESC"
            ).fetchall())
        # Mask encrypted fields
        for ch in channels:
            for field in ('api_key_encrypted', 'api_secret_encrypted', 'access_token_encrypted', 'refresh_token_encrypted'):
                if ch.get(field):
                    ch[field] = '***'
    return {'channels': channels}


@app.post("/api/channels")
async def create_channel(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    body = await request.json()
    ch_id = str(uuid.uuid4())
    with get_db() as db:
        db.execute(
            "INSERT INTO channel_connections (id, entity_id, channel_type, shop_name, api_key_encrypted, api_secret_encrypted, "
            "access_token_encrypted, refresh_token_encrypted, shop_url, region, is_active) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (ch_id, body['entity_id'], body['channel_type'], body.get('shop_name'),
             body.get('api_key'), body.get('api_secret'), body.get('access_token'), body.get('refresh_token'),
             body.get('shop_url'), body.get('region'), body.get('is_active', 1))
        )
        write_audit(db, body['entity_id'], user['uid'], 'create', 'channel_connection', ch_id,
                    None, {k: v for k, v in body.items() if 'key' not in k.lower() and 'secret' not in k.lower() and 'token' not in k.lower()})
        db.commit()
    return {'id': ch_id, 'success': True}


@app.put("/api/channels/{channel_id}")
async def update_channel(request: Request, channel_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    body = await request.json()
    with get_db() as db:
        before = dict_from_row(db.execute("SELECT * FROM channel_connections WHERE id=?", (channel_id,)).fetchone())
        if not before:
            raise HTTPException(status_code=404, detail="Channel not found")
        fields = {k: v for k, v in body.items() if k in (
            'shop_name', 'api_key_encrypted', 'api_secret_encrypted', 'access_token_encrypted',
            'refresh_token_encrypted', 'shop_url', 'region', 'is_active'
        )}
        # Map convenience names
        if 'api_key' in body: fields['api_key_encrypted'] = body['api_key']
        if 'api_secret' in body: fields['api_secret_encrypted'] = body['api_secret']
        if 'access_token' in body: fields['access_token_encrypted'] = body['access_token']
        if 'refresh_token' in body: fields['refresh_token_encrypted'] = body['refresh_token']
        if fields:
            fields['updated_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            set_clause = ", ".join(f"{k}=?" for k in fields)
            db.execute(f"UPDATE channel_connections SET {set_clause} WHERE id=?", list(fields.values()) + [channel_id])
        write_audit(db, before['entity_id'], user['uid'], 'update', 'channel_connection', channel_id,
                    None, {k: '***' if 'key' in k or 'secret' in k or 'token' in k else v for k, v in fields.items()})
        db.commit()
    return {'success': True}


@app.delete("/api/channels/{channel_id}")
async def deactivate_channel(request: Request, channel_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    with get_db() as db:
        before = dict_from_row(db.execute("SELECT * FROM channel_connections WHERE id=?", (channel_id,)).fetchone())
        if not before:
            raise HTTPException(status_code=404, detail="Channel not found")
        db.execute("UPDATE channel_connections SET is_active=0, updated_at=datetime('now') WHERE id=?", (channel_id,))
        write_audit(db, before['entity_id'], user['uid'], 'deactivate', 'channel_connection', channel_id,
                    {'is_active': 1}, {'is_active': 0})
        db.commit()
    return {'success': True}


@app.post("/api/channels/{channel_id}/sync_orders")
async def sync_channel_orders(request: Request, channel_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    with get_db() as db:
        ch = dict_from_row(db.execute("SELECT * FROM channel_connections WHERE id=?", (channel_id,)).fetchone())
        if not ch:
            raise HTTPException(status_code=404, detail="Channel not found")
        if not ch.get('is_active'):
            raise HTTPException(status_code=400, detail="Channel is not active")

        # Dispatch to channel adapter (stub or live)
        adapter = CHANNEL_ADAPTERS.get(ch['channel_type'], {})
        sync_fn = adapter.get('sync_orders', _stub_sync_orders)
        synced, _ = sync_fn(ch, db, user)

        db.execute("UPDATE channel_connections SET last_sync_at=datetime('now'), updated_at=datetime('now') WHERE id=?",
                   (channel_id,))
        write_audit(db, ch['entity_id'], user['uid'], 'sync_orders', 'channel_connection', channel_id,
                    None, {'synced_count': synced, 'stub': True})
        db.commit()
    return {'success': True, 'stub': True, 'synced_orders': synced,
            'message': f"Stub sync: {synced} orders simulated for {ch['channel_type']} channel '{ch['shop_name']}'"}


@app.post("/api/channels/{channel_id}/push_inventory")
async def push_channel_inventory(request: Request, channel_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    with get_db() as db:
        ch = dict_from_row(db.execute("SELECT * FROM channel_connections WHERE id=?", (channel_id,)).fetchone())
        if not ch:
            raise HTTPException(status_code=404, detail="Channel not found")

        # Query product mappings with available inventory
        mappings = rows_to_list(db.execute(
            "SELECT cpm.*, i.sku, "
            "COALESCE(SUM(il.qty_on_hand - COALESCE(il.qty_reserved,0)),0) as available_qty "
            "FROM channel_product_mappings cpm "
            "JOIN items i ON cpm.nexray_item_id = i.id "
            "LEFT JOIN inventory_lots il ON il.item_id = i.id AND il.status='active' "
            "WHERE cpm.channel_connection_id=? AND cpm.is_active=1 GROUP BY cpm.id",
            (channel_id,)
        ).fetchall())

        # Dispatch to channel adapter (stub or live)
        adapter = CHANNEL_ADAPTERS.get(ch['channel_type'], {})
        push_fn = adapter.get('push_inventory', _stub_push_inventory)
        pushed = push_fn(ch, db, mappings)

        db.execute("UPDATE channel_connections SET last_sync_at=datetime('now'), updated_at=datetime('now') WHERE id=?",
                   (channel_id,))
        write_audit(db, ch['entity_id'], user['uid'], 'push_inventory', 'channel_connection', channel_id,
                    None, {'pushed_count': len(pushed), 'stub': True})
        db.commit()
    return {'success': True, 'stub': True, 'pushed_items': pushed,
            'message': f"Stub push: {len(pushed)} items simulated for {ch['channel_type']} channel '{ch['shop_name']}'"}


@app.get("/api/channel_mappings")
async def get_channel_mappings(request: Request, channel_id: str = None):
    user = require_auth(request)
    with get_db() as db:
        if channel_id:
            mappings = rows_to_list(db.execute(
                "SELECT cpm.*, i.sku, i.name as item_name, cc.channel_type, cc.shop_name "
                "FROM channel_product_mappings cpm "
                "JOIN items i ON cpm.nexray_item_id = i.id "
                "JOIN channel_connections cc ON cpm.channel_connection_id = cc.id "
                "WHERE cpm.channel_connection_id=? ORDER BY cpm.created_at DESC", (channel_id,)
            ).fetchall())
        else:
            mappings = rows_to_list(db.execute(
                "SELECT cpm.*, i.sku, i.name as item_name, cc.channel_type, cc.shop_name "
                "FROM channel_product_mappings cpm "
                "JOIN items i ON cpm.nexray_item_id = i.id "
                "JOIN channel_connections cc ON cpm.channel_connection_id = cc.id "
                "ORDER BY cpm.created_at DESC"
            ).fetchall())
    return {'mappings': mappings}


@app.post("/api/channel_mappings")
async def create_channel_mapping(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    body = await request.json()
    cpm_id = str(uuid.uuid4())
    with get_db() as db:
        ch = dict_from_row(db.execute("SELECT entity_id FROM channel_connections WHERE id=?",
                                       (body['channel_connection_id'],)).fetchone())
        db.execute(
            "INSERT INTO channel_product_mappings (id, channel_connection_id, channel_product_id, channel_sku, nexray_item_id, is_active) "
            "VALUES (?,?,?,?,?,?)",
            (cpm_id, body['channel_connection_id'], body.get('channel_product_id'), body.get('channel_sku'),
             body['nexray_item_id'], body.get('is_active', 1))
        )
        write_audit(db, ch['entity_id'] if ch else None, user['uid'], 'create', 'channel_product_mapping', cpm_id, None, body)
        db.commit()
    return {'id': cpm_id, 'success': True}



# ========== CHANNEL ADAPTERS ==========

def _stub_sync_orders(channel, db, user):
    """Default stub adapter for order sync — returns simulated orders."""
    stub_orders = [
        {"channel_order_id": f"STUB-{channel['id'][:4]}-{i:03d}", "channel_status": "paid", "items": []}
        for i in range(1, 4)
    ]
    synced = 0
    for order in stub_orders:
        mapping_id = str(uuid.uuid4())
        try:
            db.execute(
                "INSERT INTO channel_order_mappings (id, channel_connection_id, channel_order_id, channel_status, sync_status, raw_order_json) "
                "VALUES (?,?,?,?,?,?)",
                (mapping_id, channel['id'], order['channel_order_id'], order['channel_status'],
                 'synced', json.dumps(order))
            )
            synced += 1
        except Exception:
            pass
    return synced, stub_orders

def _stub_push_inventory(channel, db, mappings):
    """Default stub adapter for inventory push — returns simulated push results."""
    pushed = []
    for m in mappings:
        pushed.append({
            'channel_sku': m['channel_sku'],
            'nexray_sku': m['sku'],
            'available_qty': round(m['available_qty'], 2),
            'push_status': 'stub_success'
        })
    return pushed

CHANNEL_ADAPTERS = {
    'shopify': {'sync_orders': _stub_sync_orders, 'push_inventory': _stub_push_inventory},
    'shopee': {'sync_orders': _stub_sync_orders, 'push_inventory': _stub_push_inventory},
    'lazada': {'sync_orders': _stub_sync_orders, 'push_inventory': _stub_push_inventory},
    'tiktokshop': {'sync_orders': _stub_sync_orders, 'push_inventory': _stub_push_inventory},
}


# ========== WEBHOOK RECEIVER ==========

@app.post("/api/webhooks/{channel_type}")
async def webhook_receiver(request: Request, channel_type: str):
    """Receive webhooks from channel platforms. Stores as integration_event for processing."""
    if channel_type not in ('shopify', 'shopee', 'lazada', 'tiktokshop'):
        return JSONResponse({"detail": "Unknown channel type"}, status_code=400)

    body = await request.json()
    event_id = str(uuid.uuid4())

    # TODO: Add per-channel signature verification here
    # e.g., verify HMAC for Shopify, signature for Lazada, etc.

    with get_db() as db:
        db.execute(
            "INSERT INTO integration_events (id, entity_id, event_type, event_idempotency_key, "
            "payload_json, status, direction) VALUES (?,?,?,?,?,?,?)",
            (event_id, 'system', f'{channel_type}_webhook', f'wh-{uuid.uuid4().hex[:12]}',
             json.dumps(body), 'pending', 'inbound')
        )
        db.commit()
    return {'received': True, 'event_id': event_id}


# ===== SERVE STATIC FILES + SPA FALLBACK =====
static_dir = "static"
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def serve_index():
    return FileResponse("static/index.html", media_type="text/html")

@app.get("/{path:path}")
async def catch_all(path: str):
    # API paths must never fall through to SPA — return proper JSON 404
    if path.startswith("api/"):
        return JSONResponse({"detail": "Not Found", "path": f"/{path}"}, status_code=404)

    # Path traversal protection: resolve and sandbox within static/
    static_root = Path("static").resolve()
    requested = (static_root / path).resolve()
    if not str(requested).startswith(str(static_root)):
        return JSONResponse({"detail": "Forbidden"}, status_code=403)

    if requested.is_file():
        mime_type, _ = mimetypes.guess_type(str(requested))
        if mime_type is None:
            mime_type = "application/octet-stream"
        return FileResponse(str(requested), media_type=mime_type)

    # SPA fallback for client-side routes
    index_path = static_root / "index.html"
    if index_path.is_file():
        return FileResponse(str(index_path), media_type="text/html")
    return JSONResponse({"detail": "Not Found"}, status_code=404)


# ===== STARTUP =====
@app.on_event("startup")
async def startup():
    init_db()
