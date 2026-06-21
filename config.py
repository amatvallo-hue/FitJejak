import os
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ──────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# ── AI Provider ───────────────────────────────────────────
# Tukar ke "gemini" jika nak guna Google Gemini
AI_PROVIDER = os.getenv("AI_PROVIDER", "openai")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# ── Database ──────────────────────────────────────────────
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/fitjejak.db")

# ── Admin ─────────────────────────────────────────────────
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))

# ── Free Trial ────────────────────────────────────────────
FREE_SCAN_LIMIT = 20  # Bilangan scan percuma untuk pengguna baru

# ── Credit Packages ───────────────────────────────────────
CREDIT_PACKAGES = {
    "starter": {"name": "Starter", "price_rm": 10, "scans": 50},
    "basic":   {"name": "Basic",   "price_rm": 18, "scans": 100},
    "pro":     {"name": "Pro",     "price_rm": 45, "scans": 300},
    "power":   {"name": "Power",   "price_rm": 80, "scans": 600},
}

# ── Activity Level Multipliers (untuk kira TDEE) ──────────
ACTIVITY_MULTIPLIERS = {
    "sedentary":   1.2,   # Duduk sahaja, kerja office
    "light":       1.375, # Senaman ringan 1-3 hari/minggu
    "moderate":    1.55,  # Senaman sederhana 3-5 hari/minggu
    "active":      1.725, # Senaman berat 6-7 hari/minggu
    "very_active": 1.9,   # Athlete / kerja fizikal berat
}
