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
EDIT_PROFILE_CHOOSE  = 30
EDIT_PROFILE_VALUE   = 31
MANUAL_ASK_CALORIES  = 32
MANUAL_ASK_PROTEIN   = 33
MANUAL_ASK_CARBS     = 34
MANUAL_ASK_FAT       = 35
MANUAL_CHOOSE_FIELD  = 36   # Pilih target mana nak set
MANUAL_SINGLE_VALUE  = 37   # Input satu nilai sahaja

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
        [InlineKeyboardButton("⚖️ Berat",             callback_data="ep_weight")],
        [InlineKeyboardButton("📏 Tinggi",             callback_data="ep_height")],
        [InlineKeyboardButton("🎂 Umur",               callback_data="ep_age")],
        [InlineKeyboardButton("🏃 Tahap Aktiviti",     callback_data="ep_activity")],
        [InlineKeyboardButton("🎯 Sasaran",            callback_data="ep_goal")],
        [InlineKeyboardButton("🔢 Set Target Manual",  callback_data="ep_manual")],
        [InlineKeyboardButton("❌ Batal",              callback_data="ep_cancel")],
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

    # ── Manual target flow ────────────────────────────────────────
    if field == "manual":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔥 Kalori sahaja",  callback_data="mt_calories")],
            [InlineKeyboardButton("🥩 Protein sahaja", callback_data="mt_protein")],
            [InlineKeyboardButton("🍚 Karbo sahaja",   callback_data="mt_carbs")],
            [InlineKeyboardButton("🧈 Lemak sahaja",   callback_data="mt_fat")],
            [InlineKeyboardButton("📊 Set Semua",      callback_data="mt_all")],
            [InlineKeyboardButton("❌ Batal",          callback_data="mt_cancel")],
        ])
        await query.message.reply_text(
            "🔢 Set Target Manual\n\n"
            "Nak set yang mana?\n"
            "Yang tak diset akan ikut formula automatik.",
            reply_markup=keyboard
        )
        return MANUAL_CHOOSE_FIELD

    context.user_data["edit_profile_field"] = field

    if field == "weight":
        await query.message.reply_text("⚖️ Masukkan berat baru (kg):\n\nContoh: 75")
    elif field == "height":
        await query.message.reply_text("📏 Masukkan tinggi baru (cm):\n\nContoh: 170")
    elif field == "age":
        await query.message.reply_text("🎂 Masukkan umur baru:\n\nContoh: 28")
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


# ── Manual target: pilih field mana ──────────────────────────────

_SINGLE_CONFIG = {
    "calories": ("🔥 Kalori",  "target_calories", "kcal", 500,  10000, "Contoh: 2200"),
    "protein":  ("🥩 Protein", "target_protein",  "g",    0,    1000,  "Contoh: 180"),
    "carbs":    ("🍚 Karbo",   "target_carbs",    "g",    0,    2000,  "Contoh: 250"),
    "fat":      ("🧈 Lemak",   "target_fat",      "g",    0,    500,   "Contoh: 70"),
}

async def manual_choose_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pilihan target mana nak set."""
    query = update.callback_query
    await query.answer()

    target = query.data.replace("mt_", "")

    if target == "cancel":
        await query.message.reply_text("Dibatalkan.")
        return ConversationHandler.END

    if target == "all":
        await query.message.reply_text(
            "📊 Set Semua Target\n\n"
            "Masukkan target kalori harian:\n\nContoh: 2200"
        )
        return MANUAL_ASK_CALORIES

    # Single field
    label, _, unit, lo, hi, example = _SINGLE_CONFIG[target]
    context.user_data["manual_single_field"] = target
    await query.message.reply_text(
        f"🔢 Set {label}\n\n"
        f"Masukkan nilai ({unit}):\n\n{example}"
    )
    return MANUAL_SINGLE_VALUE


async def manual_save_single(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simpan satu nilai target sahaja."""
    field = context.user_data.pop("manual_single_field", None)
    if not field:
        return ConversationHandler.END

    label, db_col, unit, lo, hi, example = _SINGLE_CONFIG[field]

    try:
        val = float(update.message.text.strip())
        if not (lo <= val <= hi):
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            f"⚠️ Nilai tidak sah. {example}\n(Antara {lo}–{hi})"
        )
        context.user_data["manual_single_field"] = field
        return MANUAL_SINGLE_VALUE

    db.update_user_profile(update.effective_user.id, **{db_col: round(val)})

    await update.message.reply_text(
        f"✅ {label} berjaya dikemaskini: {round(val)}{unit}\n\n"
        f"Target lain kekal seperti sebelum.\n"
        f"Taip /profile untuk tengok semua target."
    )
    return ConversationHandler.END


# ── Manual target: 4 soalan berturut ─────────────────────────────

async def manual_ask_protein(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Terima kalori, tanya protein."""
    try:
        val = float(update.message.text.strip())
        if not (500 <= val <= 10000): raise ValueError
    except ValueError:
        await update.message.reply_text("⚠️ Nilai tidak sah. Masukkan kalori antara 500-10000.\nContoh: 2200")
        return MANUAL_ASK_CALORIES

    context.user_data["manual_calories"] = round(val)
    await update.message.reply_text(
        f"✅ Kalori: {round(val)} kcal\n\n"
        f"🥩 Masukkan target protein (gram):\n\nContoh: 180"
    )
    return MANUAL_ASK_PROTEIN


async def manual_ask_carbs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Terima protein, tanya karbo."""
    try:
        val = float(update.message.text.strip())
        if not (0 <= val <= 1000): raise ValueError
    except ValueError:
        await update.message.reply_text("⚠️ Nilai tidak sah. Contoh: 180")
        return MANUAL_ASK_PROTEIN

    context.user_data["manual_protein"] = round(val)
    await update.message.reply_text(
        f"✅ Protein: {round(val)}g\n\n"
        f"🍚 Masukkan target karbohidrat (gram):\n\nContoh: 250"
    )
    return MANUAL_ASK_CARBS


async def manual_ask_fat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Terima karbo, tanya lemak."""
    try:
        val = float(update.message.text.strip())
        if not (0 <= val <= 2000): raise ValueError
    except ValueError:
        await update.message.reply_text("⚠️ Nilai tidak sah. Contoh: 250")
        return MANUAL_ASK_CARBS

    context.user_data["manual_carbs"] = round(val)
    await update.message.reply_text(
        f"✅ Karbo: {round(val)}g\n\n"
        f"🧈 Masukkan target lemak (gram):\n\nContoh: 70"
    )
    return MANUAL_ASK_FAT


async def manual_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Terima lemak, simpan semua target manual."""
    try:
        val = float(update.message.text.strip())
        if not (0 <= val <= 500): raise ValueError
    except ValueError:
        await update.message.reply_text("⚠️ Nilai tidak sah. Contoh: 70")
        return MANUAL_ASK_FAT

    telegram_id = update.effective_user.id
    cal  = context.user_data.pop("manual_calories")
    pro  = context.user_data.pop("manual_protein")
    carb = context.user_data.pop("manual_carbs")
    fat  = round(val)

    db.update_user_profile(
        telegram_id,
        target_calories=cal,
        target_protein=pro,
        target_carbs=carb,
        target_fat=fat
    )

    await update.message.reply_text(
        f"✅ Target manual berjaya disimpan!\n\n"
        f"📊 Target Harian Anda:\n"
        f"🔥 Kalori:  {cal:,} kcal\n"
        f"🥩 Protein: {pro}g\n"
        f"🍚 Karbo:   {carb}g\n"
        f"🧈 Lemak:   {fat}g\n\n"
        f"Taip /profile untuk tengok profil terkini."
    )
    return ConversationHandler.END


# ── Profile fields save ───────────────────────────────────────────

async def save_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Terima nilai baru, simpan, kira semula target."""
    field = context.user_data.get("edit_profile_field")
    text  = update.message.text.strip()
    telegram_id = update.effective_user.id

    user = db.get_user(telegram_id)
    if not user:
        await update.message.reply_text("⚠️ Profil tidak dijumpai.")
        return ConversationHandler.END

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

    # Kira semula target
    merged = {**user, **update_kwargs}
    target_calories, target_protein, target_carbs, target_fat = calculate_targets(
        merged["weight_kg"], merged["height_cm"], merged["age"],
        merged["gender"], merged["activity_level"], merged["goal"]
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


_KEYBOARD_BUTTONS = filters.Regex(
    r"^(📊 Hari Ini|📋 History|📈 Summary|⚖️ Berat|💳 Topup|🔗 Referral|👤 Profil|❓ Help|📸 Scan Badan|✍️ Log Manual)$"
)

async def cancel_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "⚠️ Edit profil dibatalkan. Cuba semula.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


def get_edit_profile_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(show_edit_menu, pattern="^edit_profile_menu$")],
        states={
            EDIT_PROFILE_CHOOSE: [
                CallbackQueryHandler(choose_field, pattern="^ep_")
            ],
            EDIT_PROFILE_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~_KEYBOARD_BUTTONS, save_edit)
            ],
            MANUAL_CHOOSE_FIELD: [
                CallbackQueryHandler(manual_choose_field, pattern="^mt_")
            ],
            MANUAL_SINGLE_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~_KEYBOARD_BUTTONS, manual_save_single)
            ],
            MANUAL_ASK_CALORIES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~_KEYBOARD_BUTTONS, manual_ask_protein)
            ],
            MANUAL_ASK_PROTEIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~_KEYBOARD_BUTTONS, manual_ask_carbs)
            ],
            MANUAL_ASK_CARBS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~_KEYBOARD_BUTTONS, manual_ask_fat)
            ],
            MANUAL_ASK_FAT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~_KEYBOARD_BUTTONS, manual_save)
            ],
        },
        fallbacks=[
            MessageHandler(filters.COMMAND | _KEYBOARD_BUTTONS, cancel_edit)
        ],
        allow_reentry=True
    )
