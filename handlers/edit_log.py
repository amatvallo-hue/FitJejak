"""
handlers/edit_log.py — FitJejak
Edit rekod makanan yang salah.

Flow:
1. User klik butang Edit dari /history
2. Bot tunjuk field yang boleh diedit
3. User pilih field
4. User masukkan nilai baru
5. Bot kemaskini dan confirm
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
import database as db

# ── States ────────────────────────────────────────────────────────
EDIT_CHOOSE_FIELD = 20
EDIT_ENTER_VALUE  = 21

# Field label untuk display
FIELD_LABELS = {
    "food_name": "Nama Makanan",
    "calories":  "Kalori (kcal)",
    "protein_g": "Protein (g)",
    "carbs_g":   "Karbohidrat (g)",
    "fat_g":     "Lemak (g)",
}


async def start_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User klik butang Edit — tunjuk pilihan field."""
    query = update.callback_query
    await query.answer()

    log_id = int(query.data.replace("edit_", ""))
    telegram_id = update.effective_user.id

    log = db.get_food_log(log_id, telegram_id)
    if not log:
        await query.edit_message_text("⚠️ Rekod tidak dijumpai.")
        return ConversationHandler.END

    context.user_data["edit"] = {"log_id": log_id}

    keyboard = [
        [InlineKeyboardButton("🍽 Nama Makanan", callback_data="field_food_name")],
        [InlineKeyboardButton("🔥 Kalori",       callback_data="field_calories")],
        [InlineKeyboardButton("🥩 Protein",      callback_data="field_protein_g")],
        [InlineKeyboardButton("🍚 Karbohidrat",  callback_data="field_carbs_g")],
        [InlineKeyboardButton("🧈 Lemak",        callback_data="field_fat_g")],
        [InlineKeyboardButton("❌ Batal",         callback_data="field_cancel")],
    ]

    await query.edit_message_text(
        f"✏️ Edit: {log['food_name']}\n\n"
        f"🔥 Kalori:  {int(log['calories'])} kcal\n"
        f"🥩 Protein: {log['protein_g']}g\n"
        f"🍚 Karbo:   {log['carbs_g']}g\n"
        f"🧈 Lemak:   {log['fat_g']}g\n\n"
        f"Pilih field yang nak diedit:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return EDIT_CHOOSE_FIELD


async def choose_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User pilih field → tanya nilai baru."""
    query = update.callback_query
    await query.answer()

    data = query.data  # "field_calories", "field_protein_g", etc.

    if data == "field_cancel":
        await query.edit_message_text("❌ Edit dibatalkan.")
        context.user_data.pop("edit", None)
        return ConversationHandler.END

    field = data.replace("field_", "")
    context.user_data["edit"]["field"] = field
    label = FIELD_LABELS.get(field, field)

    await query.edit_message_text(
        f"✏️ Edit {label}\n\n"
        f"Masukkan nilai baru:"
    )
    return EDIT_ENTER_VALUE


async def enter_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User masukkan nilai baru → kemaskini DB."""
    text = update.message.text.strip()
    edit_data = context.user_data.get("edit", {})
    log_id = edit_data.get("log_id")
    field = edit_data.get("field")
    telegram_id = update.effective_user.id

    if not log_id or not field:
        await update.message.reply_text("⚠️ Sesi tamat. Cuba semula dengan /history.")
        return ConversationHandler.END

    # Validate dan convert nilai
    if field == "food_name":
        value = text
    else:
        try:
            value = float(text.replace("g", "").replace("kcal", "").strip())
            if value < 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "⚠️ Masukkan nombor yang sah. Contoh: 350\nCuba lagi:"
            )
            return EDIT_ENTER_VALUE

    updated = db.update_food_log(log_id, telegram_id, field, value)

    if updated:
        label = FIELD_LABELS.get(field, field)
        display = f"{int(value)} kcal" if field == "calories" else f"{value}g" if field != "food_name" else value
        await update.message.reply_text(
            f"✅ Berjaya dikemaskini!\n\n"
            f"{label}: {display}\n\n"
            f"Taip /history untuk lihat semula."
        )
    else:
        await update.message.reply_text("⚠️ Gagal kemaskini. Cuba semula.")

    context.user_data.pop("edit", None)
    return ConversationHandler.END


async def cancel_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("edit", None)
    await update.message.reply_text("❌ Edit dibatalkan.")
    return ConversationHandler.END


def get_edit_handler():
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_edit, pattern="^edit_\\d+$")
        ],
        states={
            EDIT_CHOOSE_FIELD: [
                CallbackQueryHandler(choose_field, pattern="^field_")
            ],
            EDIT_ENTER_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_value)
            ],
        },
        fallbacks=[
            MessageHandler(filters.COMMAND, cancel_edit)
        ],
        per_user=True,
        per_chat=True,
    )
