// Generates reference outputs from the original JavaScript implementation (legacy-web/) so the
// Python port can be checked for identical results. Run: node tests/js_reference.mjs > tests/js_reference.json
import { dayTargets, emptyNutrients, MICROS } from '../legacy-web/js/nutrition.js';
import { computePace } from '../legacy-web/js/pacing.js';
import { scoreDay, summarizeHistory } from '../legacy-web/js/garden.js';
import { analyzeStack, SUPP_TEMPLATES } from '../legacy-web/js/supplements.js';

const profiles = [];
for (const sex of ['male', 'female'])
  for (const age of [25, 45, 60, 75])
    for (const [type, load] of [['general', 'low'], ['strength', 'moderate'], ['hybrid', 'high'], ['endurance', 'peak'], ['hypertrophy', 'high'], ['ultra', 'peak']])
      for (const goal of ['lose', 'maintain', 'gain_slow'])
        profiles.push({ sex, age, heightCm: 172, weightKg: sex === 'male' ? 84 : 63, activity: 'very', goal, trainingType: type, trainingLoad: load });
profiles.push({ sex: 'male', age: 30, heightCm: 180, weightKg: 90, activity: 'moderate', goal: 'maintain', trainingType: 'hybrid', trainingLoad: 'high', overrides: { kcal: 2000 } });
profiles.push({ sex: 'female', age: 30, heightCm: 165, weightKg: 60, activity: 'light', goal: 'lose', trainingType: 'general', trainingLoad: 'moderate', overrides: { protein: 140, fat: 50 } });

const targets = [];
for (const p of profiles) for (const training of [true, false]) for (const creatineG of [0, 5, 20]) {
  const t = dayTargets(p, training, { creatineG });
  targets.push({ p, training, creatineG, out: { kcal: t.kcal, protein: t.protein, carbs: t.carbs, fat: t.fat, water: t.waterMl,
    bmr: t.bmr, tdee: t.tdee, cycling: t.cycling, notes: t.notes.length, fiber: t.micros.fiber.target,
    micros: Object.fromEntries(MICROS.map(m => [m.key, [t.micros[m.key].target, t.micros[m.key].ul ?? null]])) } });
}

// Scores and pace for scaled intakes
const base = dayTargets(profiles[40], true, { creatineG: 5 });
const scores = [];
for (const f of [0, 0.3, 0.6, 0.85, 0.95, 1, 1.1, 1.3, 1.5]) for (const w of [0, 0.5, 1]) for (const [sch, tk] of [[0, 0], [3, 1], [3, 3]]) {
  const n = emptyNutrients(); n.kcal = base.kcal * f; n.protein = base.protein * f; n.carbs = base.carbs * f; n.fat = base.fat * f;
  for (const m of MICROS) n[m.key] = base.micros[m.key].target * f * (m.limit ? 0.7 : 1);
  const supp = emptyNutrients(); supp.vitD = f > 1.2 ? 120 : 10;
  n.vitD += supp.vitD;
  const r = scoreDay({ targets: base, totals: n, suppTotals: supp, waterMl: base.waterMl * w, dosesScheduled: sch, dosesTaken: tk });
  const pace = computePace({ targets: base, totals: n, waterMl: base.waterMl * w, sched: { wake: '07:00', sleep: '23:00', breakfast: '08:00', lunch: '12:30', dinner: '18:30' }, nowMin: 900 });
  scores.push({ f, w, sch, tk, score: r.score, pace: pace.map(x => [x.key, x.status, Math.round(x.expected)]) });
}
const hist = summarizeHistory([80, 80, 80, 80, 80, 80, 80, null, 90, 90, 90, 30, null, 70, 75].map((s, i) => ({ date: `2026-10-${String(i + 1).padStart(2, '0')}`, score: s })), '2026-10-15');
const stack = SUPP_TEMPLATES.filter(t => ['multi', 'iron', 'calcium', 'd3-2000'].includes(t.tid)).map((t, i) => ({ ...t, id: 's' + i, times: t.tid === 'calcium' ? ['10:00'] : t.tid === 'iron' ? ['10:00'] : t.tid === 'd3-2000' ? ['08:00', '20:00'] : t.times }));
const st = analyzeStack(stack, base);
console.log(JSON.stringify({ targets, scores, base: { kcal: base.kcal, protein: base.protein, carbs: base.carbs, fat: base.fat, water: base.waterMl, profile: profiles[40] },
  history: { streak: hist.streak, best: hist.best, shields: hist.shields, points: hist.points, treeDays: hist.treeDays, marks: hist.marks },
  stack: { warnings: st.warnings.length, vitD: st.totals.vitD, calcium: st.totals.calcium } }));
