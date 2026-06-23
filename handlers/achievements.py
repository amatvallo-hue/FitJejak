"""
handlers/achievements.py — FitJejak
Sistem achievement — definisi, check, dan award logic.
"""
import database as db

# ── Definisi Scan Achievements ────────────────────────────────────
SCAN_ACHIEVEMENTS = [
    {
        "key":   "scan_1",
        "name":  "Scan Pertama",
        "badge": "📸",
        "req":   1,
        "bonus": 0,
        "msg":   "Tahniah! Anda buat scan pertama! Perjalanan seribu batu bermula dengan satu langkah 🎉"
    },
    {
        "key":   "scan_10",
        "name":  "Rajin Scan",
        "badge": "📸⭐",
        "req":   10,
        "bonus": 0,
        "msg":   "10 scan dah! Awak dah mula jadi lebih sedar tentang pemakanan anda 💪"
    },
    {
        "key":   "scan_50",
        "name":  "Scan Veteran",
        "badge": "📸🔥",
        "req":   50,
        "bonus": 5,
        "msg":   "50 scan! Awak dah Scan Veteran sekarang 🔥\n🎁 Bonus: +5 scan percuma!"
    },
    {
        "key":   "scan_100",
        "name":  "Scan Master",
        "badge": "📸👑",
        "req":   100,
        "bonus": 10,
        "msg":   "100 SCAN! Awak adalah Scan Master FitJejak 👑\n🎁 Bonus: +10 scan percuma!"
    },
]


def get_next_scan_achievement(total_scans: int) -> dict | None:
    """Return achievement seterusnya yang belum dicapai, atau None kalau semua dah unlock."""
    for ach in SCAN_ACHIEVEMENTS:
        if total_scans < ach["req"]:
            return ach
    return None


def check_scan_achievements(telegram_id: int) -> list:
    """
    Semak dan award scan achievements yang baru dicapai.
    Return list of newly unlocked achievements.
    """
    total_scans = db.get_total_scans_used(telegram_id)
    newly_unlocked = []

    for ach in SCAN_ACHIEVEMENTS:
        if total_scans >= ach["req"]:
            awarded = db.award_achievement(telegram_id, ach["key"], ach["bonus"])
            if awarded:
                newly_unlocked.append(ach)

    return newly_unlocked


def build_achievement_progress_hint(telegram_id: int) -> str:
    """
    Return string progress hint untuk next achievement.
    Contoh: "🎯 Scan Veteran: 47/50 — lagi 3 scan!"
    Kosong kalau semua achievement dah unlock.
    """
    total_scans = db.get_total_scans_used(telegram_id)
    next_ach = get_next_scan_achievement(total_scans)

    if not next_ach:
        return ""

    remaining = next_ach["req"] - total_scans
    return (
        f"🎯 Achievement seterusnya: {next_ach['badge']} {next_ach['name']}\n"
        f"   {total_scans}/{next_ach['req']} scan — lagi {remaining} scan!"
    )
