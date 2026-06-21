"""
utils/keyboard.py — FitJejak
Persistent Reply Keyboard untuk semua user.
"""
from telegram import ReplyKeyboardMarkup

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["✍️ Log Manual"],
        ["📊 Hari Ini",  "📋 History"],
        ["📈 Summary",   "⚖️ Berat"],
        ["💳 Topup",     "🔗 Referral"],
        ["👤 Profil",    "❓ Help"],
    ],
    resize_keyboard=True,
    is_persistent=True
)
