// Supplement templates, timing guidance and stack analysis.
import { MICROS, emptyNutrients } from './nutrition.js';

const n = obj => ({ ...emptyNutrients(), ...obj });

// Per-dose amounts. Typical over-the-counter strengths; users should edit to match their label.
export const SUPP_TEMPLATES = [
  { tid: 'multi', name: 'Multivitamin (generic)', doseLabel: '1 tablet', withFood: true, times: ['08:00'],
    n: n({ vitA: 750, vitC: 90, vitD: 25, vitE: 15, vitK: 80, b12: 6, folate: 400, calcium: 200, iron: 8, magnesium: 50, zinc: 11 }) },
  { tid: 'd3-1000', name: 'Vitamin D3 1,000 IU', doseLabel: '1 softgel (25 µg)', withFood: true, times: ['08:00'], n: n({ vitD: 25 }) },
  { tid: 'd3-2000', name: 'Vitamin D3 2,000 IU', doseLabel: '1 softgel (50 µg)', withFood: true, times: ['08:00'], n: n({ vitD: 50 }) },
  { tid: 'k2', name: 'Vitamin K2 (MK-7)', doseLabel: '1 capsule (100 µg)', withFood: true, times: ['08:00'], n: n({ vitK: 100 }) },
  { tid: 'mag', name: 'Magnesium glycinate', doseLabel: '200 mg elemental', withFood: false, times: ['21:00'], n: n({ magnesium: 200 }) },
  { tid: 'zinc', name: 'Zinc', doseLabel: '15 mg', withFood: true, times: ['13:00'], n: n({ zinc: 15 }) },
  { tid: 'iron', name: 'Iron (bisglycinate)', doseLabel: '18 mg', withFood: false, times: ['10:00'], n: n({ iron: 18 }) },
  { tid: 'calcium', name: 'Calcium citrate', doseLabel: '500 mg', withFood: true, times: ['19:00'], n: n({ calcium: 500 }) },
  { tid: 'vitc', name: 'Vitamin C', doseLabel: '500 mg', withFood: false, times: ['08:00'], n: n({ vitC: 500 }) },
  { tid: 'b12', name: 'Vitamin B12', doseLabel: '1,000 µg', withFood: false, times: ['08:00'], n: n({ b12: 1000 }) },
  { tid: 'folic', name: 'Folic acid', doseLabel: '400 µg', withFood: false, times: ['08:00'], n: n({ folate: 400 }) },
  { tid: 'potassium', name: 'Potassium', doseLabel: '99 mg', withFood: true, times: ['13:00'], n: n({ potassium: 99 }) },
  { tid: 'electrolytes', name: 'Electrolyte mix', doseLabel: '1 stick / scoop', withFood: false, times: ['16:00'], n: n({ sodium: 500, potassium: 200, magnesium: 60 }) },
  { tid: 'fish-oil', name: 'Fish oil (omega-3)', doseLabel: '1 g (EPA+DHA ~600 mg)', withFood: true, times: ['19:00'], n: n({ kcal: 9, fat: 1 }) },
  { tid: 'creatine', name: 'Creatine monohydrate', doseLabel: '5 g', withFood: false, times: ['08:00'], n: n({}) },
];

const has = (s, k, min = 0.0001) => (s.n?.[k] || 0) >= min;
const nameHas = (s, re) => re.test(s.name.toLowerCase());

// Evidence-based timing guidance for a single supplement.
export function timingAdvice(s) {
  const tips = [];
  if (['vitA', 'vitD', 'vitE', 'vitK'].some(k => has(s, k)) || nameHas(s, /fish oil|omega/))
    tips.push('Fat-soluble: take with a meal that contains fat for better absorption.');
  if (has(s, 'iron', 5))
    tips.push('Iron: absorbs best on an empty stomach or with vitamin C. Keep it 2+ hours away from calcium, zinc, coffee, tea and dairy.');
  if (has(s, 'calcium', 250))
    tips.push('Calcium: the body absorbs about 500 mg at a time. Split larger doses and keep them away from iron.');
  if (has(s, 'magnesium', 100))
    tips.push('Magnesium: the evening works well and may help sleep. Glycinate is gentle on the stomach.');
  if (has(s, 'zinc', 8))
    tips.push('Zinc: take with food to avoid nausea and keep it about 2 hours apart from iron and calcium. Long-term intake above 40 mg/day can deplete copper.');
  if (nameHas(s, /creatine/)) tips.push('Creatine: take it every day; consistency matters more than timing.');
  if (nameHas(s, /electrolyte/)) tips.push('Electrolytes: best before or during long, hot or sweaty sessions.');
  if (has(s, 'b12', 100)) tips.push('B12: any time of day. Mornings are common because some people find it stimulating.');
  return tips;
}

// Analyse the whole active stack for one day: totals, UL exposure and same-time interactions.
export function analyzeStack(supps, targets) {
  const active = supps.filter(s => s.active !== false);
  const totals = emptyNutrients();
  for (const s of active) for (const k in totals) totals[k] += (s.n[k] || 0) * s.times.length;

  const warnings = [];
  for (const def of MICROS) {
    const t = targets.micros[def.key];
    if (!t?.ul || !totals[def.key]) continue;
    if (totals[def.key] > t.ul)
      warnings.push(`${def.label}: your supplements alone provide ${Math.round(totals[def.key])} ${def.unit}/day, above the ${t.ul} ${def.unit} upper limit${def.ulScope === 'supplement' ? ' for supplemental intake' : ''}.`);
    else if (def.ulScope === 'total' && totals[def.key] > t.ul * 0.6)
      warnings.push(`${def.label}: your supplements provide ${Math.round(totals[def.key])} ${def.unit}. Add food and you may get close to the ${t.ul} ${def.unit} upper limit.`);
  }
  if (totals.vitA > 0)
    warnings.push('Vitamin A: the upper limit applies to preformed vitamin A (retinol). Beta-carotene doesn\'t count, so check the label.');

  // Interactions between doses scheduled at the same time.
  const byTime = {};
  for (const s of active) for (const time of s.times) (byTime[time] ??= []).push(s);
  for (const [time, list] of Object.entries(byTime)) {
    const ironSrc = list.find(s => has(s, 'iron', 5));
    const blockers = list.filter(s => s !== ironSrc && (has(s, 'calcium', 200) || has(s, 'zinc', 8)));
    if (ironSrc && blockers.length)
      warnings.push(`${time}: ${ironSrc.name} is scheduled with ${blockers.map(b => b.name).join(', ')}. Calcium and zinc reduce iron absorption, so move one at least 2 hours apart.`);
  }
  return { totals, warnings };
}
