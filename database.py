"""
database.py — FitJejak
Menguruskan semua operasi database (SQLite)
"""
import sqlite3
import os
from datetime import date, datetime
from config import DATABASE_PATH


def get_connection():
    """Buka sambungan ke database."""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Supaya boleh akses column by name
    return conn


def init_db():
    """Cipta semua table jika belum wujud. Panggil sekali masa bot start."""
    conn = get_connection()
    c = conn.cursor()

    # ── Table: pengguna ───────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id     INTEGER PRIMARY KEY,
            username        TEXT,
            first_name      TEXT,
            weight_kg       REAL,
            height_cm       REAL,
            age             INTEGER,
            gender          TEXT,      -- 'lelaki' atau 'perempuan'
            activity_level  TEXT,      -- 'sedentary','light','moderate','active','very_active'
            goal            TEXT,      -- 'turun_berat','kekal','naik_otot'
            target_calories REAL,
            target_protein  REAL,
            scans_remaining INTEGER DEFAULT 20,
            setup_complete  INTEGER DEFAULT 0,  -- 0=belum, 1=siap
            created_at      TEXT DEFAULT (datetime('now')),
            updated_at      TEXT DEFAULT (datetime('now'))
        )
    """)

    # ── Table: log makanan ────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS food_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            log_date    TEXT NOT NULL,      -- format: YYYY-MM-DD
            food_name   TEXT NOT NULL,
            calories    REAL DEFAULT 0,
            protein_g   REAL DEFAULT 0,
            carbs_g     REAL DEFAULT 0,
            fat_g       REAL DEFAULT 0,
            health_score INTEGER DEFAULT 0, -- 1-10
            advice      TEXT,
            image_file_id TEXT,             -- Telegram file_id gambar
            logged_at   TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
        )
    """)

    # ── Table: rekod berat ────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS weight_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            log_date    TEXT NOT NULL,
            weight_kg   REAL NOT NULL,
            logged_at   TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Database siap.")


# ── FUNGSI PENGGUNA ───────────────────────────────────────────────

def get_user(telegram_id: int):
    """Dapatkan maklumat pengguna. Return None jika tiada."""
    conn = get_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
    ).fetchone()
    conn.close()
    return user


def create_user(telegram_id: int, username: str, first_name: str):
    """Daftarkan pengguna baru dengan 20 scan percuma."""
    conn = get_connection()
    conn.execute("""
        INSERT OR IGNORE INTO users (telegram_id, username, first_name)
        VALUES (?, ?, ?)
    """, (telegram_id, username, first_name))
    conn.commit()
    conn.close()


def update_user_profile(telegram_id: int, **kwargs):
    """Kemaskini profil pengguna. Hantar mana-mana field sebagai keyword argument."""
    if not kwargs:
        return
    kwargs["updated_at"] = datetime.now().isoformat()
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [telegram_id]
    conn = get_connection()
    conn.execute(f"UPDATE users SET {fields} WHERE telegram_id = ?", values)
    conn.commit()
    conn.close()


def deduct_scan(telegram_id: int) -> bool:
    """
    Tolak 1 scan dari baki pengguna.
    Return True jika berjaya, False jika scan habis.
    """
    conn = get_connection()
    user = conn.execute(
        "SELECT scans_remaining FROM users WHERE telegram_id = ?", (telegram_id,)
    ).fetchone()

    if not user or user["scans_remaining"] <= 0:
        conn.close()
        return False

    conn.execute(
        "UPDATE users SET scans_remaining = scans_remaining - 1 WHERE telegram_id = ?",
        (telegram_id,)
    )
    conn.commit()
    conn.close()
    return True


def add_credits(telegram_id: int, scans: int):
    """Tambah kredit scan untuk pengguna (selepas bayar)."""
    conn = get_connection()
    conn.execute(
        "UPDATE users SET scans_remaining = scans_remaining + ? WHERE telegram_id = ?",
        (scans, telegram_id)
    )
    conn.commit()
    conn.close()


# ── FUNGSI LOG MAKANAN ────────────────────────────────────────────

def log_food(telegram_id: int, food_name: str, calories: float,
             protein_g: float, carbs_g: float, fat_g: float,
             health_score: int, advice: str, image_file_id: str = None):
    """Simpan rekod makanan hari ini."""
    today = date.today().isoformat()
    conn = get_connection()
    conn.execute("""
        INSERT INTO food_logs
            (telegram_id, log_date, food_name, calories, protein_g, carbs_g, fat_g,
             health_score, advice, image_file_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (telegram_id, today, food_name, calories, protein_g, carbs_g, fat_g,
          health_score, advice, image_file_id))
    conn.commit()
    conn.close()


def get_today_summary(telegram_id: int) -> dict:
    """Kira jumlah kalori, protein, carb, dan lemak untuk hari ini."""
    today = date.today().isoformat()
    conn = get_connection()
    row = conn.execute("""
        SELECT
            COALESCE(SUM(calories), 0)  AS total_calories,
            COALESCE(SUM(protein_g), 0) AS total_protein,
            COALESCE(SUM(carbs_g), 0)   AS total_carbs,
            COALESCE(SUM(fat_g), 0)     AS total_fat,
            COUNT(*) AS meal_count
        FROM food_logs
        WHERE telegram_id = ? AND log_date = ?
    """, (telegram_id, today)).fetchone()
    conn.close()
    return dict(row)


def get_week_summary(telegram_id: int) -> dict:
    """Dapatkan purata nutrisi untuk 7 hari lepas."""
    conn = get_connection()
    row = conn.execute("""
        SELECT
            ROUND(AVG(daily_cal), 0)     AS avg_calories,
            ROUND(AVG(daily_protein), 0) AS avg_protein,
            COUNT(DISTINCT log_date)     AS days_logged
        FROM (
            SELECT
                log_date,
                SUM(calories)  AS daily_cal,
                SUM(protein_g) AS daily_protein
            FROM food_logs
            WHERE telegram_id = ?
              AND log_date >= date('now', '-7 days')
            GROUP BY log_date
        )
    """, (telegram_id,)).fetchone()
    conn.close()
    return dict(row)


# ── FUNGSI REKOD BERAT ────────────────────────────────────────────

def log_weight(telegram_id: int, weight_kg: float):
    """Simpan rekod berat badan hari ini. Ganti jika dah ada rekod hari sama."""
    today = date.today().isoformat()
    conn = get_connection()
    # Guna INSERT OR REPLACE supaya satu rekod sehari sahaja
    conn.execute("""
        INSERT OR REPLACE INTO weight_logs (telegram_id, log_date, weight_kg)
        VALUES (?, ?, ?)
    """, (telegram_id, today, weight_kg))
    # Kemaskini juga berat semasa dalam profil
    conn.execute(
        "UPDATE users SET weight_kg = ?, updated_at = datetime('now') WHERE telegram_id = ?",
        (weight_kg, telegram_id)
    )
    conn.commit()
    conn.close()


def get_previous_weight(telegram_id: int):
    """Dapatkan rekod berat minggu lepas (untuk perbandingan)."""
    conn = get_connection()
    row = conn.execute("""
        SELECT weight_kg FROM weight_logs
        WHERE telegram_id = ?
          AND log_date < date('now')
        ORDER BY log_date DESC
        LIMIT 1
    """, (telegram_id,)).fetchone()
    conn.close()
    return row["weight_kg"] if row else None
