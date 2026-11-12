"""Training-type macro database.

Ranges are grams per kg of body weight per day as (low, high).
Primary sources:
  - ACSM / Academy of Nutrition & Dietetics / Dietitians of Canada joint position (Thomas et al., 2016):
    carbs 3-5 (light), 5-7 (moderate ~1 h/d), 6-10 (high 1-3 h/d), 8-12 (very high 4-5 h/d);
    protein 1.2-2.0; fat 20-35% of kcal.
  - ISSN position stand: protein & exercise (Jager et al., 2017): 1.4-2.0 g/kg, ~0.25-0.4 g/kg per meal.
  - ISSN position stand: nutrient timing (Kerksick et al., 2017).
  - Helms et al., 2014 (bodybuilding contest prep): 2.3-3.1 g/kg lean mass protein in a deficit.
  - Concurrent/hybrid training has no dedicated position stand; its ranges combine the ACSM endurance
    carb bands with ISSN resistance-training protein guidance.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TrainingType:
    name: str
    examples: str
    emphasis: str  # "Balanced" | "Protein-forward" | "Carb-leaning" | "Carb-forward"
    protein: tuple[float, float]
    carbs: tuple[float, float]
    fat: tuple[float, float]
    tips: tuple[str, ...]

    @property
    def carb_first(self) -> bool:
        return self.emphasis.startswith("Carb")


TRAINING: dict[str, TrainingType] = {
    'general': TrainingType(
        name='General fitness',
        examples='Gym 2–4×/week, recreational exercise, staying healthy',
        emphasis='Balanced',
        protein=(1.2, 1.6),
        carbs=(3.0, 5.0),
        fat=(0.8, 1.2),
        tips=(
            'Spread protein over 3–4 meals (about 0.3 g/kg each) rather than one big serving.',
            'Choose mostly whole-food carbs (fruit, oats, potatoes, legumes) for fiber and micronutrients.',
        ),
    ),
    'strength': TrainingType(
        name='Strength / powerlifting',
        examples='Powerlifting, Olympic lifting, low-rep heavy training',
        emphasis='Protein-forward',
        protein=(1.6, 2.2),
        carbs=(3.0, 5.0),
        fat=(0.8, 1.2),
        tips=(
            'Have 20–40 g protein within a few hours after training.',
            'Short, heavy sessions use little glycogen, so carbs can stay moderate. Fit most of them around training.',
            'Creatine monohydrate (3–5 g/day) is the best-supported supplement for strength.',
        ),
    ),
    'hypertrophy': TrainingType(
        name='Bodybuilding / hypertrophy',
        examples='Physique training, moderate reps and high volume',
        emphasis='Protein-forward',
        protein=(1.8, 2.4),
        carbs=(4.0, 6.0),
        fat=(0.7, 1.0),
        tips=(
            'In a fat-loss phase, protein goes to the top of the range to protect muscle.',
            'High-volume sessions do use glycogen. Carbs before training help performance and pump.',
            'Have 4–5 protein feedings a day at about 0.4 g/kg each to maximize muscle protein synthesis.',
        ),
    ),
    'hiit': TrainingType(
        name='CrossFit / HIIT / functional',
        examples='CrossFit, metcons, circuit training, bootcamp',
        emphasis='Carb-leaning',
        protein=(1.6, 2.0),
        carbs=(4.0, 7.0),
        fat=(0.8, 1.0),
        tips=(
            'High-intensity work runs mostly on glycogen. Low-carb diets reliably hurt metcon performance.',
            'For two sessions a day, have 1–1.2 g/kg carbs per hour for 4 hours between them.',
        ),
    ),
    'hybrid': TrainingType(
        name='Hybrid (strength + endurance)',
        examples='HYROX, lifting plus running, tactical/military, concurrent training',
        emphasis='Carb-forward',
        protein=(1.6, 2.0),
        carbs=(5.0, 8.0),
        fat=(0.8, 1.0),
        tips=(
            'Carbs are the main fuel: endurance volume drains glycogen and lifting needs it refilled. Prioritize carbs over extra fat.',
            'For runs or sessions over 60–90 min, take in 30–60 g carbs per hour during the session.',
            'Eat more carbs on double or long days and fewer on rest days (carb periodization).',
            'Keep protein at about 1.6–2.0 g/kg. More than that crowds out carbs without extra benefit.',
        ),
    ),
    'team': TrainingType(
        name='Team / field sports',
        examples='Soccer, basketball, rugby, hockey',
        emphasis='Carb-forward',
        protein=(1.4, 1.8),
        carbs=(5.0, 7.0),
        fat=(0.8, 1.0),
        tips=(
            'Carb-load on match days: about 1–3 g/kg in the 1–4 hours before kickoff.',
            'Repeated sprints drain glycogen. Refuel with about 1 g/kg carbs plus 0.3 g/kg protein after games.',
        ),
    ),
    'combat': TrainingType(
        name='Combat sports',
        examples='BJJ, wrestling, boxing, MMA, judo',
        emphasis='Balanced',
        protein=(1.6, 2.2),
        carbs=(4.0, 6.0),
        fat=(0.8, 1.0),
        tips=(
            'Keep protein high while making weight to preserve muscle.',
            'Avoid rapid dehydration cuts. Get weight-cut plans from a sports dietitian.',
        ),
    ),
    'endurance': TrainingType(
        name='Endurance (1–3 h/day)',
        examples='Running, cycling, swimming, triathlon, rowing',
        emphasis='Carb-forward',
        protein=(1.4, 1.8),
        carbs=(6.0, 10.0),
        fat=(0.8, 1.0),
        tips=(
            'Carbs are the performance-limiting fuel. Match intake to the day: more on long or hard days, less on easy days.',
            'During sessions over 90 min, take 60–90 g carbs per hour (glucose plus fructose mixes allow the high end).',
            'Within 4 hours after hard sessions, aim for about 1–1.2 g/kg carbs per hour when the next session is soon.',
            'Watch iron (especially female runners) and vitamin D.',
        ),
    ),
    'ultra': TrainingType(
        name='Ultra-endurance (4 h+/day)',
        examples='Ultramarathon, Ironman build, stage racing, long-course training blocks',
        emphasis='Carb-forward',
        protein=(1.6, 2.0),
        carbs=(8.0, 12.0),
        fat=(1.0, 1.5),
        tips=(
            'Energy needs are very high. Eating too little (low energy availability, RED-S) is the biggest risk.',
            'Train the gut to handle 60–90+ g carbs per hour in long sessions.',
            'Fat helps reach calorie targets when food volume becomes limiting.',
        ),
    ),
    'low': TrainingType(
        name='Low intensity / mobility',
        examples='Yoga, Pilates, walking, light recreational activity',
        emphasis='Balanced',
        protein=(1.2, 1.6),
        carbs=(3.0, 5.0),
        fat=(0.8, 1.2),
        tips=(
            'Protein at 1.2–1.6 g/kg still supports healthy aging and satiety.',
            'Carb needs are modest, so build carbs from high-fiber whole foods.',
        ),
    ),
}

# Where in each range you sit, based on weekly training load.
LOADS: dict[str, dict] = {
    'low': {"label": 'Low', "detail": '< 3 h/week', "t": 0.0},
    'moderate': {"label": 'Moderate', "detail": '3–6 h/week', "t": 0.35},
    'high': {"label": 'High', "detail": '6–10 h/week', "t": 0.7},
    'peak': {"label": 'Peak', "detail": '10+ h/week', "t": 1.0},
}
