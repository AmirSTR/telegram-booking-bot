import aiosqlite
from datetime import datetime

DB_PATH = "booking.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS masters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                name TEXT NOT NULL,
                username TEXT,
                work_start TEXT DEFAULT '09:00',
                work_end TEXT DEFAULT '18:00',
                slot_duration INTEGER DEFAULT 60,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                duration INTEGER NOT NULL,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (admin_id) REFERENCES masters(telegram_id)
            );

            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                telegram_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                phone TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(admin_id, telegram_id),
                FOREIGN KEY (admin_id) REFERENCES masters(telegram_id)
            );

            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                client_telegram_id INTEGER NOT NULL,
                service_id INTEGER NOT NULL,
                booking_date TEXT NOT NULL,
                booking_time TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                reminder_24h INTEGER DEFAULT 0,
                reminder_2h INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (admin_id) REFERENCES masters(telegram_id),
                FOREIGN KEY (service_id) REFERENCES services(id)
            );

            CREATE TABLE IF NOT EXISTS waitlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                client_telegram_id INTEGER NOT NULL,
                service_id INTEGER NOT NULL,
                preferred_date TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (admin_id) REFERENCES masters(telegram_id)
            );
        """)
        await db.commit()


# ─── MASTERS ──────────────────────────────────────────────────────────────────

async def add_master(telegram_id: int, name: str, username: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO masters (telegram_id, name, username) VALUES (?, ?, ?)",
            (telegram_id, name, username)
        )
        await db.commit()


async def get_master(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM masters WHERE telegram_id = ?", (telegram_id,)
        ) as cur:
            return await cur.fetchone()


async def get_all_masters():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM masters ORDER BY name") as cur:
            return await cur.fetchall()


async def remove_master(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM masters WHERE telegram_id = ?", (telegram_id,))
        await db.commit()


async def update_master_schedule(telegram_id: int, work_start: str, work_end: str, slot_duration: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE masters SET work_start=?, work_end=?, slot_duration=? WHERE telegram_id=?",
            (work_start, work_end, slot_duration, telegram_id)
        )
        await db.commit()


# ─── SERVICES ─────────────────────────────────────────────────────────────────

async def add_service(admin_id: int, name: str, price: float, duration: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO services (admin_id, name, price, duration) VALUES (?, ?, ?, ?)",
            (admin_id, name, price, duration)
        )
        await db.commit()
        return cur.lastrowid


async def get_services(admin_id: int, active_only: bool = True):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM services WHERE admin_id = ?"
        params = [admin_id]
        if active_only:
            query += " AND is_active = 1"
        query += " ORDER BY name"
        async with db.execute(query, params) as cur:
            return await cur.fetchall()


async def get_service(service_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM services WHERE id = ?", (service_id,)) as cur:
            return await cur.fetchone()


async def delete_service(service_id: int, admin_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE services SET is_active = 0 WHERE id = ? AND admin_id = ?",
            (service_id, admin_id)
        )
        await db.commit()


# ─── CLIENTS ──────────────────────────────────────────────────────────────────

async def register_client(admin_id: int, telegram_id: int, name: str, phone: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO clients (admin_id, telegram_id, name, phone) VALUES (?, ?, ?, ?)",
            (admin_id, telegram_id, name, phone)
        )
        await db.commit()


async def get_client(admin_id: int, telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM clients WHERE admin_id = ? AND telegram_id = ?",
            (admin_id, telegram_id)
        ) as cur:
            return await cur.fetchone()


async def get_all_clients(admin_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM clients WHERE admin_id = ? ORDER BY name", (admin_id,)
        ) as cur:
            return await cur.fetchall()


# ─── BOOKINGS ─────────────────────────────────────────────────────────────────

async def create_booking(admin_id: int, client_telegram_id: int, service_id: int,
                         booking_date: str, booking_time: str):
    """
    Fix #7: Check for slot conflicts inside a transaction before inserting,
    to prevent double-booking when two clients race for the same slot.
    Returns the new booking id, or None if the slot was already taken.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # Serialise concurrent writes with an exclusive transaction
        await db.execute("BEGIN EXCLUSIVE")
        try:
            # Get service duration for overlap check
            async with db.execute(
                "SELECT duration FROM services WHERE id = ?", (service_id,)
            ) as cur:
                row = await cur.fetchone()
            if not row:
                await db.execute("ROLLBACK")
                return None
            new_duration = row[0]

            # Fetch all booked slots for that master/date
            async with db.execute(
                """SELECT b.booking_time, s.duration
                   FROM bookings b JOIN services s ON b.service_id = s.id
                   WHERE b.admin_id = ? AND b.booking_date = ? AND b.status != 'cancelled'""",
                (admin_id, booking_date)
            ) as cur:
                existing = await cur.fetchall()

            # Convert to minute ranges and check overlap
            fmt = "%H:%M"
            new_dt = datetime.strptime(booking_time, fmt)
            new_start = new_dt.hour * 60 + new_dt.minute
            new_end = new_start + new_duration

            for bt, bd in existing:
                ex_dt = datetime.strptime(bt, fmt)
                ex_start = ex_dt.hour * 60 + ex_dt.minute
                ex_end = ex_start + bd
                if new_start < ex_end and new_end > ex_start:
                    await db.execute("ROLLBACK")
                    return None  # slot conflict

            cur2 = await db.execute(
                """INSERT INTO bookings
                   (admin_id, client_telegram_id, service_id, booking_date, booking_time)
                   VALUES (?, ?, ?, ?, ?)""",
                (admin_id, client_telegram_id, service_id, booking_date, booking_time)
            )
            await db.commit()
            return cur2.lastrowid
        except Exception:
            await db.execute("ROLLBACK")
            raise


async def get_booked_slots(admin_id: int, date: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT b.booking_time, s.duration
               FROM bookings b JOIN services s ON b.service_id = s.id
               WHERE b.admin_id = ? AND b.booking_date = ? AND b.status != 'cancelled'""",
            (admin_id, date)
        ) as cur:
            return await cur.fetchall()


async def get_client_bookings(admin_id: int, client_telegram_id: int, upcoming_only: bool = True):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        today = datetime.now().strftime("%Y-%m-%d")
        query = """
            SELECT b.*, s.name as service_name, s.price
            FROM bookings b JOIN services s ON b.service_id = s.id
            WHERE b.admin_id = ? AND b.client_telegram_id = ?
        """
        params = [admin_id, client_telegram_id]
        if upcoming_only:
            query += " AND b.booking_date >= ? AND b.status NOT IN ('cancelled', 'completed')"
            params.append(today)
        query += " ORDER BY b.booking_date, b.booking_time"
        async with db.execute(query, params) as cur:
            return await cur.fetchall()


async def get_master_bookings(admin_id: int, date: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT b.*, s.name as service_name, s.price, c.name as client_name, c.phone
            FROM bookings b
            JOIN services s ON b.service_id = s.id
            JOIN clients c ON b.admin_id = c.admin_id AND b.client_telegram_id = c.telegram_id
            WHERE b.admin_id = ?
        """
        params = [admin_id]
        if date:
            query += " AND b.booking_date = ?"
            params.append(date)
        query += " ORDER BY b.booking_date, b.booking_time"
        async with db.execute(query, params) as cur:
            return await cur.fetchall()


async def cancel_booking(booking_id: int, admin_id: int = None, client_telegram_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        query = "UPDATE bookings SET status = 'cancelled' WHERE id = ?"
        params = [booking_id]
        if admin_id:
            query += " AND admin_id = ?"
            params.append(admin_id)
        if client_telegram_id:
            query += " AND client_telegram_id = ?"
            params.append(client_telegram_id)
        await db.execute(query, params)
        await db.commit()


async def confirm_booking(booking_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE bookings SET status = 'confirmed' WHERE id = ?", (booking_id,)
        )
        await db.commit()


async def complete_booking(booking_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE bookings SET status = 'completed' WHERE id = ?", (booking_id,)
        )
        await db.commit()


async def get_booking(booking_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT b.*, s.name as service_name, s.price, s.duration,
                      c.name as client_name, c.phone
               FROM bookings b
               JOIN services s ON b.service_id = s.id
               JOIN clients c ON b.admin_id = c.admin_id AND b.client_telegram_id = c.telegram_id
               WHERE b.id = ?""",
            (booking_id,)
        ) as cur:
            return await cur.fetchone()


async def get_income_stats(admin_id: int, period: str = "month"):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if period == "month":
            date_filter = "strftime('%Y-%m', b.booking_date) = strftime('%Y-%m', 'now')"
        elif period == "week":
            date_filter = "b.booking_date >= date('now', '-7 days')"
        else:
            date_filter = "strftime('%Y', b.booking_date) = strftime('%Y', 'now')"

        async with db.execute(
            f"""SELECT COUNT(*) as total_bookings,
                       SUM(s.price) as total_income,
                       COUNT(DISTINCT b.client_telegram_id) as unique_clients
                FROM bookings b JOIN services s ON b.service_id = s.id
                WHERE b.admin_id = ? AND b.status = 'completed' AND {date_filter}""",
            (admin_id,)
        ) as cur:
            return await cur.fetchone()


# ─── REMINDERS ────────────────────────────────────────────────────────────────

async def get_pending_reminders_24h():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT b.*, s.name as service_name, c.name as client_name
               FROM bookings b
               JOIN services s ON b.service_id = s.id
               JOIN clients c ON b.admin_id = c.admin_id AND b.client_telegram_id = c.telegram_id
               WHERE b.status IN ('pending', 'confirmed')
               AND b.reminder_24h = 0
               AND datetime(b.booking_date || ' ' || b.booking_time)
                   BETWEEN datetime('now', '+23 hours') AND datetime('now', '+25 hours')"""
        ) as cur:
            return await cur.fetchall()


async def get_pending_reminders_2h():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT b.*, s.name as service_name, c.name as client_name
               FROM bookings b
               JOIN services s ON b.service_id = s.id
               JOIN clients c ON b.admin_id = c.admin_id AND b.client_telegram_id = c.telegram_id
               WHERE b.status IN ('pending', 'confirmed')
               AND b.reminder_2h = 0
               AND datetime(b.booking_date || ' ' || b.booking_time)
                   BETWEEN datetime('now', '+1 hours') AND datetime('now', '+3 hours')"""
        ) as cur:
            return await cur.fetchall()


async def mark_reminder_sent(booking_id: int, reminder_type: str):
    async with aiosqlite.connect(DB_PATH) as db:
        field = "reminder_24h" if reminder_type == "24h" else "reminder_2h"
        await db.execute(f"UPDATE bookings SET {field} = 1 WHERE id = ?", (booking_id,))
        await db.commit()


# ─── WAITLIST ─────────────────────────────────────────────────────────────────

async def add_to_waitlist(admin_id: int, client_telegram_id: int, service_id: int, preferred_date: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO waitlist (admin_id, client_telegram_id, service_id, preferred_date) VALUES (?, ?, ?, ?)",
            (admin_id, client_telegram_id, service_id, preferred_date)
        )
        await db.commit()


async def get_waitlist(admin_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT w.*, s.name as service_name, c.name as client_name
               FROM waitlist w
               JOIN services s ON w.service_id = s.id
               JOIN clients c ON w.admin_id = c.admin_id AND w.client_telegram_id = c.telegram_id
               WHERE w.admin_id = ? ORDER BY w.created_at""",
            (admin_id,)
        ) as cur:
            return await cur.fetchall()


async def remove_from_waitlist(waitlist_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM waitlist WHERE id = ?", (waitlist_id,))
        await db.commit()
