"""
handlers/body_scan.py — FitJejak
Body scan feature — user hantar gambar badan, AI analisis komposisi badan.
Guna kredit scan sama seperti food scan.
"""
import logging
import json
import re
import base64
import aiohttp

from telegram import Update
from telegram.ext import ContextTypes

import database as db
from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

BODY_SCAN_PROMPT = """
Anda adalah jurulatih badan (body coach) profesional dan pakar komposisi badan.
Analisis gambar badan manusia ini secara objektif dan membina.

Balas HANYA dalam format JSON berikut (tiada teks lain):
{
  "body_fat_visual": 18.5,
  "muscle_def": "Sederhana",
  "physique_cat": "Fitness",
  "feedback": "Maklum balas membina dalam Bahasa Malaysia (3-4 ayat)"
}

Peraturan:
- body_fat_visual: anggaran % body fat berdasarkan visual (nombor sahaja)
- muscle_def: "Rendah" / "Sederhana" / "Baik" / "Sangat Baik" / "Excellent"
- physique_cat: "Slim" / "Fitness" / "Athletic" / "Muscular" / "Bulk" / "Lebih Berat"
- feedback: komen membina tentang komposisi badan, apa yang nampak positif, dan cadangan untuk improve
- Jangan judge atau kritik negatif — fokus kepada potensi dan progress
- Ingatkan ini adalah anggaran visual sahaja, bukan ukuran klinikal
- Jika BUKAN gambar manusia/badan, balas: {"error": "Hantar gambar badan penuh atau bahagian badan untuk analisis"}
"""


async def request_body_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User tekan button Scan Badan — minta hantar gambar."""
    user = db.get_user(update.effective_user.id)
    if not user or not user["setup_complete"]:
        await update.message.reply_text("⚠️ Sila /start untuk setup profil dulu.")
        return

    if user["scans_remaining"] <= 0:
        await update.message.reply_text(
            "❌ Scan anda telah habis!\n\n"
            "Topup kredit untuk teruskan.\n"
            "Taip /topup untuk lihat pakej."
        )
        return

    context.user_data["awaiting_body_scan"] = True

    await update.message.reply_text(
        "📸 Body Scan\n\n"
        "Hantar gambar badan anda sekarang.\n\n"
        "💡 Tips untuk hasil terbaik:\n"
        "• Gambar penuh (kepala hingga lutut) atau bahagian tengah\n"
        "• Pencahayaan yang baik\n"
        "• Pakai pakaian fitting atau tanpa baju (gym wear)\n\n"
        "AI akan analisis komposisi badan anda secara profesional."
    )


async def handle_body_scan_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Dipanggil dari food.py bila user hantar gambar DAN awaiting_body_scan = True.
    Return True kalau diproses sebagai body scan.
    """
    if not context.user_data.get("awaiting_body_scan"):
        return False

    context.user_data.pop("awaiting_body_scan", None)

    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)

    if not user or user["scans_remaining"] <= 0:
        await update.message.reply_text("❌ Scan habis. Topup dulu: /topup")
        return True

    processing_msg = await update.message.reply_text(
        "🔍 Menganalisis komposisi badan anda...\nIni ambil masa 5-10 saat."
    )

    # Download gambar
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    image_bytes = await file.download_as_bytearray()

    # Analisis dengan AI
    result = await _analyze_body_with_openai(bytes(image_bytes))

    await processing_msg.delete()

    if "error" in result:
        await update.message.reply_text(f"⚠️ {result['error']}")
        return True

    # Tolak 1 scan
    db.deduct_scan(telegram_id)

    # Simpan ke DB
    db.save_body_scan(
        telegram_id=telegram_id,
        body_fat_visual=result.get("body_fat_visual", 0),
        muscle_def=result.get("muscle_def", "-"),
        physique_cat=result.get("physique_cat", "-"),
        feedback=result.get("feedback", ""),
        image_file_id=photo.file_id
    )

    # Dapatkan history untuk comparison
    history = db.get_body_scan_history(telegram_id, limit=2)
    user_after = db.get_user(telegram_id)

    bf = result.get("body_fat_visual", 0)
    muscle = result.get("muscle_def", "-")
    cat = result.get("physique_cat", "-")
    feedback = result.get("feedback", "")
    scans_left = user_after["scans_remaining"] if user_after else "?"

    # Comparison dengan scan sebelum (kalau ada)
    comparison = ""
    if len(history) >= 2:
        prev = history[1]  # scan sebelum ini
        diff = round(bf - (prev["body_fat_visual"] or 0), 1)
        if diff < 0:
            comparison = f"\n📉 Body fat turun {abs(diff)}% dari scan lepas! 🎉"
        elif diff > 0:
            comparison = f"\n📈 Body fat naik {diff}% dari scan lepas."
        else:
            comparison = f"\n➡️ Body fat sama seperti scan lepas."

    reply = (
        f"📊 Keputusan Body Scan\n\n"
        f"🫀 Anggaran Body Fat: {bf}%\n"
        f"💪 Muscle Definition: {muscle}\n"
        f"🏋️ Kategori: {cat}\n"
        f"{comparison}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📝 Analisis AI:\n{feedback}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"⚠️ Ini adalah anggaran visual sahaja.\n"
        f"💳 Scan tersisa: {scans_left}"
    )

    await update.message.reply_text(reply)
    return True


async def body_scan_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tunjuk history body scan."""
    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)
    if not user or not user["setup_complete"]:
        await update.message.reply_text("⚠️ Sila /start untuk setup profil dulu.")
        return

    history = db.get_body_scan_history(telegram_id, limit=5)
    if not history:
        await update.message.reply_text(
            "📸 Belum ada body scan lagi.\n\n"
            "Tekan 📸 Scan Badan untuk mulakan!"
        )
        return

    text = "📊 History Body Scan\n\n"
    for i, scan in enumerate(history, 1):
        date_str = scan["scan_date"] or "-"
        bf = scan["body_fat_visual"] or "-"
        cat = scan["physique_cat"] or "-"
        muscle = scan["muscle_def"] or "-"
        text += (
            f"{i}. {date_str}\n"
            f"   🫀 {bf}% body fat | 💪 {muscle} | 🏋️ {cat}\n\n"
        )

    await update.message.reply_text(text.strip())


# ── AI Analysis ───────────────────────────────────────────────────

async def _analyze_body_with_openai(image_bytes: bytes) -> dict:
    """Analisis gambar badan dengan OpenAI Vision."""
    if not OPENAI_API_KEY:
        return {"error": "OPENAI_API_KEY tidak dikonfigurasi."}

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": BODY_SCAN_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_b64}",
                            "detail": "auto"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 400,
        "temperature": 0.3
    }

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    return {"error": "Ralat sistem AI. Cuba lagi."}
                data = await resp.json()
                content = data["choices"][0]["message"]["content"].strip()
                return _parse_body_response(content)
    except aiohttp.ServerTimeoutError:
        return {"error": "AI lambat respond. Cuba lagi."}
    except Exception:
        return {"error": "Ralat tidak dijangka. Cuba lagi."}


def _parse_body_response(content: str) -> dict:
    """Parse JSON response dari AI."""
    json_match = re.search(r'\{.*\}', content, re.DOTALL)
    if not json_match:
        return {"error": "AI tidak dapat menganalisis gambar ini. Cuba gambar yang lebih jelas."}
    try:
        result = json.loads(json_match.group())
        if "error" in result:
            return result
        try:
            result["body_fat_visual"] = float(result.get("body_fat_visual", 0))
        except (ValueError, TypeError):
            result["body_fat_visual"] = 0
        return result
    except json.JSONDecodeError:
        return {"error": "Ralat memproses response AI. Cuba lagi."}
