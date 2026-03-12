"""
NEXRAY v3 — Shared Database Utilities
MySQL connection config, query helpers, auth helpers, audit logging, and schema init.
"""

import pymysql
import pymysql.cursors
import hashlib
import uuid
import os
import json
from datetime import datetime, timezone, timedelta
from contextlib import contextmanager
from decimal import Decimal
from fastapi import Request, HTTPException


# ========== CONFIG ==========
MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "nexray")


# ========== CONNECTION ==========
def _get_connection():
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


@contextmanager
def get_db():
    conn = _get_connection()
    try:
        yield conn
    finally:
        conn.close()


# ========== QUERY HELPERS ==========
def fetchone(conn, sql, args=None):
    with conn.cursor() as cur:
        cur.execute(sql, args or ())
        return cur.fetchone()


def fetchall(conn, sql, args=None):
    with conn.cursor() as cur:
        cur.execute(sql, args or ())
        return cur.fetchall()


def execute(conn, sql, args=None):
    with conn.cursor() as cur:
        cur.execute(sql, args or ())
        return cur.lastrowid


# ========== SERIALIZATION HELPERS ==========
def _serialize(obj):
    """Make query results JSON-serializable (Decimal, datetime, etc.)."""
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(v) for v in obj]
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.strftime('%Y-%m-%d %H:%M:%S')
    return obj


def rows_to_list(rows):
    return _serialize(list(rows)) if rows else []


def dict_from_row(row):
    return _serialize(row) if row else None


# ========== AUTH HELPERS ==========
def get_session_user(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    with get_db() as db:
        row = fetchone(db,
            "SELECT s.*, u.id as uid, u.username, u.display_name, u.email, u.role, u.warehouse_id, u.is_active "
            "FROM sessions s JOIN users u ON s.user_id = u.id "
            "WHERE s.token=%s AND s.expires_at > %s AND u.is_active=1",
            (token, now))
    return dict_from_row(row)


def require_auth(request: Request):
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
    if user['role'] == 'system_admin':
        return
    if user['role'] not in allowed_roles:
        raise HTTPException(status_code=403, detail=f"Forbidden: requires one of {allowed_roles}")


# ========== AUDIT ==========
def write_audit(db, actor_user_id, action, object_type, object_id,
                before_json=None, after_json=None, reason_code=None, notes=None, source_channel='web'):
    execute(db,
        "INSERT INTO audit_logs (id, actor_user_id, action, object_type, object_id, "
        "before_json, after_json, reason_code, notes, source_channel, created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())",
        (str(uuid.uuid4()), actor_user_id, action, object_type, object_id,
         json.dumps(before_json) if before_json and not isinstance(before_json, str) else before_json,
         json.dumps(after_json) if after_json and not isinstance(after_json, str) else after_json,
         reason_code, notes, source_channel))


# ========== DB INIT ==========
def init_db():
    # First ensure database exists
    try:
        conn = pymysql.connect(
            host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER, password=MYSQL_PASSWORD,
            charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.close()
    except Exception:
        pass

    with get_db() as db:
        with db.cursor() as cur:
            # ========== IDENTITY & ACCESS ==========
            cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id VARCHAR(36) PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                display_name VARCHAR(200) NOT NULL,
                email VARCHAR(200),
                password_hash VARCHAR(200) NOT NULL,
                password_salt VARCHAR(100),
                role VARCHAR(50) NOT NULL,
                warehouse_id VARCHAR(36),
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT NOW(),
                updated_at DATETIME DEFAULT NOW()
            )""")

            # ========== MASTER DATA ==========
            cur.execute("""
            CREATE TABLE IF NOT EXISTS warehouses (
                id VARCHAR(36) PRIMARY KEY,
                code VARCHAR(50) UNIQUE NOT NULL,
                name VARCHAR(200) NOT NULL,
                address TEXT,
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT NOW(),
                updated_at DATETIME DEFAULT NOW()
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS locations (
                id VARCHAR(36) PRIMARY KEY,
                warehouse_id VARCHAR(36) NOT NULL,
                zone_code VARCHAR(20),
                aisle_code VARCHAR(20),
                rack_code VARCHAR(20) NOT NULL,
                level_code VARCHAR(20),
                bin_code VARCHAR(20),
                location_barcode VARCHAR(100) UNIQUE,
                location_type VARCHAR(20) DEFAULT 'rack',
                capacity_qty DECIMAL(12,4),
                is_pickable INTEGER DEFAULT 1,
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT NOW(),
                FOREIGN KEY (warehouse_id) REFERENCES warehouses(id)
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id VARCHAR(36) PRIMARY KEY,
                sku VARCHAR(100) NOT NULL UNIQUE,
                name VARCHAR(300) NOT NULL,
                description TEXT,
                item_type VARCHAR(20) NOT NULL,
                base_uom VARCHAR(20) DEFAULT 'meter',
                inbound_uom VARCHAR(20) DEFAULT 'meter',
                outbound_uom VARCHAR(20) DEFAULT 'meter',
                category VARCHAR(100),
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT NOW(),
                updated_at DATETIME DEFAULT NOW()
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS suppliers (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(300) NOT NULL,
                code VARCHAR(50),
                contact_info TEXT,
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT NOW()
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(300) NOT NULL,
                code VARCHAR(50),
                contact_info TEXT,
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT NOW()
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS item_aliases (
                id VARCHAR(36) PRIMARY KEY,
                item_id VARCHAR(36) NOT NULL,
                alias_name VARCHAR(300) NOT NULL,
                branch_context VARCHAR(100),
                created_at DATETIME DEFAULT NOW(),
                FOREIGN KEY (item_id) REFERENCES items(id)
            )""")

            # ========== UOM CONVERSIONS ==========
            cur.execute("""
            CREATE TABLE IF NOT EXISTS uom_conversions (
                id VARCHAR(36) PRIMARY KEY,
                from_uom VARCHAR(20) NOT NULL,
                to_uom VARCHAR(20) NOT NULL,
                conversion_rate DECIMAL(12,6) NOT NULL,
                created_at DATETIME DEFAULT NOW()
            )""")

            # ========== INBOUND ==========
            cur.execute("""
            CREATE TABLE IF NOT EXISTS supplier_order_lists (
                id VARCHAR(36) PRIMARY KEY,
                supplier_id VARCHAR(36),
                batch_code VARCHAR(100) UNIQUE,
                company_label VARCHAR(200),
                import_hash VARCHAR(200),
                status VARCHAR(30) DEFAULT 'draft',
                total_lines INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                notes TEXT,
                created_by VARCHAR(36),
                created_at DATETIME DEFAULT NOW(),
                updated_at DATETIME DEFAULT NOW()
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS supplier_order_list_lines (
                id VARCHAR(36) PRIMARY KEY,
                supplier_order_list_id VARCHAR(36) NOT NULL,
                line_no INTEGER NOT NULL,
                item_id VARCHAR(36),
                item_name_raw VARCHAR(300),
                qty_expected DECIMAL(12,4) NOT NULL,
                uom VARCHAR(20) DEFAULT 'meter',
                lot_info VARCHAR(200),
                shade_info VARCHAR(100),
                width_info VARCHAR(100),
                validation_status VARCHAR(20) DEFAULT 'pending',
                validation_error TEXT,
                created_at DATETIME DEFAULT NOW(),
                FOREIGN KEY (supplier_order_list_id) REFERENCES supplier_order_lists(id)
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS receivings (
                id VARCHAR(36) PRIMARY KEY,
                warehouse_id VARCHAR(36) NOT NULL,
                supplier_order_list_id VARCHAR(36),
                status VARCHAR(20) DEFAULT 'in_progress',
                received_by VARCHAR(36),
                received_at DATETIME DEFAULT NOW(),
                notes TEXT,
                created_at DATETIME DEFAULT NOW(),
                FOREIGN KEY (warehouse_id) REFERENCES warehouses(id)
            )""")

            # ========== INVENTORY ==========
            cur.execute("""
            CREATE TABLE IF NOT EXISTS inventory_lots (
                id VARCHAR(36) PRIMARY KEY,
                item_id VARCHAR(36) NOT NULL,
                tracking_id VARCHAR(100) UNIQUE NOT NULL,
                batch_no VARCHAR(100),
                shade_code VARCHAR(50),
                width_value DECIMAL(12,4),
                qty_original DECIMAL(12,4) NOT NULL,
                qty_on_hand DECIMAL(12,4) NOT NULL,
                qty_reserved DECIMAL(12,4) DEFAULT 0,
                warehouse_id VARCHAR(36) NOT NULL,
                location_id VARCHAR(36),
                status VARCHAR(20) DEFAULT 'active',
                qty_confidence VARCHAR(30) DEFAULT 'measured',
                receiving_id VARCHAR(36),
                supplier_order_line_id VARCHAR(36),
                created_by VARCHAR(36),
                created_at DATETIME DEFAULT NOW(),
                updated_at DATETIME DEFAULT NOW(),
                FOREIGN KEY (item_id) REFERENCES items(id),
                FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
                FOREIGN KEY (location_id) REFERENCES locations(id)
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS inventory_movements (
                id VARCHAR(36) PRIMARY KEY,
                event_idempotency_key VARCHAR(200) UNIQUE NOT NULL,
                movement_type VARCHAR(30) NOT NULL,
                inventory_lot_id VARCHAR(36) NOT NULL,
                tracking_id VARCHAR(100),
                sales_order_line_id VARCHAR(36),
                cut_transaction_id VARCHAR(36),
                qty_delta DECIMAL(12,4) NOT NULL,
                qty_before DECIMAL(12,4) NOT NULL,
                qty_after DECIMAL(12,4) NOT NULL,
                warehouse_from_id VARCHAR(36),
                location_from_id VARCHAR(36),
                warehouse_to_id VARCHAR(36),
                location_to_id VARCHAR(36),
                reason_code VARCHAR(100),
                action_by VARCHAR(36) NOT NULL,
                action_at DATETIME DEFAULT NOW(),
                source_channel VARCHAR(30) DEFAULT 'web',
                meta_json TEXT,
                created_at DATETIME DEFAULT NOW()
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS inventory_reservations (
                id VARCHAR(36) PRIMARY KEY,
                inventory_lot_id VARCHAR(36) NOT NULL,
                outbound_request_line_id VARCHAR(36),
                qty_reserved DECIMAL(12,4) NOT NULL,
                reason TEXT,
                status VARCHAR(30) DEFAULT 'active',
                created_by VARCHAR(36),
                approved_by VARCHAR(36),
                approved_at DATETIME,
                created_at DATETIME DEFAULT NOW()
            )""")

            # ========== OUTBOUND ==========
            cur.execute("""
            CREATE TABLE IF NOT EXISTS outbound_requests (
                id VARCHAR(36) PRIMARY KEY,
                warehouse_id VARCHAR(36) NOT NULL,
                customer_id VARCHAR(36),
                company_label VARCHAR(200),
                reference_no VARCHAR(100),
                priority INTEGER DEFAULT 0,
                status VARCHAR(30) DEFAULT 'pending',
                created_by VARCHAR(36),
                created_at DATETIME DEFAULT NOW(),
                updated_at DATETIME DEFAULT NOW()
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS outbound_request_lines (
                id VARCHAR(36) PRIMARY KEY,
                outbound_request_id VARCHAR(36) NOT NULL,
                line_no INTEGER NOT NULL,
                item_id VARCHAR(36),
                item_name_raw VARCHAR(300),
                qty_requested DECIMAL(12,4) NOT NULL,
                qty_allocated DECIMAL(12,4) DEFAULT 0,
                qty_fulfilled DECIMAL(12,4) DEFAULT 0,
                qty_variance DECIMAL(12,4) DEFAULT 0,
                uom VARCHAR(20) DEFAULT 'meter',
                variance_reason_code VARCHAR(100),
                variance_approved_by VARCHAR(36),
                status VARCHAR(30) DEFAULT 'pending',
                claimed_by VARCHAR(36),
                claimed_at DATETIME,
                picked_by VARCHAR(36),
                picked_at DATETIME,
                fulfilled_by VARCHAR(36),
                fulfilled_at DATETIME,
                created_at DATETIME DEFAULT NOW(),
                updated_at DATETIME DEFAULT NOW(),
                FOREIGN KEY (outbound_request_id) REFERENCES outbound_requests(id)
            )""")

            # ========== EXECUTION ==========
            cur.execute("""
            CREATE TABLE IF NOT EXISTS pick_tasks (
                id VARCHAR(36) PRIMARY KEY,
                outbound_request_line_id VARCHAR(36) NOT NULL,
                inventory_lot_id VARCHAR(36) NOT NULL,
                warehouse_id VARCHAR(36) NOT NULL,
                location_id VARCHAR(36),
                qty_to_pick DECIMAL(12,4) NOT NULL,
                qty_picked DECIMAL(12,4) DEFAULT 0,
                status VARCHAR(20) DEFAULT 'pending',
                assigned_to VARCHAR(36),
                started_at DATETIME,
                completed_at DATETIME,
                created_at DATETIME DEFAULT NOW(),
                FOREIGN KEY (outbound_request_line_id) REFERENCES outbound_request_lines(id),
                FOREIGN KEY (inventory_lot_id) REFERENCES inventory_lots(id)
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS cut_transactions (
                id VARCHAR(36) PRIMARY KEY,
                outbound_request_line_id VARCHAR(36) NOT NULL,
                inventory_lot_id VARCHAR(36) NOT NULL,
                tracking_id VARCHAR(100) NOT NULL,
                qty_requested DECIMAL(12,4) NOT NULL,
                qty_actual DECIMAL(12,4) NOT NULL,
                qty_variance DECIMAL(12,4) DEFAULT 0,
                variance_reason TEXT,
                variance_approved_by VARCHAR(36),
                status VARCHAR(20) DEFAULT 'recorded',
                cut_by VARCHAR(36) NOT NULL,
                cut_at DATETIME DEFAULT NOW(),
                created_at DATETIME DEFAULT NOW(),
                FOREIGN KEY (outbound_request_line_id) REFERENCES outbound_request_lines(id),
                FOREIGN KEY (inventory_lot_id) REFERENCES inventory_lots(id)
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS tag_labels (
                id VARCHAR(36) PRIMARY KEY,
                tag_code VARCHAR(100) UNIQUE NOT NULL,
                cut_transaction_id VARCHAR(36),
                inventory_lot_id VARCHAR(36),
                outbound_request_line_id VARCHAR(36),
                tag_status VARCHAR(20) DEFAULT 'generated',
                printed_at DATETIME,
                printed_by VARCHAR(36),
                scanned_at DATETIME,
                scanned_by VARCHAR(36),
                invalidated_at DATETIME,
                invalidated_by VARCHAR(36),
                invalidate_reason TEXT,
                created_at DATETIME DEFAULT NOW(),
                FOREIGN KEY (cut_transaction_id) REFERENCES cut_transactions(id)
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS print_jobs (
                id VARCHAR(36) PRIMARY KEY,
                tag_label_id VARCHAR(36),
                job_type VARCHAR(30) DEFAULT 'tag',
                status VARCHAR(20) DEFAULT 'queued',
                printer_id VARCHAR(36),
                retry_count INTEGER DEFAULT 0,
                error_message TEXT,
                created_at DATETIME DEFAULT NOW(),
                completed_at DATETIME,
                FOREIGN KEY (tag_label_id) REFERENCES tag_labels(id)
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS staging_batches (
                id VARCHAR(36) PRIMARY KEY,
                batch_code VARCHAR(100) UNIQUE NOT NULL,
                status VARCHAR(20) DEFAULT 'open',
                created_by VARCHAR(36),
                created_at DATETIME DEFAULT NOW()
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS staging_scans (
                id VARCHAR(36) PRIMARY KEY,
                staging_batch_id VARCHAR(36) NOT NULL,
                outbound_request_line_id VARCHAR(36),
                inventory_lot_id VARCHAR(36),
                tracking_id VARCHAR(100),
                scanned_qty DECIMAL(12,4),
                scan_result VARCHAR(20) DEFAULT 'valid',
                scanned_by VARCHAR(36),
                scanned_at DATETIME DEFAULT NOW(),
                FOREIGN KEY (staging_batch_id) REFERENCES staging_batches(id)
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS putaway_events (
                id VARCHAR(36) PRIMARY KEY,
                inventory_lot_id VARCHAR(36) NOT NULL,
                from_location_id VARCHAR(36),
                to_location_id VARCHAR(36) NOT NULL,
                qty_moved DECIMAL(12,4) NOT NULL,
                moved_by VARCHAR(36),
                moved_at DATETIME DEFAULT NOW(),
                status VARCHAR(20) DEFAULT 'completed',
                created_at DATETIME DEFAULT NOW(),
                FOREIGN KEY (inventory_lot_id) REFERENCES inventory_lots(id)
            )""")

            # ========== CONTROLS ==========
            cur.execute("""
            CREATE TABLE IF NOT EXISTS adjustment_requests (
                id VARCHAR(36) PRIMARY KEY,
                inventory_lot_id VARCHAR(36),
                outbound_request_line_id VARCHAR(36),
                adjustment_type VARCHAR(30) NOT NULL,
                qty_before DECIMAL(12,4),
                qty_after DECIMAL(12,4),
                reason_code VARCHAR(100) NOT NULL,
                notes TEXT,
                status VARCHAR(20) DEFAULT 'pending',
                requested_by VARCHAR(36) NOT NULL,
                requested_at DATETIME DEFAULT NOW(),
                approved_by VARCHAR(36),
                approved_at DATETIME
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS reconciliation_runs (
                id VARCHAR(36) PRIMARY KEY,
                run_type VARCHAR(20) DEFAULT 'daily',
                status VARCHAR(20) DEFAULT 'running',
                findings_count INTEGER DEFAULT 0,
                run_by VARCHAR(36),
                started_at DATETIME DEFAULT NOW(),
                completed_at DATETIME
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS reconciliation_findings (
                id VARCHAR(36) PRIMARY KEY,
                reconciliation_run_id VARCHAR(36) NOT NULL,
                finding_type VARCHAR(30) NOT NULL,
                severity VARCHAR(20) DEFAULT 'warning',
                description TEXT,
                resource_type VARCHAR(50),
                resource_id VARCHAR(36),
                resolution_status VARCHAR(20) DEFAULT 'open',
                resolved_by VARCHAR(36),
                resolved_at DATETIME,
                resolution_notes TEXT,
                created_at DATETIME DEFAULT NOW(),
                FOREIGN KEY (reconciliation_run_id) REFERENCES reconciliation_runs(id)
            )""")

            # ========== INTEGRATIONS ==========
            cur.execute("""
            CREATE TABLE IF NOT EXISTS integration_events (
                id VARCHAR(36) PRIMARY KEY,
                event_type VARCHAR(100) NOT NULL,
                event_idempotency_key VARCHAR(200) UNIQUE NOT NULL,
                payload_json TEXT,
                status VARCHAR(20) DEFAULT 'pending',
                direction VARCHAR(20) DEFAULT 'outbound',
                retry_count INTEGER DEFAULT 0,
                error_message TEXT,
                created_at DATETIME DEFAULT NOW(),
                processed_at DATETIME
            )""")

            # ========== AUDIT ==========
            cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id VARCHAR(36) PRIMARY KEY,
                actor_user_id VARCHAR(36),
                action VARCHAR(100) NOT NULL,
                object_type VARCHAR(100) NOT NULL,
                object_id VARCHAR(36),
                before_json TEXT,
                after_json TEXT,
                reason_code VARCHAR(100),
                notes TEXT,
                source_channel VARCHAR(30) DEFAULT 'web',
                created_at DATETIME DEFAULT NOW()
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS automation_runs (
                id VARCHAR(36) PRIMARY KEY,
                automation_name VARCHAR(200) NOT NULL,
                trigger_table VARCHAR(100),
                trigger_record_id VARCHAR(36),
                event_idempotency_key VARCHAR(200) UNIQUE,
                run_status VARCHAR(20) DEFAULT 'running',
                error_message TEXT,
                started_at DATETIME DEFAULT NOW(),
                finished_at DATETIME
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS workflow_locks (
                id VARCHAR(36) PRIMARY KEY,
                resource_type VARCHAR(100) NOT NULL,
                resource_id VARCHAR(36) NOT NULL,
                lock_owner VARCHAR(36) NOT NULL,
                lock_acquired_at DATETIME DEFAULT NOW(),
                lock_expires_at DATETIME,
                UNIQUE(resource_type, resource_id)
            )""")

            # ========== SESSIONS ==========
            cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id VARCHAR(36) PRIMARY KEY,
                user_id VARCHAR(36) NOT NULL,
                token VARCHAR(100) UNIQUE NOT NULL,
                created_at DATETIME DEFAULT NOW(),
                expires_at DATETIME NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )""")

            # ========== CHANNEL CONNECTIONS ==========
            cur.execute("""
            CREATE TABLE IF NOT EXISTS channel_connections (
                id VARCHAR(36) PRIMARY KEY,
                channel_type VARCHAR(30) NOT NULL,
                shop_name VARCHAR(200),
                api_key_encrypted TEXT,
                api_secret_encrypted TEXT,
                access_token_encrypted TEXT,
                refresh_token_encrypted TEXT,
                shop_url VARCHAR(500),
                region VARCHAR(20),
                is_active INTEGER DEFAULT 1,
                last_sync_at DATETIME,
                created_at DATETIME DEFAULT NOW(),
                updated_at DATETIME DEFAULT NOW()
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS channel_order_mappings (
                id VARCHAR(36) PRIMARY KEY,
                channel_connection_id VARCHAR(36) NOT NULL,
                channel_order_id VARCHAR(100) NOT NULL,
                nexray_outbound_request_id VARCHAR(36),
                channel_status VARCHAR(50),
                sync_status VARCHAR(20) DEFAULT 'pending',
                raw_order_json TEXT,
                created_at DATETIME DEFAULT NOW(),
                updated_at DATETIME DEFAULT NOW()
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS channel_product_mappings (
                id VARCHAR(36) PRIMARY KEY,
                channel_connection_id VARCHAR(36) NOT NULL,
                channel_product_id VARCHAR(100),
                channel_sku VARCHAR(100),
                nexray_item_id VARCHAR(36) NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT NOW()
            )""")

            # ========== RETURNS ==========
            cur.execute("""
            CREATE TABLE IF NOT EXISTS returns (
                id VARCHAR(36) PRIMARY KEY,
                original_tracking_id VARCHAR(100),
                new_tracking_id VARCHAR(100) UNIQUE,
                item_id VARCHAR(36) NOT NULL,
                qty_returned DECIMAL(12,4) NOT NULL,
                return_reason TEXT,
                return_type VARCHAR(20) DEFAULT 'other',
                warehouse_id VARCHAR(36),
                location_id VARCHAR(36),
                status VARCHAR(20) DEFAULT 'pending',
                received_by VARCHAR(36),
                created_at DATETIME DEFAULT NOW()
            )""")

            # ========== INDEXES ==========
            index_stmts = [
                "CREATE INDEX idx_inv_lots_warehouse ON inventory_lots(warehouse_id)",
                "CREATE INDEX idx_inv_lots_item ON inventory_lots(item_id)",
                "CREATE INDEX idx_inv_lots_tracking ON inventory_lots(tracking_id)",
                "CREATE INDEX idx_inv_lots_status ON inventory_lots(status)",
                "CREATE INDEX idx_inv_movements_lot ON inventory_movements(inventory_lot_id)",
                "CREATE INDEX idx_inv_movements_type ON inventory_movements(movement_type)",
                "CREATE INDEX idx_orl_status ON outbound_request_lines(status)",
                "CREATE INDEX idx_cut_txn_line ON cut_transactions(outbound_request_line_id)",
                "CREATE INDEX idx_tag_cut ON tag_labels(cut_transaction_id)",
                "CREATE INDEX idx_audit_object ON audit_logs(object_type, object_id)",
                "CREATE INDEX idx_integ_status ON integration_events(status)",
                "CREATE INDEX idx_sessions_token ON sessions(token)",
                "CREATE INDEX idx_sessions_user ON sessions(user_id)",
            ]
            for stmt in index_stmts:
                try:
                    cur.execute(stmt)
                except Exception:
                    pass  # index already exists

        db.commit()

        # Seed demo data if empty
        count = fetchone(db, "SELECT COUNT(*) as c FROM users")
        if count and count['c'] == 0:
            seed_demo_data(db)
            db.commit()


def seed_demo_data(db):
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    users = [
        ('usr-01', 'admin', 'System Admin', 'admin@nexray.local', 'system_admin', None),
        ('usr-02', 'warehouse1', 'Juan Cruz', 'juan@nexray.local', 'warehouse_operator', 'wh-01'),
        ('usr-03', 'lead1', 'Maria Santos', 'maria@nexray.local', 'warehouse_lead', 'wh-01'),
        ('usr-04', 'inv_admin', 'Carlos Reyes', 'carlos@nexray.local', 'inventory_admin', None),
        ('usr-05', 'manager1', 'Ana Dela Cruz', 'ana@nexray.local', 'manager', None),
        ('usr-06', 'acct1', 'Rose Lim', 'rose@nexray.local', 'accounting_operator', None),
    ]
    for uid, uname, dname, email, role, wid in users:
        salt = uuid.uuid4().hex[:16]
        phash = hashlib.sha256((salt + uname).encode()).hexdigest()
        execute(db,
            "INSERT INTO users (id, username, display_name, email, password_hash, password_salt, role, warehouse_id) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (uid, uname, dname, email, phash, salt, role, wid))

    warehouses = [
        ('wh-01', 'MNL-MAIN', 'Manila Design Center', 'Quezon City, Manila'),
        ('wh-02', 'CEB-01', 'Cebu Distribution Hub', 'Mandaue, Cebu'),
    ]
    for wid, code, name, addr in warehouses:
        execute(db, "INSERT INTO warehouses (id, code, name, address) VALUES (%s,%s,%s,%s)", (wid, code, name, addr))

    locs = [
        ('loc-01', 'wh-01', 'A', '1', 'R01', '1', 'B01', 'MNL-A1-R01-1-B01', 'rack'),
        ('loc-02', 'wh-01', 'A', '1', 'R01', '2', 'B02', 'MNL-A1-R01-2-B02', 'rack'),
        ('loc-03', 'wh-01', 'A', '1', 'R02', '1', 'B01', 'MNL-A1-R02-1-B01', 'rack'),
        ('loc-04', 'wh-01', 'B', '1', 'R01', '1', 'B01', 'MNL-B1-R01-1-B01', 'bin'),
        ('loc-05', 'wh-01', None, None, 'STG', None, 'STG-01', 'MNL-STG-01', 'staging'),
        ('loc-06', 'wh-02', 'A', '1', 'R01', '1', 'B01', 'CEB-A1-R01-1-B01', 'rack'),
    ]
    for lid, wid, zone, aisle, rack, level, binc, barcode, ltype in locs:
        execute(db,
            "INSERT INTO locations (id, warehouse_id, zone_code, aisle_code, rack_code, level_code, bin_code, location_barcode, location_type) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (lid, wid, zone, aisle, rack, level, binc, barcode, ltype))

    items_data = [
        ('itm-01', 'FAB-BLK-001', 'Blackout Curtain Fabric - Ivory', 'fabric', 'meter', 'Curtains'),
        ('itm-02', 'FAB-SHR-001', 'Sheer Voile Fabric - White', 'fabric', 'meter', 'Curtains'),
        ('itm-03', 'FAB-LIN-001', 'Linen Blend Fabric - Natural', 'fabric', 'meter', 'Curtains'),
        ('itm-04', 'FAB-VEL-001', 'Velvet Fabric - Emerald', 'fabric', 'meter', 'Curtains'),
        ('itm-05', 'CMP-ROD-001', 'Curtain Rod - Brushed Nickel 1.2m', 'component', 'piece', 'Hardware'),
        ('itm-06', 'CMP-RNG-001', 'Curtain Rings - Pack of 10', 'component', 'pack', 'Hardware'),
        ('itm-07', 'CMP-TIE-001', 'Tieback Hooks - Pair', 'component', 'pair', 'Hardware'),
    ]
    for iid, sku, name, itype, uom, cat in items_data:
        execute(db,
            "INSERT INTO items (id, sku, name, item_type, base_uom, inbound_uom, outbound_uom, category) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (iid, sku, name, itype, uom, uom, uom, cat))

    execute(db, "INSERT INTO suppliers (id, name, code) VALUES (%s,%s,%s)", ('sup-01', 'Guangzhou Textile Co.', 'GZ-TEX'))
    execute(db, "INSERT INTO suppliers (id, name, code) VALUES (%s,%s,%s)", ('sup-02', 'Shanghai Fabrics Ltd.', 'SH-FAB'))

    execute(db, "INSERT INTO customers (id, name, code) VALUES (%s,%s,%s)", ('cust-01', 'InterContinental Hotels', 'ICH'))
    execute(db, "INSERT INTO customers (id, name, code) VALUES (%s,%s,%s)", ('cust-02', 'Ayala Land Inc.', 'ALI'))

    # Seed UOM conversions
    uom_convs = [
        ('meter', 'yard', 1.09361),
        ('yard', 'meter', 0.9144),
        ('meter', 'feet', 3.28084),
        ('feet', 'meter', 0.3048),
    ]
    for from_u, to_u, rate in uom_convs:
        execute(db, "INSERT INTO uom_conversions (id, from_uom, to_uom, conversion_rate) VALUES (%s,%s,%s,%s)",
                (str(uuid.uuid4()), from_u, to_u, rate))

    lots = [
        ('lot-01', 'itm-01', 'TRK-2024-0001', 'IVR-01', 137.0, 50.0, 92.5, 10.0, 'wh-01', 'loc-01', 'active', 'measured'),
        ('lot-02', 'itm-01', 'TRK-2024-0002', 'IVR-01', 137.0, 50.0, 120.0, 0.0, 'wh-01', 'loc-02', 'active', 'measured'),
        ('lot-03', 'itm-02', 'TRK-2024-0003', 'WHT-01', 137.0, 100.0, 85.5, 0.0, 'wh-01', 'loc-03', 'active', 'measured'),
        ('lot-04', 'itm-03', 'TRK-2024-0004', 'NAT-01', 137.0, 75.0, 75.0, 0.0, 'wh-01', 'loc-04', 'active', 'supplier_reported'),
        ('lot-05', 'itm-04', 'TRK-2024-0005', 'EMR-01', 137.0, 60.0, 15.2, 0.0, 'wh-01', 'loc-01', 'active', 'measured'),
        ('lot-06', 'itm-01', 'TRK-2024-0007', 'IVR-02', 137.0, 50.0, 8.5, 0.0, 'wh-01', 'loc-01', 'active', 'measured'),
    ]
    for lid, iid, tid, shade, width, orig, onhand, reserved, wid, locid, status, conf in lots:
        execute(db,
            "INSERT INTO inventory_lots (id, item_id, tracking_id, shade_code, width_value, qty_original, qty_on_hand, qty_reserved, warehouse_id, location_id, status, qty_confidence) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (lid, iid, tid, shade, width, orig, onhand, reserved, wid, locid, status, conf))

    execute(db,
        "INSERT INTO outbound_requests (id, warehouse_id, customer_id, reference_no, status, created_by, created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
        ('or-01', 'wh-01', 'cust-01', 'PO-ICH-2024-001', 'in_progress', 'usr-05', now))

    or_lines = [
        ('orl-01', 'or-01', 1, 'itm-01', 25.0, 25.0, 25.0, 0.0, 'closed'),
        ('orl-02', 'or-01', 2, 'itm-02', 15.0, 15.0, 14.5, -0.5, 'needs_approval'),
        ('orl-03', 'or-01', 3, 'itm-03', 30.0, 30.0, 0.0, 0.0, 'allocated'),
        ('orl-04', 'or-01', 4, 'itm-04', 10.0, 0.0, 0.0, 0.0, 'pending'),
    ]
    for lid, orid, lno, iid, req, alloc, ful, var, status in or_lines:
        execute(db,
            "INSERT INTO outbound_request_lines (id, outbound_request_id, line_no, item_id, qty_requested, qty_allocated, qty_fulfilled, qty_variance, status) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (lid, orid, lno, iid, req, alloc, ful, var, status))

    # Cut transactions - qty_variance calculated in Python
    execute(db,
        "INSERT INTO cut_transactions (id, outbound_request_line_id, inventory_lot_id, tracking_id, qty_requested, qty_actual, qty_variance, cut_by, status) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        ('cut-01', 'orl-01', 'lot-01', 'TRK-2024-0001', 25.0, 25.0, 0.0, 'usr-02', 'approved'))
    execute(db,
        "INSERT INTO cut_transactions (id, outbound_request_line_id, inventory_lot_id, tracking_id, qty_requested, qty_actual, qty_variance, variance_reason, cut_by, status) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        ('cut-02', 'orl-02', 'lot-03', 'TRK-2024-0003', 15.0, 14.5, -0.5, 'Material edge defect - 0.5m unusable', 'usr-02', 'recorded'))

    execute(db,
        "INSERT INTO tag_labels (id, tag_code, cut_transaction_id, inventory_lot_id, outbound_request_line_id, tag_status, printed_at, printed_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        ('tag-01', 'NXR-TAG-0001', 'cut-01', 'lot-01', 'orl-01', 'printed', now, 'usr-02'))
    execute(db,
        "INSERT INTO tag_labels (id, tag_code, cut_transaction_id, inventory_lot_id, outbound_request_line_id, tag_status) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        ('tag-02', 'NXR-TAG-0002', 'cut-02', 'lot-03', 'orl-02', 'generated'))

    movements = [
        ('mov-01', 'recv-lot01-init', 'receive', 'lot-01', 'TRK-2024-0001', None, None, 50.0, 0.0, 50.0, None, None, 'wh-01', 'loc-01', 'usr-04'),
        ('mov-02', 'cut-01-deduct', 'deduct', 'lot-01', 'TRK-2024-0001', 'orl-01', 'cut-01', -25.0, 117.5, 92.5, 'wh-01', 'loc-01', None, None, 'usr-02'),
        ('mov-03', 'cut-02-deduct', 'deduct', 'lot-03', 'TRK-2024-0003', 'orl-02', 'cut-02', -14.5, 100.0, 85.5, 'wh-01', 'loc-03', None, None, 'usr-02'),
    ]
    for mid, ikey, mtype, lotid, tid, solid, ctid, delta, before, after, wfrom, lfrom, wto, lto, actor in movements:
        execute(db,
            "INSERT INTO inventory_movements (id, event_idempotency_key, movement_type, inventory_lot_id, tracking_id, "
            "sales_order_line_id, cut_transaction_id, qty_delta, qty_before, qty_after, warehouse_from_id, location_from_id, "
            "warehouse_to_id, location_to_id, action_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (mid, ikey, mtype, lotid, tid, solid, ctid, delta, before, after, wfrom, lfrom, wto, lto, actor))

    execute(db,
        "INSERT INTO adjustment_requests (id, outbound_request_line_id, adjustment_type, qty_before, qty_after, reason_code, notes, status, requested_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        ('adj-01', 'orl-02', 'variance_approval', 15.0, 14.5, 'material_defect', 'Edge defect on roll, 0.5m unusable section', 'pending', 'usr-02'))

    execute(db,
        "INSERT INTO integration_events (id, event_type, event_idempotency_key, payload_json, status, direction) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        ('ie-01', 'fulfillment_complete', 'ful-orl01-complete', '{"line_id":"orl-01","qty":25.0}', 'pending', 'outbound'))

    execute(db,
        "INSERT INTO reconciliation_runs (id, run_type, status, findings_count, run_by, completed_at) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        ('rec-01', 'daily', 'completed', 3, 'usr-04', now))

    findings = [
        ('rf-01', 'rec-01', 'low_remainder', 'warning', 'Lot TRK-2024-0007 has only 8.5m remaining - below 10m threshold', 'inventory_lot', 'lot-06', 'open'),
        ('rf-02', 'rec-01', 'missing_tag', 'critical', 'Cut transaction cut-02 has tag in generated state, not yet printed', 'cut_transaction', 'cut-02', 'open'),
        ('rf-03', 'rec-01', 'stuck_line', 'warning', 'Line orl-02 in needs_approval state for >24h', 'outbound_request_line', 'orl-02', 'open'),
    ]
    for fid, rid, ftype, sev, desc, rtype, resid, rstatus in findings:
        execute(db,
            "INSERT INTO reconciliation_findings (id, reconciliation_run_id, finding_type, severity, description, resource_type, resource_id, resolution_status) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (fid, rid, ftype, sev, desc, rtype, resid, rstatus))

    # Seed channel connections
    execute(db,
        "INSERT INTO channel_connections (id, channel_type, shop_name, shop_url, region, is_active, last_sync_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
        ('ch-01', 'shopify', 'NEXRAY DTC Store', 'https://nexray-dtc.myshopify.com', 'PH', 1, now))

    execute(db,
        "INSERT INTO channel_product_mappings (id, channel_connection_id, channel_product_id, channel_sku, nexray_item_id, is_active) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        ('cpm-01', 'ch-01', 'shopify-prod-001', 'FAB-BLK-001-IVR', 'itm-01', 1))
