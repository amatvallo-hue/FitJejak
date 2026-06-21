"""
bot.py — FitJejak
Fail utama untuk menjalankan bot Telegram.

Cara jalankan:
    python bot.py
"""
import logging
from datetime import time
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
)

from config import TELEGRAM_BOT_TOKEN
import database as db
from handlers.start import get_setup_handler
from handlers.food import handle_photo
from handlers.tracking import today, weight, summary, credits, topup, profile, history, handle_delete_callback, help_command, referral, handle_exercise_callback, handle_exercise_input, handle_reminder_toggle
from handlers.admin import admin
from handlers.manual_food import get_manual_food_handler
from handlers.edit_log import get_edit_handler
from handlers.edit_profile import get_edit_profile_handler
from utils.keyboard import MAIN_KEYBOARD
from handlers.reminder import (
    send_morning_reminder, send_evening_reminder, send_weekly_report,
    MORNING_HOUR_UTC, EVENING_HOUR_UTC, WEEKLY_HOUR_UTC
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
    app.add_handler(CommandHandler("profile",  profile))
    app.add_handler(CommandHandler("referral", referral))

    # 4. Admin command
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CallbackQueryHandler(handle_delete_callback, pattern="^del_"))
    app.add_handler(CallbackQueryHandler(handle_exercise_callback, pattern="^add_exercise$"))
    app.add_handler(CallbackQueryHandler(handle_reminder_toggle, pattern="^toggle_reminder_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r"^\d+(\.\d+)?$"), handle_exercise_input))

    # 5. Edit log makanan
    app.add_handler(get_edit_handler())

    # 5b. Edit profil
    app.add_handler(get_edit_profile_handler())

    # 6. Keyboard button handlers (mesti sebelum manual food)
    app.add_handler(MessageHandler(filters.Regex("^📊 Hari Ini$"),  today))
    app.add_handler(MessageHandler(filters.Regex("^📋 History$"),   history))
    app.add_handler(MessageHandler(filters.Regex("^📈 Summary$"),   summary))
    app.add_handler(MessageHandler(filters.Regex("^⚖️ Berat$"),     weight))
    app.add_handler(MessageHandler(filters.Regex("^💳 Topup$"),     topup))
    app.add_handler(MessageHandler(filters.Regex("^🔗 Referral$"),  referral))
    app.add_handler(MessageHandler(filters.Regex("^👤 Profil$"),    profile))
    app.add_handler(MessageHandler(filters.Regex("^❓ Help$"),      help_command))

    # 7. Rekod manual (ConversationHandler)
    app.add_handler(get_manual_food_handler())

    # 7. Handler media lain (video, sticker, audio, document)
    app.add_handler(MessageHandler(filters.VIDEO | filters.VIDEO_NOTE, _handle_video))
    app.add_handler(MessageHandler(filters.Sticker.ALL, _handle_sticker))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, _handle_audio))
    app.add_handler(MessageHandler(filters.Document.ALL, _handle_document))

    # 8. Unknown command — mesti paling bawah sekali
    app.add_handler(MessageHandler(filters.COMMAND, _handle_unknown_command))

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
    # Weekly report setiap Ahad 8 malam MYT (12:00 UTC, weekday=6)
    job_queue.run_daily(
        send_weekly_report,
        time=time(hour=WEEKLY_HOUR_UTC, minute=0),
        days=(6,)  # 6 = Ahad
    )
    logger.info("⏰ Reminder harian & weekly report berjaya didaftarkan.")

    # ── Jalankan bot ──────────────────────────────────────────────
    logger.info("🚀 FitJejak Bot sedang berjalan...")
    app.run_polling(allowed_updates=["message", "callback_query"])



async def _handle_video(update, context):
    await update.message.reply_text(
        "🎬 Wah, hantar movie ke? FitJejak bukan Netflix la!\n"
        "Hantar gambar makanan je ye 😄"
    )

async def _handle_sticker(update, context):
    await update.message.reply_text(
        "😂 Comel sticker tu! Tapi FitJejak tak boleh kira kalori sticker.\n"
        "Cuba snap gambar makanan awak!"
    )

async def _handle_audio(update, context):
    await update.message.reply_text(
        "🎤 Eh saya bukan Siri! Hantar gambar makanan atau taip kalori je tau 😄"
    )

async def _handle_document(update, context):
    await update.message.reply_text(
        "📎 Apa ni, hantar resume ke? Saya cuma expert pasal makanan je 😂\n"
        "Cuba snap gambar lauk awak!"
    )

async def _handle_unknown_command(update, context):
    cmd = update.message.text.split()[0] if update.message.text else ""
    await update.message.reply_text(
        f"❓ Tak kenal command '{cmd}'.\n\n"
        "Taip /help untuk senarai semua command yang ada."
    )


if __name__ == "__main__":
    main()
