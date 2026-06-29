import sqlite3
from datetime import datetime

DB_PATH = "club.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            full_name   TEXT,
            phone       TEXT,
            registered_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS bookings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            zone        TEXT NOT NULL,
            seat        INTEGER NOT NULL,
            date        TEXT NOT NULL,
            time_from   TEXT NOT NULL,
            time_to     TEXT NOT NULL,
            comment     TEXT,
            status      TEXT DEFAULT 'pending',
            created_at  TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
        """)


# ---------- Users ----------

def upsert_user(user_id: int, username: str, full_name: str):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO users (user_id, username, full_name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username  = excluded.username,
                full_name = excluded.full_name
        """, (user_id, username, full_name))


def get_user(user_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()


def save_phone(user_id: int, phone: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET phone = ? WHERE user_id = ?", (phone, user_id)
        )


# ---------- Bookings ----------

def create_booking(user_id, zone, seat, date, time_from, time_to, comment=""):
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO bookings (user_id, zone, seat, date, time_from, time_to, comment)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, zone, seat, date, time_from, time_to, comment))
        return cur.lastrowid


def get_user_bookings(user_id: int):
    with get_conn() as conn:
        return conn.execute("""
            SELECT * FROM bookings WHERE user_id = ?
            ORDER BY date DESC, time_from DESC LIMIT 10
        """, (user_id,)).fetchall()


def get_booked_seats(zone: str, date: str, time_from: str, time_to: str):
    """Вернуть занятые места на заданный слот."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT seat FROM bookings
            WHERE zone = ? AND date = ? AND status != 'cancelled'
              AND NOT (time_to <= ? OR time_from >= ?)
        """, (zone, date, time_from, time_to)).fetchall()
    return {r["seat"] for r in rows}


def cancel_booking(booking_id: int, user_id: int):
    with get_conn() as conn:
        conn.execute("""
            UPDATE bookings SET status = 'cancelled'
            WHERE id = ? AND user_id = ?
        """, (booking_id, user_id))


def confirm_booking(booking_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE bookings SET status = 'confirmed' WHERE id = ?", (booking_id,)
        )


def all_pending():
    with get_conn() as conn:
        return conn.execute("""
            SELECT b.*, u.full_name, u.username, u.phone
            FROM bookings b JOIN users u ON b.user_id = u.user_id
            WHERE b.status = 'pending'
            ORDER BY b.date, b.time_from
        """).fetchall()


def all_bookings_today():
    today = datetime.now().strftime("%Y-%m-%d")
    with get_conn() as conn:
        return conn.execute("""
            SELECT b.*, u.full_name, u.username, u.phone
            FROM bookings b JOIN users u ON b.user_id = u.user_id
            WHERE b.date = ? AND b.status != 'cancelled'
            ORDER BY b.time_from
        """, (today,)).fetchall()


def all_users_count():
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def all_bookings_count():
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM bookings WHERE status != 'cancelled'").fetchone()[0]
