import aiosqlite
import json
import logging
from pathlib import Path
from config import DATABASE_PATH

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
        self.conn = None

    async def init(self):
        self.conn = await aiosqlite.connect(DATABASE_PATH)
        self.conn.row_factory = aiosqlite.Row
        await self._create_tables()
        await self._seed_products()

    async def close(self):
        if self.conn:
            await self.conn.close()

    async def _create_tables(self):
        await self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                full_name   TEXT,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS categories (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                slug        TEXT UNIQUE NOT NULL,
                name        TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS products (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL,
                name        TEXT NOT NULL,
                description TEXT,
                photo_ids   TEXT,
                FOREIGN KEY (category_id) REFERENCES categories(id)
            );

            CREATE TABLE IF NOT EXISTS product_variants (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id  INTEGER NOT NULL,
                seeds_count INTEGER NOT NULL,
                price       INTEGER NOT NULL,
                in_stock    INTEGER DEFAULT 1,
                FOREIGN KEY (product_id) REFERENCES products(id)
            );

            CREATE TABLE IF NOT EXISTS cart_items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                variant_id  INTEGER NOT NULL,
                quantity    INTEGER DEFAULT 1,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (variant_id) REFERENCES product_variants(id),
                UNIQUE(user_id, variant_id)
            );

            CREATE TABLE IF NOT EXISTS orders (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                user_name       TEXT,
                user_phone      TEXT,
                user_city       TEXT,
                delivery_method TEXT,
                delivery_address TEXT,
                comment         TEXT,
                total           INTEGER NOT NULL,
                status          TEXT DEFAULT 'new',
                promo_code      TEXT,
                discount        INTEGER DEFAULT 0,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id    INTEGER NOT NULL,
                variant_id  INTEGER NOT NULL,
                product_name TEXT,
                seeds_count INTEGER,
                price       INTEGER,
                quantity    INTEGER,
                FOREIGN KEY (order_id) REFERENCES orders(id)
            );

            CREATE TABLE IF NOT EXISTS settings (
                key         TEXT PRIMARY KEY,
                value       TEXT
            );

            CREATE TABLE IF NOT EXISTS admin_sessions (
                user_id     INTEGER PRIMARY KEY,
                expires_at  TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
            CREATE INDEX IF NOT EXISTS idx_cart_user ON cart_items(user_id);
        """)
        await self.conn.commit()

    async def _seed_products(self):
        """Заполнить каталог, если пусто."""
        cur = await self.conn.execute("SELECT COUNT(*) FROM products")
        count = (await cur.fetchone())[0]
        if count > 0:
            return

        FEMENIZED = [
            ("Bob Marley", "Классический сорт с ярким тропическим характером."),
            ("Jamaican Star", "Звёздный сорт с насыщенным ароматом."),
            ("Kingstone", "Королевский сорт для истинных ценителей."),
            ("Reggae Spirit", "Дух регги в каждом семечке."),
            ("Sweet Poison", "Сладкий и завораживающий сорт."),
        ]
        AUTO_FEMENIZED = [
            ("Auto Bob Marley", "Автоцветущая версия классики."),
            ("Auto Jamaican Star", "Автоцвет с звёздным характером."),
            ("Auto Kingstone", "Авто-версия королевского сорта."),
            ("Auto Reggae Spirit", "Автоцвет с духом регги."),
            ("Auto Sweet Poison", "Авто-версия сладкого сорта."),
        ]
        PRICES = [(5, 1200), (10, 2000), (20, 3800)]

        await self.conn.execute(
            "INSERT OR IGNORE INTO categories (slug, name) VALUES (?, ?), (?, ?)",
            ("femenized", "Femenized", "auto_femenized", "Auto Femenized")
        )

        cat_fem = (await (await self.conn.execute(
            "SELECT id FROM categories WHERE slug = 'femenized'"
        )).fetchone())[0]
        cat_auto = (await (await self.conn.execute(
            "SELECT id FROM categories WHERE slug = 'auto_femenized'"
        )).fetchone())[0]

        for name, desc in FEMENIZED:
            cur = await self.conn.execute(
                "INSERT INTO products (category_id, name, description) VALUES (?, ?, ?)",
                (cat_fem, name, desc),
            )
            pid = cur.lastrowid
            for seeds, price in PRICES:
                await self.conn.execute(
                    "INSERT INTO product_variants (product_id, seeds_count, price) VALUES (?, ?, ?)",
                    (pid, seeds, price),
                )

        for name, desc in AUTO_FEMENIZED:
            cur = await self.conn.execute(
                "INSERT INTO products (category_id, name, description) VALUES (?, ?, ?)",
                (cat_auto, name, desc),
            )
            pid = cur.lastrowid
            for seeds, price in PRICES:
                await self.conn.execute(
                    "INSERT INTO product_variants (product_id, seeds_count, price) VALUES (?, ?, ?)",
                    (pid, seeds, price),
                )

        await self.conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?), (?, ?), (?, ?)",
            ("payment_bank", "Сбербанк", "payment_account", "Пополните в админ-панели", "manager_link", ""),
        )
        await self.conn.commit()
        logger.info("Каталог товаров заполнен")

    # ─── Users ─────────────────────────────────────────────────────────────────

    async def add_user(self, user_id: int, username: str | None, full_name: str):
        await self.conn.execute(
            """INSERT INTO users (user_id, username, full_name)
               VALUES (?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET username=?, full_name=?""",
            (user_id, username, full_name, username, full_name),
        )
        await self.conn.commit()

    # ─── Catalog ──────────────────────────────────────────────────────────────

    async def get_categories(self) -> list[dict]:
        cur = await self.conn.execute(
            "SELECT id, slug, name FROM categories ORDER BY id"
        )
        return [dict(r) for r in await cur.fetchall()]

    async def get_products_by_category(self, category_id: int) -> list[dict]:
        cur = await self.conn.execute(
            "SELECT id, name, description, photo_ids FROM products WHERE category_id = ? ORDER BY name",
            (category_id,)
        )
        return [dict(r) for r in await cur.fetchall()]

    async def get_product(self, product_id: int) -> dict | None:
        cur = await self.conn.execute(
            "SELECT p.*, c.name as category_name FROM products p "
            "JOIN categories c ON p.category_id = c.id WHERE p.id = ?",
            (product_id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None

    async def get_variants(self, product_id: int) -> list[dict]:
        cur = await self.conn.execute(
            "SELECT id, seeds_count, price, in_stock FROM product_variants WHERE product_id = ? ORDER BY seeds_count",
            (product_id,)
        )
        return [dict(r) for r in await cur.fetchall()]

    async def get_variant(self, variant_id: int) -> dict | None:
        cur = await self.conn.execute(
            """SELECT v.*, p.name as product_name, p.description, p.photo_ids, c.name as category_name
               FROM product_variants v
               JOIN products p ON v.product_id = p.id
               JOIN categories c ON p.category_id = c.id
               WHERE v.id = ?""",
            (variant_id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None

    # ─── Cart ─────────────────────────────────────────────────────────────────

    async def get_cart(self, user_id: int) -> list[dict]:
        cur = await self.conn.execute("""
            SELECT c.id as cart_id, c.variant_id, c.quantity,
                   v.seeds_count, v.price, v.in_stock, p.name as product_name
            FROM cart_items c
            JOIN product_variants v ON c.variant_id = v.id
            JOIN products p ON v.product_id = p.id
            WHERE c.user_id = ?
        """, (user_id,))
        return [dict(r) for r in await cur.fetchall()]

    async def add_to_cart(self, user_id: int, variant_id: int, quantity: int = 1) -> bool:
        cur = await self.conn.execute(
            """INSERT INTO cart_items (user_id, variant_id, quantity)
               VALUES (?, ?, ?) ON CONFLICT(user_id, variant_id) DO UPDATE SET
               quantity = quantity + excluded.quantity""",
            (user_id, variant_id, quantity),
        )
        await self.conn.commit()
        return True

    async def update_cart_quantity(self, user_id: int, cart_item_id: int, delta: int) -> bool:
        cur = await self.conn.execute(
            "SELECT id, quantity FROM cart_items WHERE id = ? AND user_id = ?",
            (cart_item_id, user_id)
        )
        row = await cur.fetchone()
        if not row:
            return False
        new_qty = max(1, row["quantity"] + delta)
        await self.conn.execute("UPDATE cart_items SET quantity = ? WHERE id = ?", (new_qty, cart_item_id))
        await self.conn.commit()
        return True

    async def remove_from_cart(self, user_id: int, cart_item_id: int):
        await self.conn.execute("DELETE FROM cart_items WHERE id = ? AND user_id = ?", (cart_item_id, user_id))
        await self.conn.commit()

    async def clear_cart(self, user_id: int):
        await self.conn.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
        await self.conn.commit()

    # ─── Orders ───────────────────────────────────────────────────────────────

    async def create_order(self, user_id: int, user_name: str, user_phone: str,
                           user_city: str, delivery_method: str, delivery_address: str,
                           comment: str, total: int, promo_code: str = None,
                           discount: int = 0) -> int:
        cur = await self.conn.execute("""
            INSERT INTO orders (user_id, user_name, user_phone, user_city, delivery_method,
                               delivery_address, comment, total, promo_code, discount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, user_name, user_phone, user_city, delivery_method,
              delivery_address, comment or "", total, promo_code, discount))
        order_id = cur.lastrowid

        cart = await self.get_cart(user_id)
        for item in cart:
            await self.conn.execute("""
                INSERT INTO order_items (order_id, variant_id, product_name, seeds_count, price, quantity)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (order_id, item["variant_id"], item["product_name"], item["seeds_count"],
                  item["price"], item["quantity"]))
        await self.clear_cart(user_id)
        await self.conn.commit()
        return order_id

    async def get_order(self, order_id: int) -> dict | None:
        cur = await self.conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = await cur.fetchone()
        if not row:
            return None
        order = dict(row)
        cur = await self.conn.execute(
            "SELECT * FROM order_items WHERE order_id = ?", (order_id,)
        )
        order["items"] = [dict(r) for r in await cur.fetchall()]
        return order

    async def get_user_orders(self, user_id: int, limit: int = 5) -> list[dict]:
        cur = await self.conn.execute(
            "SELECT id, total, status, created_at FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        )
        return [dict(r) for r in await cur.fetchall()]

    async def get_all_orders(self, limit: int = 100) -> list[dict]:
        cur = await self.conn.execute(
            "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in await cur.fetchall()]

    async def update_order_status(self, order_id: int, status: str):
        await self.conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        await self.conn.commit()

    # ─── Settings ─────────────────────────────────────────────────────────────

    async def get_setting(self, key: str) -> str | None:
        cur = await self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row["value"] if row else None

    async def set_setting(self, key: str, value: str):
        await self.conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )
        await self.conn.commit()

    # ─── Products (admin) ─────────────────────────────────────────────────────

    async def update_product(self, product_id: int, name: str = None, description: str = None, photo_ids: str = None):
        updates = []
        params = []
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if photo_ids is not None:
            updates.append("photo_ids = ?")
            params.append(photo_ids)
        if updates:
            params.append(product_id)
            await self.conn.execute(
                f"UPDATE products SET {', '.join(updates)} WHERE id = ?", params
            )
            await self.conn.commit()

    async def update_variant(self, variant_id: int, price: int = None, in_stock: int = None):
        updates = []
        params = []
        if price is not None:
            updates.append("price = ?")
            params.append(price)
        if in_stock is not None:
            updates.append("in_stock = ?")
            params.append(in_stock)
        if updates:
            params.append(variant_id)
            await self.conn.execute(
                f"UPDATE product_variants SET {', '.join(updates)} WHERE id = ?", params
            )
            await self.conn.commit()

    async def get_all_products_with_variants(self) -> list[dict]:
        cur = await self.conn.execute("""
            SELECT p.id, p.name, p.description, c.name as category_name
            FROM products p JOIN categories c ON p.category_id = c.id
            ORDER BY c.id, p.name
        """)
        products = [dict(r) for r in await cur.fetchall()]
        for p in products:
            cur = await self.conn.execute(
                "SELECT id, seeds_count, price, in_stock FROM product_variants WHERE product_id = ?",
                (p["id"],)
            )
            p["variants"] = [dict(r) for r in await cur.fetchall()]
        return products

    # ─── Admin session ────────────────────────────────────────────────────────

    async def set_admin_session(self, user_id: int):
        import datetime
        expires = (datetime.datetime.utcnow() + datetime.timedelta(hours=24)).isoformat()
        await self.conn.execute(
            "INSERT OR REPLACE INTO admin_sessions (user_id, expires_at) VALUES (?, ?)",
            (user_id, expires)
        )
        await self.conn.commit()

    async def is_admin_session(self, user_id: int) -> bool:
        import datetime
        cur = await self.conn.execute(
            "SELECT expires_at FROM admin_sessions WHERE user_id = ?", (user_id,)
        )
        row = await cur.fetchone()
        if not row:
            return False
        try:
            return datetime.datetime.fromisoformat(row["expires_at"]) > datetime.datetime.utcnow()
        except:
            return False
