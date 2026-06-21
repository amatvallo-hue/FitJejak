"""
handlers/edit_profile.py — FitJejak
Handler untuk edit profil pengguna dari /profile.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
)
import database as db
from utils.nutrition import calculate_targets

# ── States ────────────────────────────────────────────────────────
EDIT_PROFILE_CHOOSE = 30
EDIT_PROFILE_VALUE  = 31

FIELD_LABELS = {
    "weight":   "⚖️ Berat (kg)",
    "height":   "📏 Tinggi (cm)",
    "age":      "🎂 Umur",
    "activity": "🏃 Tahap Aktiviti",
    "goal":     "🎯 Sasaran",
}


async def show_edit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tunjuk menu pilih apa nak edit."""
    query = update.callback_query
    await query.answer()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚖️ Berat",          callback_data="ep_weight")],
        [InlineKeyboardButton("📏 Tinggi",          callback_data="ep_height")],
        [InlineKeyboardButton("🎂 Umur",            callback_data="ep_age")],
        [InlineKeyboardButton("🏃 Tahap Aktiviti",  callback_data="ep_activity")],
        [InlineKeyboardButton("🎯 Sasaran",         callback_data="ep_goal")],
        [InlineKeyboardButton("❌ Batal",           callback_data="ep_cancel")],
    ])

    await query.message.reply_text(
        "✏️ Apa yang nak ditukar?",
        reply_markup=keyboard
    )
    return EDIT_PROFILE_CHOOSE


async def choose_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pilihan field yang nak diedit."""
    query = update.callback_query
    await query.answer()

    field = query.data.replace("ep_", "")

    if field == "cancel":
        await query.message.reply_text("Dibatalkan.")
        return ConversationHandler.END

    context.user_data["edit_profile_field"] = field

    if field == "weight":
        await query.message.reply_text(
            "⚖️ Masukkan berat baru (kg):\n\nContoh: 75"
        )
    elif field == "height":
        await query.message.reply_text(
            "📏 Masukkan tinggi baru (cm):\n\nContoh: 170"
        )
    elif field == "age":
        await query.message.reply_text(
            "🎂 Masukkan umur baru:\n\nContoh: 28"
        )
    elif field == "activity":
        keyboard = [
            ["😴 Tidak aktif (duduk sahaja)"],
            ["🚶 Ringan (senaman 1-3x seminggu)"],
            ["🏃 Sederhana (senaman 3-5x seminggu)"],
            ["💪 Aktif (senaman 6-7x seminggu)"],
            ["🔥 Sangat aktif (kerja fizikal/athlete)"]
        ]
        await query.message.reply_text(
            "🏃 Pilih tahap aktiviti baru:",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        )
    elif field == "goal":
        keyboard = [
            ["🔥 Turunkan berat badan"],
            ["⚖️ Kekalkan berat badan"],
            ["💪 Naikkan otot"]
        ]
        await query.message.reply_text(
            "🎯 Pilih sasaran baru:",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        )

    return EDIT_PROFILE_VALUE


async def save_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Terima nilai baru, simpan, kira semula target."""
    field = context.user_data.get("edit_profile_field")
    text  = update.message.text.strip()
    telegram_id = update.effective_user.id

    user = db.get_user(telegram_id)
    if not user:
        await update.message.reply_text("⚠️ Profil tidak dijumpai.")
        return ConversationHandler.END

    # ── Validate & parse input ────────────────────────────────────
    update_kwargs = {}

    if field == "weight":
        try:
            val = float(text.replace("kg", ""))
            if not (20 <= val <= 300): raise ValueError
        except ValueError:
            await update.message.reply_text("⚠️ Berat tidak sah. Cuba lagi.\nContoh: 75")
            return EDIT_PROFILE_VALUE
        update_kwargs["weight_kg"] = val
        db.log_weight(telegram_id, val)

    elif field == "height":
        try:
            val = float(text.replace("cm", ""))
            if not (100 <= val <= 250): raise ValueError
        except ValueError:
            await update.message.reply_text("⚠️ Tinggi tidak sah. Cuba lagi.\nContoh: 170")
            return EDIT_PROFILE_VALUE
        update_kwargs["height_cm"] = val

    elif field == "age":
        try:
            val = int(text)
            if not (10 <= val <= 100): raise ValueError
        except ValueError:
            await update.message.reply_text("⚠️ Umur tidak sah. Cuba lagi.\nContoh: 28")
            return EDIT_PROFILE_VALUE
        update_kwargs["age"] = val

    elif field == "activity":
        activity_map = {
            "😴 tidak aktif (duduk sahaja)": "sedentary",
            "🚶 ringan (senaman 1-3x seminggu)": "light",
            "🏃 sederhana (senaman 3-5x seminggu)": "moderate",
            "💪 aktif (senaman 6-7x seminggu)": "active",
            "🔥 sangat aktif (kerja fizikal/athlete)": "very_active"
        }
        val = activity_map.get(text.lower())
        if not val:
            await update.message.reply_text("⚠️ Sila pilih dari pilihan yang ada.")
            return EDIT_PROFILE_VALUE
        update_kwargs["activity_level"] = val

    elif field == "goal":
        goal_map = {
            "🔥 turunkan berat badan": "turun_berat",
            "⚖️ kekalkan berat badan": "kekal",
            "💪 naikkan otot": "naik_otot"
        }
        val = goal_map.get(text.lower())
        if not val:
            await update.message.reply_text("⚠️ Sila pilih dari pilihan yang ada.")
            return EDIT_PROFILE_VALUE
        update_kwargs["goal"] = val

    # ── Kira semula target dengan nilai terbaru ───────────────────
    merged = {**user, **update_kwargs}
    target_calories, target_protein, target_carbs, target_fat = calculate_targets(
        merged["weight_kg"],
        merged["height_cm"],
        merged["age"],
        merged["gender"],
        merged["activity_level"],
        merged["goal"]
    )
    update_kwargs["target_calories"] = target_calories
    update_kwargs["target_protein"]  = target_protein
    update_kwargs["target_carbs"]    = target_carbs
    update_kwargs["target_fat"]      = target_fat

    db.update_user_profile(telegram_id, **update_kwargs)

    field_label = FIELD_LABELS.get(field, field)

    await update.message.reply_text(
        f"✅ {field_label} berjaya dikemaskini!\n\n"
        f"📊 Target harian dikira semula:\n"
        f"🔥 Kalori:  {target_calories:,} kcal\n"
        f"🥩 Protein: {target_protein}g\n"
        f"🍚 Karbo:   {target_carbs}g\n"
        f"🧈 Lemak:   {target_fat}g\n\n"
        f"Taip /profile untuk tengok profil terkini.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


async def cancel_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Dibatalkan.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def get_edit_profile_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(show_edit_menu, pattern="^edit_profile_menu$")],
        states={
            EDIT_PROFILE_CHOOSE: [
                CallbackQueryHandler(choose_field, pattern="^ep_")
            ],
            EDIT_PROFILE_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_edit)
            ],
        },
        fallbacks=[
            MessageHandler(filters.COMMAND, cancel_edit)
        ],
        allow_reentry=True
    )
