"""
handlers/tracking.py — FitJejak
Handler untuk /today, /weight, /summary, /credits, /profile, /topup
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
import database as db
from utils.nutrition import get_progress_bar, get_nutrient_bar, calculate_body_fat, get_body_fat_category
from config import CREDIT_PACKAGES, BOT_USERNAME, ADMIN_TELEGRAM_ID


async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User taip /support → tunjuk pilihan hantar teks atau gambar."""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✍️ Hantar Teks", callback_data="support_text")],
        [InlineKeyboardButton("📸 Hantar Gambar", callback_data="support_photo")],
    ])
    await update.message.reply_text(
        "📩 Hubungi Support FitJejak\n\n"
        "Pilih cara nak hantar laporan:",
        reply_markup=keyboard
    )


async def handle_support_type_callback(update, context):
    """User pilih jenis support — set flag dan minta input."""
    query = update.callback_query
    await query.answer()

    if query.data == "support_text":
        context.user_data["awaiting_support"] = "text"
        await query.edit_message_text("✍️ Taip masalah anda sekarang:")
    else:
        context.user_data["awaiting_support"] = "photo"
        await query.edit_message_text("📸 Hantar gambar (boleh sertakan caption) sekarang:")


async def _forward_support_to_admin(context, telegram_id: int, name: str, username: str,
                                     msg: str = "", photo_file_id: str = ""):
    """Forward support ke admin dengan button Balas."""
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("💬 Balas", callback_data=f"reply_user_{telegram_id}")
    ]])
    header = (
        f"📩 SUPPORT REQUEST\n\n"
        f"👤 {name} ({username})\n"
        f"🆔 ID: {telegram_id}\n\n"
    )
    try:
        if photo_file_id:
            caption = header + (f"💬 Caption:\n{msg}" if msg else "")
            await context.bot.send_photo(
                chat_id=ADMIN_TELEGRAM_ID,
                photo=photo_file_id,
                caption=caption,
                reply_markup=keyboard
            )
        else:
            await context.bot.send_message(
                chat_id=ADMIN_TELEGRAM_ID,
                text=header + f"💬 Mesej:\n{msg}",
                reply_markup=keyboard
            )
        return True
    except Exception:
        return False


async def handle_support_text_input(update, context):
    """Terima teks support dari user."""
    if context.user_data.get("awaiting_support") != "text":
        return False

    context.user_data.pop("awaiting_support", None)
    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)
    name = user["first_name"] if user else str(telegram_id)
    username = f"@{user['username']}" if user and user.get("username") else "tiada username"

    ok = await _forward_support_to_admin(context, telegram_id, name, username, msg=update.message.text)
    if ok:
        await update.message.reply_text("✅ Mesej dihantar! Support akan balas secepat mungkin 🙏")
    else:
        await update.message.reply_text("⚠️ Gagal hantar. Cuba lagi.")
    return True


async def handle_support_photo_input(update, context):
    """Terima gambar support dari user. Dipanggil dari food.py."""
    if context.user_data.get("awaiting_support") != "photo":
        return False

    context.user_data.pop("awaiting_support", None)
    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)
    name = user["first_name"] if user else str(telegram_id)
    username = f"@{user['username']}" if user and user.get("username") else "tiada username"

    photo_file_id = update.message.photo[-1].file_id
    caption = update.message.caption or ""

    ok = await _forward_support_to_admin(context, telegram_id, name, username,
                                          msg=caption, photo_file_id=photo_file_id)
    if ok:
        await update.message.reply_text("✅ Gambar dihantar! Support akan balas secepat mungkin 🙏")
    else:
        await update.message.reply_text("⚠️ Gagal hantar. Cuba lagi.")
    return True


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tunjuk semua command yang tersedia."""
    await update.message.reply_text(
        "🤖 FitJejak — Panduan Penggunaan\n\n"
        "📸 SCAN MAKANAN\n"
        "Hantar gambar makanan → AI akan kira kalori & nutrisi\n"
        "(Gunakan kredit scan)\n\n"
        "✍️ REKOD MANUAL (Percuma)\n"
        "Taip: lunch 600 kalori\n"
        "Bot akan tanya protein, karbo, lemak satu persatu\n\n"
        "━━━━━━━━━━━━━━━━\n"
        "📊 COMMANDS\n\n"
        "/today — Ringkasan nutrisi hari ini\n"
        "/history — Senarai makanan hari ini + padam\n"
        "/weight 75 — Rekod berat badan\n"
        "/summary — Purata nutrisi 7 hari lepas\n"
        "/credits — Semak baki scan\n"
        "/topup — Pakej tambah kredit\n"
        "/profile — Lihat & semak profil anda\n"
        "/referral — Dapatkan link referral & scan percuma\n"
        "/apply — Mohon jadi affiliate FitJejak\n"
        "/support [mesej] — Hubungi support\n"
        "/start — Reset & setup profil semula\n"
        "/help — Tunjuk panduan ini\n\n"
        "━━━━━━━━━━━━━━━━\n"
        "💡 TIPS\n"
        "• Gambar dari atas (bird's eye) lebih tepat\n"
        "• Pastikan makanan nampak jelas\n"
        "• Rekod manual tak gunakan kredit scan"
    )


def _require_profile(func):
    """Decorator — pastikan pengguna dah setup profil sebelum guna command."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = db.get_user(update.effective_user.id)
        if not user or not user["setup_complete"]:
            await update.message.reply_text(
                "⚠️ Profil anda belum lengkap.\nSila taip /start untuk mula setup."
            )
            return
        return await func(update, context, user)
    return wrapper


# ── /today ────────────────────────────────────────────────────────

@_require_profile
async def today(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    """Tunjuk ringkasan nutrisi hari ini."""
    telegram_id  = update.effective_user.id
    summary      = db.get_today_summary(telegram_id)
    exercise_cal = db.get_exercise_calories(telegram_id)

    target_cal   = user["target_calories"] or 2000
    target_pro   = user["target_protein"] or 160
    # Kira carbs & fat on-the-fly kalau user lama belum ada nilai
    target_carbs = user.get("target_carbs") or round((target_cal * 0.50) / 4)
    target_fat   = user.get("target_fat")   or round((target_cal * 0.30) / 9)

    # Net kalori = kalori masuk - exercise
    net_cal       = max(0, summary["total_calories"] - exercise_cal)
    cal_remaining = max(0, target_cal - net_cal)

    # Bar dan peratus semua guna NET kalori supaya konsisten
    cal_bar = get_nutrient_bar(net_cal, target_cal, " kcal")
    pro_bar = get_nutrient_bar(summary["total_protein"], target_pro, "g", reverse=True)

    pro_remaining = max(0, target_pro - summary["total_protein"])

    # Semak sama ada target tercapai (≥90%)
    cal_pct  = net_cal / target_cal if target_cal else 0
    pro_pct  = summary["total_protein"] / target_pro if target_pro else 0
    both_done = cal_pct >= 0.90 and pro_pct >= 0.90

    if both_done:
        suggestion = "🎉 Luar biasa! Target kalori & protein hari ini dah tercapai!"
    elif pro_remaining > 30:
        suggestion = f"Tambah {int(pro_remaining)}g lagi protein. Cuba dada ayam, telur, atau whey."
    elif pro_remaining > 0:
        suggestion = f"Hampir capai target protein! Tinggal {int(pro_remaining)}g lagi."
    else:
        suggestion = "Tahniah! Target protein hari ini dah capai!"

    if summary["meal_count"] == 0:
        await update.message.reply_text(
            "📊 Hari Ini\n\n"
            "Belum ada makanan direkod hari ini.\n\n"
            "📸 Hantar gambar makanan anda untuk mula menjejak!"
        )
        return

    # Header celebration kalau target tercapai
    header = "🏆 Target Hari Ini Tercapai!\n" if both_done else "📊 Ringkasan Hari Ini\n"

    # Baris exercise — tunjuk kalau ada, sorok kalau 0
    if exercise_cal > 0:
        exercise_row = (
            f"   ➕ Kalori Masuk: {int(summary['total_calories'])} kcal\n"
            f"   ➖ Exercise: -{int(exercise_cal)} kcal\n"
        )
        cal_label = f"🔥 Kalori Bersih: {int(net_cal)} / {int(target_cal)} kcal"
    else:
        exercise_row = ""
        cal_label = f"🔥 Kalori:      {int(net_cal)} / {int(target_cal)} kcal"

    baki_line = f"✅ Target kalori tercapai!" if cal_remaining == 0 else f"Baki kalori: {int(cal_remaining)} kcal"

    carb_bar = get_nutrient_bar(summary["total_carbs"], target_carbs, "g") if target_carbs else "—"
    fat_bar  = get_nutrient_bar(summary["total_fat"], target_fat, "g") if target_fat else "—"

    reply = (
        f"{header}"
        f"{summary['meal_count']} hidangan direkod\n\n"
        f"{cal_label}\n"
        f"{exercise_row}"
        f"    {cal_bar}\n\n"
        f"🥩 Protein:\n"
        f"    {pro_bar}\n\n"
        f"🍚 Karbohidrat:\n"
        f"    {carb_bar}\n\n"
        f"🧈 Lemak:\n"
        f"    {fat_bar}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💡 {suggestion}\n\n"
        f"{baki_line}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏃 Tambah Kalori Exercise", callback_data="add_exercise")],
        [InlineKeyboardButton("📤 Share Progress",         callback_data="share_progress")],
    ])

    await update.message.reply_text(reply, reply_markup=keyboard)


async def handle_exercise_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle butang Tambah Kalori Exercise."""
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "🏃 Rekod Kalori Exercise\n\n"
        "Pilih cara rekod:\n\n"
        "✍️ TAIP KALORI — Percuma\n"
        "Taip terus berapa kalori dibakar.\n"
        "Rujukan: Jogging 30min ≈ 300 kcal | Gym 1j ≈ 400 kcal\n\n"
        "📸 SCAN SMARTWATCH — Guna 1 kredit\n"
        "Hantar screenshot dari Apple Watch, Garmin,\n"
        "Fitbit, Samsung Health, Strava dll.\n"
        "AI akan baca data terus dari skrin anda.\n\n"
        "━━━━━━━━━━━━━━━━\n"
        "Taip nombor ATAU hantar gambar sekarang:"
    )
    context.user_data["waiting_exercise_cal"] = True
    context.user_data["awaiting_exercise_scan"] = True


async def handle_exercise_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Terima input kalori exercise dari user."""
    if not context.user_data.get("waiting_exercise_cal"):
        return

    import re as _re
    raw = update.message.text.strip()
    # Strip unit kalau ada: "108kcal", "108 kal", "108cal"
    num_match = _re.search(r'(\d+(?:\.\d+)?)', raw)
    try:
        cal = float(num_match.group(1)) if num_match else 0
        if not (0 < cal <= 5000):
            raise ValueError
    except (ValueError, AttributeError):
        await update.message.reply_text("⚠️ Sila masukkan nombor yang sah. Contoh: 300")
        return

    context.user_data.pop("waiting_exercise_cal", None)
    context.user_data.pop("awaiting_exercise_scan", None)
    telegram_id = update.effective_user.id
    db.save_exercise_calories(telegram_id, cal)

    # Ambil data semasa untuk context
    user = db.get_user(telegram_id)
    today = db.get_today_summary(telegram_id)
    goal = user.get("goal", "kekal") if user else "kekal"
    target_cal = int(user.get("target_calories") or 2000) if user else 2000
    dimakan = int(today["total_calories"] or 0)
    dibakar = int(cal)
    bersih = dimakan - dibakar
    baki = target_cal - bersih

    # Mesej ikut goal
    if goal == "turun_berat":
        if bersih < target_cal:
            defisit = target_cal - bersih
            goal_msg = f"✅ Defisit {defisit} kcal — bagus untuk turun berat!\nJangan makan balik kalori yang dah dibakar ya 😄"
        else:
            goal_msg = f"⚠️ Kalori bersih masih melebihi target.\nCuba kurangkan makan atau exercise lebih."
    elif goal == "naik_otot":
        if bersih < target_cal:
            goal_msg = f"⚠️ Kurang {baki} kcal lagi!\nDah exercise, badan perlukan bahan bakar — makan protein sekarang 💪"
        else:
            goal_msg = f"✅ Kalori mencukupi untuk bina otot. Teruskan! 💪"
    else:  # kekal
        if baki > 0:
            goal_msg = f"💡 Ada ruang {baki} kcal lagi.\nBoleh makan sedikit lagi untuk kekalkan berat badan."
        else:
            goal_msg = f"✅ Kalori seimbang hari ini. Bagus! ⚖️"

    await update.message.reply_text(
        f"✅ {dibakar} kcal exercise direkod!\n\n"
        f"📊 Situasi anda sekarang:\n"
        f"🍽️ Dimakan:  {dimakan} kcal\n"
        f"🏃 Dibakar:  -{dibakar} kcal\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💪 Bersih:   {bersih} kcal\n"
        f"🎯 Target:   {target_cal} kcal\n\n"
        f"{goal_msg}"
    )


async def handle_exercise_scan_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Analisis screenshot smartwatch/fitness app untuk kalori exercise.
    Dipanggil dari food.handle_photo bila awaiting_exercise_scan = True.
    Return True supaya food.handle_photo tahu gambar dah diproses.
    """
    from ai_analyzer import analyze_exercise_image

    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)

    # Semak baki scan
    if not user or user["scans_remaining"] <= 0:
        await update.message.reply_text(
            "❌ Baki scan anda habis!\n\n"
            "Topup kredit: /topup\n"
            "Atau taip kalori terus (percuma)."
        )
        context.user_data.pop("awaiting_exercise_scan", None)
        context.user_data.pop("waiting_exercise_cal", None)
        return True

    processing_msg = await update.message.reply_text(
        "🔍 Membaca data fitness anda...\nIni ambil masa 5-10 saat"
    )

    # Download gambar
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    image_bytes = await file.download_as_bytearray()

    result = await analyze_exercise_image(bytes(image_bytes))
    await processing_msg.delete()

    if "error" in result:
        await update.message.reply_text(
            f"⚠️ {result['error']}\n\n"
            "Scan tidak ditolak. Cuba:\n"
            "• Screenshot yang lebih jelas\n"
            "• Atau taip kalori terus (percuma)"
        )
        return True

    # Tolak 1 scan
    db.deduct_scan(telegram_id)

    cal = result["calories_burned"]
    db.save_exercise_calories(telegram_id, cal)

    # Clear flags
    context.user_data.pop("awaiting_exercise_scan", None)
    context.user_data.pop("waiting_exercise_cal", None)

    # Ambil data semasa untuk feedback
    user_fresh = db.get_user(telegram_id)
    today = db.get_today_summary(telegram_id)
    goal = user.get("goal", "kekal") or "kekal"
    target_cal = int(user.get("target_calories") or 2000)
    dimakan = int(today["total_calories"] or 0)
    dibakar = int(cal)
    bersih = dimakan - dibakar
    baki = target_cal - bersih

    duration_text = f" ({int(result['duration_min'])} min)" if result.get("duration_min") else ""
    notes_text = f"\n📌 {result['notes']}" if result.get("notes") else ""
    remaining = user_fresh["scans_remaining"] if user_fresh else "?"

    if goal == "turun_berat":
        defisit = target_cal - bersih
        goal_msg = (f"✅ Defisit {defisit} kcal — bagus untuk turun berat!" if bersih < target_cal
                    else "⚠️ Kalori bersih masih melebihi target. Cuba exercise lebih.")
    elif goal == "naik_otot":
        goal_msg = (f"⚠️ Kurang {baki} kcal lagi! Makan protein sekarang 💪" if bersih < target_cal
                    else "✅ Kalori mencukupi untuk bina otot. Teruskan! 💪")
    else:
        goal_msg = (f"💡 Ada ruang {baki} kcal lagi." if baki > 0
                    else "✅ Kalori seimbang hari ini. Bagus! ⚖️")

    await update.message.reply_text(
        f"✅ {result['activity_name']}{duration_text} direkod!{notes_text}\n\n"
        f"🔥 Kalori dibakar: {dibakar} kcal\n\n"
        f"📊 Situasi anda sekarang:\n"
        f"🍽️ Dimakan:  {dimakan} kcal\n"
        f"🏃 Dibakar:  -{dibakar} kcal\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💪 Bersih:   {bersih} kcal\n"
        f"🎯 Target:   {target_cal} kcal\n\n"
        f"{goal_msg}\n\n"
        f"💳 Baki scan: {remaining}"
    )
    return True


# ── /weight ───────────────────────────────────────────────────────

@_require_profile
async def weight(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    """Rekod berat badan. Contoh: /weight 75.5"""
    args = context.args

    if not args:
        # Tunjuk weight history
        history = db.get_weight_history(update.effective_user.id)
        if not history:
            await update.message.reply_text(
                "⚖️ Belum ada rekod berat.\n\n"
                "Rekod berat anda: /weight 75"
            )
            return

        first_weight = history[0]["weight_kg"]
        last_weight  = history[-1]["weight_kg"]
        total_change = last_weight - first_weight

        if total_change < 0:
            trend = f"turun {abs(total_change):.1f}kg ✅"
        elif total_change > 0:
            trend = f"naik {total_change:.1f}kg 📈"
        else:
            trend = "tiada perubahan ➡️"

        lines = "⚖️ History Berat\n\n"
        prev = None
        for rec in history:
            date_str = rec["log_date"][5:]  # buang year, tunjuk MM-DD
            w = rec["weight_kg"]
            if prev is not None:
                diff = w - prev
                arrow = "↓" if diff < 0 else ("↑" if diff > 0 else "→")
                lines += f"{date_str}  {w}kg  {arrow}{abs(diff):.1f}\n"
            else:
                lines += f"{date_str}  {w}kg\n"
            prev = w

        lines += (
            f"\n━━━━━━━━━━━━━━━━\n"
            f"Jumlah: {trend}\n"
            f"({first_weight}kg → {last_weight}kg)\n\n"
            f"Rekod berat baru: /weight 75"
        )

        await update.message.reply_text(lines)
        return

    try:
        new_weight = float(args[0].replace("kg", ""))
        if not (20 <= new_weight <= 300):
            raise ValueError
    except ValueError:
        await update.message.reply_text("⚠️ Berat tidak sah. Contoh: /weight 75")
        return

    telegram_id = update.effective_user.id
    prev_weight = db.get_previous_weight(telegram_id)
    db.log_weight(telegram_id, new_weight)

    if prev_weight:
        diff = new_weight - prev_weight
        if diff < 0:
            change_text = f"turun {abs(diff):.1f}kg ✅"
        elif diff > 0:
            change_text = f"naik {diff:.1f}kg"
        else:
            change_text = "tiada perubahan"

        reply = (
            f"⚖️ Berat Direkodkan\n\n"
            f"Lepas:    {prev_weight}kg\n"
            f"Sekarang: {new_weight}kg\n"
            f"Perubahan: {change_text}\n\n"
        )

        goal = user["goal"]
        if goal == "turun_berat" and diff < 0:
            reply += "Bagus! Teruskan! 💪"
        elif goal == "naik_otot" and diff > 0:
            reply += "Baik! Berat naik — pastikan protein mencukupi 🥩"
        else:
            reply += "Rekod disimpan."
    else:
        reply = (
            f"⚖️ Berat Direkodkan\n\n"
            f"Berat: {new_weight}kg\n\n"
            f"Rekod pertama disimpan. Baik!"
        )

    await update.message.reply_text(reply)


# ── /summary ──────────────────────────────────────────────────────

@_require_profile
async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    """Tunjuk ringkasan minggu ini."""
    week = db.get_week_summary(update.effective_user.id)

    target_cal = user["target_calories"] or 2000
    target_pro = user["target_protein"] or 160

    avg_cal = week["avg_calories"] or 0
    avg_pro = week["avg_protein"] or 0
    days = week["days_logged"] or 0

    consistency = int((days / 7) * 100)

    if consistency >= 80:
        consistency_label = "Cemerlang 🏆"
    elif consistency >= 50:
        consistency_label = "Sederhana 👍"
    else:
        consistency_label = "Perlu ditingkatkan 📈"

    protein_status = "Mencukupi ✅" if avg_pro >= target_pro * 0.9 else "Perlu ditambah ⚠️"

    reply = (
        f"📈 Ringkasan Minggu Ini\n\n"
        f"📅 Hari direkod: {days}/7\n"
        f"📊 Konsistensi:  {consistency}% — {consistency_label}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🔥 Purata Kalori:  {int(avg_cal)} / {int(target_cal)} kcal\n"
        f"🥩 Purata Protein: {int(avg_pro)} / {int(target_pro)}g — {protein_status}\n"
        f"━━━━━━━━━━━━━━━━\n\n"
    )

    if avg_pro < target_pro * 0.8:
        reply += "💡 Protein anda rendah minggu ini. Cuba tambah dada ayam, telur, atau whey."
    elif avg_cal > target_cal * 1.1:
        reply += "💡 Kalori anda sedikit tinggi. Cuba kurangkan minyak dan gula."
    else:
        reply += "💡 Teruskan usaha anda! Konsistensi adalah kunci."

    await update.message.reply_text(reply)


# ── /credits ─────────────────────────────────────────────────────

@_require_profile
async def credits(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    """Tunjuk baki scan pengguna."""
    remaining = user["scans_remaining"]

    if remaining > 20:
        status = "Banyak lagi ✅"
    elif remaining > 5:
        status = "Cukup 👍"
    else:
        status = "Hampir habis ⚠️"

    await update.message.reply_text(
        f"💳 Baki Scan Anda\n\n"
        f"Scan tersisa: {remaining} — {status}\n\n"
        f"Taip /topup untuk tambah kredit."
    )


# ── /referral ────────────────────────────────────────────────────

@_require_profile
async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    """Tunjuk kod & link referral pengguna."""
    telegram_id = update.effective_user.id
    code = db.get_or_create_referral_code(telegram_id)
    count = user.get("referral_count") or 0
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{code}"

    await update.message.reply_text(
        f"🔗 Referral Anda\n\n"
        f"Kod: <code>{code}</code>\n"
        f"Link: {link}\n\n"
        f"👥 Kawan yang dah join: {count} orang\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🎁 Cara kerja:\n"
        f"• Share link di atas kepada kawan\n"
        f"• Bila kawan join &amp; setup profil — awak dapat +5 scan\n"
        f"• Kawan pun dapat +5 scan percuma!\n\n"
        f"Kongsi dan kumpul scan percuma! 💪",
        parse_mode="HTML"
    )


# ── /topup ────────────────────────────────────────────────────────

async def topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tunjuk pakej kredit yang tersedia."""
    pkg_lines = ""
    for pkg in CREDIT_PACKAGES.values():
        per_scan = round(pkg['price_rm'] / pkg['scans'] * 100) / 100
        pkg_lines += f"• {pkg['name']} — RM{pkg['price_rm']} ({pkg['scans']} scan / RM{per_scan:.2f} setiap scan)\n"

    await update.message.reply_text(
        f"💳 Pakej Kredit FitJejak\n\n"
        f"{pkg_lines}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"Untuk top up, hubungi admin:\n"
        f"@fitjejak_support\n\n"
        f"(Sistem pembayaran automatik akan datang tidak lama lagi)"
    )


# ── /profile ─────────────────────────────────────────────────────

@_require_profile
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    """Tunjuk profil semasa pengguna."""
    goal_label = {
        "turun_berat": "Turunkan Berat Badan 🔥",
        "kekal":       "Kekalkan Berat Badan ⚖️",
        "naik_otot":   "Naikkan Otot 💪"
    }.get(user["goal"], "?")

    activity_label = {
        "sedentary":   "Tidak aktif 😴",
        "light":       "Ringan 🚶",
        "moderate":    "Sederhana 🏃",
        "active":      "Aktif 💪",
        "very_active": "Sangat aktif 🔥"
    }.get(user["activity_level"], "?")

    # Kira body fat on-the-fly
    bf = calculate_body_fat(
        user["weight_kg"], user["height_cm"], user["age"], user["gender"]
    )
    bf_category = get_body_fat_category(bf, user["gender"])

    # Fix target_carbs / target_fat untuk user lama yang NULL/0
    _tid = update.effective_user.id
    target_cal = user.get("target_calories") or 2000
    if not user.get("target_carbs"):
        target_carbs = round((target_cal * 0.50) / 4)
        target_fat   = round((target_cal * 0.30) / 9)
        db.update_user_profile(_tid, target_carbs=target_carbs, target_fat=target_fat)
        user["target_carbs"] = target_carbs
        user["target_fat"]   = target_fat

    # 4 slot reminder — default ON kalau column belum wujud (user lama)
    def _r(slot):
        val = user.get(f"reminder_{slot}")
        return 1 if val is None else int(val)

    slots = [
        ("pagi",       "🌅 Pagi 8am"),
        ("tengahari",  "☀️ Tengah 12pm"),
        ("petang",     "🌤️ Petang 5pm"),
        ("malam",      "🌙 Malam 9pm"),
    ]

    reminder_buttons = []
    for slot, label in slots:
        on = _r(slot)
        icon = "🔔" if on else "🔕"
        reminder_buttons.append(
            InlineKeyboardButton(
                f"{icon} {label}",
                callback_data=f"rem_{slot}_{'off' if on else 'on'}"
            )
        )

    reply = (
        f"👤 Profil Anda\n\n"
        f"⚖️ Berat:     {user['weight_kg']}kg\n"
        f"📏 Tinggi:   {user['height_cm']}cm\n"
        f"🎂 Umur:     {user['age']} tahun\n"
        f"🚻 Jantina:  {user['gender'].capitalize()}\n"
        f"🏃 Aktiviti: {activity_label}\n"
        f"🎯 Sasaran:  {goal_label}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🫀 Anggaran Body Fat: {bf}% — {bf_category}\n\n"
        f"📊 Target Harian:\n"
        f"🔥 Kalori:  {int(user['target_calories'] or 0):,} kcal\n"
        f"🥩 Protein: {int(user['target_protein'] or 0)}g\n"
        f"🍚 Karbo:   {int(user.get('target_carbs') or 0)}g\n"
        f"🧈 Lemak:   {int(user.get('target_fat') or 0)}g\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💳 Baki Scan: <b>{user['scans_remaining']} scan</b>\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🔔 Reminder Harian (tekan untuk ON/OFF):"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Edit Profil", callback_data="edit_profile_menu")],
        # 2 buttons per row untuk reminder
        [reminder_buttons[0], reminder_buttons[1]],
        [reminder_buttons[2], reminder_buttons[3]],
    ])

    await update.message.reply_text(reply, reply_markup=keyboard, parse_mode="HTML")


async def handle_reminder_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle reminder slot ON/OFF. Pattern: rem_SLOT_on | rem_SLOT_off"""
    query = update.callback_query
    await query.answer()

    telegram_id = update.effective_user.id
    # data contoh: rem_pagi_off  → slot=pagi, action=off (nak matikan)
    parts = query.data.split("_")   # ['rem', 'pagi', 'off']
    slot   = parts[1]               # pagi / tengahari / petang / malam
    action = parts[2]               # on / off
    turn_on = (action == "on")

    col = f"reminder_{slot}"
    db.update_user_profile(telegram_id, **{col: 1 if turn_on else 0})

    slot_label = {
        "pagi":      "Pagi 8am 🌅",
        "tengahari": "Tengah Hari 12pm ☀️",
        "petang":    "Petang 5pm 🌤️",
        "malam":     "Malam 9pm 🌙",
    }.get(slot, slot)

    if turn_on:
        msg = f"🔔 Reminder {slot_label} dihidupkan!"
    else:
        msg = f"🔕 Reminder {slot_label} dimatikan."

    icon = "🔔" if turn_on else "🔕"
    await query.message.reply_text(
        f"{icon} Reminder {slot_label} {'dihidupkan' if turn_on else 'dimatikan'}.\n\n"
        f"Taip /profile untuk tengok status reminder terkini."
    )


# ── /history ──────────────────────────────────────────────────────

@_require_profile
async def history(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    """Tunjuk senarai makanan yang dah dilog hari ini dengan butang Delete."""
    logs = db.get_today_logs(update.effective_user.id)

    if not logs:
        await update.message.reply_text(
            "📋 Tiada rekod makanan hari ini.\n\n"
            "📸 Hantar gambar atau taip kalori untuk mula rekod."
        )
        return

    text = "📋 Log Makanan Hari Ini\n\n"
    keyboard = []

    for i, log in enumerate(logs, 1):
        time_str = log["logged_at"][11:16] if log["logged_at"] else ""
        text += (
            f"{i}. {log['food_name']}\n"
            f"   🔥 {int(log['calories'])} kcal  🥩 {log['protein_g']}g protein"
        )
        if time_str:
            text += f"  ({time_str})"
        text += "\n\n"

        keyboard.append([
            InlineKeyboardButton(
                f"✏️ Edit #{i}",
                callback_data=f"edit_{log['id']}"
            ),
            InlineKeyboardButton(
                f"🗑 Padam #{i}",
                callback_data=f"del_{log['id']}"
            ),
        ])

    await update.message.reply_text(
        text.strip(),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle butang padam dari /history."""
    query = update.callback_query
    await query.answer()

    log_id = int(query.data.replace("del_", ""))
    telegram_id = update.effective_user.id

    deleted = db.delete_food_log(log_id, telegram_id)

    if deleted:
        # Rebuild senarai terkini (tanpa rekod yang dipadam)
        logs = db.get_today_logs(telegram_id)

        if not logs:
            await query.edit_message_text("📋 Tiada lagi rekod makanan hari ini.\n\n✅ Rekod dipadam.")
            return

        text = "📋 Log Makanan Hari Ini\n\n"
        keyboard = []

        for i, log in enumerate(logs, 1):
            time_str = log["logged_at"][11:16] if log["logged_at"] else ""
            text += (
                f"{i}. {log['food_name']}\n"
                f"   🔥 {int(log['calories'])} kcal  🥩 {log['protein_g']}g protein"
            )
            if time_str:
                text += f"  ({time_str})"
            text += "\n\n"

            keyboard.append([
                InlineKeyboardButton(f"✏️ Edit #{i}", callback_data=f"edit_{log['id']}"),
                InlineKeyboardButton(f"🗑 Padam #{i}", callback_data=f"del_{log['id']}"),
            ])

        await query.edit_message_text(
            text.strip() + "\n\n✅ Rekod dipadam.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        # Jika gagal, kekalkan message + keyboard asal
        await query.answer("⚠️ Rekod tidak dijumpai atau dah dipadam.", show_alert=True)


async def handle_relog_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User tekan 🔄 Log Semula — copy rekod lama, save baru, PERCUMA (tanpa scan)."""
    query = update.callback_query
    telegram_id = update.effective_user.id

    log_id = int(query.data.replace("relog_", ""))
    log = db.get_food_log(log_id, telegram_id)

    if not log:
        await query.answer("⚠️ Rekod tidak dijumpai.", show_alert=True)
        return

    # Log semula — tanpa scan, tanpa AI
    db.log_food(
        telegram_id=telegram_id,
        food_name=log["food_name"],
        calories=log["calories"],
        protein_g=log["protein_g"],
        carbs_g=log["carbs_g"],
        fat_g=log["fat_g"],
        health_score=log.get("health_score", 5),
        advice="Log semula",
        image_file_id=None
    )

    # Update streak
    db.update_streak(telegram_id)

    await query.answer(f"✅ {log['food_name']} dilog semula!")
    try:
        await context.bot.send_message(
            chat_id=telegram_id,
            text=(
                f"🔄 *{log['food_name']}* dilog semula!\n\n"
                f"🔥 {int(log['calories'])} kcal  🥩 {log['protein_g']}g protein\n\n"
                f"_Scan tidak ditolak — log semula adalah percuma_ ✅"
            ),
            parse_mode="Markdown"
        )
    except Exception:
        pass


@_require_profile
async def relog(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    """Tunjuk top 3 makanan kerap untuk log semula tanpa scan."""
    telegram_id = update.effective_user.id
    foods = db.get_frequent_foods(telegram_id, limit=3)

    if not foods:
        await update.message.reply_text(
            "📋 Belum ada rekod makanan lagi.\n\n"
            "Scan gambar makanan dulu untuk mula!"
        )
        return

    text = "🔄 Log Semula — Pilih Makanan\n\n"
    keyboard = []

    for i, f in enumerate(foods):
        text += (
            f"{i+1}. {f['food_name']}\n"
            f"   🔥 {int(f['calories'])} kcal  🥩 {int(f['protein_g'])}g protein\n\n"
        )
        # Guna index (0,1,2) dalam callback — elak masalah nama panjang/special char
        keyboard.append([InlineKeyboardButton(
            f"🔄 {f['food_name']}",
            callback_data=f"relog_fav_{i}"
        )])

    # Simpan foods dalam user_data untuk callback ambil balik
    context.user_data["relog_foods"] = foods

    text += "_Percuma — scan tidak ditolak_ ✅"
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def handle_relog_fav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User pilih makanan dari /relog — log terus, percuma."""
    query = update.callback_query
    await query.answer()  # jawab dulu, elak loading spinner
    telegram_id = update.effective_user.id

    idx = int(query.data.replace("relog_fav_", ""))
    foods = context.user_data.get("relog_foods") or db.get_frequent_foods(telegram_id, limit=3)

    if idx >= len(foods):
        await context.bot.send_message(chat_id=telegram_id, text="⚠️ Makanan tidak dijumpai.")
        return

    food = foods[idx]

    try:
        db.log_food(
            telegram_id=telegram_id,
            food_name=food["food_name"],
            calories=float(food["calories"] or 0),
            protein_g=float(food["protein_g"] or 0),
            carbs_g=float(food["carbs_g"] or 0),
            fat_g=float(food["fat_g"] or 0),
            health_score=5,
            advice="Log semula",
            image_file_id=None
        )
        db.update_streak(telegram_id)

        await context.bot.send_message(
            chat_id=telegram_id,
            text=(
                f"🔄 *{food['food_name']}* dilog semula!\n\n"
                f"🔥 {int(float(food['calories']))} kcal  🥩 {int(float(food['protein_g']))}g protein\n\n"
                f"_Scan tidak ditolak — log semula adalah percuma_ ✅"
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        await context.bot.send_message(
            chat_id=telegram_id,
            text=f"⚠️ Ralat: {e}"
        )


async def handle_share_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate teks cantik untuk user share progress."""
    query = update.callback_query
    await query.answer()

    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)
    if not user:
        return

    from datetime import datetime, timezone, timedelta
    today_str = datetime.now(timezone(timedelta(hours=8))).strftime("%-d %b %Y")

    summary    = db.get_today_summary(telegram_id)
    target_cal = int(user.get("target_calories") or 2000)
    target_pro = int(user.get("target_protein") or 160)
    streak     = user.get("current_streak") or 0
    name       = user.get("first_name") or "Saya"

    cal_pct = int((summary["total_calories"] / target_cal) * 100) if target_cal else 0
    pro_pct = int((summary["total_protein"]  / target_pro)  * 100) if target_pro else 0

    cal_icon = "✅" if cal_pct >= 90 else ("⚠️" if cal_pct >= 60 else "❌")
    pro_icon = "✅" if pro_pct >= 90 else ("⚠️" if pro_pct >= 60 else "❌")

    streak_line = f"🔥 Streak: {streak} hari berturut-turut!\n" if streak >= 3 else ""

    text = (
        f"📊 Progress Harian — {name}\n"
        f"{today_str}\n\n"
        f"{cal_icon} Kalori:  {int(summary['total_calories'])}/{target_cal} kcal ({cal_pct}%)\n"
        f"{pro_icon} Protein: {int(summary['total_protein'])}/{target_pro}g ({pro_pct}%)\n\n"
        f"{streak_line}"
        f"Dijejak dengan FitJejak 💪\n"
        f"t.me/FitJejak_bot"
    )

    try:
        await context.bot.send_message(
            chat_id=telegram_id,
            text=f"📤 Screenshot dan share ni:\n\n{text}"
        )
    except Exception:
        pass


# ── /promo ────────────────────────────────────────────────────────

@_require_profile
async def promo(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    """Guna promo code untuk dapat bonus scan."""
    if not context.args:
        await update.message.reply_text(
            "🎟️ Masukkan kod promo anda:\n\n"
            "Contoh: /promo FITJEJAK10\n\n"
            "💡 Promo code hanya untuk pengguna yang dah buat topup pertama."
        )
        return

    code = context.args[0].strip().upper()
    telegram_id = update.effective_user.id

    success, message = db.apply_promo_code(telegram_id, code)

    if success:
        # Dapatkan baki terkini
        updated = db.get_user(telegram_id)
        remaining = updated["scans_remaining"] if updated else "?"
        await update.message.reply_text(
            f"{message}\n\n"
            f"💳 Baki scan anda sekarang: *{remaining} scan*",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(f"❌ {message}")


async def affiliate_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dashboard untuk affiliate — tunjuk earnings & referral link."""
    from datetime import datetime, timezone, timedelta
    telegram_id = update.effective_user.id

    aff = db.get_affiliate(telegram_id)
    if not aff or aff["status"] != "active":
        await update.message.reply_text(
            "⛔ Anda bukan affiliate FitJejak.\n\n"
            "Hubungi admin jika anda berminat menjadi affiliate."
        )
        return

    # Bulan semasa
    now_myt = datetime.now(timezone(timedelta(hours=8)))
    month_str = now_myt.strftime('%Y-%m')
    month_label = now_myt.strftime('%B %Y')

    # Earnings bulan ini
    this_month = db.get_affiliate_earnings_summary(telegram_id, month_str)
    # All-time
    all_time = db.get_affiliate_earnings_summary(telegram_id)

    # Referral link
    ref_code = db.get_or_create_referral_code(telegram_id)
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{ref_code}"

    rate_pct = int(aff["commission_rate"] * 100)

    await update.message.reply_text(
        f"💼 Dashboard Affiliate FitJejak\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"📅 {month_label}\n"
        f"Komisen: RM{this_month['pending']:.2f} (belum dibayar)\n"
        f"Transaksi: {this_month['transactions']} topup\n\n"
        f"📊 All-Time\n"
        f"Total komisen: RM{all_time['total']:.2f}\n"
        f"Sudah dibayar: RM{all_time['paid']:.2f}\n"
        f"Belum dibayar: RM{all_time['pending']:.2f}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🏦 Maklumat Pembayaran\n"
        f"Bank: {aff['bank_name']}\n"
        f"Akaun: {aff['bank_acc']}\n"
        f"Kadar komisyen: {rate_pct}%\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🔗 Link Referral Anda:\n"
        f"{ref_link}\n\n"
        f"💡 Setiap topup dari referral anda = {rate_pct}% komisyen\n"
        f"Bayaran dibuat setiap awal bulan."
    )
