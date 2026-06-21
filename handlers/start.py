"""
handlers/start.py — FitJejak
Handler untuk /start dan proses setup profil pengguna.
Menggunakan ConversationHandler untuk soal-jawab berperingkat.
"""
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, filters
)
import database as db
from utils.nutrition import calculate_targets

# ── State untuk ConversationHandler ──────────────────────────────
(
    ASK_WEIGHT, ASK_HEIGHT, ASK_AGE, ASK_GENDER,
    ASK_ACTIVITY, ASK_GOAL
) = range(6)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handler untuk command /start"""
    user = update.effective_user
    telegram_id = user.id

    # Daftarkan pengguna jika baru
    db.create_user(telegram_id, user.username or "", user.first_name or "")

    # Semak ada referral code dalam args (/start ref_XXXXXX)
    args = context.args
    if args and args[0].startswith("ref_"):
        ref_code = args[0][4:]  # buang "ref_" prefix
        context.user_data["pending_referral"] = ref_code

    existing = db.get_user(telegram_id)

    # Jika dah setup, tunjuk menu utama
    if existing and existing["setup_complete"]:
        await update.message.reply_text(
            f"👋 Selamat kembali, {user.first_name}!\n\n"
            "Apa yang anda nak buat hari ini?\n\n"
            "📸 Hantar gambar makanan — untuk scan nutrisi\n"
            "📊 /today — Ringkasan hari ini\n"
            "⚖️ /weight [kg] — Rekod berat badan\n"
            "📈 /summary — Ringkasan minggu ini\n"
            "💳 /credits — Semak baki scan\n"
            "⚙️ /profile — Tukar profil"
        )
        return ConversationHandler.END

    # Pengguna baru — mula setup
    await update.message.reply_text(
        f"🏋️ Selamat datang ke FitJejak, {user.first_name}!\n\n"
        "Saya akan bantu anda jejak nutrisi harian dengan mudah.\n"
        "Hantar sahaja gambar makanan, saya uruskan yang lain!\n\n"
        "Jom setup profil anda dulu. Ini ambil masa 1 minit sahaja.\n\n"
        "📊 Soalan 1/6: Berapa berat badan anda sekarang? (dalam kg)\n\n"
        "Contoh: 75"
    )
    return ASK_WEIGHT


async def ask_weight(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Terima berat badan."""
    try:
        weight = float(update.message.text.strip().replace("kg", ""))
        if not (20 <= weight <= 300):
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "⚠️ Sila masukkan berat dalam kg yang sah.\n_Contoh: 75_",
            parse_mode="Markdown"
        )
        return ASK_WEIGHT

    context.user_data["weight"] = weight

    await update.message.reply_text(
        "📊 Soalan 2/6: Berapa tinggi anda? (dalam cm)\n\nContoh: 170"
    )
    return ASK_HEIGHT


async def ask_height(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Terima tinggi badan."""
    try:
        height = float(update.message.text.strip().replace("cm", ""))
        if not (100 <= height <= 250):
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "⚠️ Sila masukkan tinggi dalam cm yang sah.\nContoh: 170"
        )
        return ASK_HEIGHT

    context.user_data["height"] = height

    await update.message.reply_text(
        "📊 Soalan 3/6: Berapa umur anda?\n\nContoh: 25"
    )
    return ASK_AGE


async def ask_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Terima umur."""
    try:
        age = int(update.message.text.strip())
        if not (10 <= age <= 100):
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "⚠️ Sila masukkan umur yang sah.\nContoh: 25"
        )
        return ASK_AGE

    context.user_data["age"] = age

    keyboard = [["Lelaki", "Perempuan"]]
    await update.message.reply_text(
        "📊 Soalan 4/6: Jantina anda?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return ASK_GENDER


async def ask_gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Terima jantina."""
    text = update.message.text.strip().lower()
    if text not in ["lelaki", "perempuan"]:
        await update.message.reply_text("⚠️ Sila pilih Lelaki atau Perempuan.")
        return ASK_GENDER

    context.user_data["gender"] = text

    keyboard = [
        ["😴 Tidak aktif (duduk sahaja)"],
        ["🚶 Ringan (senaman 1-3x seminggu)"],
        ["🏃 Sederhana (senaman 3-5x seminggu)"],
        ["💪 Aktif (senaman 6-7x seminggu)"],
        ["🔥 Sangat aktif (kerja fizikal/athlete)"]
    ]
    await update.message.reply_text(
        "📊 Soalan 5/6: Tahap aktiviti harian anda?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return ASK_ACTIVITY


async def ask_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Terima tahap aktiviti."""
    activity_map = {
        "😴 tidak aktif (duduk sahaja)": "sedentary",
        "🚶 ringan (senaman 1-3x seminggu)": "light",
        "🏃 sederhana (senaman 3-5x seminggu)": "moderate",
        "💪 aktif (senaman 6-7x seminggu)": "active",
        "🔥 sangat aktif (kerja fizikal/athlete)": "very_active"
    }
    text = update.message.text.strip().lower()
    activity = activity_map.get(text)

    if not activity:
        await update.message.reply_text("⚠️ Sila pilih salah satu pilihan di atas.")
        return ASK_ACTIVITY

    context.user_data["activity"] = activity

    keyboard = [
        ["🔥 Turunkan berat badan"],
        ["⚖️ Kekalkan berat badan"],
        ["💪 Naikkan otot"]
    ]
    await update.message.reply_text(
        "📊 Soalan 6/6: Apakah sasaran utama anda?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return ASK_GOAL


async def ask_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Terima goal dan simpan profil. Kira target kalori & protein."""
    goal_map = {
        "🔥 turunkan berat badan": "turun_berat",
        "⚖️ kekalkan berat badan": "kekal",
        "💪 naikkan otot": "naik_otot"
    }
    text = update.message.text.strip().lower()
    goal = goal_map.get(text)

    if not goal:
        await update.message.reply_text("⚠️ Sila pilih salah satu sasaran di atas.")
        return ASK_GOAL

    # Ambil data dari user_data
    d = context.user_data
    weight  = d["weight"]
    height  = d["height"]
    age     = d["age"]
    gender  = d["gender"]
    activity = d["activity"]

    # Kira target
    target_calories, target_protein, target_carbs, target_fat = calculate_targets(
        weight, height, age, gender, activity, goal
    )

    # Simpan ke database
    telegram_id = update.effective_user.id
    db.update_user_profile(
        telegram_id,
        weight_kg=weight,
        height_cm=height,
        age=age,
        gender=gender,
        activity_level=activity,
        goal=goal,
        target_calories=target_calories,
        target_protein=target_protein,
        target_carbs=target_carbs,
        target_fat=target_fat,
        setup_complete=1
    )
    # Rekod berat pertama
    db.log_weight(telegram_id, weight)

    # Proses referral kalau ada
    referral_bonus = ""
    pending_ref = context.user_data.pop("pending_referral", None)
    if pending_ref:
        referrer = db.get_user_by_referral_code(pending_ref)
        if referrer and referrer["telegram_id"] != telegram_id:
            success = db.process_referral(telegram_id, referrer["telegram_id"])
            if success:
                referral_bonus = f"🎁 Bonus referral: +5 scan percuma!\n"
                # Notify referrer
                try:
                    await context.bot.send_message(
                        chat_id=referrer["telegram_id"],
                        text=f"🎉 Kawan anda baru join FitJejak guna kod referral anda!\n"
                             f"Anda dapat +5 scan percuma sebagai hadiah. Terima kasih!"
                    )
                except Exception:
                    pass

    goal_label = {
        "turun_berat": "Turunkan Berat Badan 🔥",
        "kekal":       "Kekalkan Berat Badan ⚖️",
        "naik_otot":   "Naikkan Otot 💪"
    }[goal]

    await update.message.reply_text(
        f"✅ Profil berjaya disimpan!\n\n"
        f"👤 Berat: {weight}kg | Tinggi: {height}cm\n"
        f"🎯 Sasaran: {goal_label}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📊 Sasaran Harian Anda:\n"
        f"🔥 Kalori: {target_calories:,} kcal\n"
        f"🥩 Protein: {target_protein}g\n"
        f"🍚 Karbo:   {target_carbs}g\n"
        f"🧈 Lemak:   {target_fat}g\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"🎁 Anda ada 20 scan percuma untuk dicuba!\n"
        f"{referral_bonus}\n"
        f"📸 Sekarang, hantar gambar makanan pertama anda!",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


async def _photo_during_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Jika pengguna hantar gambar semasa setup belum siap."""
    await update.message.reply_text(
        "⚠️ Sila lengkapkan setup profil dulu.\n"
        "Jawab soalan yang ditanya, atau taip /cancel untuk mula semula."
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Batalkan setup."""
    await update.message.reply_text(
        "Setup dibatalkan. Taip /start bila anda bersedia.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


def get_setup_handler() -> ConversationHandler:
    """Return ConversationHandler untuk setup profil."""
    return ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_WEIGHT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_weight)],
            ASK_HEIGHT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_height)],
            ASK_AGE:      [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_age)],
            ASK_GENDER:   [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_gender)],
            ASK_ACTIVITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_activity)],
            ASK_GOAL:     [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_goal)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(filters.PHOTO, _photo_during_setup),
        ],
        allow_reentry=True
    )
