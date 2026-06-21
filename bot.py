"""
bot.py — FitJejak
Fail utama untuk menjalankan bot Telegram.

Cara jalankan:
    python bot.py
"""
import logging
from datetime import time
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters
)

from config import TELEGRAM_BOT_TOKEN
import database as db
from handlers.start import get_setup_handler
from handlers.food import handle_photo
from handlers.tracking import today, weight, summary, credits, topup, profile
from handlers.admin import admin
from handlers.food import handle_text_food
from handlers.reminder import (
    send_morning_reminder, send_evening_reminder,
    MORNING_HOUR_UTC, EVENING_HOUR_UTC
)

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

    # 5. Handler teks biasa — analisis makanan dari teks
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_text_food
    ))

    # ── Daftar reminder harian ────────────────────────────────────
    job_queue = app.job_queue
    # Pagi 8:00 AM MYT (00:00 UTC)
    job_queue.run_daily(
        send_morning_reminder,
        time=time(hour=MORNING_HOUR_UTC, minute=0)
    )
    # Malam 9:00 PM MYT (13:00 UTC)
    job_queue.run_daily(
        send_evening_reminder,
        time=time(hour=EVENING_HOUR_UTC, minute=0)
    )
    logger.info("⏰ Reminder harian berjaya didaftarkan.")

    # ── Jalankan bot ──────────────────────────────────────────────
    logger.info("🚀 FitJejak Bot sedang berjalan...")
    app.run_polling(allowed_updates=["message", "callback_query"])



if __name__ == "__main__":
    main()
