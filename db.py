import os
from dataclasses import dataclass
from typing import Optional, Sequence

import aiosqlite


DB_PATH = os.getenv("PR5_TASK1_DB_PATH", "shop_aiogram.db")


@dataclass(frozen=True)
class Shoe:
    id: int
    name: str
    category: str
    price_uah: float
    sizes: str  # "39,40,41"


@dataclass(frozen=True)
class OrderRow:
    id: int
    created_at: str
    status: str
    shoe_name: str
    size: int
    phone: str
    price_uah: float


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS shoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price_uah REAL NOT NULL,
                sizes TEXT NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                shoe_id INTEGER NOT NULL,
                size INTEGER NOT NULL,
                phone TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'new',
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (shoe_id) REFERENCES shoes(id)
            )
            """
        )
        await db.commit()

    await seed_catalog_if_empty()


async def seed_catalog_if_empty() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM shoes")
        row = await cur.fetchone()
        await cur.close()
        if row and row[0] and row[0] > 0:
            return

        demo = [
            ("Кросівки Basic", "унісекс", 1999.0, "38,39,40,41,42,43"),
            ("Кеди Classic", "унісекс", 1499.0, "36,37,38,39,40,41"),
            ("Туфлі Office", "чоловіче", 2299.0, "40,41,42,43,44"),
            ("Черевики Winter", "жіноче", 2599.0, "37,38,39,40"),
        ]
        await db.executemany(
            "INSERT INTO shoes (name, category, price_uah, sizes) VALUES (?, ?, ?, ?)",
            demo,
        )
        await db.commit()


async def get_or_create_user(tg_id: int, username: Optional[str], first_name: Optional[str]) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id FROM users WHERE tg_id = ?", (tg_id,))
        row = await cur.fetchone()
        await cur.close()
        if row:
            return int(row[0])

        cur2 = await db.execute(
            "INSERT INTO users (tg_id, username, first_name) VALUES (?, ?, ?)",
            (tg_id, username, first_name),
        )
        await db.commit()
        return int(cur2.lastrowid)


async def list_shoes() -> Sequence[Shoe]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id, name, category, price_uah, sizes FROM shoes ORDER BY id ASC")
        rows = await cur.fetchall()
        await cur.close()
    return [Shoe(int(r[0]), str(r[1]), str(r[2]), float(r[3]), str(r[4])) for r in rows]


async def get_shoe(shoe_id: int) -> Optional[Shoe]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, name, category, price_uah, sizes FROM shoes WHERE id = ?",
            (shoe_id,),
        )
        row = await cur.fetchone()
        await cur.close()
    if not row:
        return None
    return Shoe(int(row[0]), str(row[1]), str(row[2]), float(row[3]), str(row[4]))


async def create_order(user_id: int, shoe_id: int, size: int, phone: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO orders (user_id, shoe_id, size, phone) VALUES (?, ?, ?, ?)",
            (user_id, shoe_id, size, phone),
        )
        await db.commit()
        return int(cur.lastrowid)


async def list_orders_for_user(tg_id: int) -> Sequence[OrderRow]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id FROM users WHERE tg_id = ?", (tg_id,))
        user = await cur.fetchone()
        await cur.close()
        if not user:
            return []
        user_id = int(user[0])

        cur2 = await db.execute(
            """
            SELECT
                o.id,
                o.created_at,
                o.status,
                s.name,
                o.size,
                o.phone,
                s.price_uah
            FROM orders o
            JOIN shoes s ON s.id = o.shoe_id
            WHERE o.user_id = ?
            ORDER BY o.created_at DESC
            """,
            (user_id,),
        )
        rows = await cur2.fetchall()
        await cur2.close()
    return [
        OrderRow(
            id=int(r[0]),
            created_at=str(r[1]),
            status=str(r[2]),
            shoe_name=str(r[3]),
            size=int(r[4]),
            phone=str(r[5]),
            price_uah=float(r[6]),
        )
        for r in rows
    ]


async def count_orders_for_user(tg_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id FROM users WHERE tg_id = ?", (tg_id,))
        user = await cur.fetchone()
        await cur.close()
        if not user:
            return 0
        user_id = int(user[0])
        cur2 = await db.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", (user_id,))
        row = await cur2.fetchone()
        await cur2.close()
    return int(row[0]) if row else 0

