"""
ai_analyzer.py — FitJejak
Analisis gambar makanan menggunakan AI Vision API.
Support: OpenAI GPT-4o Vision & Google Gemini Vision
"""
import base64
import json
import re
import aiohttp
from config import AI_PROVIDER, OPENAI_API_KEY, GEMINI_API_KEY


# ── Prompt untuk AI ───────────────────────────────────────────────
FOOD_ANALYSIS_PROMPT = """
Anda adalah pakar nutrisi. Analisis gambar makanan ini dan berikan anggaran nutrisi.

Balas HANYA dalam format JSON berikut (tiada teks lain):
{
  "food_name": "Nama makanan dalam Bahasa Malaysia",
  "calories": 650,
  "protein_g": 32,
  "carbs_g": 75,
  "fat_g": 22,
  "health_score": 7,
  "advice": "Cadangan ringkas dalam Bahasa Malaysia (1-2 ayat)"
}

Peraturan:
- Jika ada beberapa item makanan, gabungkan semua dalam satu anggaran
- health_score adalah 1-10 (10 paling sihat)
- advice fokus pada protein dan kalori
- Semua nilai adalah anggaran — tidak perlu terlalu tepat
- Jika BUKAN gambar makanan, balas: {"error": "Ini bukan gambar makanan"}
"""


FOOD_TEXT_PROMPT = """
Anda adalah pakar nutrisi. Pengguna menyebut nama makanan berikut. Berikan anggaran nutrisi.

Balas HANYA dalam format JSON berikut (tiada teks lain):
{
  "food_name": "Nama makanan dalam Bahasa Malaysia",
  "calories": 650,
  "protein_g": 32,
  "carbs_g": 75,
  "fat_g": 22,
  "health_score": 7,
  "advice": "Cadangan ringkas dalam Bahasa Malaysia (1-2 ayat)"
}

Peraturan:
- Andaikan saiz hidangan biasa (1 pinggan / 1 bungkus)
- health_score adalah 1-10 (10 paling sihat)
- advice fokus pada protein dan kalori
- Jika BUKAN makanan, balas: {"error": "Sila masukkan nama makanan yang sah"}
"""


async def analyze_food_text(food_description: str) -> dict:
    """
    Analisis teks makanan dan return maklumat nutrisi.

    Args:
        food_description: Nama/penerangan makanan dalam teks

    Returns:
        dict dengan keys: food_name, calories, protein_g, carbs_g, fat_g,
                          health_score, advice
        atau dict dengan key 'error' jika gagal
    """
    if AI_PROVIDER == "openai":
        return await _analyze_text_with_openai(food_description)
    else:
        return {"error": f"AI provider tidak dikenali: {AI_PROVIDER}"}


async def _analyze_text_with_openai(food_description: str) -> dict:
    """Analisis teks makanan menggunakan OpenAI."""
    if not OPENAI_API_KEY:
        return {"error": "OPENAI_API_KEY tidak dikonfigurasi"}

    payload = {
        "model": "gpt-4o-mini",  # Mini cukup untuk teks, lebih murah
        "messages": [
            {
                "role": "user",
                "content": f"{FOOD_TEXT_PROMPT}\n\nMakanan: {food_description}"
            }
        ],
        "max_tokens": 300,
        "temperature": 0.3
    }

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.openai.com/v1/chat/completions",
            json=payload,
            headers=headers
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                return {"error": f"OpenAI API error {resp.status}: {error_text[:200]}"}

            data = await resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            return _parse_ai_response(content)


async def analyze_food_image(image_bytes: bytes) -> dict:
    """
    Analisis gambar makanan dan return maklumat nutrisi.

    Args:
        image_bytes: Gambar dalam format bytes

    Returns:
        dict dengan keys: food_name, calories, protein_g, carbs_g, fat_g,
                          health_score, advice
        atau dict dengan key 'error' jika gagal
    """
    if AI_PROVIDER == "openai":
        return await _analyze_with_openai(image_bytes)
    elif AI_PROVIDER == "gemini":
        return await _analyze_with_gemini(image_bytes)
    else:
        return {"error": f"AI provider tidak dikenali: {AI_PROVIDER}"}


async def _analyze_with_openai(image_bytes: bytes) -> dict:
    """Analisis menggunakan OpenAI GPT-4o Vision."""
    if not OPENAI_API_KEY:
        return {"error": "OPENAI_API_KEY tidak dikonfigurasi dalam fail .env"}

    # Encode gambar ke base64
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": FOOD_ANALYSIS_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_b64}",
                            "detail": "low"  # Lebih murah, cukup untuk food recognition
                        }
                    }
                ]
            }
        ],
        "max_tokens": 300,
        "temperature": 0.3  # Rendah supaya jawapan lebih konsisten
    }

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.openai.com/v1/chat/completions",
            json=payload,
            headers=headers
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                return {"error": f"OpenAI API error {resp.status}: {error_text[:200]}"}

            data = await resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            return _parse_ai_response(content)


async def _analyze_with_gemini(image_bytes: bytes) -> dict:
    """Analisis menggunakan Google Gemini Vision."""
    if not GEMINI_API_KEY:
        return {"error": "GEMINI_API_KEY tidak dikonfigurasi dalam fail .env"}

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": FOOD_ANALYSIS_PROMPT},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": image_b64
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 300
        }
    }

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    )

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                return {"error": f"Gemini API error {resp.status}: {error_text[:200]}"}

            data = await resp.json()
            content = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            return _parse_ai_response(content)


def _parse_ai_response(content: str) -> dict:
    """
    Parse JSON response dari AI.
    Handle kes di mana AI tambah teks sebelum/selepas JSON.
    """
    # Cuba cari JSON dalam response
    json_match = re.search(r'\{.*\}', content, re.DOTALL)
    if not json_match:
        return {"error": "AI tidak dapat menganalisis gambar ini. Cuba gambar yang lebih jelas."}

    try:
        result = json.loads(json_match.group())

        # Validasi fields yang diperlukan
        if "error" in result:
            return result

        required = ["food_name", "calories", "protein_g", "carbs_g", "fat_g",
                    "health_score", "advice"]
        for field in required:
            if field not in result:
                result[field] = 0 if field != "food_name" and field != "advice" else "?"

        # Pastikan semua nilai numerik adalah float/int
        for field in ["calories", "protein_g", "carbs_g", "fat_g", "health_score"]:
            try:
                result[field] = float(result[field])
            except (ValueError, TypeError):
                result[field] = 0

        result["health_score"] = max(1, min(10, int(result["health_score"])))
        return result

    except json.JSONDecodeError:
        return {"error": "Ralat memproses response AI. Sila cuba lagi."}
