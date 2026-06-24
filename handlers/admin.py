"""
handlers/admin.py — FitJejak
Command /admin untuk pengurusan bot (hanya admin sahaja).

Cara guna:
    /admin                        — Tunjuk menu admin
    /admin stats                  — Dashboard stats
    /admin users                  — Senarai semua pengguna
    /admin info <telegram_id>     — Info satu pengguna
    /admin add <telegram_id> <n>  — Tambah n scan kepada pengguna
    /admin affiliate add <id> <bank> <acc> — Daftar affiliate
    /admin affiliate list         — Senarai affiliates
    /admin affiliate payout [YYYY-MM] — Payout bulan ini
    /admin affiliate remove <id>  — Nyahaktifkan affiliate
"""
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db
from config import ADMIN_TELEGRAM_ID

_MYT = timezone(timedelta(hours=8))


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
            "/admin stats — Dashboard stats\n"
            "/admin users — Senarai pengguna\n"
            "/admin info <id> — Info pengguna\n"
            "/admin add <id> <scan> — Tambah kredit\n"
            "/admin promo create CODE SCAN [DESC] — Cipta promo code\n"
            "/admin promo list — Senarai promo codes\n\n"
            "── AFFILIATE ──\n"
            "/admin affiliate add <id> <bank> <no_akaun>\n"
            "/admin affiliate list\n"
            "/admin affiliate payout [YYYY-MM]\n"
            "/admin affiliate remove <id>\n\n"
            "Contoh:\n"
            "/admin add 123456789 100\n"
            "/admin affiliate add 123456789 Maybank 1234567890"
        )
        return

    subcommand = args[0].lower()

    # /admin broadcast keyboard — hantar keyboard baru ke semua user
    if subcommand == "broadcast" and len(args) > 1 and args[1].lower() == "keyboard":
        from utils.keyboard import MAIN_KEYBOARD
        users = db.get_users_for_reminder()
        sent = 0
        for u in users:
            try:
                await context.bot.send_message(
                    chat_id=u["telegram_id"],
                    text="🔄 FitJejak dikemaskini! Keyboard baru dah siap 💪",
                    reply_markup=MAIN_KEYBOARD
                )
                sent += 1
            except Exception:
                pass
        await update.message.reply_text(f"✅ Keyboard baru dihantar kepada {sent} user.")
        return

    # /admin stats
    if subcommand == "stats":
        await _cmd_stats(update)

    # /admin users
    elif subcommand == "users":
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

    # /admin affiliate
    elif subcommand == "affiliate":
        if len(args) < 2:
            await update.message.reply_text(
                "⚠️ Subcommand affiliate:\n"
                "/admin affiliate add <id> <bank> <no_akaun>\n"
                "/admin affiliate list\n"
                "/admin affiliate payout [YYYY-MM]\n"
                "/admin affiliate remove <id>"
            )
            return
        sub2 = args[1].lower()
        if sub2 == "add":
            if len(args) < 5:
                await update.message.reply_text("⚠️ Format: /admin affiliate add <id> <bank> <no_akaun>")
                return
            await _cmd_affiliate_add(update, args[2], args[3], args[4])
        elif sub2 == "list":
            await _cmd_affiliate_list(update)
        elif sub2 == "payout":
            month = args[2] if len(args) > 2 else None
            await _cmd_affiliate_payout(update, context, month)
        elif sub2 == "remove":
            if len(args) < 3:
                await update.message.reply_text("⚠️ Format: /admin affiliate remove <id>")
                return
            await _cmd_affiliate_remove(update, args[2])
        else:
            await update.message.reply_text(f"⚠️ Sub-affiliate tidak dikenali: {sub2}")

    # /admin promo
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


async def _cmd_stats(update: Update):
    """Tunjuk dashboard stats FitJejak."""
    s = db.get_admin_stats()

    pending_note = f"\n⏳ Pending topup: {s['pending_topup']} request — /admin users" if s["pending_topup"] > 0 else ""

    text = (
        f"📊 Stats FitJejak — {s['today_label']}\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"👥 PENGGUNA\n"
        f"Total: {s['total_users']} | Setup: {s['setup_users']}\n"
        f"Daftar hari ini: {s['new_today']} orang\n"
        f"Aktif hari ini: {s['active_today']} orang\n\n"
        f"📸 SCAN\n"
        f"AI scan hari ini: {s['scans_today']}\n"
        f"Total AI scan (all-time): {s['total_scans_used']}\n"
        f"Total log manual: {s['total_manual_logs']}\n\n"
        f"💰 REVENUE\n"
        f"{s['month_label']}: RM{s['revenue_month']:.2f} ({s['topups_month']} topup)\n"
        f"All-time: RM{s['revenue_total']:.2f} ({s['topups_total']} topup)"
        f"{pending_note}"
    )

    await update.message.reply_text(text)


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


async def _cmd_affiliate_add(update: Update, user_id_str: str, bank_name: str, bank_acc: str):
    """Daftarkan affiliate baru."""
    try:
        user_id = int(user_id_str)
    except ValueError:
        await update.message.reply_text("⚠️ ID mesti nombor.")
        return

    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text(f"❌ Pengguna {user_id} tidak dijumpai dalam sistem.")
        return

    ok = db.add_affiliate(user_id, bank_name, bank_acc)
    if not ok:
        await update.message.reply_text(f"⚠️ {user['first_name'] or user_id} sudah didaftar sebagai affiliate.")
        return

    await update.message.reply_text(
        f"✅ Affiliate berjaya didaftarkan!\n\n"
        f"👤 {user['first_name'] or '-'} (@{user['username'] or '-'})\n"
        f"🏦 Bank: {bank_name}\n"
        f"💳 Akaun: {bank_acc}\n"
        f"📊 Kadar: 5%\n\n"
        f"Mereka boleh guna /affiliate untuk tengok dashboard."
    )


async def _cmd_affiliate_list(update: Update):
    """Senarai semua affiliates + earnings bulan ini."""
    affiliates = db.get_all_affiliates()

    if not affiliates:
        await update.message.reply_text("Tiada affiliate lagi.\nGuna: /admin affiliate add <id> <bank> <acc>")
        return

    now_myt = datetime.now(_MYT)
    month_str = now_myt.strftime('%Y-%m')
    month_label = now_myt.strftime('%B %Y')

    lines = [f"💼 Affiliates FitJejak ({len(affiliates)} orang)\n{month_label}\n"]
    for a in affiliates:
        status_icon = "✅" if a["status"] == "active" else "❌"
        name = a["first_name"] or str(a["telegram_id"])
        username = f"@{a['username']}" if a.get("username") else "-"
        earnings = db.get_affiliate_earnings_summary(a["telegram_id"], month_str)
        lines.append(
            f"{status_icon} {name} ({username})\n"
            f"   Bank: {a['bank_name']} {a['bank_acc']}\n"
            f"   Bulan ini: RM{earnings['pending']:.2f} ({earnings['transactions']} topup)"
        )

    await update.message.reply_text("\n\n".join(lines))


async def _cmd_affiliate_payout(update: Update, context, month: str = None):
    """Tunjuk senarai payout bulan ini dengan butang Dah Bayar."""
    now_myt = datetime.now(_MYT)
    if not month:
        month = now_myt.strftime('%Y-%m')

    # Parse month label
    try:
        month_dt = datetime.strptime(month, '%Y-%m')
        month_label = month_dt.strftime('%B %Y')
    except ValueError:
        await update.message.reply_text("⚠️ Format bulan: YYYY-MM. Contoh: /admin affiliate payout 2026-06")
        return

    payouts = db.get_affiliate_payout_list(month)

    if not payouts:
        await update.message.reply_text(f"✅ Tiada bayaran tertunggak untuk {month_label}.")
        return

    total_all = sum(p["total_commission"] for p in payouts)

    await update.message.reply_text(
        f"💰 Payout Affiliate — {month_label}\n"
        f"Jumlah: RM{total_all:.2f} ({len(payouts)} affiliate)\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"Klik 'Dah Bayar' selepas buat pemindahan:"
    )

    for p in payouts:
        name = p["first_name"] or str(p["affiliate_id"])
        username = f"@{p['username']}" if p.get("username") else ""
        text = (
            f"👤 {name} {username}\n"
            f"🏦 {p['bank_name']} — {p['bank_acc']}\n"
            f"💵 RM{p['total_commission']:.2f} ({p['transactions']} topup)"
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                f"✅ Dah Bayar RM{p['total_commission']:.2f}",
                callback_data=f"aff_paid_{p['affiliate_id']}_{month}"
            )
        ]])
        await update.message.reply_text(text, reply_markup=keyboard)


async def _cmd_affiliate_remove(update: Update, user_id_str: str):
    """Nyahaktifkan affiliate."""
    try:
        user_id = int(user_id_str)
    except ValueError:
        await update.message.reply_text("⚠️ ID mesti nombor.")
        return

    user = db.get_user(user_id)
    db.remove_affiliate(user_id)
    name = user["first_name"] if user else str(user_id)
    await update.message.reply_text(f"❌ Affiliate {name} telah dinyahaktifkan.")


async def handle_affiliate_application_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback bila admin klik Luluskan/Tolak untuk affiliate application."""
    query = update.callback_query

    if update.effective_user.id != ADMIN_TELEGRAM_ID:
        await query.answer("⛔ Akses ditolak.", show_alert=True)
        return

    await query.answer()

    data = query.data  # aff_approv_<id> atau aff_reject_<id>
    parts = data.split("_")
    action = parts[1]   # 'approv' atau 'reject'
    app_id = int(parts[2])

    if action == "approv":
        app = db.approve_affiliate_application(app_id)
        if not app:
            await query.edit_message_text(query.message.text + "\n\n⚠️ Permohonan dah diproses sebelum ini.")
            return

        await query.edit_message_text(
            query.message.text + f"\n\n✅ DILULUSKAN oleh admin"
        )

        # Notify affiliate
        ref_code = db.get_or_create_referral_code(app["telegram_id"])
        from config import BOT_USERNAME
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{ref_code}"
        try:
            await context.bot.send_message(
                chat_id=app["telegram_id"],
                text=(
                    f"🎉 Tahniah! Permohonan affiliate anda telah DILULUSKAN!\n\n"
                    f"💼 Anda kini affiliate FitJejak\n"
                    f"📊 Kadar komisyen: 5% setiap topup\n"
                    f"💰 Bayaran: awal bulan ke {app['bank_name']} {app['bank_acc']}\n\n"
                    f"🔗 Link Referral Anda:\n{ref_link}\n\n"
                    f"Share link ni kepada kawan-kawan anda!\n"
                    f"Taip /affiliate untuk tengok dashboard."
                )
            )
        except Exception:
            pass

    elif action == "reject":
        app = db.reject_affiliate_application(app_id)
        if not app:
            await query.edit_message_text(query.message.text + "\n\n⚠️ Permohonan dah diproses sebelum ini.")
            return

        await query.edit_message_text(
            query.message.text + f"\n\n❌ DITOLAK oleh admin"
        )

        # Notify applicant
        try:
            await context.bot.send_message(
                chat_id=app["telegram_id"],
                text=(
                    "❌ Maaf, permohonan affiliate anda tidak berjaya pada masa ini.\n\n"
                    "Anda boleh hubungi kami melalui /support untuk maklumat lanjut."
                )
            )
        except Exception:
            pass


async def handle_affiliate_paid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback bila admin klik 'Dah Bayar' untuk affiliate."""
    query = update.callback_query

    if update.effective_user.id != ADMIN_TELEGRAM_ID:
        await query.answer("⛔ Akses ditolak.", show_alert=True)
        return

    await query.answer()

    # Pattern: aff_paid_<affiliate_id>_<month>
    data = query.data  # e.g. "aff_paid_123456_2026-06"
    parts = data.split("_")
    # aff_paid_<id>_<YYYY-MM>  → parts: ['aff', 'paid', '<id>', '<YYYY>', '<MM>']
    # handle month with dash: rejoin from index 3
    affiliate_id = int(parts[2])
    month = "_".join(parts[3:])  # handles 'YYYY-MM'

    total_paid = db.mark_affiliate_paid(affiliate_id, month)

    if total_paid == 0:
        await query.edit_message_text(
            query.message.text + "\n\n✅ (Sudah ditanda bayar sebelum ini)"
        )
        return

    user = db.get_user(affiliate_id)
    name = user["first_name"] if user else str(affiliate_id)

    await query.edit_message_text(
        query.message.text + f"\n\n✅ DIBAYAR — RM{total_paid:.2f} kepada {name}"
    )

    # Notify affiliate
    try:
        await context.bot.send_message(
            chat_id=affiliate_id,
            text=(
                f"💰 Bayaran Komisen Diterima!\n\n"
                f"Bulan: {month}\n"
                f"Jumlah: RM{total_paid:.2f}\n\n"
                f"Terima kasih atas sokongan anda kepada FitJejak! 🙏"
            )
        )
    except Exception:
        pass


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


# ── Admin Reply kepada User ───────────────────────────────────────

async def handle_reply_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin tekan button 💬 Balas — simpan user_id dan minta admin taip balasan."""
    query = update.callback_query

    if update.effective_user.id != ADMIN_TELEGRAM_ID:
        await query.answer("⛔ Akses ditolak.", show_alert=True)
        return

    await query.answer()

    user_id = int(query.data.split("_")[2])
    user = db.get_user(user_id)
    name = user["first_name"] if user else str(user_id)

    context.user_data["admin_reply_to"] = user_id
    context.user_data["admin_reply_name"] = name

    await query.message.reply_text(
        f"💬 Taip balasan untuk {name} (ID: {user_id}):\n\n"
        f"(Taip /cancel untuk batalkan)"
    )


async def handle_admin_reply_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Semak kalau admin dalam mode reply, proses balasan.
    Return True kalau diproses, False kalau bukan.
    """
    if update.effective_user.id != ADMIN_TELEGRAM_ID:
        return False

    reply_to = context.user_data.get("admin_reply_to")
    if not reply_to:
        return False

    text = update.message.text or ""

    if text.strip().lower() == "/cancel":
        context.user_data.pop("admin_reply_to", None)
        context.user_data.pop("admin_reply_name", None)
        await update.message.reply_text("❌ Balasan dibatalkan.")
        return True

    name = context.user_data.get("admin_reply_name", str(reply_to))

    try:
        await update.get_bot().send_message(
            chat_id=reply_to,
            text=(
                f"📩 Mesej dari FitJejak Support:\n\n"
                f"{text}\n\n"
                f"— Admin FitJejak 🙏"
            )
        )
        await update.message.reply_text(f"✅ Balasan berjaya dihantar kepada {name}!")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Gagal hantar ke {name}: {e}")

    context.user_data.pop("admin_reply_to", None)
    context.user_data.pop("admin_reply_name", None)
    return True
