"""
database.py — FitJejak
Menguruskan semua operasi database (PostgreSQL)
"""
import os
import pg8000.dbapi as psycopg2
from urllib.parse import urlparse
from datetime import date, datetime


def get_connection():
    """Buka sambungan ke PostgreSQL database."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise Exception("DATABASE_URL tidak dijumpai dalam environment variables!")
    parsed = urlparse(database_url)
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        database=parsed.path[1:],
        user=parsed.username,
        password=parsed.password,
        ssl_context=True
    )
    return conn


def init_db():
    """Cipta semua table jika belum wujud. Panggil sekali masa bot start."""
    conn = get_connection()
    c = conn.cursor()

    # ── Table: pengguna ───────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id     BIGINT PRIMARY KEY,
            username        TEXT,
            first_name      TEXT,
            weight_kg       REAL,
            height_cm       REAL,
            age             INTEGER,
            gender          TEXT,
            activity_level  TEXT,
            goal            TEXT,
            target_calories REAL,
            target_protein  REAL,
            scans_remaining INTEGER DEFAULT 20,
            setup_complete  INTEGER DEFAULT 0,
            created_at      TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
            updated_at      TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
        )
    """)

    # ── Table: log makanan ────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS food_logs (
            id          SERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL,
            log_date    TEXT NOT NULL,
            food_name   TEXT NOT NULL,
            calories    REAL DEFAULT 0,
            protein_g   REAL DEFAULT 0,
            carbs_g     REAL DEFAULT 0,
            fat_g       REAL DEFAULT 0,
            health_score INTEGER DEFAULT 0,
            advice      TEXT,
            image_file_id TEXT,
            logged_at   TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
        )
    """)

    # ── Table: rekod berat ────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS weight_logs (
            id          SERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL,
            log_date    TEXT NOT NULL,
            weight_kg   REAL NOT NULL,
            logged_at   TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
            UNIQUE(telegram_id, log_date)
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Database siap.")


def _fetchone_dict(cursor):
    """Convert fetchone result ke dict."""
    row = cursor.fetchone()
    if row is None:
        return None
    cols = [desc[0] for desc in cursor.description]
    return dict(zip(cols, row))


def _fetchall_dict(cursor):
    """Convert fetchall result ke list of dict."""
    cols = [desc[0] for desc in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


# ── FUNGSI PENGGUNA ───────────────────────────────────────────────

def get_user(telegram_id: int):
    """Dapatkan maklumat pengguna. Return None jika tiada."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
    user = _fetchone_dict(c)
    conn.close()
    return user


def create_user(telegram_id: int, username: str, first_name: str):
    """Daftarkan pengguna baru dengan 20 scan percuma."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO users (telegram_id, username, first_name)
        VALUES (%s, %s, %s)
        ON CONFLICT (telegram_id) DO NOTHING
    """, (telegram_id, username, first_name))
    conn.commit()
    conn.close()


def update_user_profile(telegram_id: int, **kwargs):
    """Kemaskini profil pengguna."""
    if not kwargs:
        return
    kwargs["updated_at"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    fields = ", ".join(f"{k} = %s" for k in kwargs)
    values = list(kwargs.values()) + [telegram_id]
    conn = get_connection()
    c = conn.cursor()
    c.execute(f"UPDATE users SET {fields} WHERE telegram_id = %s", values)
    conn.commit()
    conn.close()


def deduct_scan(telegram_id: int) -> bool:
    """Tolak 1 scan. Return True jika berjaya, False jika habis."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT scans_remaining FROM users WHERE telegram_id = %s", (telegram_id,))
    row = c.fetchone()

    if not row or row[0] <= 0:
        conn.close()
        return False

    c.execute(
        "UPDATE users SET scans_remaining = scans_remaining - 1 WHERE telegram_id = %s",
        (telegram_id,)
    )
    conn.commit()
    conn.close()
    return True


def add_credits(telegram_id: int, scans: int):
    """Tambah kredit scan untuk pengguna."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE users SET scans_remaining = scans_remaining + %s WHERE telegram_id = %s",
        (scans, telegram_id)
    )
    conn.commit()
    conn.close()


def get_all_users():
    """Dapatkan senarai semua pengguna (untuk admin)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT telegram_id, first_name, username, scans_remaining, setup_complete, created_at
        FROM users
        ORDER BY created_at DESC
    """)
    users = _fetchall_dict(c)
    conn.close()
    return users


# ── FUNGSI LOG MAKANAN ────────────────────────────────────────────

def log_food(telegram_id: int, food_name: str, calories: float,
             protein_g: float, carbs_g: float, fat_g: float,
             health_score: int, advice: str, image_file_id: str = None):
    """Simpan rekod makanan hari ini."""
    today = date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO food_logs
            (telegram_id, log_date, food_name, calories, protein_g, carbs_g, fat_g,
             health_score, advice, image_file_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (telegram_id, today, food_name, calories, protein_g, carbs_g, fat_g,
          health_score, advice, image_file_id))
    conn.commit()
    conn.close()


def get_today_summary(telegram_id: int) -> dict:
    """Kira jumlah nutrisi untuk hari ini."""
    today = date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT
            COALESCE(SUM(calories), 0)  AS total_calories,
            COALESCE(SUM(protein_g), 0) AS total_protein,
            COALESCE(SUM(carbs_g), 0)   AS total_carbs,
            COALESCE(SUM(fat_g), 0)     AS total_fat,
            COUNT(*) AS meal_count
        FROM food_logs
        WHERE telegram_id = %s AND log_date = %s
    """, (telegram_id, today))
    row = _fetchone_dict(c)
    conn.close()
    return row


def get_week_summary(telegram_id: int) -> dict:
    """Dapatkan purata nutrisi untuk 7 hari lepas."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT
            ROUND(AVG(daily_cal)::numeric, 0)     AS avg_calories,
            ROUND(AVG(daily_protein)::numeric, 0) AS avg_protein,
            COUNT(DISTINCT log_date)               AS days_logged
        FROM (
            SELECT
                log_date,
                SUM(calories)  AS daily_cal,
                SUM(protein_g) AS daily_protein
            FROM food_logs
            WHERE telegram_id = %s
              AND log_date >= to_char(NOW() - INTERVAL '7 days', 'YYYY-MM-DD')
            GROUP BY log_date
        ) daily
    """, (telegram_id,))
    row = _fetchone_dict(c)
    conn.close()
    return row


# ── FUNGSI REKOD BERAT ────────────────────────────────────────────

def log_weight(telegram_id: int, weight_kg: float):
    """Simpan rekod berat badan hari ini."""
    today = date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO weight_logs (telegram_id, log_date, weight_kg)
        VALUES (%s, %s, %s)
        ON CONFLICT (telegram_id, log_date) DO UPDATE SET weight_kg = EXCLUDED.weight_kg
    """, (telegram_id, today, weight_kg))
    c.execute(
        "UPDATE users SET weight_kg = %s, updated_at = to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS') WHERE telegram_id = %s",
        (weight_kg, telegram_id)
    )
    conn.commit()
    conn.close()


def get_previous_weight(telegram_id: int):
    """Dapatkan rekod berat sebelum hari ini."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT weight_kg FROM weight_logs
        WHERE telegram_id = %s
          AND log_date < to_char(NOW(), 'YYYY-MM-DD')
        ORDER BY log_date DESC
        LIMIT 1
    """, (telegram_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None
