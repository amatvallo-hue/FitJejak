"""
handlers/payment.py — FitJejak
ToyyibPay integration:
- create_toyyibpay_bill(): generate payment link
- handle_payment_callback(): terima callback dari ToyyibPay bila bayar berjaya
"""
import logging
import aiohttp
from aiohttp import web

import database as db
from config import (
    TOYYIBPAY_API_KEY, TOYYIBPAY_CATEGORY_CODE,
    TOYYIBPAY_BASE_URL, RAILWAY_URL, CREDIT_PACKAGES
)

logger = logging.getLogger(__name__)


async def create_toyyibpay_bill(request_id: int, pkg_key: str,
                                 amount_rm: float, user_name: str) -> tuple[str, str]:
    """
    Buat bill ToyyibPay.
    Return (bill_code, payment_url) atau (None, None) jika gagal.
    """
    pkg = CREDIT_PACKAGES.get(pkg_key, {})
    callback_url = f"https://{RAILWAY_URL}/payment/callback"

    data = {
        "userSecretKey":        TOYYIBPAY_API_KEY,
        "categoryCode":         TOYYIBPAY_CATEGORY_CODE,
        "billName":             f"FitJejak {pkg.get('name', pkg_key)}",
        "billDescription":      f"Topup {pkg.get('scans', 0)} scan kredit FitJejak",
        "billPriceSetting":     1,          # fixed price
        "billPayorInfo":        1,          # collect payer info
        "billAmount":           int(amount_rm * 100),  # dalam sen (RM10 = 1000)
        "billReturnUrl":        "https://t.me/FitJejakBot",
        "billCallbackUrl":      callback_url,
        "billTo":               user_name or "FitJejak User",
        "billEmail":            "",
        "billPhone":            "",
        "billSplitPayment":     0,
        "billSplitPaymentArgs": "",
        "billPaymentChannel":   0,          # semua channel
        "billContentEmail":     "",
        "billChargeToCustomer": 1,          # fee tanggung customer
        "billExternalReferenceNo": str(request_id),
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{TOYYIBPAY_BASE_URL}/index.php/api/createBill",
                data=data,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                result = await resp.json(content_type=None)

                if result and isinstance(result, list) and result[0].get("BillCode"):
                    bill_code = result[0]["BillCode"]
                    payment_url = f"{TOYYIBPAY_BASE_URL}/{bill_code}"
                    # Simpan bill_code dalam DB
                    db.save_bill_code(request_id, bill_code)
                    return bill_code, payment_url

                logger.error(f"ToyyibPay response error: {result}")
                return None, None

    except Exception as e:
        logger.error(f"ToyyibPay create bill error: {e}")
        return None, None


async def handle_payment_callback(request: web.Request) -> web.Response:
    """
    Callback dari ToyyibPay bila user buat payment.
    ToyyibPay POST ke: https://fitjejak-production.up.railway.app/payment/callback
    """
    try:
        data = await request.post()

        bill_code  = data.get("billcode", "")
        order_id   = data.get("order_id", "")
        status     = data.get("status", "0")
        amount     = data.get("amount", "0")

        logger.info(f"Payment callback: billcode={bill_code}, order_id={order_id}, status={status}")

        # status: 1=berjaya, 2=pending, 3=gagal
        if str(status) != "1":
            logger.info(f"Payment not successful, status={status}")
            return web.Response(text="OK")

        # Cari request_id dari order_id
        if not order_id or not order_id.isdigit():
            logger.warning(f"Invalid order_id: {order_id}")
            return web.Response(text="OK")

        request_id = int(order_id)
        req = db.get_topup_request(request_id)

        if not req:
            logger.warning(f"Request {request_id} not found")
            return web.Response(text="OK")

        if req["status"] == "approved":
            logger.info(f"Request {request_id} already approved")
            return web.Response(text="OK")

        # Luluskan topup
        approved_req = db.approve_topup_request(request_id)
        if not approved_req:
            return web.Response(text="OK")

        # Notify user via Telegram
        bot = request.app.get("bot")
        if bot:
            pkg = CREDIT_PACKAGES.get(approved_req["package_key"], {})
            user_after = db.get_user(approved_req["telegram_id"])
            baki = user_after["scans_remaining"] if user_after else approved_req["scans"]

            try:
                await bot.send_message(
                    chat_id=approved_req["telegram_id"],
                    text=(
                        f"🎉 Pembayaran berjaya disahkan!\n\n"
                        f"📦 Pakej: {pkg.get('name', '')}\n"
                        f"✅ +{approved_req['scans']} scan ditambah\n"
                        f"💳 Baki sekarang: {baki} scan\n\n"
                        f"Terima kasih! Selamat scan 📸"
                    )
                )
            except Exception as e:
                logger.error(f"Gagal notify user {approved_req['telegram_id']}: {e}")

        return web.Response(text="OK")

    except Exception as e:
        logger.error(f"Callback handler error: {e}")
        return web.Response(text="OK")


async def health_check(request: web.Request) -> web.Response:
    """Health check endpoint."""
    return web.Response(text="FitJejak OK")
