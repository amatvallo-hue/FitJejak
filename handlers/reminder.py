"""
handlers/reminder.py — FitJejak
Reminder harian automatik kepada semua pengguna.

- Pagi (8:00 AM MYT): Semangat pagi + galak log makanan
- Malam (9:00 PM MYT): Check sama ada dah log hari ni atau belum
"""
import logging
import database as db

logger = logging.getLogger(__name__)

# Malaysia = UTC+8, jadi:
# 8:00 AM MYT = 00:00 UTC
# 9:00 PM MYT = 13:00 UTC
MORNING_HOUR_UTC = 0   # 8 pagi MYT
EVENING_HOUR_UTC = 13  # 9 malam MYT


async def send_morning_reminder(context):
    """Hantar reminder pagi kepada semua pengguna."""
    users = db.get_users_for_reminder()
    sent = 0

    messages = [
        "🌅 Selamat pagi! Hari baru, semangat baru 💪\n\nJangan lupa snap gambar sarapan awak untuk jejak nutrisi hari ini. Konsistensi adalah kunci!",
        "☀️ Good morning! Dah breakfast?\n\nHantar gambar makanan awak dan biar FitJejak kira kalori untuk awak 📸",
        "🌄 Pagi-pagi dah semangat! 💪\n\nMula hari dengan betul — log sarapan awak sekarang dan kekalkan streak harian awak!",
        "🌞 Selamat pagi! Ingat matlamat awak hari ini?\n\n📸 Hantar gambar makanan untuk mula jejak nutrisi hari ini.",
    ]

    from datetime import date
    # Guna hari dalam minggu untuk pilih mesej (supaya tak sama tiap hari)
    day_index = date.today().weekday() % len(messages)
    text = messages[day_index]

    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user["telegram_id"],
                text=text
            )
            sent += 1
        except Exception as e:
            # Pengguna mungkin dah block bot
            logger.warning(f"Gagal hantar morning reminder ke {user['telegram_id']}: {e}")

    logger.info(f"Morning reminder dihantar kepada {sent}/{len(users)} pengguna.")


async def send_evening_reminder(context):
    """Hantar reminder malam — bezakan antara yang dah log dan belum."""
    users = db.get_users_for_reminder()
    sent_logged = 0
    sent_not_logged = 0

    for user in users:
        telegram_id = user["telegram_id"]
        name = user["first_name"] or "Kawan"

        try:
            if db.has_logged_today(telegram_id):
                # Dah log — bagi pujian
                text = (
                    f"🌙 Tahniah {name}! Awak dah log makanan hari ini ✅\n\n"
                    f"Konsistensi awak sangat bagus. Teruskan esok!\n\n"
                    f"Taip /today untuk tengok ringkasan hari ini 📊"
                )
                sent_logged += 1
            else:
                # Belum log langsung
                text = (
                    f"🌙 Eh {name}, awak belum log makanan hari ini!\n\n"
                    f"Tak apa, masih sempat lagi 😊 Snap gambar makan malam awak sekarang.\n\n"
                    f"📸 Hantar gambar dan FitJejak akan kira kalori untuk awak."
                )
                sent_not_logged += 1

            await context.bot.send_message(chat_id=telegram_id, text=text)

        except Exception as e:
            logger.warning(f"Gagal hantar evening reminder ke {telegram_id}: {e}")

    logger.info(
        f"Evening reminder: {sent_logged} dah log, {sent_not_logged} belum log."
    )
