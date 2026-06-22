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
            "/admin add <id> <scan> — Tambah kredit\n"
            "/admin promo create CODE SCAN [DESC] — Cipta promo code\n"
            "/admin promo list — Senarai promo codes\n\n"
            "Contoh:\n"
            "/admin add 123456789 100\n"
            "/admin promo create FITJEJAK10 10 Promo new user"
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

    # /admin promo create CODE SCANS [DESC]
    elif subcommand == "promo":
        if len(args) < 2:
            await update.message.reply_text(
                "⚠️ Subcommand promo:\n"
                "/admin promo create CODE SCANS [DESC]\n"
                "/admin promo list"
            )
            return
        sub2 = args[1].lower()
        if sub2 == "create":
            if len(args) < 4:
                await update.message.reply_text("⚠️ Contoh: /admin promo create FITJEJAK10 10")
                return
            await _cmd_promo_create(update, args[2], args[3], " ".join(args[4:]) if len(args) > 4 else "")
        elif sub2 == "list":
            await _cmd_promo_list(update)
        else:
            await update.message.reply_text(f"⚠️ Sub-promo tidak dikenali: {sub2}")

    else:
        await update.message.reply_text(f"⚠️ Subcommand tidak dikenali: {subcommand}")


async def _cmd_users(update: Update):
    """Senaraikan semua pengguna."""
    users = db.get_all_users()

    if not users:
        await update.message.reply_text("Tiada pengguna lagi.")
        return

    total = len(users)
    setup_done = sum(1 for u in users if u["setup_complete"])
    total_referrals = sum(u.get("referral_count") or 0 for u in users)

    lines = [
        f"👥 Pengguna: {total} orang ({setup_done} setup lengkap)\n"
        f"🔗 Jumlah Referral: {total_referrals}\n"
    ]

    for u in users:
        name = u["first_name"] or "?"
        username = f"@{u['username']}" if u["username"] else "-"
        setup = "✅" if u["setup_complete"] else "⏳"
        scans = u["scans_remaining"]
        ref = u.get("referral_count") or 0
        ref_str = f" | 🔗 {ref}" if ref > 0 else ""
        topup = u.get("topup_count") or 0
        topup_str = f" | 💳 {topup}x" if topup > 0 else ""
        lines.append(
            f"{setup} {name} ({username})\n"
            f"   Scan: {scans}{ref_str}{topup_str}"
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


async def _cmd_promo_create(update: Update, code: str, scans_str: str, description: str):
    """Cipta promo code baru."""
    try:
        scans = int(scans_str)
        if scans <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("⚠️ Jumlah scan mesti nombor positif.")
        return

    ok = db.create_promo_code(code.upper(), scans, description)
    if ok:
        await update.message.reply_text(
            f"✅ Promo code berjaya dicipta!\n\n"
            f"Kod: {code.upper()}\n"
            f"Bonus: +{scans} scan\n"
            f"Desc: {description or '-'}\n\n"
            f"User boleh guna: /promo {code.upper()}"
        )
    else:
        await update.message.reply_text(f"❌ Kod '{code.upper()}' sudah wujud.")


async def _cmd_promo_list(update: Update):
    """Senaraikan semua promo codes."""
    promos = db.get_all_promo_codes()

    if not promos:
        await update.message.reply_text("Tiada promo code lagi.\nGuna: /admin promo create CODE SCANS")
        return

    lines = [f"🎟️ Promo Codes ({len(promos)} kod)\n"]
    for p in promos:
        status = "✅" if p["is_active"] else "❌"
        expiry = p["expiry_date"] or "Tiada had"
        max_u = f"{p['max_uses']}" if p["max_uses"] else "∞"
        lines.append(
            f"{status} {p['code']} — +{p['bonus_scans']} scan\n"
            f"   Guna: {p['uses_count']}/{max_u} | Tamat: {expiry}"
        )

    await update.message.reply_text("\n\n".join(lines))
