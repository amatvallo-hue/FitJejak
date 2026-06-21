"""
bot.py — FitJejak
Fail utama untuk menjalankan bot Telegram.

Cara jalankan:
    python bot.py
"""
import logging
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters
)

from config import TELEGRAM_BOT_TOKEN
import database as db
from handlers.start import get_setup_handler
from handlers.food import handle_photo
from handlers.tracking import today, weight, summary, credits, topup, profile
from handlers.admin import admin

# ── Setup logging ─────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    """Entry point utama bot."""

    # Semak token
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN tidak dijumpai dalam fail .env!")
        logger.error("   Sila salin .env.example ke .env dan isi token anda.")
        return

    # Init database
    db.init_db()

    # Bina aplikasi bot
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # ── Daftar handlers ───────────────────────────────────────────
    # 1. Setup profil (ConversationHandler — mesti daftar dulu)
    app.add_handler(get_setup_handler())

    # 2. Handler gambar makanan
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # 3. Commands tracking
    app.add_handler(CommandHandler("today",   today))
    app.add_handler(CommandHandler("weight",  weight))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(CommandHandler("credits", credits))
    app.add_handler(CommandHandler("topup",   topup))
    app.add_handler(CommandHandler("profile", profile))

    # 4. Admin command
    app.add_handler(CommandHandler("admin", admin))

    # 5. Handler teks biasa (jika bukan command)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        _handle_unknown_text
    ))

    # ── Jalankan bot ──────────────────────────────────────────────
    logger.info("🚀 FitJejak Bot sedang berjalan...")
    app.run_polling(allowed_updates=["message", "callback_query"])


async def _handle_unknown_text(update, context):
    """Reply bila pengguna hantar teks yang tidak dikenali."""
    await update.message.reply_text(
        "📸 Hantar *gambar makanan* untuk analisis nutrisi\\!\n\n"
        "Atau guna command:\n"
        "/today — Ringkasan hari ini\n"
        "/weight \\[kg\\] — Rekod berat\n"
        "/summary — Ringkasan minggu\n"
        "/credits — Baki scan\n"
        "/profile — Profil anda",
        parse_mode="MarkdownV2"
    )


if __name__ == "__main__":
    main()
