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

logger = logging.getLogger(__name__)

# Malaysia = UTC+8
MORNING_HOUR_UTC   = 0   # 8:00 pagi MYT
NOON_HOUR_UTC      = 4   # 12:00 tengah hari MYT
AFTERNOON_HOUR_UTC = 9   # 5:00 petang MYT
EVENING_HOUR_UTC   = 13  # 9:00 malam MYT
WEEKLY_HOUR_UTC    = 12  # 8:00 malam MYT (Ahad)


async def send_morning_reminder(context):
    """8 pagi — semangat + galak log sarapan."""
    users = db.get_users_for_reminder("pagi")
    sent = 0

    from datetime import date
    messages = [
        "🌅 Selamat pagi! Hari baru, semangat baru 💪\n\nJangan lupa snap gambar sarapan awak untuk jejak nutrisi hari ini!",
        "☀️ Good morning! Dah breakfast?\n\nHantar gambar makanan dan biar FitJejak kira kalori untuk awak 📸",
        "🌄 Pagi-pagi dah semangat! 💪\n\nMula hari dengan betul — log sarapan awak sekarang dan kekalkan streak!",
        "🌞 Selamat pagi! Ingat matlamat awak hari ini?\n\n📸 Snap gambar sarapan dan mula jejak nutrisi!",
    ]
    day_index = date.today().weekday() % len(messages)
    text = messages[day_index]

    for user in users:
        try:
            await context.bot.send_message(chat_id=user["telegram_id"], text=text)
            sent += 1
        except Exception as e:
            logger.warning(f"Gagal morning reminder → {user['telegram_id']}: {e}")

    logger.info(f"Morning reminder: {sent}/{len(users)} pengguna.")


async def send_noon_reminder(context):
    """12 tengah hari — galak log makan tengah hari."""
    users = db.get_users_for_reminder("tengahari")
    sent = 0

    from datetime import date
    messages = [
        "🍱 Dah makan tengah hari?\n\nSnap gambar lauk awak dan log sekarang. Jangan bagi kalori lari! 😄",
        "🕛 Waktu lunch! Jangan lupa log makan tengah hari awak 📸\n\nTinggal beberapa klik je dengan FitJejak.",
        "☀️ Dah dekat tengah hari ni. Lunch dah order?\n\nHantar gambar bila dah dapat — FitJejak uruskan yang lain!",
        "🍛 Makan tengah hari penting untuk kekalkan tenaga! 💪\n\nLog makanan awak dengan snap gambar sekarang.",
    ]
    day_index = date.today().weekday() % len(messages)
    text = messages[day_index]

    for user in users:
        try:
            await context.bot.send_message(chat_id=user["telegram_id"], text=text)
            sent += 1
        except Exception as e:
            logger.warning(f"Gagal noon reminder → {user['telegram_id']}: {e}")

    logger.info(f"Noon reminder: {sent}/{len(users)} pengguna.")


async def send_afternoon_reminder(context):
    """5 petang — galak log snack / check progress."""
    users = db.get_users_for_reminder("petang")
    sent = 0

    from datetime import date
    messages = [
        "🌤️ Petang dah tiba! Ada makan snack petang?\n\nLog sekarang dan check berapa lagi kalori untuk malam. Taip /today 📊",
        "🥤 5 petang! Snack time ke?\n\nHantar gambar snack awak — FitJejak akan kira untuk awak 😄",
        "🌅 Dah nak habis waktu kerja! Check progress hari ini dengan /today 📊\n\nMasih ada ruang untuk makan malam yang sihat!",
        "🍎 Petang ni ada snack? Log je semua, jangan skip!\n\nKonsistensi adalah kunci kejayaan 💪",
    ]
    day_index = date.today().weekday() % len(messages)
    text = messages[day_index]

    for user in users:
        try:
            await context.bot.send_message(chat_id=user["telegram_id"], text=text)
            sent += 1
        except Exception as e:
            logger.warning(f"Gagal afternoon reminder → {user['telegram_id']}: {e}")

    logger.info(f"Afternoon reminder: {sent}/{len(users)} pengguna.")


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
