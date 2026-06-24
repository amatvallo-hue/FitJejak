"""
database.py — FitJejak
Menguruskan semua operasi database (PostgreSQL)
"""
import os
import random
import string
import pg8000.dbapi as psycopg2
from urllib.parse import urlparse
from datetime import date, datetime, timezone, timedelta

# Malaysia = UTC+8
_MYT = timezone(timedelta(hours=8))

def _today_myt() -> str:
    """Return tarikh hari ini dalam Malaysia timezone (UTC+8)."""
    return datetime.now(_MYT).date().isoformat()

def _yesterday_myt() -> str:
    """Return tarikh semalam dalam Malaysia timezone (UTC+8)."""
    return (datetime.now(_MYT).date() - timedelta(days=1)).isoformat()


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
            current_streak  INTEGER DEFAULT 0,
            longest_streak  INTEGER DEFAULT 0,
            last_log_date   TEXT,
            created_at      TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
            updated_at      TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
        )
    """)

    # Tambah kolum baru kalau belum ada (untuk user sedia ada)
    # Guna IF NOT EXISTS supaya tak ada exception & transaction tak aborted
    for col, definition in [
        ("current_streak",  "INTEGER DEFAULT 0"),
        ("longest_streak",  "INTEGER DEFAULT 0"),
        ("last_log_date",   "TEXT"),
        ("target_carbs",    "REAL"),
        ("target_fat",      "REAL"),
        ("referral_code",    "TEXT"),
        ("referred_by",      "BIGINT"),
        ("referral_count",   "INTEGER DEFAULT 0"),
        ("reminder_enabled",     "INTEGER DEFAULT 1"),   # legacy — kekal untuk backward compat
        ("reminder_pagi",        "INTEGER DEFAULT 1"),
        ("reminder_tengahari",   "INTEGER DEFAULT 1"),
        ("reminder_petang",      "INTEGER DEFAULT 1"),
        ("reminder_malam",       "INTEGER DEFAULT 1"),
        ("topup_count",          "INTEGER DEFAULT 0"),
        ("promo_used",           "TEXT"),
    ]:
        c.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {definition}")

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

    # ── Table: exercise calories harian ──────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS exercise_logs (
            id          SERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL,
            log_date    TEXT NOT NULL,
            calories_burned REAL DEFAULT 0,
            logged_at   TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
            UNIQUE(telegram_id, log_date)
        )
    """)

    # ── Table: promo codes ───────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS promo_codes (
            id          SERIAL PRIMARY KEY,
            code        TEXT UNIQUE NOT NULL,
            bonus_scans INTEGER NOT NULL,
            description TEXT,
            max_uses    INTEGER DEFAULT 0,
            uses_count  INTEGER DEFAULT 0,
            expiry_date TEXT,
            is_active   INTEGER DEFAULT 1,
            created_at  TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
        )
    """)

    # ── Table: body scans ────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS body_scans (
            id              SERIAL PRIMARY KEY,
            telegram_id     BIGINT NOT NULL,
            scan_date       TEXT NOT NULL,
            body_fat_visual REAL,
            muscle_def      TEXT,
            physique_cat    TEXT,
            feedback        TEXT,
            image_file_id   TEXT,
            scanned_at      TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
        )
    """)

    # ── Table: topup requests ────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS topup_requests (
            id          SERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL,
            package_key TEXT NOT NULL,
            amount_rm   REAL NOT NULL,
            scans       INTEGER NOT NULL,
            slip_file_id TEXT,
            bill_code   TEXT,
            status      TEXT DEFAULT 'pending',
            created_at  TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
            approved_at TEXT
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

    # ── Table: affiliate_applications ────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS affiliate_applications (
            id          SERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL,
            bank_name   TEXT NOT NULL,
            bank_acc    TEXT NOT NULL,
            status      TEXT DEFAULT 'pending',
            created_at  TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
        )
    """)

    # ── Table: affiliates ─────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS affiliates (
            telegram_id     BIGINT PRIMARY KEY,
            bank_name       TEXT NOT NULL,
            bank_acc        TEXT NOT NULL,
            commission_rate REAL DEFAULT 0.05,
            status          TEXT DEFAULT 'active',
            joined_at       TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
        )
    """)

    # ── Table: affiliate_earnings ─────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS affiliate_earnings (
            id                  SERIAL PRIMARY KEY,
            affiliate_id        BIGINT NOT NULL,
            from_user_id        BIGINT NOT NULL,
            topup_request_id    INTEGER NOT NULL,
            amount_rm           REAL NOT NULL,
            commission_rm       REAL NOT NULL,
            month               TEXT NOT NULL,
            paid                INTEGER DEFAULT 0,
            paid_at             TEXT,
            created_at          TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
        )
    """)

    # ── Table: user_achievements ──────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_achievements (
            id              SERIAL PRIMARY KEY,
            telegram_id     BIGINT NOT NULL,
            achievement_key TEXT NOT NULL,
            unlocked_at     TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
            bonus_given     INTEGER DEFAULT 0,
            UNIQUE(telegram_id, achievement_key)
        )
    """)

    # ── Migrate: tambah column baru kalau belum ada ──────────────
    migrations = [
        "ALTER TABLE topup_requests ADD COLUMN IF NOT EXISTS bill_code TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS pending_referral TEXT",
    ]
    for sql in migrations:
        try:
            c.execute(sql)
        except Exception:
            pass

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
    kwargs["updated_at"] = datetime.now(_MYT).strftime('%Y-%m-%d %H:%M:%S')
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


def add_credits(telegram_id: int, scans: int, is_topup: bool = False):
    """Tambah kredit scan untuk pengguna."""
    conn = get_connection()
    c = conn.cursor()
    if is_topup:
        c.execute("""
            UPDATE users
            SET scans_remaining = scans_remaining + %s,
                topup_count = topup_count + 1
            WHERE telegram_id = %s
        """, (scans, telegram_id))
    else:
        c.execute(
            "UPDATE users SET scans_remaining = scans_remaining + %s WHERE telegram_id = %s",
            (scans, telegram_id)
        )
    conn.commit()
    conn.close()


def update_streak(telegram_id: int) -> int:
    """
    Kemaskini streak pengguna selepas log makanan.
    Return streak semasa.
    """
    today = _today_myt()
    yesterday = _yesterday_myt()

    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT current_streak, longest_streak, last_log_date FROM users WHERE telegram_id = %s", (telegram_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return 0

    current_streak = row[0] or 0
    longest_streak = row[1] or 0
    last_log_date  = row[2]

    if last_log_date == today:
        # Dah log hari ni — tak perlu update streak
        conn.close()
        return current_streak
    elif last_log_date == yesterday:
        # Log semalam — sambung streak
        current_streak += 1
    else:
        # Ada gap — reset
        current_streak = 1

    longest_streak = max(longest_streak, current_streak)

    c.execute("""
        UPDATE users SET current_streak = %s, longest_streak = %s, last_log_date = %s
        WHERE telegram_id = %s
    """, (current_streak, longest_streak, today, telegram_id))
    conn.commit()
    conn.close()
    return current_streak


def get_users_for_reminder(slot: str = None):
    """
    Dapatkan pengguna yang dah setup profil DAN reminder slot ON.
    slot: 'pagi' | 'tengahari' | 'petang' | 'malam' | None (semua)
    """
    conn = get_connection()
    c = conn.cursor()

    if slot in ("pagi", "tengahari", "petang", "malam"):
        col = f"reminder_{slot}"
        c.execute(f"""
            SELECT telegram_id, first_name, goal, current_streak, scans_remaining
            FROM users
            WHERE setup_complete = 1
              AND (COALESCE({col}, 1) = 1)
        """)
    else:
        # Fallback: guna reminder_enabled lama
        c.execute("""
            SELECT telegram_id, first_name, goal, current_streak, scans_remaining
            FROM users
            WHERE setup_complete = 1
              AND (reminder_enabled IS NULL OR reminder_enabled = 1)
        """)

    users = _fetchall_dict(c)
    conn.close()
    return users


def has_logged_today(telegram_id: int) -> bool:
    """Semak sama ada pengguna dah log makanan hari ini."""
    today = _today_myt()
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT COUNT(*) FROM food_logs
        WHERE telegram_id = %s AND log_date = %s
    """, (telegram_id, today))
    row = c.fetchone()
    conn.close()
    return row[0] > 0


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
    today = _today_myt()
    now_myt = datetime.now(_MYT).strftime('%Y-%m-%d %H:%M:%S')
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO food_logs
            (telegram_id, log_date, food_name, calories, protein_g, carbs_g, fat_g,
             health_score, advice, image_file_id, logged_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (telegram_id, today, food_name, calories, protein_g, carbs_g, fat_g,
          health_score, advice, image_file_id, now_myt))
    log_id = c.lastrowid
    conn.commit()
    conn.close()
    return log_id


def get_today_summary(telegram_id: int) -> dict:
    """Kira jumlah nutrisi untuk hari ini."""
    today = _today_myt()
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


def update_food_log(log_id: int, telegram_id: int, field: str, value) -> bool:
    """Kemaskini satu field dalam log makanan. Return True jika berjaya."""
    allowed = {"food_name", "calories", "protein_g", "carbs_g", "fat_g"}
    if field not in allowed:
        return False
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        f"UPDATE food_logs SET {field} = %s WHERE id = %s AND telegram_id = %s",
        (value, log_id, telegram_id)
    )
    updated = c.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def get_food_log(log_id: int, telegram_id: int) -> dict:
    """Dapatkan satu rekod log makanan."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM food_logs WHERE id = %s AND telegram_id = %s",
        (log_id, telegram_id)
    )
    log = _fetchone_dict(c)
    conn.close()
    return log


def get_today_logs(telegram_id: int) -> list:
    """Dapatkan senarai semua log makanan hari ini."""
    today = _today_myt()
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, food_name, calories, protein_g, carbs_g, fat_g, logged_at
        FROM food_logs
        WHERE telegram_id = %s AND log_date = %s
        ORDER BY logged_at ASC
    """, (telegram_id, today))
    logs = _fetchall_dict(c)
    conn.close()
    return logs


def delete_food_log(log_id: int, telegram_id: int) -> bool:
    """Padam satu log makanan. Return True jika berjaya."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        DELETE FROM food_logs
        WHERE id = %s AND telegram_id = %s
    """, (log_id, telegram_id))
    deleted = c.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


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
              AND log_date >= %s
            GROUP BY log_date
        ) daily
    """, (telegram_id, (datetime.now(_MYT).date() - timedelta(days=7)).isoformat()))
    row = _fetchone_dict(c)
    conn.close()
    return row


# ── FUNGSI REKOD BERAT ────────────────────────────────────────────

def log_weight(telegram_id: int, weight_kg: float):
    """Simpan rekod berat badan hari ini."""
    today = _today_myt()
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO weight_logs (telegram_id, log_date, weight_kg)
        VALUES (%s, %s, %s)
        ON CONFLICT (telegram_id, log_date) DO UPDATE SET weight_kg = EXCLUDED.weight_kg
    """, (telegram_id, today, weight_kg))
    now_myt = datetime.now(_MYT).strftime('%Y-%m-%d %H:%M:%S')
    c.execute(
        "UPDATE users SET weight_kg = %s, updated_at = %s WHERE telegram_id = %s",
        (weight_kg, now_myt, telegram_id)
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
          AND log_date < %s
        ORDER BY log_date DESC
        LIMIT 1
    """, (telegram_id, _today_myt()))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def get_weight_history(telegram_id: int, limit: int = 7) -> list:
    """Dapatkan history berat terkini."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT log_date, weight_kg
        FROM weight_logs
        WHERE telegram_id = %s
        ORDER BY log_date DESC
        LIMIT %s
    """, (telegram_id, limit))
    rows = _fetchall_dict(c)
    conn.close()
    return list(reversed(rows))  # oldest first untuk display


# ── FUNGSI REFERRAL ───────────────────────────────────────────────

# ── FUNGSI PROMO ─────────────────────────────────────────────────

def create_promo_code(code: str, bonus_scans: int, description: str = "",
                      max_uses: int = 0, expiry_date: str = None) -> bool:
    """Cipta promo code baru. Return False kalau code dah wujud."""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO promo_codes (code, bonus_scans, description, max_uses, expiry_date)
            VALUES (%s, %s, %s, %s, %s)
        """, (code.upper(), bonus_scans, description, max_uses, expiry_date))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def get_promo_code(code: str) -> dict:
    """Dapatkan maklumat promo code."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM promo_codes WHERE code = %s AND is_active = 1", (code.upper(),))
    row = _fetchone_dict(c)
    conn.close()
    return row


def apply_promo_code(telegram_id: int, code: str) -> tuple[bool, str]:
    """
    Apply promo code untuk user.
    Return (success, message).
    """
    user = get_user(telegram_id)
    if not user:
        return False, "Profil tidak dijumpai."

    # Semak dah guna promo sebelum ni
    if user.get("promo_used"):
        return False, f"Anda dah pernah guna kod promo sebelum ini ({user['promo_used']})."

    # Semak dah topup sekurang-kurangnya sekali
    if not user.get("topup_count") or user["topup_count"] < 1:
        return False, "Kod promo hanya untuk pengguna yang dah buat topup pertama."

    promo = get_promo_code(code)
    if not promo:
        return False, "Kod promo tidak sah atau tidak aktif."

    # Semak expiry
    if promo["expiry_date"]:
        today = _today_myt()
        if today > promo["expiry_date"]:
            return False, "Kod promo ini dah tamat tempoh."

    # Semak max uses
    if promo["max_uses"] > 0 and promo["uses_count"] >= promo["max_uses"]:
        return False, "Kod promo ini dah habis digunakan."

    # Apply — tambah scan + mark promo used
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE users SET scans_remaining = scans_remaining + %s, promo_used = %s WHERE telegram_id = %s",
        (promo["bonus_scans"], code.upper(), telegram_id)
    )
    c.execute(
        "UPDATE promo_codes SET uses_count = uses_count + 1 WHERE code = %s",
        (code.upper(),)
    )
    conn.commit()
    conn.close()

    return True, f"✅ Kod promo berjaya! +{promo['bonus_scans']} scan bonus ditambah."


def get_all_promo_codes() -> list:
    """Dapatkan senarai semua promo codes (untuk admin)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM promo_codes ORDER BY created_at DESC")
    rows = _fetchall_dict(c)
    conn.close()
    return rows


# ── FUNGSI TOPUP REQUESTS ────────────────────────────────────────

def create_topup_request(telegram_id: int, package_key: str, amount_rm: float, scans: int) -> int:
    """Cipta topup request baru. Return id."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO topup_requests (telegram_id, package_key, amount_rm, scans)
        VALUES (%s, %s, %s, %s)
        RETURNING id
    """, (telegram_id, package_key, amount_rm, scans))
    row = c.fetchone()
    conn.commit()
    conn.close()
    return row[0]


def update_topup_slip(request_id: int, slip_file_id: str):
    """Update slip gambar pada request."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE topup_requests SET slip_file_id = %s WHERE id = %s",
        (slip_file_id, request_id)
    )
    conn.commit()
    conn.close()


def save_bill_code(request_id: int, bill_code: str):
    """Simpan ToyyibPay bill code pada request."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE topup_requests SET bill_code = %s WHERE id = %s",
        (bill_code, request_id)
    )
    conn.commit()
    conn.close()


def get_topup_request(request_id: int) -> dict:
    """Dapatkan satu topup request."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM topup_requests WHERE id = %s", (request_id,))
    row = _fetchone_dict(c)
    conn.close()
    return row


def approve_topup_request(request_id: int) -> dict:
    """
    Luluskan topup request:
    - Tambah scans kepada user
    - Update status → 'approved'
    - Increment topup_count
    Return request dict (untuk notify user).
    """
    conn = get_connection()
    c = conn.cursor()

    # Dapatkan request
    c.execute("SELECT * FROM topup_requests WHERE id = %s", (request_id,))
    req = _fetchone_dict(c)
    if not req or req["status"] == "approved":
        conn.close()
        return None

    # Tambah scans + topup_count
    c.execute("""
        UPDATE users
        SET scans_remaining = scans_remaining + %s,
            topup_count = COALESCE(topup_count, 0) + 1
        WHERE telegram_id = %s
    """, (req["scans"], req["telegram_id"]))

    # Update status
    c.execute("""
        UPDATE topup_requests
        SET status = 'approved', approved_at = to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
        WHERE id = %s
    """, (request_id,))

    # ── Semak affiliate commission ────────────────────────────
    # Cari siapa yang refer user ini
    c.execute("SELECT referred_by FROM users WHERE telegram_id = %s", (req["telegram_id"],))
    ref_row = c.fetchone()
    referrer_id = ref_row[0] if ref_row and ref_row[0] else None

    if referrer_id:
        # Semak sama ada referrer adalah affiliate aktif
        c.execute(
            "SELECT commission_rate FROM affiliates WHERE telegram_id = %s AND status = 'active'",
            (referrer_id,)
        )
        aff_row = c.fetchone()
        if aff_row:
            commission_rate = float(aff_row[0])
            commission_rm = round(req["amount_rm"] * commission_rate, 2)
            month_str = datetime.now(_MYT).strftime('%Y-%m')
            c.execute("""
                INSERT INTO affiliate_earnings
                    (affiliate_id, from_user_id, topup_request_id, amount_rm, commission_rm, month)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (referrer_id, req["telegram_id"], request_id, req["amount_rm"], commission_rm, month_str))

    conn.commit()
    conn.close()
    return req


def reject_topup_request(request_id: int) -> dict:
    """Tolak topup request. Return request dict."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM topup_requests WHERE id = %s", (request_id,))
    req = _fetchone_dict(c)
    if not req or req["status"] != "pending":
        conn.close()
        return None
    c.execute("UPDATE topup_requests SET status = 'rejected' WHERE id = %s", (request_id,))
    conn.commit()
    conn.close()
    return req


def has_completed_topup(telegram_id: int) -> bool:
    """Semak sama ada user pernah buat topup yang berjaya sebelum ni."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT COUNT(*) FROM topup_requests WHERE telegram_id = %s AND status = 'approved'",
        (telegram_id,)
    )
    count = c.fetchone()[0]
    conn.close()
    return count > 0


def get_pending_topup_requests() -> list:
    """Senarai semua topup yang menunggu kelulusan."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT r.*, u.first_name, u.username
        FROM topup_requests r
        LEFT JOIN users u ON u.telegram_id = r.telegram_id
        WHERE r.status = 'pending'
        ORDER BY r.created_at ASC
    """)
    rows = _fetchall_dict(c)
    conn.close()
    return rows


# ── FUNGSI EXERCISE ───────────────────────────────────────────────

def get_exercise_calories(telegram_id: int) -> float:
    """Dapatkan kalori exercise hari ini."""
    today = _today_myt()
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT calories_burned FROM exercise_logs
        WHERE telegram_id = %s AND log_date = %s
    """, (telegram_id, today))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0.0


def save_exercise_calories(telegram_id: int, calories_burned: float):
    """Simpan atau update kalori exercise hari ini."""
    today = _today_myt()
    conn = get_connection()
    c = conn.cursor()
    now_myt = datetime.now(_MYT).strftime('%Y-%m-%d %H:%M:%S')
    c.execute("""
        INSERT INTO exercise_logs (telegram_id, log_date, calories_burned)
        VALUES (%s, %s, %s)
        ON CONFLICT (telegram_id, log_date)
        DO UPDATE SET calories_burned = EXCLUDED.calories_burned,
                      logged_at = %s
    """, (telegram_id, today, calories_burned, now_myt))
    conn.commit()
    conn.close()


# ── FUNGSI REFERRAL ───────────────────────────────────────────────

def _generate_unique_code() -> str:
    """Jana kod referral 6 huruf unik (A-Z, 0-9)."""
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=6))


def get_or_create_referral_code(telegram_id: int) -> str:
    """Dapatkan kod referral user. Jana baru kalau belum ada."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT referral_code FROM users WHERE telegram_id = %s", (telegram_id,))
    row = c.fetchone()

    if row and row[0]:
        conn.close()
        return row[0]

    # Jana kod unik — pastikan tak duplicate
    while True:
        code = _generate_unique_code()
        c.execute("SELECT 1 FROM users WHERE referral_code = %s", (code,))
        if not c.fetchone():
            break

    c.execute(
        "UPDATE users SET referral_code = %s WHERE telegram_id = %s",
        (code, telegram_id)
    )
    conn.commit()
    conn.close()
    return code


def save_pending_referral(telegram_id: int, ref_code: str):
    """Simpan referral code dalam DB supaya tak hilang kalau bot restart."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE users SET pending_referral = %s WHERE telegram_id = %s AND referred_by IS NULL",
        (ref_code, telegram_id)
    )
    conn.commit()
    conn.close()


def get_pending_referral(telegram_id: int) -> str:
    """Ambil dan clear pending referral code dari DB."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT pending_referral FROM users WHERE telegram_id = %s", (telegram_id,))
    row = c.fetchone()
    code = row[0] if row and row[0] else None
    if code:
        c.execute("UPDATE users SET pending_referral = NULL WHERE telegram_id = %s", (telegram_id,))
        conn.commit()
    conn.close()
    return code


def get_user_by_referral_code(code: str):
    """Cari user berdasarkan kod referral."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE referral_code = %s", (code,))
    user = _fetchone_dict(c)
    conn.close()
    return user


def process_referral(new_user_id: int, referrer_id: int) -> bool:
    """
    Proses referral selepas new user siap setup.
    - Tandakan referred_by pada new user
    - Tambah referral_count pada referrer
    - Bagi +5 scan kepada kedua-dua
    Return True jika berjaya, False kalau dah pernah diproses.
    """
    conn = get_connection()
    c = conn.cursor()

    # Semak sama ada dah diproses
    c.execute("SELECT referred_by FROM users WHERE telegram_id = %s", (new_user_id,))
    row = c.fetchone()
    if row and row[0]:
        conn.close()
        return False  # dah ada referrer, skip

    # Update new user
    c.execute("""
        UPDATE users
        SET referred_by = %s, scans_remaining = scans_remaining + 5
        WHERE telegram_id = %s
    """, (referrer_id, new_user_id))

    # Update referrer
    c.execute("""
        UPDATE users
        SET referral_count = referral_count + 1,
            scans_remaining = scans_remaining + 5
        WHERE telegram_id = %s
    """, (referrer_id,))

    conn.commit()
    conn.close()
    return True


# ── FUNGSI BODY SCAN ──────────────────────────────────────────────

def save_body_scan(telegram_id: int, body_fat_visual: float, muscle_def: str,
                   physique_cat: str, feedback: str, image_file_id: str = None):
    """Simpan keputusan body scan."""
    today = _today_myt()
    now_myt = datetime.now(_MYT).strftime('%Y-%m-%d %H:%M:%S')
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO body_scans
            (telegram_id, scan_date, body_fat_visual, muscle_def, physique_cat, feedback, image_file_id, scanned_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (telegram_id, today, body_fat_visual, muscle_def, physique_cat, feedback, image_file_id, now_myt))
    conn.commit()
    conn.close()


def get_body_scan_history(telegram_id: int, limit: int = 5) -> list:
    """Dapatkan history body scan terkini."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM body_scans
        WHERE telegram_id = %s
        ORDER BY scanned_at DESC
        LIMIT %s
    """, (telegram_id, limit))
    rows = _fetchall_dict(c)
    conn.close()
    return rows


# ── FUNGSI ACHIEVEMENT ───────────────────────────────────────────

def get_total_scans_used(telegram_id: int) -> int:
    """Jumlah AI scan yang pernah dibuat (food_logs dengan image_file_id)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT COUNT(*) FROM food_logs WHERE telegram_id = %s AND image_file_id IS NOT NULL",
        (telegram_id,)
    )
    count = c.fetchone()[0]
    conn.close()
    return int(count)


def has_achievement(telegram_id: int, key: str) -> bool:
    """Semak sama ada user dah dapat achievement ini."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT 1 FROM user_achievements WHERE telegram_id = %s AND achievement_key = %s",
        (telegram_id, key)
    )
    result = c.fetchone() is not None
    conn.close()
    return result


def award_achievement(telegram_id: int, key: str, bonus_scans: int = 0) -> bool:
    """
    Beri achievement kepada user. Return True jika berjaya (baru unlock).
    Jika dah ada, return False.
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO user_achievements (telegram_id, achievement_key, bonus_given)
            VALUES (%s, %s, %s)
        """, (telegram_id, key, bonus_scans))

        if bonus_scans > 0:
            c.execute("""
                UPDATE users SET scans_remaining = scans_remaining + %s
                WHERE telegram_id = %s
            """, (bonus_scans, telegram_id))

        conn.commit()
        conn.close()
        return True
    except Exception:
        # UNIQUE constraint — dah ada
        conn.close()
        return False


def get_user_achievements(telegram_id: int) -> list:
    """Senarai semua achievement yang dah dibuka."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT achievement_key, unlocked_at, bonus_given
        FROM user_achievements
        WHERE telegram_id = %s
        ORDER BY unlocked_at ASC
    """, (telegram_id,))
    rows = _fetchall_dict(c)
    conn.close()
    return rows


# ── FUNGSI AFFILIATE ──────────────────────────────────────────────

def add_affiliate(telegram_id: int, bank_name: str, bank_acc: str) -> bool:
    """Daftarkan user sebagai affiliate. Return False jika dah wujud."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT 1 FROM affiliates WHERE telegram_id = %s", (telegram_id,))
    if c.fetchone():
        conn.close()
        return False
    c.execute(
        "INSERT INTO affiliates (telegram_id, bank_name, bank_acc) VALUES (%s, %s, %s)",
        (telegram_id, bank_name, bank_acc)
    )
    conn.commit()
    conn.close()
    return True


def remove_affiliate(telegram_id: int):
    """Nyahaktifkan affiliate."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE affiliates SET status = 'inactive' WHERE telegram_id = %s", (telegram_id,))
    conn.commit()
    conn.close()


def get_affiliate(telegram_id: int) -> dict:
    """Dapatkan maklumat affiliate."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM affiliates WHERE telegram_id = %s", (telegram_id,))
    row = _fetchone_dict(c)
    conn.close()
    return row


def get_all_affiliates() -> list:
    """Senarai semua affiliates."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT a.*, u.first_name, u.username
        FROM affiliates a
        LEFT JOIN users u ON u.telegram_id = a.telegram_id
        ORDER BY a.joined_at DESC
    """)
    rows = _fetchall_dict(c)
    conn.close()
    return rows


def save_affiliate_application(telegram_id: int, bank_name: str, bank_acc: str) -> int:
    """Simpan permohonan affiliate baru. Return app_id."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO affiliate_applications (telegram_id, bank_name, bank_acc)
        VALUES (%s, %s, %s)
        RETURNING id
    """, (telegram_id, bank_name, bank_acc))
    app_id = c.fetchone()[0]
    conn.commit()
    conn.close()
    return app_id


def get_affiliate_application(app_id: int) -> dict:
    """Dapatkan satu permohonan affiliate."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM affiliate_applications WHERE id = %s", (app_id,))
    row = _fetchone_dict(c)
    conn.close()
    return row


def approve_affiliate_application(app_id: int) -> dict:
    """
    Luluskan permohonan affiliate.
    Return application dict, atau None jika tak jumpa/dah diproses.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM affiliate_applications WHERE id = %s AND status = 'pending'", (app_id,))
    app = _fetchone_dict(c)
    if not app:
        conn.close()
        return None

    # Daftar dalam affiliates
    c.execute("""
        INSERT INTO affiliates (telegram_id, bank_name, bank_acc)
        VALUES (%s, %s, %s)
        ON CONFLICT (telegram_id) DO UPDATE
        SET bank_name = EXCLUDED.bank_name,
            bank_acc = EXCLUDED.bank_acc,
            status = 'active'
    """, (app["telegram_id"], app["bank_name"], app["bank_acc"]))

    # Update status permohonan
    c.execute("UPDATE affiliate_applications SET status = 'approved' WHERE id = %s", (app_id,))
    conn.commit()
    conn.close()
    return app


def reject_affiliate_application(app_id: int) -> dict:
    """Tolak permohonan affiliate. Return application dict."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM affiliate_applications WHERE id = %s AND status = 'pending'", (app_id,))
    app = _fetchone_dict(c)
    if not app:
        conn.close()
        return None
    c.execute("UPDATE affiliate_applications SET status = 'rejected' WHERE id = %s", (app_id,))
    conn.commit()
    conn.close()
    return app


def has_pending_affiliate_application(telegram_id: int) -> bool:
    """Semak ada permohonan pending dari user ini."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT 1 FROM affiliate_applications WHERE telegram_id = %s AND status = 'pending'",
        (telegram_id,)
    )
    result = c.fetchone() is not None
    conn.close()
    return result


def get_affiliate_earnings_summary(affiliate_id: int, month: str = None) -> dict:
    """
    Ringkasan earnings affiliate.
    month format: 'YYYY-MM'. Jika None, semua bulan.
    Return dict: total_earned, total_paid, pending, transactions
    """
    conn = get_connection()
    c = conn.cursor()

    where = "WHERE affiliate_id = %s"
    params = [affiliate_id]
    if month:
        where += " AND month = %s"
        params.append(month)

    c.execute(f"""
        SELECT
            COALESCE(SUM(commission_rm), 0) as total,
            COALESCE(SUM(CASE WHEN paid = 1 THEN commission_rm ELSE 0 END), 0) as paid,
            COALESCE(SUM(CASE WHEN paid = 0 THEN commission_rm ELSE 0 END), 0) as pending,
            COUNT(*) as transactions
        FROM affiliate_earnings
        {where}
    """, params)
    row = c.fetchone()
    conn.close()
    return {
        "total":        float(row[0]),
        "paid":         float(row[1]),
        "pending":      float(row[2]),
        "transactions": int(row[3]),
    }


def get_affiliate_payout_list(month: str) -> list:
    """
    Senarai affiliate yang ada unpaid earnings untuk bulan tertentu.
    Untuk admin payout view.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT
            ae.affiliate_id,
            u.first_name,
            u.username,
            a.bank_name,
            a.bank_acc,
            SUM(ae.commission_rm) as total_commission,
            COUNT(*) as transactions
        FROM affiliate_earnings ae
        LEFT JOIN users u ON u.telegram_id = ae.affiliate_id
        LEFT JOIN affiliates a ON a.telegram_id = ae.affiliate_id
        WHERE ae.month = %s AND ae.paid = 0
        GROUP BY ae.affiliate_id, u.first_name, u.username, a.bank_name, a.bank_acc
        ORDER BY total_commission DESC
    """, (month,))
    rows = _fetchall_dict(c)
    conn.close()
    return rows


def mark_affiliate_paid(affiliate_id: int, month: str) -> float:
    """
    Mark semua unpaid earnings affiliate untuk bulan ini sebagai paid.
    Return jumlah yang dibayar.
    """
    now_myt = datetime.now(_MYT).strftime('%Y-%m-%d %H:%M:%S')
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT COALESCE(SUM(commission_rm), 0)
        FROM affiliate_earnings
        WHERE affiliate_id = %s AND month = %s AND paid = 0
    """, (affiliate_id, month))
    total = float(c.fetchone()[0])

    c.execute("""
        UPDATE affiliate_earnings
        SET paid = 1, paid_at = %s
        WHERE affiliate_id = %s AND month = %s AND paid = 0
    """, (now_myt, affiliate_id, month))
    conn.commit()
    conn.close()
    return total


# ── ADMIN STATS ───────────────────────────────────────────────────

def get_admin_stats() -> dict:
    """
    Dapatkan stats keseluruhan untuk admin dashboard.
    Semua tarikh dalam MYT (UTC+8).
    """
    today = _today_myt()
    now_myt = datetime.now(_MYT)
    month_start = now_myt.strftime('%Y-%m-01')

    conn = get_connection()
    c = conn.cursor()

    # ── Users
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM users WHERE setup_complete = 1")
    setup_users = c.fetchone()[0]

    # Daftar hari ini (MYT) — created_at format: 'YYYY-MM-DD HH24:MI:SS'
    c.execute("SELECT COUNT(*) FROM users WHERE created_at LIKE %s", (f"{today}%",))
    new_today = c.fetchone()[0]

    # ── Active users hari ini (ada food log hari ini)
    c.execute(
        "SELECT COUNT(DISTINCT telegram_id) FROM food_logs WHERE log_date = %s",
        (today,)
    )
    active_today = c.fetchone()[0]

    # ── Scan usage hari ini
    c.execute(
        "SELECT COUNT(*) FROM food_logs WHERE log_date = %s AND image_file_id IS NOT NULL",
        (today,)
    )
    scans_today = c.fetchone()[0]

    # ── Revenue bulan ini (approved topup, amount_rm)
    c.execute("""
        SELECT COALESCE(SUM(amount_rm), 0), COUNT(*)
        FROM topup_requests
        WHERE status = 'approved' AND created_at >= %s
    """, (month_start,))
    row = c.fetchone()
    revenue_month = float(row[0])
    topups_month = int(row[1])

    # ── Revenue all-time
    c.execute("""
        SELECT COALESCE(SUM(amount_rm), 0), COUNT(*)
        FROM topup_requests
        WHERE status = 'approved'
    """)
    row = c.fetchone()
    revenue_total = float(row[0])
    topups_total = int(row[1])

    # ── Pending topup (tunggu lulus)
    c.execute("SELECT COUNT(*) FROM topup_requests WHERE status = 'pending'")
    pending_topup = c.fetchone()[0]

    # ── Total scans digunakan all-time (AI scan sahaja)
    c.execute("SELECT COUNT(*) FROM food_logs WHERE image_file_id IS NOT NULL")
    total_scans_used = c.fetchone()[0]

    # ── Total log manual all-time
    c.execute("SELECT COUNT(*) FROM food_logs WHERE image_file_id IS NULL")
    total_manual_logs = c.fetchone()[0]

    conn.close()

    return {
        "total_users":      total_users,
        "setup_users":      setup_users,
        "new_today":        new_today,
        "active_today":     active_today,
        "scans_today":      scans_today,
        "revenue_month":    revenue_month,
        "topups_month":     topups_month,
        "revenue_total":    revenue_total,
        "topups_total":     topups_total,
        "pending_topup":    pending_topup,
        "total_scans_used": total_scans_used,
        "total_manual_logs":total_manual_logs,
        "month_label":      now_myt.strftime('%B %Y'),
        "today_label":      today,
    }
