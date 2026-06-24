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

    # ── Step 5: Kira karbo dan lemak sasaran ─────────────────────
    # Karbo: 50% dari kalori ÷ 4 (4 kcal per gram karbo)
    # Lemak: 30% dari kalori ÷ 9 (9 kcal per gram lemak)
    target_carbs = (target_calories * 0.50) / 4
    target_fat   = (target_calories * 0.30) / 9

    return round(target_calories), round(target_protein), round(target_carbs), round(target_fat)


def calculate_body_fat(weight_kg: float, height_cm: float, age: int, gender: str) -> float:
    """
    Anggaran body fat % menggunakan BMI Method (Deurenberg formula).
    BF% = (1.20 × BMI) + (0.23 × age) − 10.8 (lelaki) / 0 (perempuan) − 5.4
    """
    height_m = height_cm / 100
    bmi = weight_kg / (height_m ** 2)

    if gender == "lelaki":
        body_fat = (1.20 * bmi) + (0.23 * age) - 10.8 - 5.4
    else:
        body_fat = (1.20 * bmi) + (0.23 * age) - 5.4

    return round(max(body_fat, 2.0), 1)


def get_body_fat_category(body_fat: float, gender: str) -> str:
    """Label kategori body fat berdasarkan jantina."""
    if gender == "lelaki":
        if body_fat < 6:
            return "Essential Fat 🔬"
        elif body_fat < 14:
            return "Atlet 🏆"
        elif body_fat < 18:
            return "Fit 💪"
        elif body_fat < 25:
            return "Average ✅"
        else:
            return "Lebih Lemak ⚠️"
    else:
        if body_fat < 14:
            return "Essential Fat 🔬"
        elif body_fat < 21:
            return "Atlet 🏆"
        elif body_fat < 25:
            return "Fit 💪"
        elif body_fat < 32:
            return "Average ✅"
        else:
            return "Lebih Lemak ⚠️"


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
    Cipta progress bar teks menggunakan emoji supaya render elok semua device.
    Contoh: 🟩🟩🟩🟩🟩⬜⬜⬜⬜⬜ 50%
    """
    if target <= 0:
        return "⬜" * length + " 0%"
    ratio = min(current / target, 1.0)
    filled = int(ratio * length)
    bar = "🟩" * filled + "⬜" * (length - filled)
    percent = int(ratio * 100)
    return f"{bar} {percent}%"


def get_nutrient_bar(current: float, target: float, unit: str, reverse: bool = False) -> str:
    """
    Return 2-line display: progress bar (warna merah/hijau) + warning text.

    reverse=True  → protein: merah bila KURANG dari target
    reverse=False → kalori/karbo/lemak: merah bila TERLEBIH target
    """
    if target <= 0:
        return f"{'⬜' * 10} —\n   ({int(current)}/{int(target)}{unit})"

    ratio = current / target
    percent = int(ratio * 100)
    diff = abs(int(current - target))
    over = current > target

    if reverse:
        # Protein — hijau bila cukup/lebih, merah bila kurang
        if ratio >= 0.9:
            bar = "🟩" * 10
            status = "✅ Cukup!"
        else:
            filled = min(int(ratio * 10), 10)
            bar = "🟥" * filled + "⬜" * (10 - filled)
            status = f"⚠️ Kurang {diff}{unit} lagi!"
    else:
        # Kalori / karbo / lemak — hijau bila ok, merah bila terlebih
        if over:
            bar = "🟥" * 10
            status = f"⚠️ Terlebih {diff}{unit}!"
        else:
            filled = int(ratio * 10)
            bar = "🟩" * filled + "⬜" * (10 - filled)
            status = "✅ Dalam kawalan"

    bar_line = f"{bar} {percent}%"
    detail   = f"   ({int(current)}/{int(target)}{unit}) {status}"
    return f"{bar_line}\n{detail}"
