// Nutrition science: target calculation, DRIs, and nutrient math.
// Values from NIH ODS / IOM Dietary Reference Intakes (adults).

export const MACROS = [
  { key: 'protein', label: 'Protein', unit: 'g', kcalPerG: 4 },
  { key: 'carbs', label: 'Carbs', unit: 'g', kcalPerG: 4 },
  { key: 'fat', label: 'Fat', unit: 'g', kcalPerG: 9 },
];

// ulScope: 'total' = UL applies to food + supplements, 'supplement' = UL applies only to supplemental/synthetic forms.
export const MICROS = [
  { key: 'fiber', label: 'Fiber', unit: 'g' },
  { key: 'sodium', label: 'Sodium', unit: 'mg', limit: true },
  { key: 'potassium', label: 'Potassium', unit: 'mg' },
  { key: 'calcium', label: 'Calcium', unit: 'mg', ulScope: 'total' },
  { key: 'iron', label: 'Iron', unit: 'mg', ulScope: 'total' },
  { key: 'magnesium', label: 'Magnesium', unit: 'mg', ulScope: 'supplement' },
  { key: 'zinc', label: 'Zinc', unit: 'mg', ulScope: 'total' },
  { key: 'vitA', label: 'Vitamin A', unit: 'µg', ulScope: 'supplement' },
  { key: 'vitC', label: 'Vitamin C', unit: 'mg', ulScope: 'total' },
  { key: 'vitD', label: 'Vitamin D', unit: 'µg', ulScope: 'total' },
  { key: 'vitE', label: 'Vitamin E', unit: 'mg', ulScope: 'supplement' },
  { key: 'vitK', label: 'Vitamin K', unit: 'µg' },
  { key: 'b12', label: 'Vitamin B12', unit: 'µg' },
  { key: 'folate', label: 'Folate', unit: 'µg', ulScope: 'supplement' },
];

export const NUTRIENT_KEYS = ['kcal', 'protein', 'carbs', 'fat', 'sugar', ...MICROS.map(m => m.key)];

export const ACTIVITY = {
  sedentary: { label: 'Sedentary (desk job, little exercise)', mult: 1.2 },
  light: { label: 'Lightly active (1–3 workouts/wk)', mult: 1.375 },
  moderate: { label: 'Moderately active (3–5 workouts/wk)', mult: 1.55 },
  very: { label: 'Very active (6–7 workouts/wk)', mult: 1.725 },
  extra: { label: 'Extremely active (physical job + training)', mult: 1.9 },
};

export const GOALS = {
  lose: { label: 'Lose ~0.5 kg / 1 lb per week', delta: -500 },
  lose_slow: { label: 'Lose slowly (~0.25 kg / 0.5 lb per week)', delta: -250 },
  maintain: { label: 'Maintain weight', delta: 0 },
  gain_slow: { label: 'Lean gain (~0.25 kg / 0.5 lb per week)', delta: 250 },
};

// Adult DRIs. [male, female] per age band.
function driTable(sex, age) {
  const m = sex === 'male';
  const older = age >= 51, oldest = age >= 71;
  return {
    sodium:    { target: 2300, limit: true },
    potassium: { target: m ? 3400 : 2600 },
    calcium:   { target: (m ? oldest : older) ? 1200 : 1000, ul: older ? 2000 : 2500 },
    iron:      { target: m || older ? 8 : 18, ul: 45 },
    magnesium: { target: m ? (age >= 31 ? 420 : 400) : (age >= 31 ? 320 : 310), ul: 350 },
    zinc:      { target: m ? 11 : 8, ul: 40 },
    vitA:      { target: m ? 900 : 700, ul: 3000 },
    vitC:      { target: m ? 90 : 75, ul: 2000 },
    vitD:      { target: oldest ? 20 : 15, ul: 100 },
    vitE:      { target: 15, ul: 1000 },
    vitK:      { target: m ? 120 : 90 },
    b12:       { target: 2.4 },
    folate:    { target: 400, ul: 1000 },
  };
}

export function bmr({ sex, age, heightCm, weightKg }) {
  return 10 * weightKg + 6.25 * heightCm - 5 * age + (sex === 'male' ? 5 : -161);
}

export function computeTargets(p) {
  if (!p) return null;
  const o = p.overrides || {};
  const base = bmr(p);
  const tdee = base * (ACTIVITY[p.activity]?.mult ?? 1.2);
  const floor = p.sex === 'male' ? 1500 : 1200;
  let kcal = Math.max(floor, Math.round((tdee + (GOALS[p.goal]?.delta ?? 0)) / 10) * 10);
  if (o.kcal) kcal = o.kcal;
  const protein = o.protein || Math.round((p.proteinPerKg ?? 1.8) * p.weightKg);
  const fat = o.fat || Math.round((kcal * (p.fatPct ?? 30)) / 100 / 9);
  const carbs = o.carbs || Math.max(0, Math.round((kcal - protein * 4 - fat * 9) / 4));
  const micros = driTable(p.sex, p.age);
  micros.fiber = { target: Math.round((kcal / 1000) * 14) };
  return { bmr: Math.round(base), tdee: Math.round(tdee), kcal, protein, carbs, fat, micros, floorApplied: !o.kcal && kcal === floor };
}

export function emptyNutrients() {
  return Object.fromEntries(NUTRIENT_KEYS.map(k => [k, 0]));
}

export function scaleNutrients(per100, grams) {
  const f = grams / 100;
  const out = emptyNutrients();
  for (const k of NUTRIENT_KEYS) out[k] = (per100[k] || 0) * f;
  return out;
}

export function sumNutrients(list) {
  const out = emptyNutrients();
  for (const n of list) for (const k of NUTRIENT_KEYS) out[k] += n?.[k] || 0;
  return out;
}

// Status for a micronutrient. `supplementAmount` lets Stage 2 apply supplement-only ULs.
export function microStatus(def, target, total, supplementAmount = 0) {
  if (!target) return { pct: 0, status: 'none' };
  if (target.limit) {
    const pct = total / target.target;
    return { pct, status: pct > 1 ? 'over' : 'ok-limit' };
  }
  const ulBase = def.ulScope === 'supplement' ? supplementAmount : total;
  if (target.ul && def.ulScope && ulBase > target.ul) return { pct: total / target.target, status: 'over' };
  const pct = total / target.target;
  return { pct, status: pct >= 1 ? 'met' : pct >= 0.5 ? 'mid' : 'low' };
}

export const kgToLb = kg => kg * 2.20462;
export const lbToKg = lb => lb / 2.20462;
export const cmToIn = cm => cm / 2.54;
export const inToCm = i => i * 2.54;

export function fmt(v, unit) {
  if (v == null || isNaN(v)) return '0';
  const abs = Math.abs(v);
  const trim = x => x.replace(/\.?0+$/, '');
  const s = abs < 0.005 ? '0' : abs >= 100 ? Math.round(v).toLocaleString() : abs >= 10 ? v.toFixed(0) : abs >= 1 ? trim(v.toFixed(1)) : trim(v.toFixed(2));
  return unit ? `${s} ${unit}` : s;
}
