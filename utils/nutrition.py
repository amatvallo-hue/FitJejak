"""
utils/nutrition.py — FitJejak
Pengiraan kalori sasaran (TDEE) dan protein berdasarkan profil pengguna.
"""
from config import ACTIVITY_MULTIPLIERS


def calculate_targets(weight_kg: float, height_cm: float, age: int,
                      gender: str, activity_level: str, goal: str) -> tuple[float, float]:
    """
    Kira kalori dan protein sasaran harian.

    Formula:
    - BMR (Mifflin-St Jeor): Paling tepat untuk kebanyakan orang
    - TDEE = BMR × activity multiplier
    - Kalori disesuaikan mengikut goal

    Returns:
        (target_calories, target_protein_g)
    """
    # ── Step 1: Kira BMR ─────────────────────────────────────────
    if gender == "lelaki":
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
    else:
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161

    # ── Step 2: Kira TDEE ────────────────────────────────────────
    multiplier = ACTIVITY_MULTIPLIERS.get(activity_level, 1.375)
    tdee = bmr * multiplier

    # ── Step 3: Adjust mengikut goal ─────────────────────────────
    if goal == "turun_berat":
        target_calories = tdee - 500   # Defisit 500 kcal = turun ~0.5kg/minggu
    elif goal == "naik_otot":
        target_calories = tdee + 300   # Surplus 300 kcal untuk muscle gain
    else:  # kekal
        target_calories = tdee

    # ── Step 4: Kira protein sasaran ─────────────────────────────
    # Standard: 1.6–2.2g protein per kg berat badan
    if goal == "naik_otot":
        protein_per_kg = 2.2  # Lebih protein untuk bina otot
    elif goal == "turun_berat":
        protein_per_kg = 2.0  # Protein tinggi semasa diet untuk jaga muscle
    else:
        protein_per_kg = 1.6

    target_protein = weight_kg * protein_per_kg

    return round(target_calories), round(target_protein)


def get_health_score_emoji(score: int) -> str:
    """Return emoji berdasarkan health score."""
    if score >= 8:
        return "🟢"
    elif score >= 5:
        return "🟡"
    else:
        return "🔴"


def get_progress_bar(current: float, target: float, length: int = 10) -> str:
    """
    Cipta progress bar teks.
    Contoh: ████████░░ 80%
    """
    if target <= 0:
        return "░" * length + " 0%"
    ratio = min(current / target, 1.0)
    filled = int(ratio * length)
    bar = "█" * filled + "░" * (length - filled)
    percent = int(ratio * 100)
    return f"{bar} {percent}%"
