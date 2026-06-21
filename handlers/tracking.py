"""
handlers/tracking.py — FitJejak
Handler untuk /today, /weight, /summary, /credits, /profile, /topup
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
import database as db
from utils.nutrition import get_progress_bar, calculate_body_fat, get_body_fat_category
from config import CREDIT_PACKAGES


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
    target_carbs = user.get("target_carbs") or 0
    target_fat   = user.get("target_fat") or 0

    # Net kalori = kalori masuk - exercise
    net_cal       = summary["total_calories"] - exercise_cal
    cal_remaining = max(0, target_cal - net_cal)

    cal_bar = get_progress_bar(summary["total_calories"], target_cal)
    pro_bar = get_progress_bar(summary["total_protein"], target_pro)

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
    exercise_row = (
        f"🏃 Exercise:    -{int(exercise_cal)} kcal\n"
        f"⚖️ Net Kalori:  {int(net_cal)} kcal\n\n"
    ) if exercise_cal > 0 else ""

    reply = (
        f"{header}"
        f"{summary['meal_count']} hidangan direkod\n\n"
        f"🔥 Kalori:      {int(summary['total_calories'])} / {int(target_cal)} kcal\n"
        f"    {cal_bar}\n"
        f"{exercise_row}"
        f"🥩 Protein:     {int(summary['total_protein'])} / {int(target_pro)}g\n"
        f"    {pro_bar}\n\n"
        f"🍚 Karbohidrat: {int(summary['total_carbs'])}g / {int(target_carbs)}g\n"
        f"    {get_progress_bar(summary['total_carbs'], target_carbs) if target_carbs else '—'}\n\n"
        f"🧈 Lemak:       {int(summary['total_fat'])}g / {int(target_fat)}g\n"
        f"    {get_progress_bar(summary['total_fat'], target_fat) if target_fat else '—'}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💡 {suggestion}\n\n"
        f"Baki kalori: {int(cal_remaining)} kcal"
    )

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🏃 Tambah Kalori Exercise", callback_data="add_exercise")
    ]])

    await update.message.reply_text(reply, reply_markup=keyboard)


async def handle_exercise_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle butang Tambah Kalori Exercise."""
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "🏃 Berapa kalori yang anda dah burned hari ini?\n\n"
        "Contoh: 350\n"
        "(Tengok dari smartwatch atau fitness app anda)"
    )
    context.user_data["waiting_exercise_cal"] = True


async def handle_exercise_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Terima input kalori exercise dari user."""
    if not context.user_data.get("waiting_exercise_cal"):
        return

    try:
        cal = float(update.message.text.strip())
        if not (0 < cal <= 5000):
            raise ValueError
    except ValueError:
        await update.message.reply_text("⚠️ Sila masukkan nombor yang sah. Contoh: 350")
        return

    context.user_data.pop("waiting_exercise_cal")
    db.save_exercise_calories(update.effective_user.id, cal)
    await update.message.reply_text(
        f"✅ {int(cal)} kcal exercise berjaya direkod!\n\n"
        f"Taip /today untuk tengok net kalori anda."
    )


# ── /weight ───────────────────────────────────────────────────────

@_require_profile
async def weight(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    """Rekod berat badan. Contoh: /weight 75.5"""
    args = context.args

    if not args:
        await update.message.reply_text(
            "⚖️ Cara guna: /weight 75\nAtau: /weight 75.5"
        )
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
    bot_username = context.bot.username

    link = f"https://t.me/{bot_username}?start=ref_{code}"

    await update.message.reply_text(
        f"🔗 Referral Anda\n\n"
        f"Kod: `{code}`\n"
        f"Link: {link}\n\n"
        f"👥 Kawan yang dah join: {count} orang\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🎁 Cara kerja:\n"
        f"• Share link di atas kepada kawan\n"
        f"• Bila kawan join & setup profil — awak dapat +5 scan\n"
        f"• Kawan pun dapat +5 scan percuma!\n\n"
        f"Kongsi dan kumpul scan percuma! 💪",
        parse_mode="Markdown"
    )


# ── /topup ────────────────────────────────────────────────────────

async def topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tunjuk pakej kredit yang tersedia."""
    lines = ["💳 Pakej Kredit FitJejak\n"]
    for key, pkg in CREDIT_PACKAGES.items():
        lines.append(f"• RM{pkg['price_rm']} — {pkg['scans']} scan")
    lines.append("\nUntuk top up, hubungi kami atau guna link pembayaran.")
    lines.append("(Sistem pembayaran akan diintegrasikan tidak lama lagi)")

    await update.message.reply_text("\n".join(lines))


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
        f"Taip /start untuk reset profil"
    )

    await update.message.reply_text(reply)


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
            )
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
        await query.edit_message_text(
            query.message.text + "\n\n✅ Rekod berjaya dipadam.\nTaip /history untuk lihat semula."
        )
    else:
        await query.edit_message_text("⚠️ Rekod tidak dijumpai atau dah dipadam.")
