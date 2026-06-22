"""
handlers/food.py — FitJejak
Handler untuk analisis gambar makanan yang dihantar pengguna.
"""
from telegram import Update
from telegram.ext import ContextTypes
import database as db
import re
from ai_analyzer import analyze_food_image
from utils.nutrition import get_health_score_emoji, get_progress_bar
from handlers.topup import handle_payment_slip
from handlers.body_scan import handle_body_scan_photo


def _get_streak_text(streak: int) -> str:
    """Return teks streak yang sesuai."""
    if streak == 0 or streak == 1:
        return "🔥 Streak: 1 hari — mula yang bagus!"
    elif streak == 3:
        return f"🔥 Streak: {streak} hari — dah 3 hari! Teruskan! 💪"
    elif streak == 7:
        return f"🔥 Streak: {streak} hari — SEMINGGU penuh! Luar biasa! 🏆"
    elif streak == 14:
        return f"🔥 Streak: {streak} hari — 2 minggu berturut-turut! Awak serius ni! 🌟"
    elif streak == 30:
        return f"🔥 Streak: {streak} hari — SEBULAN! Awak legend! 👑"
    elif streak > 1:
        return f"🔥 Streak: {streak} hari berturut-turut!"
    return ""


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

    # ── Semak dulu: adakah user tengah hantar slip topup? ────────
    if context.user_data.get("pending_topup_id"):
        is_slip = await handle_payment_slip(update, context)
        if is_slip:
            return

    # ── Semak: adakah user dalam mode body scan? ─────────────────
    if context.user_data.get("awaiting_body_scan"):
        is_body = await handle_body_scan_photo(update, context)
        if is_body:
            return

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
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    image_bytes = await file.download_as_bytearray()

    # ── Baca caption jika ada (contoh: "nasi 250g ayam 150g") ────
    caption = update.message.caption or ""

    # ── Hantar ke AI untuk analisis ──────────────────────────────
    result = await analyze_food_image(bytes(image_bytes), caption=caption)

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
    today_summary = db.get_today_summary(telegram_id)
    user_fresh = db.get_user(telegram_id)
    streak = db.update_streak(telegram_id)

    target_cal   = user["target_calories"] or 2000
    target_pro   = user["target_protein"] or 160
    target_carbs = user.get("target_carbs") or 0
    target_fat   = user.get("target_fat") or 0

    cal_progress   = get_progress_bar(today_summary["total_calories"], target_cal)
    pro_progress   = get_progress_bar(today_summary["total_protein"], target_pro)
    carb_progress  = get_progress_bar(today_summary["total_carbs"], target_carbs) if target_carbs else None
    fat_progress   = get_progress_bar(today_summary["total_fat"], target_fat) if target_fat else None
    score_emoji    = get_health_score_emoji(int(result["health_score"]))

    remaining = user_fresh["scans_remaining"]
    remaining_text = f"Baki scan: {remaining}" if remaining > 5 else f"⚠️ Baki scan: {remaining} — /topup"

    streak_text = _get_streak_text(streak)

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
        f"🔥 Kalori:  {cal_progress} ({int(today_summary['total_calories'])}/{int(target_cal)} kcal)\n"
        f"🥩 Protein: {pro_progress} ({int(today_summary['total_protein'])}/{int(target_pro)}g)\n"
    )
    if carb_progress:
        reply += f"🍚 Karbo:   {carb_progress} ({int(today_summary['total_carbs'])}/{int(target_carbs)}g)\n"
    if fat_progress:
        reply += f"🧈 Lemak:   {fat_progress} ({int(today_summary['total_fat'])}/{int(target_fat)}g)\n"

    reply += (
        f"━━━━━━━━━━━━━━━━\n"
        f"{streak_text}\n"
        f"{remaining_text}"
    )

    await update.message.reply_text(reply)


def _parse_manual_entry(text: str):
    """
    Parse teks manual dari user.
    Format: [nama] [kalori] kal/kalori [protein] protein/g
    Contoh: "lunch 600 kalori 30 protein"
            "nasi lemak 650kal 25g protein"
            "dinner 500 kalori 40 protein 60 carb 15 lemak"

    Return dict atau None jika format tak dikenali.
    """
    text_lower = text.lower()

    # Cari kalori
    cal_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:kal(?:ori)?|kcal|cal)', text_lower)
    # Cari protein
    pro_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:g\s*)?protein', text_lower)

    if not cal_match and not pro_match:
        return None  # Bukan format manual

    calories = float(cal_match.group(1)) if cal_match else 0
    protein = float(pro_match.group(1)) if pro_match else 0

    # Cari carb dan lemak (optional)
    carb_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:g\s*)?(?:carb|karbohidrat|karbo)', text_lower)
    fat_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:g\s*)?(?:lemak|fat|minyak)', text_lower)
    carbs = float(carb_match.group(1)) if carb_match else 0
    fat = float(fat_match.group(1)) if fat_match else 0

    # Nama makanan — buang angka dan keyword nutrisi
    food_name = re.sub(
        r'\d+(?:\.\d+)?\s*(?:kal(?:ori)?|kcal|cal|protein|g\s+protein|carb|karbohidrat|karbo|lemak|fat)',
        '', text, flags=re.IGNORECASE
    ).strip(" ,.-")
    food_name = food_name if food_name else "Makanan"

    return {
        "food_name": food_name.title(),
        "calories": calories,
        "protein_g": protein,
        "carbs_g": carbs,
        "fat_g": fat,
    }


async def handle_text_food(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Dipanggil bila pengguna hantar teks.
    - Format manual (ada kalori/protein): simpan terus, PERCUMA
    - Format lain: tunjuk cara guna
    """
    telegram_id = update.effective_user.id
    text = update.message.text.strip()

    user = db.get_user(telegram_id)

    # Semak profil
    if not user or not user["setup_complete"]:
        await update.message.reply_text(
            "⚠️ Profil anda belum lengkap.\n"
            "Sila taip /start untuk mula setup."
        )
        return

    # Cuba parse manual entry
    parsed = _parse_manual_entry(text)

    if not parsed:
        # Bukan format yang dikenali
        await update.message.reply_text(
            "📸 Hantar GAMBAR makanan untuk analisis AI.\n\n"
            "Atau rekod manual (PERCUMA):\n"
            "Contoh: lunch 600 kalori 30 protein\n"
            "Contoh: nasi lemak 650kcal 25g protein\n\n"
            "Commands:\n"
            "/today — Ringkasan hari ini\n"
            "/credits — Baki scan"
        )
        return

    # Simpan ke DB — TANPA tolak scan, TANPA guna AI
    db.log_food(
        telegram_id=telegram_id,
        food_name=parsed["food_name"],
        calories=parsed["calories"],
        protein_g=parsed["protein_g"],
        carbs_g=parsed["carbs_g"],
        fat_g=parsed["fat_g"],
        health_score=5,
        advice="Rekod manual",
        image_file_id=None
    )

    today_summary = db.get_today_summary(telegram_id)
    target_cal   = user["target_calories"] or 2000
    target_pro   = user["target_protein"] or 160
    target_carbs = user.get("target_carbs") or 0
    target_fat   = user.get("target_fat") or 0

    cal_progress  = get_progress_bar(today_summary["total_calories"], target_cal)
    pro_progress  = get_progress_bar(today_summary["total_protein"], target_pro)
    carb_progress = get_progress_bar(today_summary["total_carbs"], target_carbs) if target_carbs else None
    fat_progress  = get_progress_bar(today_summary["total_fat"], target_fat) if target_fat else None

    reply = (
        f"✅ {parsed['food_name']} direkod!\n\n"
        f"🔥 Kalori:  {int(parsed['calories'])} kcal\n"
        f"🥩 Protein: {parsed['protein_g']}g\n"
    )
    if parsed["carbs_g"]:
        reply += f"🍚 Karbo:   {parsed['carbs_g']}g\n"
    if parsed["fat_g"]:
        reply += f"🧈 Lemak:   {parsed['fat_g']}g\n"

    reply += f"\n━━━━━━━━━━━━━━━━\n📊 Progress Hari Ini:\n"
    reply += f"🔥 Kalori:  {cal_progress} ({int(today_summary['total_calories'])}/{int(target_cal)} kcal)\n"
    reply += f"🥩 Protein: {pro_progress} ({int(today_summary['total_protein'])}/{int(target_pro)}g)\n"
    if carb_progress:
        reply += f"🍚 Karbo:   {carb_progress} ({int(today_summary['total_carbs'])}/{int(target_carbs)}g)\n"
    if fat_progress:
        reply += f"🧈 Lemak:   {fat_progress} ({int(today_summary['total_fat'])}/{int(target_fat)}g)\n"
    reply += f"━━━━━━━━━━━━━━━━\n📝 Rekod manual — scan tidak ditolak"

    await update.message.reply_text(reply)
