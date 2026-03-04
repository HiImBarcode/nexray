"""
NEXRAY — FastAPI Backend Server
Private internal operations platform for multi-entity textile operations.
Deploy on Railway, Render, or any cloud platform.
"""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
import sqlite3
import hashlib
import uuid
import os
from datetime import datetime, timezone
from contextlib import contextmanager

# ========== CONFIG ==========
DB_PATH = os.environ.get("NEXRAY_DB_PATH", "nexray.db")

app = FastAPI(title="NEXRAY Operations Platform", version="1.0.0")

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
        """)

        # Seed demo data if empty
        if db.execute("SELECT COUNT(*) FROM entities").fetchone()[0] == 0:
            seed_demo_data(db)

        db.commit()


def seed_demo_data(db):
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    entities = [
        ('ent-01', 'Premium Projects', 'PREM'),
        ('ent-02', 'B2B Wholesale', 'B2B'),
        ('ent-03', 'DTC E-Commerce', 'DTC'),
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
        phash = hashlib.sha256(('nexray2024_' + uname).encode()).hexdigest()
        db.execute("INSERT INTO users (id, username, display_name, email, password_hash, role, entity_id, warehouse_id) VALUES (?,?,?,?,?,?,?,?)",
                   (uid, uname, dname, email, phash, role, eid, wid))

    warehouses = [
        ('wh-01', 'ent-01', 'MNL-MAIN', 'Manila Main Warehouse', 'Quezon City, Manila'),
        ('wh-02', 'ent-01', 'CEB-01', 'Cebu Warehouse', 'Mandaue, Cebu'),
        ('wh-03', 'ent-02', 'AUR-01', 'Aurora Warehouse', 'Aurora, Quezon'),
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


# ========== API ROUTES ==========

@app.get("/api/dashboard")
async def get_dashboard(entity_id: str = "ent-01"):
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
async def get_inventory(entity_id: str = "ent-01", warehouse_id: str = None, status: str = "active", item_type: str = None):
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
async def get_outbound(entity_id: str = "ent-01", status: str = None):
    with get_db() as db:
        query = """SELECT orl.*, i.sku, i.name as item_name, orq.reference_no, orq.warehouse_id, w.code as warehouse_code
                   FROM outbound_request_lines orl LEFT JOIN outbound_requests orq ON orl.outbound_request_id = orq.id
                   LEFT JOIN items i ON orl.item_id = i.id LEFT JOIN warehouses w ON orq.warehouse_id = w.id WHERE orl.entity_id=?"""
        args = [entity_id]
        if status: query += " AND orl.status=?"; args.append(status)
        query += " ORDER BY orl.created_at DESC"
        return {'lines': rows_to_list(db.execute(query, args).fetchall())}


@app.get("/api/cuts")
async def get_cuts(entity_id: str = "ent-01"):
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
async def get_tags(entity_id: str = "ent-01"):
    with get_db() as db:
        tags = rows_to_list(db.execute("""
            SELECT tl.*, ct.qty_actual as cut_qty, il.tracking_id as lot_tracking, i.name as item_name
            FROM tag_labels tl LEFT JOIN cut_transactions ct ON tl.cut_transaction_id = ct.id
            LEFT JOIN inventory_lots il ON tl.inventory_lot_id = il.id LEFT JOIN items i ON il.item_id = i.id
            WHERE tl.entity_id=? ORDER BY tl.created_at DESC
        """, (entity_id,)).fetchall())
    return {'tags': tags}


@app.get("/api/warehouses")
async def get_warehouses(entity_id: str = "ent-01"):
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
async def get_locations(warehouse_id: str = "wh-01"):
    with get_db() as db:
        locs = rows_to_list(db.execute("""
            SELECT l.*,
                (SELECT COUNT(*) FROM inventory_lots il WHERE il.location_id=l.id AND il.status='active') as lot_count,
                (SELECT COALESCE(SUM(il.qty_on_hand),0) FROM inventory_lots il WHERE il.location_id=l.id AND il.status='active') as total_qty
            FROM locations l WHERE l.warehouse_id=? ORDER BY l.zone_code, l.aisle_code, l.rack_code, l.level_code
        """, (warehouse_id,)).fetchall())
    return {'locations': locs}


@app.get("/api/adjustments")
async def get_adjustments(entity_id: str = "ent-01", status: str = None):
    with get_db() as db:
        query = "SELECT * FROM adjustment_requests WHERE entity_id=?"
        args = [entity_id]
        if status: query += " AND status=?"; args.append(status)
        query += " ORDER BY requested_at DESC"
        return {'adjustments': rows_to_list(db.execute(query, args).fetchall())}


@app.get("/api/findings")
async def get_findings(entity_id: str = "ent-01", resolution_status: str = None):
    with get_db() as db:
        query = "SELECT * FROM reconciliation_findings WHERE entity_id=?"
        args = [entity_id]
        if resolution_status: query += " AND resolution_status=?"; args.append(resolution_status)
        query += " ORDER BY created_at DESC"
        return {'findings': rows_to_list(db.execute(query, args).fetchall())}


@app.get("/api/movements")
async def get_movements(entity_id: str = "ent-01", lot_id: str = None):
    with get_db() as db:
        query = """SELECT im.*, il.tracking_id as lot_tracking, i.name as item_name
                   FROM inventory_movements im LEFT JOIN inventory_lots il ON im.inventory_lot_id = il.id
                   LEFT JOIN items i ON il.item_id = i.id WHERE im.entity_id=?"""
        args = [entity_id]
        if lot_id: query += " AND im.inventory_lot_id=?"; args.append(lot_id)
        query += " ORDER BY im.action_at DESC LIMIT 100"
        return {'movements': rows_to_list(db.execute(query, args).fetchall())}


@app.get("/api/integration_events")
async def get_integration_events(entity_id: str = "ent-01", status: str = None):
    with get_db() as db:
        query = "SELECT * FROM integration_events WHERE entity_id=?"
        args = [entity_id]
        if status: query += " AND status=?"; args.append(status)
        query += " ORDER BY created_at DESC"
        return {'events': rows_to_list(db.execute(query, args).fetchall())}


@app.get("/api/users")
async def get_users():
    with get_db() as db:
        users = rows_to_list(db.execute("""
            SELECT u.id, u.username, u.display_name, u.email, u.role, u.entity_id, u.warehouse_id, u.is_active,
                   e.name as entity_name, w.name as warehouse_name
            FROM users u LEFT JOIN entities e ON u.entity_id = e.id LEFT JOIN warehouses w ON u.warehouse_id = w.id
            ORDER BY u.role, u.display_name
        """).fetchall())
    return {'users': users}


@app.get("/api/entities")
async def get_entities():
    with get_db() as db:
        return {'entities': rows_to_list(db.execute("SELECT * FROM entities ORDER BY name").fetchall())}


@app.get("/api/audit_log")
async def get_audit_log(entity_id: str = "ent-01"):
    with get_db() as db:
        logs = rows_to_list(db.execute("""
            SELECT al.*, u.display_name as actor_name FROM audit_logs al
            LEFT JOIN users u ON al.actor_user_id = u.id
            WHERE al.entity_id=? OR al.entity_id IS NULL ORDER BY al.created_at DESC LIMIT 50
        """, (entity_id,)).fetchall())
    return {'logs': logs}


@app.get("/api/supplier_orders")
async def get_supplier_orders(entity_id: str = "ent-01"):
    with get_db() as db:
        orders = rows_to_list(db.execute("""
            SELECT sol.*, s.name as supplier_name FROM supplier_order_lists sol
            LEFT JOIN suppliers s ON sol.supplier_id = s.id WHERE sol.entity_id=? ORDER BY sol.created_at DESC
        """, (entity_id,)).fetchall())
    return {'orders': orders}


@app.get("/api/print_jobs")
async def get_print_jobs(entity_id: str = "ent-01"):
    with get_db() as db:
        jobs = rows_to_list(db.execute("""
            SELECT pj.*, tl.tag_code FROM print_jobs pj
            LEFT JOIN tag_labels tl ON pj.tag_label_id = tl.id WHERE pj.entity_id=? ORDER BY pj.created_at DESC
        """, (entity_id,)).fetchall())
    return {'jobs': jobs}


# ===== POST ENDPOINTS =====
@app.post("/api/approve_adjustment")
async def approve_adjustment(request: Request):
    body = await request.json()
    with get_db() as db:
        db.execute("UPDATE adjustment_requests SET status='approved', approved_by=?, approved_at=datetime('now') WHERE id=?",
                   (body.get('approved_by', 'usr-05'), body['id']))
        db.commit()
    return {'success': True}


@app.post("/api/reject_adjustment")
async def reject_adjustment(request: Request):
    body = await request.json()
    with get_db() as db:
        db.execute("UPDATE adjustment_requests SET status='rejected', approved_by=?, approved_at=datetime('now') WHERE id=?",
                   (body.get('rejected_by', 'usr-05'), body['id']))
        db.commit()
    return {'success': True}


@app.post("/api/resolve_finding")
async def resolve_finding(request: Request):
    body = await request.json()
    with get_db() as db:
        db.execute("UPDATE reconciliation_findings SET resolution_status='resolved', resolved_by=?, resolved_at=datetime('now'), resolution_notes=? WHERE id=?",
                   (body.get('resolved_by', 'usr-04'), body.get('notes', ''), body['id']))
        db.commit()
    return {'success': True}


@app.post("/api/update_line_status")
async def update_line_status(request: Request):
    body = await request.json()
    with get_db() as db:
        db.execute("UPDATE outbound_request_lines SET status=?, updated_at=datetime('now') WHERE id=?",
                   (body['status'], body['id']))
        db.commit()
    return {'success': True}


@app.post("/api/retry_integration")
async def retry_integration(request: Request):
    body = await request.json()
    with get_db() as db:
        db.execute("UPDATE integration_events SET status='pending', retry_count=retry_count+1 WHERE id=?", (body['id'],))
        db.commit()
    return {'success': True}


# ===== HEALTH CHECK =====
@app.get("/api/health")
async def health_check():
    try:
        with get_db() as db:
            db.execute("SELECT 1")
        return {"status": "ok", "service": "nexray", "version": "1.0.0"}
    except Exception as e:
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=503)


# ===== SERVE STATIC FILES + SPA FALLBACK =====
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def serve_index():
    return FileResponse("static/index.html")

@app.get("/{path:path}")
async def catch_all(path: str):
    file_path = f"static/{path}"
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    return FileResponse("static/index.html")


# ===== STARTUP =====
@app.on_event("startup")
async def startup():
    init_db()
