"""
handlers/manual_food.py — FitJejak
Rekod makanan manual melalui conversation step-by-step.

Flow:
1. User hantar teks dengan kalori → bot capture
2. Bot tanya protein → user jawab atau Skip
3. Bot tanya karbohidrat → user jawab atau Skip
4. Bot tanya lemak → user jawab atau Skip
5. Bot simpan dan tunjuk summary
"""
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler,
    MessageHandler, CallbackQueryHandler, filters
)
import database as db
from utils.nutrition import get_progress_bar

# ── States ────────────────────────────────────────────────────────
ASK_PROTEIN = 10
ASK_CARBS   = 11
ASK_FAT     = 12

# ── Keyboard Skip ─────────────────────────────────────────────────
SKIP_KEYBOARD = InlineKeyboardMarkup([[
    InlineKeyboardButton("Langkau ⏭️", callback_data="skip")
]])


def detect_calories(text: str):
    """
    Detect kalori dalam teks.
    Return (food_name, calories) atau None jika tiada.
    """
    text_lower = text.lower()
    cal_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:kal(?:ori)?|kcal|cal)', text_lower)
    if not cal_match:
        return None

    calories = float(cal_match.group(1))

    # Nama makanan — buang bahagian kalori
    food_name = re.sub(
        r'\d+(?:\.\d+)?\s*(?:kal(?:ori)?|kcal|cal)',
        '', text, flags=re.IGNORECASE
    ).strip(" ,.-")
    food_name = food_name.title() if food_name else "Makanan"

    return food_name, calories


# ── Step 1: Entry — detect kalori ─────────────────────────────────

async def start_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point — user hantar teks dengan kalori."""
    text = update.message.text.strip()
    result = detect_calories(text)

    if result is None:
        # Bukan format manual — tunjuk panduan
        await update.message.reply_text(
            "📝 Untuk rekod manual (PERCUMA), sertakan kalori:\n\n"
            "Contoh:\n"
            "• lunch 600 kalori\n"
            "• nasi lemak 650kcal\n"
            "• dinner 500kal\n\n"
            "📸 Atau hantar GAMBAR untuk analisis AI."
        )
        return ConversationHandler.END

    food_name, calories = result

    # Semak profil
    user = db.get_user(update.effective_user.id)
    if not user or not user["setup_complete"]:
        await update.message.reply_text(
            "⚠️ Profil belum lengkap. Taip /start untuk setup."
        )
        return ConversationHandler.END

    # Simpan dalam session
    context.user_data["manual"] = {
        "food_name": food_name,
        "calories": calories,
        "protein_g": 0,
        "carbs_g": 0,
        "fat_g": 0,
    }

    await update.message.reply_text(
        f"✅ {food_name} — {int(calories)} kcal\n\n"
        f"🥩 Berapa gram protein?",
        reply_markup=SKIP_KEYBOARD
    )
    return ASK_PROTEIN


# ── Step 2: Protein ───────────────────────────────────────────────

async def ask_protein(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Terima jawapan protein dari teks."""
    text = update.message.text.strip()
    try:
        val = float(re.search(r'\d+(?:\.\d+)?', text).group())
        context.user_data["manual"]["protein_g"] = val
    except:
        await update.message.reply_text(
            "⚠️ Masukkan nombor sahaja. Contoh: 30\nAtau tekan Langkau.",
            reply_markup=SKIP_KEYBOARD
        )
        return ASK_PROTEIN

    await update.message.reply_text(
        f"✅ Protein: {val}g\n\n"
        f"🍚 Berapa gram karbohidrat?",
        reply_markup=SKIP_KEYBOARD
    )
    return ASK_CARBS


async def skip_protein(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip protein."""
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "⏭️ Protein dilangkau\n\n🍚 Berapa gram karbohidrat?",
        reply_markup=SKIP_KEYBOARD
    )
    return ASK_CARBS


# ── Step 3: Karbohidrat ───────────────────────────────────────────

async def ask_carbs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Terima jawapan karbohidrat dari teks."""
    text = update.message.text.strip()
    try:
        val = float(re.search(r'\d+(?:\.\d+)?', text).group())
        context.user_data["manual"]["carbs_g"] = val
    except:
        await update.message.reply_text(
            "⚠️ Masukkan nombor sahaja. Contoh: 60\nAtau tekan Langkau.",
            reply_markup=SKIP_KEYBOARD
        )
        return ASK_CARBS

    await update.message.reply_text(
        f"✅ Karbohidrat: {val}g\n\n"
        f"🧈 Berapa gram lemak?",
        reply_markup=SKIP_KEYBOARD
    )
    return ASK_FAT


async def skip_carbs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip karbohidrat."""
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "⏭️ Karbohidrat dilangkau\n\n🧈 Berapa gram lemak?",
        reply_markup=SKIP_KEYBOARD
    )
    return ASK_FAT


# ── Step 4: Lemak → Simpan ────────────────────────────────────────

async def ask_fat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Terima jawapan lemak dan simpan."""
    text = update.message.text.strip()
    try:
        val = float(re.search(r'\d+(?:\.\d+)?', text).group())
        context.user_data["manual"]["fat_g"] = val
    except:
        await update.message.reply_text(
            "⚠️ Masukkan nombor sahaja. Contoh: 20\nAtau tekan Langkau.",
            reply_markup=SKIP_KEYBOARD
        )
        return ASK_FAT

    return await _save_and_reply(update, context)


async def skip_fat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip lemak dan terus simpan."""
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("⏭️ Lemak dilangkau")
    return await _save_and_reply(update, context, from_callback=True)


# ── Simpan ke DB dan tunjuk result ───────────────────────────────

async def _save_and_reply(update, context, from_callback=False):
    """Simpan rekod dan hantar summary."""
    data = context.user_data.get("manual", {})
    telegram_id = update.effective_user.id

    db.log_food(
        telegram_id=telegram_id,
        food_name=data["food_name"],
        calories=data["calories"],
        protein_g=data["protein_g"],
        carbs_g=data["carbs_g"],
        fat_g=data["fat_g"],
        health_score=5,
        advice="Rekod manual",
        image_file_id=None
    )

    user = db.get_user(telegram_id)
    today = db.get_today_summary(telegram_id)
    target_cal = user["target_calories"] or 2000
    target_pro = user["target_protein"] or 160

    cal_bar = get_progress_bar(today["total_calories"], target_cal)
    pro_bar = get_progress_bar(today["total_protein"], target_pro)

    reply = (
        f"✅ {data['food_name']} direkod!\n\n"
        f"🔥 Kalori:  {int(data['calories'])} kcal\n"
    )
    if data["protein_g"]:
        reply += f"🥩 Protein: {data['protein_g']}g\n"
    if data["carbs_g"]:
        reply += f"🍚 Karbo:   {data['carbs_g']}g\n"
    if data["fat_g"]:
        reply += f"🧈 Lemak:   {data['fat_g']}g\n"

    reply += (
        f"\n━━━━━━━━━━━━━━━━\n"
        f"📊 Progress Hari Ini:\n"
        f"🔥 {cal_bar} ({int(today['total_calories'])}/{int(target_cal)} kcal)\n"
        f"🥩 {pro_bar} ({int(today['total_protein'])}/{int(target_pro)}g protein)\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📝 Rekod manual — scan tidak ditolak"
    )

    # Hantar ke chat yang betul
    if from_callback:
        await context.bot.send_message(chat_id=telegram_id, text=reply)
    else:
        await update.message.reply_text(reply)

    context.user_data.pop("manual", None)
    return ConversationHandler.END


# ── Cancel ────────────────────────────────────────────────────────

async def cancel_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("manual", None)
    await update.message.reply_text("❌ Rekod dibatalkan.")
    return ConversationHandler.END


# ── ConversationHandler ───────────────────────────────────────────

def get_manual_food_handler():
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & ~filters.COMMAND, start_manual)
        ],
        states={
            ASK_PROTEIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_protein),
                CallbackQueryHandler(skip_protein, pattern="^skip$"),
            ],
            ASK_CARBS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_carbs),
                CallbackQueryHandler(skip_carbs, pattern="^skip$"),
            ],
            ASK_FAT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_fat),
                CallbackQueryHandler(skip_fat, pattern="^skip$"),
            ],
        },
        fallbacks=[
            MessageHandler(filters.COMMAND, cancel_manual)
        ],
        per_user=True,
        per_chat=True,
    )
