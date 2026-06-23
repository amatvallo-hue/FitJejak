"""
handlers/affiliate_apply.py — FitJejak
ConversationHandler untuk permohonan affiliate.
Flow: /apply → bank name → no akaun → hantar ke admin untuk kelulusan
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CommandHandler, MessageHandler, filters
)
import database as db
from config import ADMIN_TELEGRAM_ID

# States
ASK_BANK_NAME, ASK_BANK_ACC = range(2)

_KEYBOARD_BUTTONS = filters.Regex(
    r"^(📊 Hari Ini|📋 History|📈 Summary|⚖️ Berat|💳 Topup|🔗 Referral|👤 Profil|❓ Help|📸 Scan Badan|✍️ Log Manual)$"
)


async def apply_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Mula proses permohonan affiliate."""
    telegram_id = update.effective_user.id

    # Semak dah setup profil
    user = db.get_user(telegram_id)
    if not user or not user["setup_complete"]:
        await update.message.reply_text(
            "⚠️ Sila lengkapkan setup profil dulu.\nTaip /start untuk mula."
        )
        return ConversationHandler.END

    # Semak dah jadi affiliate
    existing = db.get_affiliate(telegram_id)
    if existing and existing["status"] == "active":
        await update.message.reply_text(
            "✅ Anda sudah pun menjadi affiliate FitJejak!\n\n"
            "Taip /affiliate untuk tengok dashboard anda."
        )
        return ConversationHandler.END

    # Semak ada pending application
    if db.has_pending_affiliate_application(telegram_id):
        await update.message.reply_text(
            "⏳ Permohonan anda sedang dalam semakan admin.\n\n"
            "Sila tunggu. Anda akan dimaklumkan sebaik keputusan dibuat."
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "💼 Permohonan Affiliate FitJejak\n\n"
        "Sebagai affiliate, anda akan dapat 5% komisyen daripada setiap topup "
        "yang dilakukan oleh pengguna yang mendaftar melalui link referral anda.\n\n"
        "Bayaran dibuat setiap awal bulan ke akaun bank anda.\n\n"
        "━━━━━━━━━━━━━━━━\n"
        "Langkah 1/2: Nama bank anda?\n\n"
        "Contoh: Maybank, CIMB, RHB, Public Bank, BSN"
    )
    return ASK_BANK_NAME


async def ask_bank_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Terima nama bank."""
    bank_name = update.message.text.strip()

    if len(bank_name) < 2 or len(bank_name) > 50:
        await update.message.reply_text(
            "⚠️ Nama bank tidak sah. Sila masukkan semula.\nContoh: Maybank"
        )
        return ASK_BANK_NAME

    context.user_data["aff_bank_name"] = bank_name

    await update.message.reply_text(
        f"✅ Bank: {bank_name}\n\n"
        "Langkah 2/2: Nombor akaun bank anda?\n\n"
        "Contoh: 1234567890"
    )
    return ASK_BANK_ACC


async def ask_bank_acc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Terima no akaun, simpan permohonan, hantar ke admin."""
    bank_acc = update.message.text.strip().replace(" ", "").replace("-", "")

    if not bank_acc.isdigit() or len(bank_acc) < 6 or len(bank_acc) > 20:
        await update.message.reply_text(
            "⚠️ No akaun tidak sah (nombor sahaja, 6-20 digit).\n"
            "Contoh: 1234567890"
        )
        return ASK_BANK_ACC

    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)
    bank_name = context.user_data.get("aff_bank_name", "-")

    # Simpan ke DB
    app_id = db.save_affiliate_application(telegram_id, bank_name, bank_acc)

    # Hantar ke admin untuk kelulusan
    name = user["first_name"] or str(telegram_id)
    username = f"@{user['username']}" if user.get("username") else "tiada username"

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Luluskan", callback_data=f"aff_approv_{app_id}"),
        InlineKeyboardButton("❌ Tolak",    callback_data=f"aff_reject_{app_id}"),
    ]])

    try:
        await context.bot.send_message(
            chat_id=ADMIN_TELEGRAM_ID,
            text=(
                f"📋 PERMOHONAN AFFILIATE BARU\n\n"
                f"👤 {name} ({username})\n"
                f"🆔 ID: {telegram_id}\n"
                f"📊 Topup sebelum ini: {user.get('topup_count') or 0}x\n\n"
                f"🏦 Bank: {bank_name}\n"
                f"💳 No Akaun: {bank_acc}\n\n"
                f"Kadar komisyen: 5%"
            ),
            reply_markup=keyboard
        )
    except Exception:
        pass

    await update.message.reply_text(
        "✅ Permohonan anda telah dihantar!\n\n"
        f"🏦 Bank: {bank_name}\n"
        f"💳 Akaun: {bank_acc}\n\n"
        "⏳ Admin akan semak dan anda akan dimaklumkan sebaik keputusan dibuat.\n"
        "Biasanya dalam masa 1-2 hari bekerja."
    )
    context.user_data.pop("aff_bank_name", None)
    return ConversationHandler.END


async def cancel_apply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Batalkan permohonan."""
    context.user_data.pop("aff_bank_name", None)
    await update.message.reply_text("❌ Permohonan dibatalkan.")
    return ConversationHandler.END


def get_affiliate_apply_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("apply", apply_start)],
        states={
            ASK_BANK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~_KEYBOARD_BUTTONS, ask_bank_name)],
            ASK_BANK_ACC:  [MessageHandler(filters.TEXT & ~filters.COMMAND & ~_KEYBOARD_BUTTONS, ask_bank_acc)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_apply),
            MessageHandler(filters.COMMAND | _KEYBOARD_BUTTONS, cancel_apply),
        ],
        allow_reentry=True
    )
