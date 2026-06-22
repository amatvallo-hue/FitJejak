import os
from dotenv import load_dotenv

load_dotenv()

# -- Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# -- AI Provider
# Tukar ke "gemini" jika nak guna Google Gemini
AI_PROVIDER = os.getenv("AI_PROVIDER", "openai")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# -- Database
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/fitjejak.db")

# -- Admin
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))

# -- Topup / Payment
# Letak path gambar QR code (contoh: "assets/qr.jpg")
QR_IMAGE_PATH = os.getenv("QR_IMAGE_PATH", "assets/qr.jpg")
PAYMENT_ACCOUNT_NAME   = os.getenv("PAYMENT_ACCOUNT_NAME", "FitJejak")
PAYMENT_ACCOUNT_NUMBER = os.getenv("PAYMENT_ACCOUNT_NUMBER", "")

# -- Free Trial
FREE_SCAN_LIMIT = 20  # Bilangan scan percuma untuk pengguna baru

# -- Credit Packages
CREDIT_PACKAGES = {
    "starter": {"name": "Starter", "price_rm": 10, "scans": 50},
    "basic":   {"name": "Basic",   "price_rm": 18, "scans": 100},
    "pro":     {"name": "Pro",     "price_rm": 45, "scans": 300},
    "power":   {"name": "Power",   "price_rm": 80, "scans": 600},
}

# -- Activity Level Multipliers (untuk kira TDEE)
ACTIVITY_MULTIPLIERS = {
    "sedentary":   1.2,
    "light":       1.375,
    "moderate":    1.55,
    "active":      1.725,
    "very_active": 1.9,
}
