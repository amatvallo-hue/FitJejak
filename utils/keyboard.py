"""
utils/keyboard.py — FitJejak
Persistent Reply Keyboard untuk semua user.
"""
from telegram import ReplyKeyboardMarkup

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["✍️ Log Manual",  "🔄 Log Semula"],
        ["📸 Scan Badan",  "📊 Hari Ini"],
        ["📋 History",     "⚖️ Berat"],
        ["📈 Summary",     "💳 Topup"],
        ["🔗 Referral",    "👤 Profil"],
        ["❓ Help"],
    ],
    resize_keyboard=True,
    is_persistent=True
)
