"""
handlers/topup.py — FitJejak
Flow topup kredit (ToyyibPay):
  1. User pilih pakej → bot panggil ToyyibPay API → dapat link bayaran
  2. User bayar melalui link (FPX/kad)
  3. ToyyibPay callback ke Railway → kredit auto ditambah
  4. User dapat notifikasi

Fallback (QR manual) kalau ToyyibPay gagal.
"""
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ContextTypes

import database as db
from config import (
    CREDIT_PACKAGES, ADMIN_TELEGRAM_ID,
    QR_IMAGE_PATH, PAYMENT_ACCOUNT_NAME, PAYMENT_ACCOUNT_NUMBER
)
from handlers.payment import create_toyyibpay_bill

logger = logging.getLogger(__name__)


# ── Step 1: Tunjuk senarai pakej ─────────────────────────────────

async def topup_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tunjuk pilihan pakej topup sebagai inline buttons."""
    user = db.get_user(update.effective_user.id)
    if not user or not user["setup_complete"]:
        await update.message.reply_text("⚠️ Sila /start untuk setup profil dulu.")
        return

    buttons = []
    for key, pkg in CREDIT_PACKAGES.items():
        label = f"{pkg['name']} — RM{pkg['price_rm']} ({pkg['scans']} scan)"
        buttons.append([InlineKeyboardButton(label, callback_data=f"topup_pkg_{key}")])

    buttons.append([InlineKeyboardButton("❌ Batal", callback_data="topup_cancel")])

    await update.message.reply_text(
        "💳 Pilih Pakej Topup\n\n"
        "Bayar melalui FPX / kad kredit.\n"
        "Kredit ditambah automatik selepas bayaran berjaya.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ── Step 2: User pilih pakej → tunjuk QR ─────────────────────────

async def handle_package_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback bila user tekan butang pakej."""
    query = update.callback_query
    await query.answer()

    if query.data == "topup_cancel":
        await query.edit_message_text("❌ Topup dibatalkan.")
        return

    pkg_key = query.data.replace("topup_pkg_", "")
    pkg = CREDIT_PACKAGES.get(pkg_key)
    if not pkg:
        await query.edit_message_text("⚠️ Pakej tidak dijumpai.")
        return

    telegram_id = update.effective_user.id

    user_info = db.get_user(telegram_id)
    user_name = user_info["first_name"] if user_info else "FitJejak User"

    # Simpan request dalam DB
    request_id = db.create_topup_request(
        telegram_id, pkg_key, pkg["price_rm"], pkg["scans"]
    )

    # Edit mesej lama dulu
    await query.edit_message_text(
        f"⏳ Menjana link pembayaran...\n\n"
        f"Pakej: {pkg['name']} — RM{pkg['price_rm']}\n"
        f"Kredit: {pkg['scans']} scan"
    )

    # Cuba jana link ToyyibPay
    bill_code, payment_url = await create_toyyibpay_bill(
        request_id, pkg_key, pkg["price_rm"], user_name
    )

    if payment_url:
        # ToyyibPay berjaya — hantar link
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Bayar Sekarang", url=payment_url)]
        ])
        await context.bot.send_message(
            chat_id=telegram_id,
            text=(
                f"✅ Link pembayaran sedia!\n\n"
                f"📦 Pakej: {pkg['name']}\n"
                f"💰 Jumlah: RM{pkg['price_rm']:.2f}\n"
                f"🎯 Kredit: {pkg['scans']} scan\n\n"
                f"Tekan butang di bawah untuk bayar melalui FPX / kad kredit.\n"
                f"Kredit akan ditambah automatik selepas bayaran berjaya. 🎉"
            ),
            reply_markup=keyboard
        )
    else:
        # Fallback ke QR manual
        logger.warning(f"ToyyibPay gagal untuk request #{request_id} — fallback ke QR manual")

        # Simpan dalam user_data supaya tau bila user hantar slip
        context.user_data["pending_topup_id"] = request_id
        context.user_data["pending_topup_pkg"] = pkg["name"]
        context.user_data["pending_topup_rm"] = pkg["price_rm"]

        caption = (
            f"💳 Arahan Pembayaran (Manual)\n\n"
            f"Pakej: {pkg['name']}\n"
            f"Jumlah: RM{pkg['price_rm']:.2f}\n\n"
        )
        if PAYMENT_ACCOUNT_NAME:
            caption += f"Nama: {PAYMENT_ACCOUNT_NAME}\n"
        if PAYMENT_ACCOUNT_NUMBER:
            caption += f"No. Akaun: {PAYMENT_ACCOUNT_NUMBER}\n"
        caption += (
            f"\n⚠️ Pastikan jumlah TEPAT: RM{pkg['price_rm']:.2f}\n\n"
            f"Selepas transfer, hantar gambar slip di chat ini.\n"
            f"Admin akan verify dalam 1-24 jam."
        )

        qr_sent = False
        if os.path.exists(QR_IMAGE_PATH):
            try:
                with open(QR_IMAGE_PATH, "rb") as qr_file:
                    await context.bot.send_photo(
                        chat_id=telegram_id,
                        photo=InputFile(qr_file),
                        caption=caption
                    )
                qr_sent = True
            except Exception as e:
                logger.warning(f"Gagal hantar QR image: {e}")

        if not qr_sent:
            await context.bot.send_message(chat_id=telegram_id, text=caption)

        await context.bot.send_message(
            chat_id=telegram_id,
            text="📸 Hantar gambar slip pembayaran sekarang:"
        )


# ── Step 3: User hantar slip (gambar) ────────────────────────────

async def handle_payment_slip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Dipanggil dari food.py bila user hantar gambar DAN ada pending_topup_id.
    Return True jika slip berjaya diproses (supaya food.py skip analisis makanan).
    """
    telegram_id = update.effective_user.id
    request_id = context.user_data.get("pending_topup_id")

    if not request_id:
        return False  # Bukan slip topup — food.py proses sebagai gambar makanan

    pkg_name = context.user_data.get("pending_topup_pkg", "")
    amount_rm = context.user_data.get("pending_topup_rm", 0)

    # Ambil file_id gambar yang dihantar user
    photo = update.message.photo[-1]  # ambil resolusi tertinggi
    slip_file_id = photo.file_id

    # Simpan slip dalam DB
    db.update_topup_slip(request_id, slip_file_id)

    # Clear user_data
    context.user_data.pop("pending_topup_id", None)
    context.user_data.pop("pending_topup_pkg", None)
    context.user_data.pop("pending_topup_rm", None)

    # Maklum user
    await update.message.reply_text(
        "✅ Slip diterima! Admin sedang verify.\n\n"
        "Kredit akan ditambah selepas disahkan.\n"
        "Anda akan dapat notifikasi bila siap."
    )

    # Notify admin dengan slip + butang approve/reject
    user_info = db.get_user(telegram_id)
    name = user_info["first_name"] if user_info else str(telegram_id)
    username = f"@{user_info['username']}" if user_info and user_info.get("username") else "-"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Duit Masuk", callback_data=f"topup_approve_{request_id}"),
            InlineKeyboardButton("❌ Tolak",      callback_data=f"topup_reject_{request_id}"),
        ]
    ])

    caption = (
        f"💳 TOPUP REQUEST #{request_id}\n\n"
        f"👤 {name} ({username})\n"
        f"🆔 ID: {telegram_id}\n"
        f"📦 Pakej: {pkg_name}\n"
        f"💰 Amaun: RM{amount_rm:.2f}\n\n"
        f"Tekan ✅ Duit Masuk untuk luluskan."
    )

    try:
        await context.bot.send_photo(
            chat_id=ADMIN_TELEGRAM_ID,
            photo=slip_file_id,
            caption=caption,
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Gagal notify admin: {e}")

    return True  # Signal ke food.py untuk skip food analysis


# ── Step 4: Admin sahkan / tolak ─────────────────────────────────

async def handle_topup_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback bila admin tekan Duit Masuk atau Tolak."""
    query = update.callback_query
    telegram_id = update.effective_user.id

    # Hanya admin boleh approve
    if telegram_id != ADMIN_TELEGRAM_ID:
        await query.answer("⛔ Anda bukan admin.", show_alert=True)
        return

    await query.answer()

    data = query.data  # topup_approve_123 atau topup_reject_123
    parts = data.split("_")
    action = parts[1]       # "approve" atau "reject"
    request_id = int(parts[2])

    if action == "approve":
        req = db.approve_topup_request(request_id)
        if not req:
            await query.edit_message_caption(
                query.message.caption + "\n\n⚠️ Request ini dah diproses atau tidak dijumpai."
            )
            return

        pkg = CREDIT_PACKAGES.get(req["package_key"], {})
        pkg_name = pkg.get("name", req["package_key"])

        # Update mesej admin
        await query.edit_message_caption(
            query.message.caption + f"\n\n✅ DILULUSKAN oleh admin."
        )

        # Notify user
        try:
            user_after = db.get_user(req["telegram_id"])
            baki = user_after["scans_remaining"] if user_after else req["scans"]
            await context.bot.send_message(
                chat_id=req["telegram_id"],
                text=(
                    f"🎉 Topup berjaya disahkan!\n\n"
                    f"📦 Pakej: {pkg_name}\n"
                    f"✅ +{req['scans']} scan ditambah\n"
                    f"💳 Baki sekarang: {baki} scan\n\n"
                    f"Terima kasih! Selamat scan 📸"
                )
            )
        except Exception as e:
            logger.error(f"Gagal notify user #{req['telegram_id']}: {e}")

    elif action == "reject":
        req = db.reject_topup_request(request_id)
        if not req:
            await query.edit_message_caption(
                query.message.caption + "\n\n⚠️ Request ini dah diproses atau tidak dijumpai."
            )
            return

        # Update mesej admin
        await query.edit_message_caption(
            query.message.caption + "\n\n❌ DITOLAK oleh admin."
        )

        # Notify user
        try:
            await context.bot.send_message(
                chat_id=req["telegram_id"],
                text=(
                    "❌ Topup anda tidak dapat disahkan.\n\n"
                    "Kemungkinan slip tidak jelas atau amaun tidak tepat.\n"
                    "Sila hubungi admin atau cuba semula: /topup"
                )
            )
        except Exception as e:
            logger.error(f"Gagal notify user #{req['telegram_id']}: {e}")
