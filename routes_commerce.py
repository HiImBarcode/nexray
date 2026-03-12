"""
NEXRAY v3 — Commerce Hub API Routes
Listings engine, unified order hub, stock sync, fulfillment/printing,
e-commerce returns, and affiliate management.
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

VALID_COMPANY_LABELS = [
    "Larry's Hitex Division Inc.",
    "Fabric Life",
    "Casa Finds",
]


# ========== DB INIT ==========

def init_commerce_db():
    with get_db() as db:
        with db.cursor() as cur:
            # ---------- Listings Engine ----------
            cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id VARCHAR(36) PRIMARY KEY,
                sku VARCHAR(100) UNIQUE NOT NULL,
                name VARCHAR(300) NOT NULL,
                description TEXT,
                category VARCHAR(200),
                brand VARCHAR(200),
                base_price DECIMAL(12,2),
                cost_price DECIMAL(12,2),
                weight_grams INTEGER,
                images JSON,
                tags JSON,
                item_id VARCHAR(36),
                company_label VARCHAR(200),
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT NOW(),
                updated_at DATETIME DEFAULT NOW()
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS platform_listings (
                id VARCHAR(36) PRIMARY KEY,
                product_id VARCHAR(36) NOT NULL,
                platform VARCHAR(50) NOT NULL,
                platform_product_id VARCHAR(200),
                platform_sku VARCHAR(200),
                shop_id VARCHAR(36),
                title VARCHAR(500),
                description TEXT,
                price DECIMAL(12,2),
                compare_at_price DECIMAL(12,2),
                platform_category VARCHAR(300),
                platform_attributes JSON,
                listing_url VARCHAR(500),
                status VARCHAR(30) DEFAULT 'draft',
                sync_status VARCHAR(30) DEFAULT 'pending',
                last_synced_at DATETIME,
                error_message TEXT,
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT NOW(),
                updated_at DATETIME DEFAULT NOW()
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS product_variants (
                id VARCHAR(36) PRIMARY KEY,
                product_id VARCHAR(36) NOT NULL,
                variant_name VARCHAR(200),
                sku_suffix VARCHAR(50),
                price_override DECIMAL(12,2),
                attributes JSON,
                item_id VARCHAR(36),
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT NOW()
            )""")

            # ---------- Unified Order Hub ----------
            cur.execute("""
            CREATE TABLE IF NOT EXISTS ecommerce_orders (
                id VARCHAR(36) PRIMARY KEY,
                platform VARCHAR(50) NOT NULL,
                platform_order_id VARCHAR(200),
                shop_id VARCHAR(36),
                company_label VARCHAR(200),
                customer_name VARCHAR(300),
                customer_phone VARCHAR(100),
                customer_email VARCHAR(200),
                shipping_address TEXT,
                shipping_method VARCHAR(200),
                tracking_number VARCHAR(200),
                carrier VARCHAR(100),
                subtotal DECIMAL(12,2),
                shipping_fee DECIMAL(12,2),
                discount DECIMAL(12,2) DEFAULT 0,
                total DECIMAL(12,2),
                currency VARCHAR(10) DEFAULT 'PHP',
                platform_status VARCHAR(50),
                internal_status VARCHAR(30) DEFAULT 'new',
                payment_status VARCHAR(30) DEFAULT 'pending',
                outbound_request_id VARCHAR(36),
                notes TEXT,
                ordered_at DATETIME,
                confirmed_at DATETIME,
                shipped_at DATETIME,
                delivered_at DATETIME,
                created_at DATETIME DEFAULT NOW(),
                updated_at DATETIME DEFAULT NOW()
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS ecommerce_order_items (
                id VARCHAR(36) PRIMARY KEY,
                order_id VARCHAR(36) NOT NULL,
                platform_item_id VARCHAR(200),
                product_id VARCHAR(36),
                variant_id VARCHAR(36),
                item_id VARCHAR(36),
                sku VARCHAR(100),
                name VARCHAR(300),
                qty INTEGER NOT NULL,
                unit_price DECIMAL(12,2),
                total_price DECIMAL(12,2),
                created_at DATETIME DEFAULT NOW()
            )""")

            # ---------- Stock Sync ----------
            cur.execute("""
            CREATE TABLE IF NOT EXISTS stock_sync_rules (
                id VARCHAR(36) PRIMARY KEY,
                shop_id VARCHAR(36) NOT NULL,
                item_id VARCHAR(36),
                sync_direction VARCHAR(20) DEFAULT 'push',
                buffer_qty DECIMAL(12,4) DEFAULT 0,
                buffer_percent DECIMAL(5,2) DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT NOW()
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS stock_sync_logs (
                id VARCHAR(36) PRIMARY KEY,
                shop_id VARCHAR(36),
                item_id VARCHAR(36),
                platform VARCHAR(50),
                direction VARCHAR(20),
                qty_pushed DECIMAL(12,4),
                qty_available DECIMAL(12,4),
                status VARCHAR(30) DEFAULT 'success',
                error_message TEXT,
                created_at DATETIME DEFAULT NOW()
            )""")

            # ---------- Fulfillment & Printing ----------
            cur.execute("""
            CREATE TABLE IF NOT EXISTS print_queue (
                id VARCHAR(36) PRIMARY KEY,
                job_type VARCHAR(50) NOT NULL,
                status VARCHAR(30) DEFAULT 'pending',
                order_ids JSON,
                template VARCHAR(100),
                company_label VARCHAR(200),
                file_url VARCHAR(500),
                printed_by VARCHAR(36),
                printed_at DATETIME,
                error_message TEXT,
                created_at DATETIME DEFAULT NOW()
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS pick_lists (
                id VARCHAR(36) PRIMARY KEY,
                batch_code VARCHAR(100),
                status VARCHAR(30) DEFAULT 'open',
                order_count INTEGER DEFAULT 0,
                line_count INTEGER DEFAULT 0,
                assigned_to VARCHAR(36),
                company_label VARCHAR(200),
                completed_at DATETIME,
                created_at DATETIME DEFAULT NOW()
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS pick_list_lines (
                id VARCHAR(36) PRIMARY KEY,
                pick_list_id VARCHAR(36) NOT NULL,
                order_id VARCHAR(36),
                item_id VARCHAR(36),
                sku VARCHAR(100),
                item_name VARCHAR(300),
                qty_to_pick INTEGER,
                qty_picked INTEGER DEFAULT 0,
                location VARCHAR(200),
                status VARCHAR(30) DEFAULT 'pending',
                created_at DATETIME DEFAULT NOW()
            )""")

            # ---------- Returns & After-Sales ----------
            cur.execute("""
            CREATE TABLE IF NOT EXISTS ecommerce_returns (
                id VARCHAR(36) PRIMARY KEY,
                order_id VARCHAR(36) NOT NULL,
                platform VARCHAR(50),
                platform_return_id VARCHAR(200),
                return_type VARCHAR(30),
                reason VARCHAR(300),
                customer_notes TEXT,
                status VARCHAR(30) DEFAULT 'requested',
                refund_amount DECIMAL(12,2),
                return_tracking VARCHAR(200),
                return_carrier VARCHAR(100),
                resolution_notes TEXT,
                resolved_by VARCHAR(36),
                resolved_at DATETIME,
                created_at DATETIME DEFAULT NOW(),
                updated_at DATETIME DEFAULT NOW()
            )""")

            # ---------- Affiliate Manager ----------
            cur.execute("""
            CREATE TABLE IF NOT EXISTS affiliates (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(300) NOT NULL,
                platform VARCHAR(50),
                platform_affiliate_id VARCHAR(200),
                contact_info TEXT,
                commission_rate DECIMAL(5,2) DEFAULT 0,
                tier VARCHAR(50) DEFAULT 'standard',
                total_gmv DECIMAL(14,2) DEFAULT 0,
                total_orders INTEGER DEFAULT 0,
                company_label VARCHAR(200),
                is_active INTEGER DEFAULT 1,
                notes TEXT,
                created_at DATETIME DEFAULT NOW(),
                updated_at DATETIME DEFAULT NOW()
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS affiliate_commissions (
                id VARCHAR(36) PRIMARY KEY,
                affiliate_id VARCHAR(36) NOT NULL,
                order_id VARCHAR(36),
                order_total DECIMAL(12,2),
                commission_rate DECIMAL(5,2),
                commission_amount DECIMAL(12,2),
                status VARCHAR(30) DEFAULT 'pending',
                paid_at DATETIME,
                created_at DATETIME DEFAULT NOW()
            )""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS affiliate_samples (
                id VARCHAR(36) PRIMARY KEY,
                affiliate_id VARCHAR(36) NOT NULL,
                product_id VARCHAR(36),
                item_id VARCHAR(36),
                qty INTEGER DEFAULT 1,
                status VARCHAR(30) DEFAULT 'requested',
                tracking_number VARCHAR(200),
                approved_by VARCHAR(36),
                shipped_at DATETIME,
                created_at DATETIME DEFAULT NOW()
            )""")

            # ---------- Indexes ----------
            index_stmts = [
                "CREATE INDEX idx_products_sku ON products(sku)",
                "CREATE INDEX idx_products_company ON products(company_label)",
                "CREATE INDEX idx_products_item ON products(item_id)",
                "CREATE INDEX idx_pl_product ON platform_listings(product_id)",
                "CREATE INDEX idx_pl_platform ON platform_listings(platform)",
                "CREATE INDEX idx_pl_shop ON platform_listings(shop_id)",
                "CREATE INDEX idx_pv_product ON product_variants(product_id)",
                "CREATE INDEX idx_eco_platform ON ecommerce_orders(platform)",
                "CREATE INDEX idx_eco_status ON ecommerce_orders(internal_status)",
                "CREATE INDEX idx_eco_company ON ecommerce_orders(company_label)",
                "CREATE INDEX idx_eco_shop ON ecommerce_orders(shop_id)",
                "CREATE INDEX idx_eoi_order ON ecommerce_order_items(order_id)",
                "CREATE INDEX idx_ssr_shop ON stock_sync_rules(shop_id)",
                "CREATE INDEX idx_ssl_shop ON stock_sync_logs(shop_id)",
                "CREATE INDEX idx_pq_status ON print_queue(status)",
                "CREATE INDEX idx_pkl_picklist ON pick_list_lines(pick_list_id)",
                "CREATE INDEX idx_er_order ON ecommerce_returns(order_id)",
                "CREATE INDEX idx_aff_company ON affiliates(company_label)",
                "CREATE INDEX idx_ac_affiliate ON affiliate_commissions(affiliate_id)",
                "CREATE INDEX idx_as_affiliate ON affiliate_samples(affiliate_id)",
            ]
            for stmt in index_stmts:
                try:
                    cur.execute(stmt)
                except Exception:
                    pass  # index already exists

        db.commit()


# ========================================================================
#  PRODUCTS & LISTINGS
# ========================================================================

@router.get("/api/products")
async def list_products(request: Request, company_label: str = None, category: str = None, is_active: int = 1):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager', 'warehouse_lead')
    with get_db() as db:
        query = "SELECT * FROM products WHERE is_active=%s"
        args = [is_active]
        if company_label:
            query += " AND company_label=%s"; args.append(company_label)
        if category:
            query += " AND category=%s"; args.append(category)
        query += " ORDER BY created_at DESC"
        return {'products': rows_to_list(fetchall(db, query, args))}


@router.get("/api/products/{product_id}")
async def get_product(request: Request, product_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager', 'warehouse_lead')
    with get_db() as db:
        product = dict_from_row(fetchone(db, "SELECT * FROM products WHERE id=%s", (product_id,)))
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        product['variants'] = rows_to_list(fetchall(db,
            "SELECT * FROM product_variants WHERE product_id=%s ORDER BY created_at", (product_id,)))
        product['listings'] = rows_to_list(fetchall(db,
            "SELECT * FROM platform_listings WHERE product_id=%s ORDER BY platform", (product_id,)))
    return product


@router.post("/api/products")
async def create_product(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    body = await request.json()
    pid = str(uuid.uuid4())
    with get_db() as db:
        execute(db,
            "INSERT INTO products (id, sku, name, description, category, brand, base_price, cost_price, "
            "weight_grams, images, tags, item_id, company_label, is_active) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (pid, body['sku'], body['name'], body.get('description'), body.get('category'),
             body.get('brand'), body.get('base_price'), body.get('cost_price'),
             body.get('weight_grams'),
             json.dumps(body.get('images', [])),
             json.dumps(body.get('tags', [])),
             body.get('item_id'), body.get('company_label'),
             body.get('is_active', 1)))
        # Create variants if provided
        for v in body.get('variants', []):
            vid = str(uuid.uuid4())
            execute(db,
                "INSERT INTO product_variants (id, product_id, variant_name, sku_suffix, price_override, attributes, item_id, is_active) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (vid, pid, v.get('variant_name'), v.get('sku_suffix'), v.get('price_override'),
                 json.dumps(v.get('attributes', {})), v.get('item_id'), v.get('is_active', 1)))
        write_audit(db, user['uid'], 'create', 'product', pid, None, body)
        db.commit()
    return {'id': pid, 'success': True}


@router.put("/api/products/{product_id}")
async def update_product(request: Request, product_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    body = await request.json()
    with get_db() as db:
        before = dict_from_row(fetchone(db, "SELECT * FROM products WHERE id=%s", (product_id,)))
        if not before:
            raise HTTPException(status_code=404, detail="Product not found")
        allowed = ('sku', 'name', 'description', 'category', 'brand', 'base_price', 'cost_price',
                   'weight_grams', 'item_id', 'company_label', 'is_active')
        fields = {k: v for k, v in body.items() if k in allowed}
        # Handle JSON fields separately
        if 'images' in body:
            fields['images'] = json.dumps(body['images'])
        if 'tags' in body:
            fields['tags'] = json.dumps(body['tags'])
        if fields:
            set_clause = ", ".join(f"{k}=%s" for k in fields)
            set_clause += ", updated_at=NOW()"
            execute(db, f"UPDATE products SET {set_clause} WHERE id=%s", list(fields.values()) + [product_id])
        write_audit(db, user['uid'], 'update', 'product', product_id, before, body)
        db.commit()
    return {'success': True}


@router.post("/api/products/{product_id}/publish")
async def publish_product(request: Request, product_id: str):
    """Publish a product to selected platforms — creates platform_listings."""
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    body = await request.json()
    platforms = body.get('platforms', [])
    if not platforms:
        raise HTTPException(status_code=400, detail="platforms array required")
    with get_db() as db:
        product = dict_from_row(fetchone(db, "SELECT * FROM products WHERE id=%s", (product_id,)))
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        listing_ids = []
        for p in platforms:
            lid = str(uuid.uuid4())
            execute(db,
                "INSERT INTO platform_listings (id, product_id, platform, shop_id, title, description, price, "
                "compare_at_price, platform_category, platform_attributes, status, sync_status) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (lid, product_id, p.get('platform'), p.get('shop_id'),
                 p.get('title', product.get('name')),
                 p.get('description', product.get('description')),
                 p.get('price', product.get('base_price')),
                 p.get('compare_at_price'),
                 p.get('platform_category'),
                 json.dumps(p.get('platform_attributes', {})),
                 'draft', 'pending'))
            listing_ids.append(lid)
        write_audit(db, user['uid'], 'publish', 'product', product_id, None,
                    {'platforms': [p.get('platform') for p in platforms], 'listing_ids': listing_ids})
        db.commit()
    return {'success': True, 'listing_ids': listing_ids}


@router.get("/api/platform_listings")
async def list_platform_listings(request: Request, platform: str = None, status: str = None, shop_id: str = None):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager', 'warehouse_lead')
    with get_db() as db:
        query = """SELECT pl.*, p.sku as product_sku, p.name as product_name, p.company_label
                   FROM platform_listings pl
                   LEFT JOIN products p ON pl.product_id = p.id WHERE 1=1"""
        args = []
        if platform:
            query += " AND pl.platform=%s"; args.append(platform)
        if status:
            query += " AND pl.status=%s"; args.append(status)
        if shop_id:
            query += " AND pl.shop_id=%s"; args.append(shop_id)
        query += " ORDER BY pl.created_at DESC"
        return {'listings': rows_to_list(fetchall(db, query, args))}


@router.put("/api/platform_listings/{listing_id}")
async def update_platform_listing(request: Request, listing_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    body = await request.json()
    with get_db() as db:
        before = dict_from_row(fetchone(db, "SELECT * FROM platform_listings WHERE id=%s", (listing_id,)))
        if not before:
            raise HTTPException(status_code=404, detail="Listing not found")
        allowed = ('title', 'description', 'price', 'compare_at_price', 'platform_category',
                   'platform_sku', 'listing_url', 'status', 'is_active')
        fields = {k: v for k, v in body.items() if k in allowed}
        if 'platform_attributes' in body:
            fields['platform_attributes'] = json.dumps(body['platform_attributes'])
        if fields:
            set_clause = ", ".join(f"{k}=%s" for k in fields)
            set_clause += ", updated_at=NOW()"
            execute(db, f"UPDATE platform_listings SET {set_clause} WHERE id=%s",
                    list(fields.values()) + [listing_id])
        write_audit(db, user['uid'], 'update', 'platform_listing', listing_id, before, body)
        db.commit()
    return {'success': True}


@router.post("/api/platform_listings/{listing_id}/sync")
async def sync_platform_listing(request: Request, listing_id: str):
    """Mark a listing for sync to the platform."""
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    with get_db() as db:
        before = dict_from_row(fetchone(db, "SELECT * FROM platform_listings WHERE id=%s", (listing_id,)))
        if not before:
            raise HTTPException(status_code=404, detail="Listing not found")
        execute(db,
            "UPDATE platform_listings SET sync_status='pending', updated_at=NOW() WHERE id=%s",
            (listing_id,))
        write_audit(db, user['uid'], 'sync', 'platform_listing', listing_id, before,
                    {'sync_status': 'pending'})
        db.commit()
    return {'success': True}


@router.post("/api/products/bulk_publish")
async def bulk_publish_products(request: Request):
    """Bulk publish multiple products to selected platforms."""
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    body = await request.json()
    product_ids = body.get('product_ids', [])
    platforms = body.get('platforms', [])
    if not product_ids or not platforms:
        raise HTTPException(status_code=400, detail="product_ids and platforms arrays required")
    with get_db() as db:
        all_listing_ids = []
        for product_id in product_ids:
            product = dict_from_row(fetchone(db, "SELECT * FROM products WHERE id=%s", (product_id,)))
            if not product:
                continue
            for p in platforms:
                lid = str(uuid.uuid4())
                execute(db,
                    "INSERT INTO platform_listings (id, product_id, platform, shop_id, title, description, price, "
                    "compare_at_price, platform_category, platform_attributes, status, sync_status) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (lid, product_id, p.get('platform'), p.get('shop_id'),
                     p.get('title', product.get('name')),
                     p.get('description', product.get('description')),
                     p.get('price', product.get('base_price')),
                     p.get('compare_at_price'),
                     p.get('platform_category'),
                     json.dumps(p.get('platform_attributes', {})),
                     'draft', 'pending'))
                all_listing_ids.append(lid)
        write_audit(db, user['uid'], 'bulk_publish', 'product', None, None,
                    {'product_ids': product_ids, 'listing_ids': all_listing_ids})
        db.commit()
    return {'success': True, 'listing_ids': all_listing_ids}


# ========================================================================
#  ECOMMERCE ORDERS
# ========================================================================

@router.get("/api/ecommerce_orders")
async def list_ecommerce_orders(request: Request, platform: str = None, internal_status: str = None,
                                 company_label: str = None, date_from: str = None, date_to: str = None):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager', 'warehouse_lead', 'warehouse_operator')
    with get_db() as db:
        query = "SELECT * FROM ecommerce_orders WHERE 1=1"
        args = []
        if platform:
            query += " AND platform=%s"; args.append(platform)
        if internal_status:
            query += " AND internal_status=%s"; args.append(internal_status)
        if company_label:
            query += " AND company_label=%s"; args.append(company_label)
        if date_from:
            query += " AND ordered_at >= %s"; args.append(date_from)
        if date_to:
            query += " AND ordered_at <= %s"; args.append(date_to)
        query += " ORDER BY created_at DESC"
        return {'orders': rows_to_list(fetchall(db, query, args))}


@router.get("/api/ecommerce_orders/{order_id}")
async def get_ecommerce_order(request: Request, order_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager', 'warehouse_lead', 'warehouse_operator')
    with get_db() as db:
        order = dict_from_row(fetchone(db, "SELECT * FROM ecommerce_orders WHERE id=%s", (order_id,)))
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        order['items'] = rows_to_list(fetchall(db,
            "SELECT * FROM ecommerce_order_items WHERE order_id=%s ORDER BY created_at", (order_id,)))
    return order


@router.post("/api/ecommerce_orders/sync")
async def sync_ecommerce_orders(request: Request):
    """Trigger order sync from all connected platforms (placeholder)."""
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    with get_db() as db:
        write_audit(db, user['uid'], 'sync_orders', 'ecommerce_order', None, None,
                    {'triggered_at': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')})
        db.commit()
    return {'success': True, 'message': 'Order sync triggered'}


@router.post("/api/ecommerce_orders/bulk_confirm")
async def bulk_confirm_orders(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager', 'warehouse_lead')
    body = await request.json()
    order_ids = body.get('order_ids', [])
    if not order_ids:
        raise HTTPException(status_code=400, detail="order_ids array required")
    with get_db() as db:
        now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        for oid in order_ids:
            execute(db,
                "UPDATE ecommerce_orders SET internal_status='confirmed', confirmed_at=%s, updated_at=NOW() "
                "WHERE id=%s AND internal_status='new'",
                (now_str, oid))
        write_audit(db, user['uid'], 'bulk_confirm', 'ecommerce_order', None, None,
                    {'order_ids': order_ids})
        db.commit()
    return {'success': True}


@router.post("/api/ecommerce_orders/bulk_ship")
async def bulk_ship_orders(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager', 'warehouse_lead')
    body = await request.json()
    shipments = body.get('shipments', [])
    if not shipments:
        raise HTTPException(status_code=400, detail="shipments array required (each with order_id, tracking_number, carrier)")
    with get_db() as db:
        now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        for s in shipments:
            execute(db,
                "UPDATE ecommerce_orders SET internal_status='shipped', tracking_number=%s, carrier=%s, "
                "shipped_at=%s, updated_at=NOW() WHERE id=%s AND internal_status IN ('confirmed','picking','packed')",
                (s.get('tracking_number'), s.get('carrier'), now_str, s['order_id']))
        write_audit(db, user['uid'], 'bulk_ship', 'ecommerce_order', None, None,
                    {'shipments': shipments})
        db.commit()
    return {'success': True}


@router.post("/api/ecommerce_orders/bulk_cancel")
async def bulk_cancel_orders(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    body = await request.json()
    order_ids = body.get('order_ids', [])
    reason = body.get('reason', '')
    if not order_ids:
        raise HTTPException(status_code=400, detail="order_ids array required")
    with get_db() as db:
        for oid in order_ids:
            before = dict_from_row(fetchone(db, "SELECT * FROM ecommerce_orders WHERE id=%s", (oid,)))
            execute(db,
                "UPDATE ecommerce_orders SET internal_status='cancelled', notes=CONCAT(COALESCE(notes,''), %s), updated_at=NOW() WHERE id=%s",
                (f"\n[Cancelled] {reason}", oid))
        write_audit(db, user['uid'], 'bulk_cancel', 'ecommerce_order', None, None,
                    {'order_ids': order_ids, 'reason': reason})
        db.commit()
    return {'success': True}


@router.post("/api/ecommerce_orders/{order_id}/confirm")
async def confirm_order(request: Request, order_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager', 'warehouse_lead')
    with get_db() as db:
        before = dict_from_row(fetchone(db, "SELECT * FROM ecommerce_orders WHERE id=%s", (order_id,)))
        if not before:
            raise HTTPException(status_code=404, detail="Order not found")
        now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        execute(db,
            "UPDATE ecommerce_orders SET internal_status='confirmed', confirmed_at=%s, updated_at=NOW() WHERE id=%s",
            (now_str, order_id))
        write_audit(db, user['uid'], 'confirm', 'ecommerce_order', order_id, before,
                    {'internal_status': 'confirmed'})
        db.commit()
    return {'success': True}


@router.post("/api/ecommerce_orders/{order_id}/ship")
async def ship_order(request: Request, order_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager', 'warehouse_lead')
    body = await request.json()
    with get_db() as db:
        before = dict_from_row(fetchone(db, "SELECT * FROM ecommerce_orders WHERE id=%s", (order_id,)))
        if not before:
            raise HTTPException(status_code=404, detail="Order not found")
        now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        execute(db,
            "UPDATE ecommerce_orders SET internal_status='shipped', tracking_number=%s, carrier=%s, "
            "shipped_at=%s, updated_at=NOW() WHERE id=%s",
            (body.get('tracking_number'), body.get('carrier'), now_str, order_id))
        write_audit(db, user['uid'], 'ship', 'ecommerce_order', order_id, before,
                    {'internal_status': 'shipped', 'tracking_number': body.get('tracking_number')})
        db.commit()
    return {'success': True}


@router.post("/api/ecommerce_orders/{order_id}/cancel")
async def cancel_order(request: Request, order_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    body = await request.json()
    with get_db() as db:
        before = dict_from_row(fetchone(db, "SELECT * FROM ecommerce_orders WHERE id=%s", (order_id,)))
        if not before:
            raise HTTPException(status_code=404, detail="Order not found")
        reason = body.get('reason', '')
        execute(db,
            "UPDATE ecommerce_orders SET internal_status='cancelled', notes=CONCAT(COALESCE(notes,''), %s), updated_at=NOW() WHERE id=%s",
            (f"\n[Cancelled] {reason}", order_id))
        write_audit(db, user['uid'], 'cancel', 'ecommerce_order', order_id, before,
                    {'internal_status': 'cancelled', 'reason': reason})
        db.commit()
    return {'success': True}


# ========================================================================
#  STOCK SYNC
# ========================================================================

@router.get("/api/stock_sync/rules")
async def list_stock_sync_rules(request: Request, shop_id: str = None):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    with get_db() as db:
        query = "SELECT * FROM stock_sync_rules WHERE 1=1"
        args = []
        if shop_id:
            query += " AND shop_id=%s"; args.append(shop_id)
        query += " ORDER BY created_at DESC"
        return {'rules': rows_to_list(fetchall(db, query, args))}


@router.post("/api/stock_sync/rules")
async def create_stock_sync_rule(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    body = await request.json()
    rid = str(uuid.uuid4())
    with get_db() as db:
        execute(db,
            "INSERT INTO stock_sync_rules (id, shop_id, item_id, sync_direction, buffer_qty, buffer_percent, is_active) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (rid, body['shop_id'], body.get('item_id'), body.get('sync_direction', 'push'),
             body.get('buffer_qty', 0), body.get('buffer_percent', 0), body.get('is_active', 1)))
        write_audit(db, user['uid'], 'create', 'stock_sync_rule', rid, None, body)
        db.commit()
    return {'id': rid, 'success': True}


@router.put("/api/stock_sync/rules/{rule_id}")
async def update_stock_sync_rule(request: Request, rule_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    body = await request.json()
    with get_db() as db:
        before = dict_from_row(fetchone(db, "SELECT * FROM stock_sync_rules WHERE id=%s", (rule_id,)))
        if not before:
            raise HTTPException(status_code=404, detail="Sync rule not found")
        allowed = ('shop_id', 'item_id', 'sync_direction', 'buffer_qty', 'buffer_percent', 'is_active')
        fields = {k: v for k, v in body.items() if k in allowed}
        if fields:
            set_clause = ", ".join(f"{k}=%s" for k in fields)
            execute(db, f"UPDATE stock_sync_rules SET {set_clause} WHERE id=%s",
                    list(fields.values()) + [rule_id])
        write_audit(db, user['uid'], 'update', 'stock_sync_rule', rule_id, before, body)
        db.commit()
    return {'success': True}


@router.post("/api/stock_sync/push")
async def trigger_stock_push(request: Request):
    """Trigger manual stock push to all platforms (placeholder)."""
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    with get_db() as db:
        write_audit(db, user['uid'], 'stock_push', 'stock_sync', None, None,
                    {'triggered_at': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')})
        db.commit()
    return {'success': True, 'message': 'Stock push triggered'}


@router.get("/api/stock_sync/logs")
async def list_stock_sync_logs(request: Request, shop_id: str = None, status: str = None):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    with get_db() as db:
        query = "SELECT * FROM stock_sync_logs WHERE 1=1"
        args = []
        if shop_id:
            query += " AND shop_id=%s"; args.append(shop_id)
        if status:
            query += " AND status=%s"; args.append(status)
        query += " ORDER BY created_at DESC LIMIT 200"
        return {'logs': rows_to_list(fetchall(db, query, args))}


# ========================================================================
#  FULFILLMENT & PRINTING
# ========================================================================

@router.get("/api/print_queue")
async def list_print_queue(request: Request, status: str = None, company_label: str = None):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager', 'warehouse_lead', 'warehouse_operator')
    with get_db() as db:
        query = "SELECT * FROM print_queue WHERE 1=1"
        args = []
        if status:
            query += " AND status=%s"; args.append(status)
        if company_label:
            query += " AND company_label=%s"; args.append(company_label)
        query += " ORDER BY created_at DESC"
        return {'jobs': rows_to_list(fetchall(db, query, args))}


@router.post("/api/print_queue")
async def create_print_job(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager', 'warehouse_lead', 'warehouse_operator')
    body = await request.json()
    jid = str(uuid.uuid4())
    with get_db() as db:
        execute(db,
            "INSERT INTO print_queue (id, job_type, status, order_ids, template, company_label) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (jid, body['job_type'], 'pending',
             json.dumps(body.get('order_ids', [])),
             body.get('template'), body.get('company_label')))
        write_audit(db, user['uid'], 'create', 'print_queue', jid, None, body)
        db.commit()
    return {'id': jid, 'success': True}


@router.post("/api/print_queue/{job_id}/mark_printed")
async def mark_printed(request: Request, job_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager', 'warehouse_lead', 'warehouse_operator')
    with get_db() as db:
        before = dict_from_row(fetchone(db, "SELECT * FROM print_queue WHERE id=%s", (job_id,)))
        if not before:
            raise HTTPException(status_code=404, detail="Print job not found")
        execute(db,
            "UPDATE print_queue SET status='printed', printed_by=%s, printed_at=NOW() WHERE id=%s",
            (user['uid'], job_id))
        write_audit(db, user['uid'], 'mark_printed', 'print_queue', job_id, before,
                    {'status': 'printed'})
        db.commit()
    return {'success': True}


@router.get("/api/pick_lists")
async def list_pick_lists(request: Request, status: str = None, company_label: str = None):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager', 'warehouse_lead', 'warehouse_operator')
    with get_db() as db:
        query = "SELECT * FROM pick_lists WHERE 1=1"
        args = []
        if status:
            query += " AND status=%s"; args.append(status)
        if company_label:
            query += " AND company_label=%s"; args.append(company_label)
        query += " ORDER BY created_at DESC"
        return {'pick_lists': rows_to_list(fetchall(db, query, args))}


@router.post("/api/pick_lists/generate")
async def generate_pick_list(request: Request):
    """Generate a pick list from confirmed ecommerce orders."""
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager', 'warehouse_lead')
    body = await request.json()
    order_ids = body.get('order_ids', [])
    if not order_ids:
        raise HTTPException(status_code=400, detail="order_ids array required")
    with get_db() as db:
        pl_id = str(uuid.uuid4())
        batch_code = f"PL-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{pl_id[:8]}"
        # Gather order items
        placeholders = ",".join(["%s"] * len(order_ids))
        items = fetchall(db,
            f"SELECT eoi.*, eo.company_label FROM ecommerce_order_items eoi "
            f"JOIN ecommerce_orders eo ON eoi.order_id = eo.id "
            f"WHERE eoi.order_id IN ({placeholders}) ORDER BY eoi.sku",
            order_ids)
        items = rows_to_list(items) if items else []
        company_label = body.get('company_label')
        line_count = 0
        for item in items:
            line_id = str(uuid.uuid4())
            execute(db,
                "INSERT INTO pick_list_lines (id, pick_list_id, order_id, item_id, sku, item_name, "
                "qty_to_pick, qty_picked, location, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (line_id, pl_id, item.get('order_id'), item.get('item_id'),
                 item.get('sku'), item.get('name'), item.get('qty', 0), 0, None, 'pending'))
            line_count += 1
        execute(db,
            "INSERT INTO pick_lists (id, batch_code, status, order_count, line_count, assigned_to, company_label) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (pl_id, batch_code, 'open', len(order_ids), line_count,
             body.get('assigned_to'), company_label))
        write_audit(db, user['uid'], 'generate', 'pick_list', pl_id, None,
                    {'order_ids': order_ids, 'line_count': line_count})
        db.commit()
    return {'id': pl_id, 'batch_code': batch_code, 'success': True}


@router.put("/api/pick_lists/{pick_list_id}/pick_line")
async def pick_line(request: Request, pick_list_id: str):
    """Update picked quantity for a line in a pick list."""
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager', 'warehouse_lead', 'warehouse_operator')
    body = await request.json()
    line_id = body.get('line_id')
    qty_picked = body.get('qty_picked')
    if not line_id or qty_picked is None:
        raise HTTPException(status_code=400, detail="line_id and qty_picked required")
    with get_db() as db:
        before = dict_from_row(fetchone(db,
            "SELECT * FROM pick_list_lines WHERE id=%s AND pick_list_id=%s", (line_id, pick_list_id)))
        if not before:
            raise HTTPException(status_code=404, detail="Pick list line not found")
        new_status = 'picked' if qty_picked >= before.get('qty_to_pick', 0) else ('short' if qty_picked > 0 else 'pending')
        execute(db,
            "UPDATE pick_list_lines SET qty_picked=%s, status=%s WHERE id=%s",
            (qty_picked, new_status, line_id))
        # Update pick list status to in_progress if still open
        execute(db,
            "UPDATE pick_lists SET status='in_progress' WHERE id=%s AND status='open'",
            (pick_list_id,))
        write_audit(db, user['uid'], 'pick_line', 'pick_list_line', line_id, before,
                    {'qty_picked': qty_picked, 'status': new_status})
        db.commit()
    return {'success': True}


@router.post("/api/pick_lists/{pick_list_id}/complete")
async def complete_pick_list(request: Request, pick_list_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager', 'warehouse_lead')
    with get_db() as db:
        before = dict_from_row(fetchone(db, "SELECT * FROM pick_lists WHERE id=%s", (pick_list_id,)))
        if not before:
            raise HTTPException(status_code=404, detail="Pick list not found")
        execute(db,
            "UPDATE pick_lists SET status='completed', completed_at=NOW() WHERE id=%s",
            (pick_list_id,))
        write_audit(db, user['uid'], 'complete', 'pick_list', pick_list_id, before,
                    {'status': 'completed'})
        db.commit()
    return {'success': True}


# ========================================================================
#  ECOMMERCE RETURNS
# ========================================================================

@router.get("/api/ecommerce_returns")
async def list_ecommerce_returns(request: Request, status: str = None, platform: str = None):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager', 'warehouse_lead')
    with get_db() as db:
        query = """SELECT er.*, eo.platform_order_id, eo.customer_name, eo.company_label
                   FROM ecommerce_returns er
                   LEFT JOIN ecommerce_orders eo ON er.order_id = eo.id WHERE 1=1"""
        args = []
        if status:
            query += " AND er.status=%s"; args.append(status)
        if platform:
            query += " AND er.platform=%s"; args.append(platform)
        query += " ORDER BY er.created_at DESC"
        return {'returns': rows_to_list(fetchall(db, query, args))}


@router.post("/api/ecommerce_returns")
async def create_ecommerce_return(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager', 'warehouse_lead')
    body = await request.json()
    rid = str(uuid.uuid4())
    with get_db() as db:
        order = dict_from_row(fetchone(db, "SELECT * FROM ecommerce_orders WHERE id=%s", (body['order_id'],)))
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        execute(db,
            "INSERT INTO ecommerce_returns (id, order_id, platform, platform_return_id, return_type, reason, "
            "customer_notes, status, refund_amount, return_tracking, return_carrier) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (rid, body['order_id'], body.get('platform', order.get('platform')),
             body.get('platform_return_id'), body.get('return_type', 'return_refund'),
             body.get('reason'), body.get('customer_notes'), 'requested',
             body.get('refund_amount'), body.get('return_tracking'), body.get('return_carrier')))
        write_audit(db, user['uid'], 'create', 'ecommerce_return', rid, None, body)
        db.commit()
    return {'id': rid, 'success': True}


@router.post("/api/ecommerce_returns/{return_id}/approve")
async def approve_return(request: Request, return_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    with get_db() as db:
        before = dict_from_row(fetchone(db, "SELECT * FROM ecommerce_returns WHERE id=%s", (return_id,)))
        if not before:
            raise HTTPException(status_code=404, detail="Return not found")
        execute(db,
            "UPDATE ecommerce_returns SET status='approved', updated_at=NOW() WHERE id=%s",
            (return_id,))
        write_audit(db, user['uid'], 'approve', 'ecommerce_return', return_id, before,
                    {'status': 'approved'})
        db.commit()
    return {'success': True}


@router.post("/api/ecommerce_returns/{return_id}/receive")
async def receive_return(request: Request, return_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager', 'warehouse_lead')
    with get_db() as db:
        before = dict_from_row(fetchone(db, "SELECT * FROM ecommerce_returns WHERE id=%s", (return_id,)))
        if not before:
            raise HTTPException(status_code=404, detail="Return not found")
        execute(db,
            "UPDATE ecommerce_returns SET status='received', updated_at=NOW() WHERE id=%s",
            (return_id,))
        write_audit(db, user['uid'], 'receive', 'ecommerce_return', return_id, before,
                    {'status': 'received'})
        db.commit()
    return {'success': True}


@router.post("/api/ecommerce_returns/{return_id}/refund")
async def refund_return(request: Request, return_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    body = await request.json()
    with get_db() as db:
        before = dict_from_row(fetchone(db, "SELECT * FROM ecommerce_returns WHERE id=%s", (return_id,)))
        if not before:
            raise HTTPException(status_code=404, detail="Return not found")
        refund_amount = body.get('refund_amount', before.get('refund_amount'))
        execute(db,
            "UPDATE ecommerce_returns SET status='refunded', refund_amount=%s, resolved_by=%s, "
            "resolved_at=NOW(), resolution_notes=%s, updated_at=NOW() WHERE id=%s",
            (refund_amount, user['uid'], body.get('resolution_notes'), return_id))
        write_audit(db, user['uid'], 'refund', 'ecommerce_return', return_id, before,
                    {'status': 'refunded', 'refund_amount': refund_amount})
        db.commit()
    return {'success': True}


@router.post("/api/ecommerce_returns/{return_id}/reject")
async def reject_return(request: Request, return_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    body = await request.json()
    with get_db() as db:
        before = dict_from_row(fetchone(db, "SELECT * FROM ecommerce_returns WHERE id=%s", (return_id,)))
        if not before:
            raise HTTPException(status_code=404, detail="Return not found")
        execute(db,
            "UPDATE ecommerce_returns SET status='rejected', resolved_by=%s, resolved_at=NOW(), "
            "resolution_notes=%s, updated_at=NOW() WHERE id=%s",
            (user['uid'], body.get('resolution_notes', ''), return_id))
        write_audit(db, user['uid'], 'reject', 'ecommerce_return', return_id, before,
                    {'status': 'rejected'})
        db.commit()
    return {'success': True}


# ========================================================================
#  AFFILIATES
# ========================================================================

@router.get("/api/affiliates")
async def list_affiliates(request: Request, company_label: str = None, platform: str = None, is_active: int = 1):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    with get_db() as db:
        query = "SELECT * FROM affiliates WHERE is_active=%s"
        args = [is_active]
        if company_label:
            query += " AND company_label=%s"; args.append(company_label)
        if platform:
            query += " AND platform=%s"; args.append(platform)
        query += " ORDER BY created_at DESC"
        return {'affiliates': rows_to_list(fetchall(db, query, args))}


@router.post("/api/affiliates")
async def create_affiliate(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    body = await request.json()
    aid = str(uuid.uuid4())
    with get_db() as db:
        execute(db,
            "INSERT INTO affiliates (id, name, platform, platform_affiliate_id, contact_info, "
            "commission_rate, tier, company_label, is_active, notes) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (aid, body['name'], body.get('platform'), body.get('platform_affiliate_id'),
             body.get('contact_info'), body.get('commission_rate', 0),
             body.get('tier', 'standard'), body.get('company_label'),
             body.get('is_active', 1), body.get('notes')))
        write_audit(db, user['uid'], 'create', 'affiliate', aid, None, body)
        db.commit()
    return {'id': aid, 'success': True}


@router.put("/api/affiliates/{affiliate_id}")
async def update_affiliate(request: Request, affiliate_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    body = await request.json()
    with get_db() as db:
        before = dict_from_row(fetchone(db, "SELECT * FROM affiliates WHERE id=%s", (affiliate_id,)))
        if not before:
            raise HTTPException(status_code=404, detail="Affiliate not found")
        allowed = ('name', 'platform', 'platform_affiliate_id', 'contact_info', 'commission_rate',
                   'tier', 'total_gmv', 'total_orders', 'company_label', 'is_active', 'notes')
        fields = {k: v for k, v in body.items() if k in allowed}
        if fields:
            set_clause = ", ".join(f"{k}=%s" for k in fields)
            set_clause += ", updated_at=NOW()"
            execute(db, f"UPDATE affiliates SET {set_clause} WHERE id=%s",
                    list(fields.values()) + [affiliate_id])
        write_audit(db, user['uid'], 'update', 'affiliate', affiliate_id, before, body)
        db.commit()
    return {'success': True}


@router.get("/api/affiliates/{affiliate_id}/commissions")
async def get_affiliate_commissions(request: Request, affiliate_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager', 'accounting_operator')
    with get_db() as db:
        affiliate = dict_from_row(fetchone(db, "SELECT * FROM affiliates WHERE id=%s", (affiliate_id,)))
        if not affiliate:
            raise HTTPException(status_code=404, detail="Affiliate not found")
        commissions = rows_to_list(fetchall(db,
            "SELECT * FROM affiliate_commissions WHERE affiliate_id=%s ORDER BY created_at DESC",
            (affiliate_id,)))
    return {'affiliate': affiliate, 'commissions': commissions}


@router.get("/api/affiliates/{affiliate_id}/samples")
async def get_affiliate_samples(request: Request, affiliate_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    with get_db() as db:
        affiliate = dict_from_row(fetchone(db, "SELECT * FROM affiliates WHERE id=%s", (affiliate_id,)))
        if not affiliate:
            raise HTTPException(status_code=404, detail="Affiliate not found")
        samples = rows_to_list(fetchall(db,
            "SELECT * FROM affiliate_samples WHERE affiliate_id=%s ORDER BY created_at DESC",
            (affiliate_id,)))
    return {'affiliate': affiliate, 'samples': samples}


@router.post("/api/affiliate_samples")
async def create_affiliate_sample(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    body = await request.json()
    sid = str(uuid.uuid4())
    with get_db() as db:
        affiliate = dict_from_row(fetchone(db, "SELECT * FROM affiliates WHERE id=%s", (body['affiliate_id'],)))
        if not affiliate:
            raise HTTPException(status_code=404, detail="Affiliate not found")
        execute(db,
            "INSERT INTO affiliate_samples (id, affiliate_id, product_id, item_id, qty, status) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (sid, body['affiliate_id'], body.get('product_id'), body.get('item_id'),
             body.get('qty', 1), 'requested'))
        write_audit(db, user['uid'], 'create', 'affiliate_sample', sid, None, body)
        db.commit()
    return {'id': sid, 'success': True}


@router.post("/api/affiliate_samples/{sample_id}/approve")
async def approve_affiliate_sample(request: Request, sample_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager')
    with get_db() as db:
        before = dict_from_row(fetchone(db, "SELECT * FROM affiliate_samples WHERE id=%s", (sample_id,)))
        if not before:
            raise HTTPException(status_code=404, detail="Sample not found")
        execute(db,
            "UPDATE affiliate_samples SET status='approved', approved_by=%s WHERE id=%s",
            (user['uid'], sample_id))
        write_audit(db, user['uid'], 'approve', 'affiliate_sample', sample_id, before,
                    {'status': 'approved'})
        db.commit()
    return {'success': True}


@router.post("/api/affiliate_samples/{sample_id}/ship")
async def ship_affiliate_sample(request: Request, sample_id: str):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager', 'warehouse_lead')
    body = await request.json()
    with get_db() as db:
        before = dict_from_row(fetchone(db, "SELECT * FROM affiliate_samples WHERE id=%s", (sample_id,)))
        if not before:
            raise HTTPException(status_code=404, detail="Sample not found")
        execute(db,
            "UPDATE affiliate_samples SET status='shipped', tracking_number=%s, shipped_at=NOW() WHERE id=%s",
            (body.get('tracking_number'), sample_id))
        write_audit(db, user['uid'], 'ship', 'affiliate_sample', sample_id, before,
                    {'status': 'shipped', 'tracking_number': body.get('tracking_number')})
        db.commit()
    return {'success': True}


@router.get("/api/affiliate_commissions")
async def list_affiliate_commissions(request: Request, affiliate_id: str = None, status: str = None):
    user = require_auth(request)
    require_role(user, 'system_admin', 'inventory_admin', 'manager', 'accounting_operator')
    with get_db() as db:
        query = "SELECT ac.*, a.name as affiliate_name FROM affiliate_commissions ac LEFT JOIN affiliates a ON ac.affiliate_id = a.id WHERE 1=1"
        args = []
        if affiliate_id:
            query += " AND ac.affiliate_id=%s"; args.append(affiliate_id)
        if status:
            query += " AND ac.status=%s"; args.append(status)
        query += " ORDER BY ac.created_at DESC"
        return {'commissions': rows_to_list(fetchall(db, query, args))}


@router.post("/api/affiliate_commissions/bulk_pay")
async def bulk_pay_commissions(request: Request):
    user = require_auth(request)
    require_role(user, 'system_admin', 'manager', 'accounting_operator')
    body = await request.json()
    commission_ids = body.get('commission_ids', [])
    if not commission_ids:
        raise HTTPException(status_code=400, detail="commission_ids array required")
    with get_db() as db:
        for cid in commission_ids:
            execute(db,
                "UPDATE affiliate_commissions SET status='paid', paid_at=NOW() WHERE id=%s AND status IN ('pending','confirmed')",
                (cid,))
        write_audit(db, user['uid'], 'bulk_pay', 'affiliate_commission', None, None,
                    {'commission_ids': commission_ids})
        db.commit()
    return {'success': True}
