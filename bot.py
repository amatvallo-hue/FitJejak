"""
bot.py — FitJejak
Fail utama untuk menjalankan bot Telegram.

Cara jalankan:
    python bot.py

Bot berjalan dalam 2 mode serentak:
  - Telegram polling (terima mesej dari user)
  - aiohttp web server port 8080 (terima callback dari ToyyibPay)
"""
import asyncio
import logging
from datetime import time
from aiohttp import web
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
)

from config import TELEGRAM_BOT_TOKEN
import database as db
from handlers.start import get_setup_handler
from handlers.food import handle_photo
from handlers.tracking import today, weight, summary, credits, profile, history, handle_delete_callback, handle_relog_callback, handle_relog_fav_callback, handle_share_callback, relog, help_command, referral, handle_exercise_callback, handle_exercise_input, handle_reminder_toggle, promo, support, affiliate_dashboard, handle_support_type_callback
from handlers.topup import topup_menu, handle_package_selection, handle_topup_decision, handle_cancel_slip_callback
from handlers.payment import handle_payment_callback, health_check
from handlers.body_scan import request_body_photo, body_scan_history
from handlers.admin import admin, handle_affiliate_paid_callback, handle_affiliate_application_callback, handle_reply_user_callback, handle_admin_reply_text
from handlers.affiliate_apply import get_affiliate_apply_handler
from handlers.manual_food import get_manual_food_handler
from handlers.edit_log import get_edit_handler
from handlers.edit_profile import get_edit_profile_handler
from utils.keyboard import MAIN_KEYBOARD
from handlers.reminder import (
    send_morning_reminder, send_noon_reminder,
    send_afternoon_reminder, send_evening_reminder,
    send_weekly_report,
    MORNING_HOUR_UTC, NOON_HOUR_UTC, AFTERNOON_HOUR_UTC,
    EVENING_HOUR_UTC, WEEKLY_HOUR_UTC
)

# ── Setup logging ─────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def main():
    """Entry point utama bot — jalankan Telegram polling + aiohttp serentak."""

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
    app.add_handler(CommandHandler("topup",   topup_menu))
    app.add_handler(CommandHandler("profile",  profile))
    app.add_handler(CommandHandler("referral", referral))
    app.add_handler(CommandHandler("support",   support))
    app.add_handler(CommandHandler("promo",     promo))
    app.add_handler(CommandHandler("affiliate", affiliate_dashboard))

    # 4. Admin command
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", _handle_reset))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CallbackQueryHandler(handle_delete_callback,   pattern="^del_"))
    app.add_handler(CallbackQueryHandler(handle_relog_callback,     pattern="^relog_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_relog_fav_callback, pattern="^relog_fav_"))
    app.add_handler(CallbackQueryHandler(handle_share_callback,     pattern="^share_progress$"))
    app.add_handler(CommandHandler("relog", relog))
    app.add_handler(CallbackQueryHandler(handle_exercise_callback, pattern="^add_exercise$"))
    app.add_handler(CallbackQueryHandler(handle_reminder_toggle,   pattern="^rem_"))
    app.add_handler(CallbackQueryHandler(handle_package_selection, pattern="^topup_pkg_|^topup_cancel$"))
    app.add_handler(CallbackQueryHandler(handle_cancel_slip_callback, pattern="^topup_cancel_slip$"))
    app.add_handler(CallbackQueryHandler(handle_topup_decision,      pattern="^topup_approve_|^topup_reject_"))
    app.add_handler(CallbackQueryHandler(handle_affiliate_paid_callback,        pattern="^aff_paid_"))
    app.add_handler(CallbackQueryHandler(handle_affiliate_application_callback, pattern="^aff_approv_|^aff_reject_"))
    app.add_handler(CallbackQueryHandler(handle_reply_user_callback,            pattern="^reply_user_"))
    app.add_handler(CallbackQueryHandler(handle_support_type_callback,          pattern="^support_text$|^support_photo$"))

    # 5. Edit log makanan
    app.add_handler(get_edit_handler())

    # 5b. Edit profil
    app.add_handler(get_edit_profile_handler())

    # 6. Keyboard button handlers (mesti sebelum manual food)
    app.add_handler(MessageHandler(filters.Regex("^📊 Hari Ini$"),  today))
    app.add_handler(MessageHandler(filters.Regex("^📋 History$"),   history))
    app.add_handler(MessageHandler(filters.Regex("^📈 Summary$"),   summary))
    app.add_handler(MessageHandler(filters.Regex("^⚖️ Berat$"),     weight))
    app.add_handler(MessageHandler(filters.Regex("^💳 Topup$"),     topup_menu))
    app.add_handler(MessageHandler(filters.Regex("^🔗 Referral$"),  referral))
    app.add_handler(MessageHandler(filters.Regex("^👤 Profil$"),    profile))
    app.add_handler(MessageHandler(filters.Regex("^❓ Help$"),      help_command))
    app.add_handler(MessageHandler(filters.Regex("^📸 Scan Badan$"), request_body_photo))
    app.add_handler(MessageHandler(filters.Regex("^🔄 Log Semula$"), relog))
    app.add_handler(MessageHandler(filters.Regex("^✍️ Log Manual$"), _handle_log_manual_button))
    app.add_handler(CommandHandler("bodyscan", body_scan_history))

    # 7. Admin reply text — mesti SEBELUM semua text handler lain
    async def _admin_reply_gate(update, context):
        handled = await handle_admin_reply_text(update, context)
        if not handled:
            # Admin mungkin dalam support text mode atau exercise mode — process macam biasa
            from handlers.tracking import handle_support_text_input, handle_exercise_input
            if context.user_data.get("awaiting_support") == "text":
                await handle_support_text_input(update, context)
            elif context.user_data.get("waiting_exercise_cal"):
                await handle_exercise_input(update, context)
            else:
                # Fallback — proses sebagai manual food
                from handlers.manual_food import start_manual
                await start_manual(update, context)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.User(user_id=286370035),
        _admin_reply_gate
    ))

    # 7b. Affiliate application — mesti SEBELUM manual food (supaya text input tak ditangkap dulu)
    app.add_handler(get_affiliate_apply_handler())

    # 8. Rekod manual (ConversationHandler — tangkap semua teks, mesti paling bawah)
    app.add_handler(get_manual_food_handler())

    # Exercise input — mesti SELEPAS semua ConversationHandlers supaya tak intercept
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r"^\d+(\.\d+)?$"), handle_exercise_input))

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
    # Tengah hari 12:00 PM MYT (04:00 UTC)
    job_queue.run_daily(
        send_noon_reminder,
        time=time(hour=NOON_HOUR_UTC, minute=0)
    )
    # Petang 5:00 PM MYT (09:00 UTC)
    job_queue.run_daily(
        send_afternoon_reminder,
        time=time(hour=AFTERNOON_HOUR_UTC, minute=0)
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
    logger.info("⏰ 4x reminder harian & weekly report berjaya didaftarkan.")

    # ── Setup aiohttp web server (untuk ToyyibPay callback) ───────
    web_app = web.Application()
    web_app["bot"] = app.bot  # share bot object untuk hantar mesej dari callback
    web_app.router.add_get("/",                  health_check)
    web_app.router.add_post("/payment/callback", handle_payment_callback)

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    logger.info("🌐 aiohttp web server berjalan di port 8080")

    # ── Jalankan Telegram polling serentak dengan aiohttp ─────────
    logger.info("🚀 FitJejak Bot sedang berjalan...")
    async with app:
        await app.start()
        await app.updater.start_polling(allowed_updates=["message", "callback_query"])

        # Tunggu sampai bot dihenti (Ctrl+C atau Railway stop)
        try:
            await asyncio.Event().wait()
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            await app.updater.stop()
            await app.stop()
            await runner.cleanup()



async def _handle_reset(update, context):
    """Clear semua pending state — selesaikan masalah bot stuck."""
    context.user_data.clear()
    await update.message.reply_text(
        "✅ Bot dah reset. Cuba hantar gambar makanan semula.",
        reply_markup=MAIN_KEYBOARD
    )


async def _handle_log_manual_button(update, context):
    """User tekan button ✍️ Log Manual — tunjuk cara guna."""
    await update.message.reply_text(
        "✍️ Log Manual (Percuma)\n\n"
        "Taip nama makanan + kalori:\n\n"
        "Contoh:\n"
        "• nasi lemak 650 kalori\n"
        "• whey protein 130 kcal\n"
        "• roti bakar 200kal\n\n"
        "Hantar sekarang! 👇"
    )


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
    asyncio.run(main())
