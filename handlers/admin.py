"""
handlers/admin.py — FitJejak
Command /admin untuk pengurusan bot (hanya admin sahaja).

Cara guna:
    /admin                        — Tunjuk menu admin
    /admin users                  — Senarai semua pengguna
    /admin info <telegram_id>     — Info satu pengguna
    /admin add <telegram_id> <n>  — Tambah n scan kepada pengguna
"""
from telegram import Update
from telegram.ext import ContextTypes
import database as db
from config import ADMIN_TELEGRAM_ID


def _is_admin(update: Update) -> bool:
    """Semak sama ada penghantar mesej adalah admin."""
    return update.effective_user.id == ADMIN_TELEGRAM_ID


# ── /admin ────────────────────────────────────────────────────────

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main admin command."""

    if not _is_admin(update):
        await update.message.reply_text("⛔ Akses ditolak.")
        return

    args = context.args

    # /admin — tunjuk menu
    if not args:
        await update.message.reply_text(
            "🔧 Panel Admin FitJejak\n\n"
            "/admin users — Senarai pengguna\n"
            "/admin info <id> — Info pengguna\n"
            "/admin add <id> <scan> — Tambah kredit\n\n"
            "Contoh:\n"
            "/admin add 123456789 100\n"
            "/admin info 123456789"
        )
        return

    subcommand = args[0].lower()

    # /admin users
    if subcommand == "users":
        await _cmd_users(update)

    # /admin info <telegram_id>
    elif subcommand == "info":
        if len(args) < 2:
            await update.message.reply_text("⚠️ Contoh: /admin info 123456789")
            return
        await _cmd_info(update, args[1])

    # /admin add <telegram_id> <scans>
    elif subcommand == "add":
        if len(args) < 3:
            await update.message.reply_text("⚠️ Contoh: /admin add 123456789 100")
            return
        await _cmd_add(update, args[1], args[2])

    else:
        await update.message.reply_text(f"⚠️ Subcommand tidak dikenali: {subcommand}")


async def _cmd_users(update: Update):
    """Senaraikan semua pengguna."""
    users = db.get_all_users()

    if not users:
        await update.message.reply_text("Tiada pengguna lagi.")
        return

    lines = [f"👥 Pengguna ({len(users)} orang)\n"]
    for u in users:
        name = u["first_name"] or "?"
        username = f"@{u['username']}" if u["username"] else "-"
        setup = "✅" if u["setup_complete"] else "⏳"
        scans = u["scans_remaining"]
        lines.append(
            f"{setup} {name} ({username})\n"
            f"   ID: {u['telegram_id']} | Scan: {scans}"
        )

    # Telegram limit 4096 chars — hantar bahagi-bahagi jika perlu
    text = "\n\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n...(potong)"

    await update.message.reply_text(text)


async def _cmd_info(update: Update, user_id_str: str):
    """Tunjuk info detail satu pengguna."""
    try:
        user_id = int(user_id_str)
    except ValueError:
        await update.message.reply_text("⚠️ ID mesti nombor. Contoh: /admin info 123456789")
        return

    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text(f"❌ Pengguna {user_id} tidak dijumpai.")
        return

    goal_label = {
        "turun_berat": "Turun berat",
        "kekal": "Kekal",
        "naik_otot": "Naik otot"
    }.get(user["goal"] or "", "-")

    reply = (
        f"👤 Info Pengguna\n\n"
        f"ID: {user['telegram_id']}\n"
        f"Nama: {user['first_name'] or '-'}\n"
        f"Username: @{user['username'] or '-'}\n"
        f"Setup: {'Lengkap ✅' if user['setup_complete'] else 'Belum ⏳'}\n\n"
        f"⚖️ Berat: {user['weight_kg'] or '-'}kg\n"
        f"📏 Tinggi: {user['height_cm'] or '-'}cm\n"
        f"🎂 Umur: {user['age'] or '-'} tahun\n"
        f"🎯 Sasaran: {goal_label}\n\n"
        f"💳 Scan tersisa: {user['scans_remaining']}\n"
        f"📅 Daftar: {user['created_at'] or '-'}"
    )

    await update.message.reply_text(reply)


async def _cmd_add(update: Update, user_id_str: str, scans_str: str):
    """Tambah kredit scan kepada pengguna."""
    try:
        user_id = int(user_id_str)
        scans = int(scans_str)
        if scans <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "⚠️ Format salah. Contoh: /admin add 123456789 100"
        )
        return

    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text(f"❌ Pengguna {user_id} tidak dijumpai.")
        return

    before = user["scans_remaining"]
    db.add_credits(user_id, scans)
    after = before + scans

    await update.message.reply_text(
        f"✅ Kredit berjaya ditambah!\n\n"
        f"Pengguna: {user['first_name'] or user_id}\n"
        f"Sebelum: {before} scan\n"
        f"Ditambah: +{scans} scan\n"
        f"Selepas: {after} scan"
    )
