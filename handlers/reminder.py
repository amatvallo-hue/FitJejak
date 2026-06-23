"""
handlers/reminder.py — FitJejak
Reminder harian automatik — 4 waktu:
  - Pagi       8:00 AM MYT (00:00 UTC)
  - Tengah hari 12:00 PM MYT (04:00 UTC)
  - Petang     5:00 PM MYT  (09:00 UTC)
  - Malam      9:00 PM MYT  (13:00 UTC)
"""
import logging
import database as db
from handlers.achievements import get_next_scan_achievement, build_achievement_progress_hint

logger = logging.getLogger(__name__)

# Malaysia = UTC+8
MORNING_HOUR_UTC   = 0   # 8:00 pagi MYT
NOON_HOUR_UTC      = 4   # 12:00 tengah hari MYT
AFTERNOON_HOUR_UTC = 9   # 5:00 petang MYT
EVENING_HOUR_UTC   = 13  # 9:00 malam MYT
WEEKLY_HOUR_UTC    = 12  # 8:00 malam MYT (Ahad)


def _build_morning_text(name: str, goal: str, has_logged: bool, streak: int, scans_left: int, telegram_id: int) -> str:
    """
    Bina teks morning reminder 3-layer:
    Layer 1: Log status (dah log / belum log)
    Layer 2: Goal (turun_berat / naik_otot / kekal)
    Layer 3: Situational (streak, achievement, low scan)
    """
    # ── Layer 1 + 2: Log status × Goal ───────────────────────────
    if has_logged:
        if goal == "turun_berat":
            core = (
                f"🌅 Eh rajin {name}! Dah log awal pagi 👍\n"
                f"Defisit kalori hari ni dah mula — teruskan semangat tu!"
            )
        elif goal == "naik_otot":
            core = (
                f"🌅 Dah log awal {name}! Protein pagi dah cover ke? 💪\n"
                f"Taip /today untuk check progress!"
            )
        else:  # kekal
            core = (
                f"🌅 Awal-awal dah rekod {name}! Bagus tu 😄\n"
                f"Teruskan — awak dah lebih baik dari semalam!"
            )
    else:
        if goal == "turun_berat":
            core = (
                f"☀️ Eh {name}, dah bangun? Jom snap sarapan!\n"
                f"Ingat — kalori pagi tu penting untuk kekalkan defisit hari ni 🔥"
            )
        elif goal == "naik_otot":
            core = (
                f"☀️ Pagi {name}! Dah makan protein belum? 💪\n"
                f"Badan awak perlukan bahan bakar lepas tidur — jom log sarapan!"
            )
        else:  # kekal
            core = (
                f"☀️ Selamat pagi {name}! Macam mana hari ni?\n"
                f"Snap gambar sarapan dan kekalkan rekod cantik awak! 📸"
            )

    # ── Layer 3: Situational ─────────────────────────────────────
    suffix = ""

    if has_logged:
        # Pujian streak kalau dah log
        if streak >= 7:
            suffix = f"\n\n🔥 Streak {streak} hari — gila konsisten! Jangan putus tau!"
    else:
        # Galak kalau belum log
        if streak >= 7:
            suffix = f"\n\n🔥 Jangan putus streak {streak} hari tu! Log sekarang 📸"
        elif streak == 0:
            suffix = f"\n\n💪 Hari baru, peluang baru! Jom start streak hari ni!"

    # Achievement — contextual kalau dekat, rotating tip kalau jauh
    if not suffix:
        total_scans = db.get_total_scans_used(telegram_id)
        next_ach = get_next_scan_achievement(total_scans)
        if next_ach:
            remaining = next_ach["req"] - total_scans
            if remaining <= 5:
                # Dekat — tunjuk contextual hint
                suffix = f"\n\n🎯 Lagi {remaining} scan je nak buka {next_ach['badge']} {next_ach['name']}!"
            else:
                # Jauh — rotate tip harian
                from datetime import datetime, timezone, timedelta
                day_index = datetime.now(timezone(timedelta(hours=8))).weekday()
                achievement_tips = [
                    "💡 Tahu tak? Scan 50 makanan dapat badge + 5 scan percuma! Taip /profile.",
                    "🏅 FitJejak ada Achievement! Setiap scan bawa awak lebih dekat ke hadiah 🎁",
                    "📸 Setiap gambar yang awak hantar = selangkah ke achievement seterusnya!",
                    "🎯 Achievement Scan Veteran: 50 scan dapat badge 📸🔥 + bonus scan percuma!",
                    "👑 Scan Master menanti — 100 scan dapat badge eksklusif + 10 scan percuma!",
                    "🏅 Dah check achievement anda hari ini? Taip /profile untuk tengok progress!",
                    "💪 Konsisten scan setiap hari = achievement terbuka = scan percuma! 📸",
                ]
                suffix = f"\n\n{achievement_tips[day_index % len(achievement_tips)]}"

    # Low scan warning
    if scans_left is not None and 0 < scans_left <= 5:
        suffix += f"\n\n⚠️ Baki scan tinggal {scans_left} — topup kejap supaya tak terputus! /topup"

    return core + suffix


async def send_morning_reminder(context):
    """8 pagi — personalised ikut goal + log status + situational."""
    users = db.get_users_for_reminder("pagi")
    sent_logged = 0
    sent_not_logged = 0

    for user in users:
        telegram_id = user["telegram_id"]
        name        = user.get("first_name") or "Kawan"
        goal        = user.get("goal") or "kekal"
        streak      = user.get("current_streak") or 0
        scans_left  = user.get("scans_remaining")

        try:
            has_logged = db.has_logged_today(telegram_id)
            text = _build_morning_text(name, goal, has_logged, streak, scans_left, telegram_id)

            if has_logged:
                sent_logged += 1
            else:
                sent_not_logged += 1

            await context.bot.send_message(chat_id=telegram_id, text=text)
        except Exception as e:
            logger.warning(f"Gagal morning reminder → {telegram_id}: {e}")

    logger.info(f"Morning reminder: {sent_logged} dah log, {sent_not_logged} belum log.")


async def send_noon_reminder(context):
    """12 tengah hari — galak log makan tengah hari."""
    users = db.get_users_for_reminder("tengahari")
    sent_logged = 0
    sent_not_logged = 0

    messages_not_logged = [
        "🍱 Eh {name}, dah makan tengah hari?\n\nSnap gambar lauk awak dan log sekarang. Jangan bagi kalori lari! 😄",
        "🕛 Waktu lunch {name}! Dah order belum? 📸\n\nHantar gambar bila dah dapat — FitJejak uruskan yang lain!",
        "☀️ Tengah hari dah {name}! Lunch sempat log ke?\n\nSnap gambar sekarang — mudah je!",
        "🍛 Jangan skip lunch {name}! Makan tengah hari penting untuk kekalkan tenaga 💪\n\nLog sekarang dengan snap gambar.",
    ]
    messages_logged = [
        "🍱 Dah ada rekod awal {name}! Lunch pula sekarang?\n\nSnap gambar dan kekalkan rekod penuh hari ini 😄",
        "🕛 Tengah hari dah! Sambung log {name} 📸\n\nTaip /today untuk tengok baki kalori hari ini.",
        "☀️ Siap log tadi, bagus {name}! Lunch pula sekarang?\n\nHantar gambar dan kekalkan rekod penuh hari ini!",
        "🍛 Momentum dah ada, teruskan {name}! Log makan tengah hari awak sekarang 💪",
    ]

    from datetime import datetime, timezone, timedelta
    day_index = datetime.now(timezone(timedelta(hours=8))).weekday() % len(messages_not_logged)

    for user in users:
        telegram_id = user["telegram_id"]
        name = user.get("first_name") or "Kawan"
        try:
            if db.has_logged_today(telegram_id):
                text = messages_logged[day_index].format(name=name)
                sent_logged += 1
            else:
                text = messages_not_logged[day_index].format(name=name)
                sent_not_logged += 1
            await context.bot.send_message(chat_id=telegram_id, text=text)
        except Exception as e:
            logger.warning(f"Gagal noon reminder → {telegram_id}: {e}")

    logger.info(f"Noon reminder: {sent_logged} dah log, {sent_not_logged} belum log.")


async def send_afternoon_reminder(context):
    """5 petang — galak log snack / check progress."""
    users = db.get_users_for_reminder("petang")
    sent_logged = 0
    sent_not_logged = 0

    messages_not_logged = [
        "🌤️ Petang dah tiba {name}! Belum log lagi hari ni?\n\nSnap gambar apa yang dimakan dan log sekarang. Taip /today 📊",
        "🥤 5 petang {name}! FitJejak tunggu rekod awak 📸\n\nLog sekarang jangan tangguh!",
        "🌅 Nak habis kerja dah {name}! Sempat log makanan hari ini lagi?\n\nHantar gambar — mudah je!",
        "🍎 Petang ni jangan skip log {name}! Konsisten sikit lagi — awak boleh buat! 💪",
    ]
    messages_logged = [
        "🌤️ Petang dah tiba {name}! Ada snack petang?\n\nLog sekarang dan check baki kalori untuk malam. Taip /today 📊",
        "🥤 5 petang {name}! Snack time ke? 😄\n\nHantar gambar snack awak — FitJejak kira untuk awak!",
        "🌅 Nak habis kerja dah! Check progress hari ini dengan /today 📊\n\nMasih ada ruang untuk makan malam yang sihat {name}!",
        "🍎 Rekod dah ada {name}! Ada snack petang? Log je semua 💪",
    ]

    from datetime import datetime, timezone, timedelta
    day_index = datetime.now(timezone(timedelta(hours=8))).weekday() % len(messages_not_logged)

    for user in users:
        telegram_id = user["telegram_id"]
        name = user.get("first_name") or "Kawan"
        try:
            if db.has_logged_today(telegram_id):
                text = messages_logged[day_index].format(name=name)
                sent_logged += 1
            else:
                text = messages_not_logged[day_index].format(name=name)
                sent_not_logged += 1
            await context.bot.send_message(chat_id=telegram_id, text=text)
        except Exception as e:
            logger.warning(f"Gagal afternoon reminder → {telegram_id}: {e}")

    logger.info(f"Afternoon reminder: {sent_logged} dah log, {sent_not_logged} belum log.")


async def send_evening_reminder(context):
    """9 malam — check log hari ini, puji atau galak."""
    users = db.get_users_for_reminder("malam")
    sent_logged = 0
    sent_not_logged = 0

    for user in users:
        telegram_id = user["telegram_id"]
        name = user["first_name"] or "Kawan"

        try:
            if db.has_logged_today(telegram_id):
                text = (
                    f"🌙 Tahniah {name}! Awak dah log makanan hari ini ✅\n\n"
                    f"Konsistensi awak sangat bagus. Teruskan esok!\n\n"
                    f"Taip /today untuk tengok ringkasan hari ini 📊"
                )
                sent_logged += 1
            else:
                text = (
                    f"🌙 Eh {name}, awak belum log makanan hari ini!\n\n"
                    f"Tak apa, masih sempat lagi 😊 Snap gambar makan malam awak sekarang.\n\n"
                    f"📸 Hantar gambar dan FitJejak akan kira kalori untuk awak."
                )
                sent_not_logged += 1

            await context.bot.send_message(chat_id=telegram_id, text=text)

        except Exception as e:
            logger.warning(f"Gagal evening reminder → {telegram_id}: {e}")

    logger.info(f"Evening reminder: {sent_logged} dah log, {sent_not_logged} belum log.")


async def send_weekly_report(context):
    """Laporan mingguan setiap Ahad 8 malam MYT."""
    users = db.get_users_for_reminder()
    sent = 0

    for user in users:
        telegram_id = user["telegram_id"]
        name = user["first_name"] or "Kawan"

        try:
            week = db.get_week_summary(telegram_id)
            full_user = db.get_user(telegram_id)

            avg_cal = int(week["avg_calories"] or 0)
            avg_pro = int(week["avg_protein"] or 0)
            days    = int(week["days_logged"] or 0)
            streak  = full_user.get("current_streak") or 0
            target_cal = int(full_user.get("target_calories") or 2000)
            target_pro = int(full_user.get("target_protein") or 160)
            consistency = int((days / 7) * 100)

            if consistency >= 80 and avg_pro >= target_pro * 0.9:
                verdict = "Minggu yang CEMERLANG! Awak betul-betul komited 🏆"
            elif consistency >= 50:
                verdict = "Minggu yang OK! Cuba tingkatkan konsistensi minggu depan 💪"
            else:
                verdict = "Minggu yang mencabar. Tak apa, minggu depan kita cuba lagi! 😊"

            if avg_pro < target_pro * 0.8:
                tip = "💡 Protein awak rendah minggu ni. Cuba tambah telur, ayam atau ikan."
            elif avg_cal > target_cal * 1.1:
                tip = "💡 Kalori sedikit tinggi minggu ni. Cuba kurangkan minyak dan gula."
            else:
                tip = "💡 Nutrisi awak dalam kawalan. Teruskan!"

            text = (
                f"📊 Laporan Mingguan — {name}\n\n"
                f"📅 Hari direkod: {days}/7 hari ({consistency}%)\n"
                f"🔥 Purata Kalori: {avg_cal} / {target_cal} kcal\n"
                f"🥩 Purata Protein: {avg_pro} / {target_pro}g\n"
                f"🔥 Streak semasa: {streak} hari\n\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"{verdict}\n\n"
                f"{tip}\n\n"
                f"Semangat minggu depan! 💪"
            )

            await context.bot.send_message(chat_id=telegram_id, text=text)
            sent += 1

        except Exception as e:
            logger.warning(f"Gagal weekly report → {telegram_id}: {e}")

    logger.info(f"Weekly report: {sent}/{len(users)} pengguna.")
