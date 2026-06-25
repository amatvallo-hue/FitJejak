"""
handlers/manual_food.py — FitJejak
Rekod makanan manual — kalori sahaja (percuma).
Protein/karbo/lemak hanya via scan AI.
"""
import re
from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler,
    MessageHandler, filters
)
import database as db
from utils.nutrition import get_nutrient_bar


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

    food_name = re.sub(
        r'\d+(?:\.\d+)?\s*(?:kal(?:ori)?|kcal|cal)',
        '', text, flags=re.IGNORECASE
    ).strip(" ,.-")
    food_name = food_name.title() if food_name else "Makanan"

    return food_name, calories


async def start_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point — user hantar teks dengan kalori, terus simpan."""
    # Jika user tengah dalam exercise flow, redirect ke exercise handler
    if context.user_data.get("waiting_exercise_cal"):
        from handlers.tracking import handle_exercise_input
        await handle_exercise_input(update, context)
        return ConversationHandler.END

    text = update.message.text.strip()
    result = detect_calories(text)

    if result is None:
        await update.message.reply_text(
            "📝 Untuk rekod manual (PERCUMA), sertakan kalori:\n\n"
            "Contoh:\n"
            "• lunch 600 kalori\n"
            "• nasi lemak 650kcal\n"
            "• dinner 500kal\n\n"
            "📸 Atau hantar GAMBAR untuk analisis AI penuh."
        )
        return ConversationHandler.END

    food_name, calories = result

    user = db.get_user(update.effective_user.id)
    if not user or not user["setup_complete"]:
        await update.message.reply_text(
            "⚠️ Profil belum lengkap. Taip /start untuk setup."
        )
        return ConversationHandler.END

    telegram_id = update.effective_user.id

    # Simpan kalori sahaja — protein/karbo/lemak = 0
    db.log_food(
        telegram_id=telegram_id,
        food_name=food_name,
        calories=calories,
        protein_g=0,
        carbs_g=0,
        fat_g=0,
        health_score=5,
        advice="Rekod manual",
        image_file_id=None
    )

    today      = db.get_today_summary(telegram_id)
    target_cal = user["target_calories"] or 2000
    cal_bar    = get_nutrient_bar(today["total_calories"], target_cal, " kcal")
    remaining  = user["scans_remaining"]

    reply = (
        f"✅ {food_name} direkod!\n"
        f"🔥 {int(calories)} kcal\n\n"
        f"📊 Kalori Hari Ini:\n"
        f"{cal_bar}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💡 Nak track protein, karbo & lemak?\n"
        f"Scan gambar makanan untuk data lengkap!\n"
        f"Baki scan: {remaining}"
    )

    await update.message.reply_text(reply)
    return ConversationHandler.END


async def cancel_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("manual", None)
    await update.message.reply_text("❌ Rekod dibatalkan.")
    return ConversationHandler.END


def get_manual_food_handler():
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & ~filters.COMMAND, start_manual)
        ],
        states={},
        fallbacks=[
            MessageHandler(filters.COMMAND, cancel_manual)
        ],
        per_user=True,
        per_chat=True,
    )
