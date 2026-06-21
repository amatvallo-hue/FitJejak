# 🏋️ FitJejak Bot

Bot Telegram AI untuk jejak nutrisi harian — hantar gambar makanan, dapat analisis kalori & protein.

---

## 🚀 Setup (Panduan Beginner)

### Langkah 1 — Dapatkan Telegram Bot Token

1. Buka Telegram, cari **@BotFather**
2. Hantar `/newbot`
3. Ikut arahan — pilih nama dan username untuk bot anda
4. BotFather akan bagi **token** — salin token tersebut

---

### Langkah 2 — Dapatkan AI API Key

**Pilihan A: OpenAI (Recommended)**
1. Pergi ke https://platform.openai.com/api-keys
2. Klik **Create new secret key**
3. Salin key tersebut

**Pilihan B: Google Gemini (Ada free tier)**
1. Pergi ke https://aistudio.google.com/apikey
2. Klik **Create API key**
3. Salin key tersebut

---

### Langkah 3 — Setup Fail .env

```bash
# Di dalam folder FitJejak, jalankan:
cp .env.example .env
```

Kemudian buka fail `.env` dan isi:

```
TELEGRAM_BOT_TOKEN=masukkan_token_dari_botfather_di_sini
AI_PROVIDER=openai
OPENAI_API_KEY=masukkan_openai_api_key_di_sini
```

---

### Langkah 4 — Install Python & Dependencies

**Install Python** (jika belum ada):
- Download dari https://python.org/downloads
- Pastikan versi 3.10 atau lebih baru

**Install dependencies:**

```bash
# Buka Terminal / Command Prompt dalam folder FitJejak
pip install -r requirements.txt
```

---

### Langkah 5 — Jalankan Bot

```bash
python bot.py
```

Jika berjaya, anda akan nampak:
```
✅ Database siap.
🚀 FitJejak Bot sedang berjalan...
```

Sekarang cari bot anda di Telegram dan hantar `/start`!

---

## 📁 Struktur Projek

```
FitJejak/
├── bot.py              ← Fail utama (jalankan ini)
├── config.py           ← Konfigurasi
├── database.py         ← Simpan data pengguna
├── ai_analyzer.py      ← Analisis gambar makanan
├── handlers/
│   ├── start.py        ← Setup profil (/start)
│   ├── food.py         ← Analisis gambar
│   └── tracking.py     ← /today, /weight, /summary
├── utils/
│   └── nutrition.py    ← Kira kalori & protein sasaran
├── data/               ← Database SQLite (auto-created)
├── .env                ← API keys anda (JANGAN share!)
├── .env.example        ← Template .env
└── requirements.txt    ← Python packages
```

---

## 💬 Commands Bot

| Command | Fungsi |
|---------|--------|
| /start | Setup profil / menu utama |
| 📸 Gambar | Analisis nutrisi makanan |
| /today | Ringkasan kalori & protein hari ini |
| /weight 75 | Rekod berat badan |
| /summary | Ringkasan minggu ini |
| /credits | Semak baki scan |
| /topup | Pakej kredit |
| /profile | Lihat profil anda |

---

## ⚠️ Perkara Penting

- **Jangan share** fail `.env` kepada sesiapa
- File `.env` sudah ada dalam `.gitignore` — selamat untuk push ke GitHub
- Database disimpan dalam `data/fitjejak.db` — backup secara berkala

---

## 🔧 Troubleshooting

**Bot tidak respond:**
- Pastikan bot.py masih berjalan di terminal
- Semak TELEGRAM_BOT_TOKEN dalam .env

**Error "OpenAI API key":**
- Semak OPENAI_API_KEY dalam .env
- Pastikan akaun OpenAI ada kredit

**Error semasa install:**
```bash
# Cuba dengan pip3
pip3 install -r requirements.txt

# Atau dengan python -m pip
python -m pip install -r requirements.txt
```
