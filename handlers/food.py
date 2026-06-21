"""
handlers/food.py — FitJejak
Handler untuk analisis gambar makanan yang dihantar pengguna.
"""
from telegram import Update
from telegram.ext import ContextTypes
import database as db
from ai_analyzer import analyze_food_image
from utils.nutrition import get_health_score_emoji, get_progress_bar


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Dipanggil bila pengguna hantar gambar.
    1. Semak profil dan baki scan
    2. Download gambar
    3. Hantar ke AI
    4. Simpan ke database
    5. Reply dengan keputusan
    """
    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)

    # ── Semak sama ada pengguna dah setup profil ─────────────────
    if not user or not user["setup_complete"]:
        await update.message.reply_text(
            "⚠️ Profil anda belum lengkap.\n"
            "Sila taip /start untuk mula setup."
        )
        return

    # ── Semak baki scan ──────────────────────────────────────────
    if user["scans_remaining"] <= 0:
        await update.message.reply_text(
            "❌ *Scan anda telah habis\\!*\n\n"
            "Top up kredit untuk teruskan menggunakan FitJejak\\.\n"
            "Taip /topup untuk lihat pakej kredit\\.",
            parse_mode="MarkdownV2"
        )
        return

    # ── Tunjuk "sedang menganalisis..." ──────────────────────────
    processing_msg = await update.message.reply_text(
        "🔍 Menganalisis makanan anda...\nIni ambil masa 5-10 saat"
    )

    # ── Download gambar dari Telegram ────────────────────────────
    # Ambil resolusi tertinggi yang tersedia
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    image_bytes = await file.download_as_bytearray()

    # ── Hantar ke AI untuk analisis ──────────────────────────────
    result = await analyze_food_image(bytes(image_bytes))

    # Padam mesej "sedang menganalisis"
    await processing_msg.delete()

    # ── Handle error dari AI ─────────────────────────────────────
    if "error" in result:
        await update.message.reply_text(
            f"⚠️ {result['error']}\n\n"
            "Sila cuba:\n"
            "• Gambar yang lebih terang\n"
            "• Gambar dari atas (bird's eye view)\n"
            "• Pastikan makanan nampak jelas"
        )
        return

    # ── Tolak 1 scan ─────────────────────────────────────────────
    db.deduct_scan(telegram_id)

    # ── Simpan log makanan ───────────────────────────────────────
    db.log_food(
        telegram_id=telegram_id,
        food_name=result["food_name"],
        calories=result["calories"],
        protein_g=result["protein_g"],
        carbs_g=result["carbs_g"],
        fat_g=result["fat_g"],
        health_score=result["health_score"],
        advice=result["advice"],
        image_file_id=photo.file_id
    )

    # ── Dapatkan summary hari ini untuk progress ─────────────────
    today = db.get_today_summary(telegram_id)
    user_fresh = db.get_user(telegram_id)  # Refresh untuk baki scan terkini

    target_cal = user["target_calories"] or 2000
    target_pro = user["target_protein"] or 160

    cal_progress = get_progress_bar(today["total_calories"], target_cal)
    pro_progress = get_progress_bar(today["total_protein"], target_pro)
    score_emoji = get_health_score_emoji(int(result["health_score"]))

    # ── Bina reply mesej ─────────────────────────────────────────
    remaining = user_fresh["scans_remaining"]
    remaining_text = f"Baki scan: {remaining}" if remaining > 5 else f"⚠️ Baki scan: {remaining} — /topup"

    reply = (
        f"✅ {result['food_name']}\n\n"
        f"🔥 Kalori:      {int(result['calories'])} kcal\n"
        f"🥩 Protein:     {result['protein_g']}g\n"
        f"🍚 Karbohidrat: {result['carbs_g']}g\n"
        f"🧈 Lemak:       {result['fat_g']}g\n"
        f"{score_emoji} Health Score: {int(result['health_score'])}/10\n\n"
        f"💡 {result['advice']}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📊 Progress Hari Ini:\n"
        f"🔥 Kalori:  {cal_progress} ({int(today['total_calories'])}/{int(target_cal)} kcal)\n"
        f"🥩 Protein: {pro_progress} ({int(today['total_protein'])}/{int(target_pro)}g)\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"{remaining_text}"
    )

    await update.message.reply_text(reply)


