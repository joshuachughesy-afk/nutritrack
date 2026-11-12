// Progression: each day plants a seed; how well you hit your goals decides how big that day's tree grows.
import { MICROS, microStatus, fmt } from './nutrition.js';

export const TREE_DAY = 65; // score that counts as a "tree day" for streaks

export const STAGES = [
  { min: 0, name: 'Seed', blurb: 'Freshly planted. Log something to get it going.' },
  { min: 15, name: 'Sprout', blurb: 'Breaking ground.' },
  { min: 40, name: 'Sapling', blurb: 'Taking root.' },
  { min: 65, name: 'Young tree', blurb: 'A solid day. This counts toward your streak.' },
  { min: 85, name: 'Mighty tree', blurb: 'Excellent. Nearly every goal hit.' },
  { min: 95, name: 'Flourishing tree', blurb: 'A perfect day. It\'s blossoming.' },
];
export const stageFor = score => STAGES.reduce((s, st, i) => (score >= st.min ? i : s), 0);

export const LEVELS = [0, 300, 800, 1500, 2500, 4000, 6000, 8500, 11500, 15000];
export const SPECIES = {
  oak:    { name: 'Oak',         level: 1, canopy: ['#3f8f4f', '#2f7a40'], trunk: '#7a5232', shape: 'round' },
  pine:   { name: 'Pine',        level: 2, canopy: ['#2f6f4a', '#245c3c'], trunk: '#6b4a2e', shape: 'cone' },
  cherry: { name: 'Cherry blossom', level: 3, canopy: ['#f2a7c3', '#e687ab'], trunk: '#6e4434', shape: 'round', bloom: '#ffffff' },
  maple:  { name: 'Autumn maple', level: 4, canopy: ['#e0823a', '#c9612a'], trunk: '#6b4430', shape: 'round' },
  birch:  { name: 'Birch',       level: 5, canopy: ['#9cc95a', '#7fb143'], trunk: '#e9e4d8', shape: 'oval' },
  golden: { name: 'Golden tree', level: 7, canopy: ['#f2c94c', '#e0a92e'], trunk: '#7a5a2a', shape: 'round', bloom: '#fff6c9' },
};

export function levelInfo(points) {
  let level = 1;
  for (let i = 0; i < LEVELS.length; i++) if (points >= LEVELS[i]) level = i + 1;
  const cur = LEVELS[level - 1], next = LEVELS[level] ?? null;
  return { level, points, cur, next, progress: next ? (points - cur) / (next - cur) : 1 };
}

const clamp01 = v => Math.max(0, Math.min(1, v));
const band = (actual, target, full, zero) => { const dev = Math.abs(actual / target - 1); return clamp01(1 - (dev - full) / (zero - full)); };

/*
 * Score a day out of 100. Points:
 *   calories 20 (full within ±10%, none beyond ±30%) · protein 15 (full at ≥90%, none <50%)
 *   carbs 10 (±15% / ±40%) · fat 5 (±20% / ±50%) · micronutrients 20 (average coverage, −2 per limit exceeded)
 *   water 15 · supplements 10 (if you have none scheduled, the rest is scaled up to 100)
 * More than 25% over your calorie target caps the day at 60 (a sapling), so it can't count as a tree day.
 */
export function scoreDay({ targets, totals, suppTotals, waterMl, dosesScheduled, dosesTaken }) {
  const parts = [];
  parts.push({ key: 'kcal', label: 'Calories', max: 20, pts: 20 * band(totals.kcal, targets.kcal, 0.10, 0.30) });
  parts.push({ key: 'protein', label: 'Protein', max: 15, pts: 15 * clamp01((totals.protein / targets.protein - 0.5) / 0.4) });
  parts.push({ key: 'carbs', label: 'Carbs', max: 10, pts: 10 * band(totals.carbs, targets.carbs, 0.15, 0.40) });
  parts.push({ key: 'fat', label: 'Fat', max: 5, pts: 5 * band(totals.fat, targets.fat, 0.20, 0.50) });

  const micro = MICROS.filter(m => !m.limit);
  const coverage = micro.reduce((a, m) => a + Math.min(totals[m.key] / targets.micros[m.key].target, 1), 0) / micro.length;
  const over = MICROS.filter(m => microStatus(m, targets.micros[m.key], totals[m.key], suppTotals?.[m.key] ?? 0).status === 'over').length;
  parts.push({ key: 'micros', label: 'Micronutrients', max: 20, pts: Math.max(0, 20 * coverage - 2 * over), over });

  parts.push({ key: 'water', label: 'Water', max: 15, pts: 15 * clamp01(waterMl / targets.waterMl) });
  if (dosesScheduled > 0) parts.push({ key: 'supps', label: 'Supplements', max: 10, pts: (10 * dosesTaken) / dosesScheduled });

  const max = parts.reduce((a, p) => a + p.max, 0);
  const raw = parts.reduce((a, p) => a + p.pts, 0);
  const scale = 100 / max;
  parts.forEach(p => { p.pts *= scale; p.max *= scale; });
  let score = Math.round(raw * scale);
  // Big calorie overshoots can't be "made up" with other goals: cap the day at sapling.
  const capped = totals.kcal > targets.kcal * 1.25 && score > TREE_DAY - 5;
  if (capped) score = TREE_DAY - 5;
  return { score, parts, capped };
}

// Concrete next actions, ordered by how many points they'd add.
export function growthTips({ parts, targets, totals, waterMl, dosesScheduled, dosesTaken, gaps, waterFmt }) {
  const tips = [];
  const get = k => parts.find(p => p.key === k);
  const add = (k, text) => { const p = get(k); if (p && p.max - p.pts >= 1) tips.push({ gain: p.max - p.pts, text }); };
  const kcalGap = targets.kcal - totals.kcal;
  add('kcal', kcalGap > 0 ? `Eat about ${fmt(kcalGap)} kcal more` : `You're ${fmt(-kcalGap)} kcal over, so keep the rest of today light`);
  if (totals.protein < targets.protein * 0.9) add('protein', `Add ${fmt(targets.protein * 0.9 - totals.protein)} g protein (Greek yogurt, chicken, tofu, whey)`);
  const carbGap = targets.carbs - totals.carbs;
  add('carbs', carbGap > 0 ? `Add ${fmt(carbGap)} g carbs (oats, rice, fruit, potatoes)` : `Carbs are ${fmt(-carbGap)} g over target`);
  const fatGap = targets.fat - totals.fat;
  add('fat', fatGap > 0 ? `Add ${fmt(fatGap)} g fat (nuts, olive oil, avocado)` : `Fat is ${fmt(-fatGap)} g over target`);
  if (waterMl < targets.waterMl) add('water', `Drink ${waterFmt(targets.waterMl - waterMl)} more water`);
  if (dosesScheduled > dosesTaken) add('supps', `Take your ${dosesScheduled - dosesTaken} remaining supplement dose${dosesScheduled - dosesTaken > 1 ? 's' : ''}`);
  if (gaps?.length) add('micros', `Boost ${gaps.slice(0, 2).map(g => `${g.def.label} (${g.foods[0]?.name.toLowerCase() ?? 'varied foods'})`).join(' and ')}`);
  return tips.sort((a, b) => b.gain - a.gain).slice(0, 3);
}

/*
 * Walk the history day by day: streaks, shields and total points.
 * `days` = [{ date, score|null }] in ascending order up to and including today.
 * A tree day (≥65) extends the streak; every 7 in a row earns a shield (max 2).
 * A missed day uses a shield if you have one; otherwise the streak resets. Today never breaks a streak (it isn't over).
 */
export function summarizeHistory(days, today) {
  let streak = 0, best = 0, shields = 0, points = 0, treeDays = 0;
  const marks = {};
  for (const { date, score } of days) {
    if (score != null) points += score;
    const isTree = score != null && score >= TREE_DAY;
    if (isTree) {
      streak++; treeDays++;
      if (streak % 7 === 0) shields = Math.min(2, shields + 1);
      marks[date] = 'tree';
    } else if (date === today) {
      marks[date] = 'today';
    } else if (shields > 0 && streak > 0) {
      shields--; marks[date] = 'shielded';
    } else {
      streak = 0; marks[date] = 'missed';
    }
    best = Math.max(best, streak);
  }
  return { streak, best, shields, points, treeDays, marks };
}

// ---- Tree drawing (SVG). stage 0–5, species key, `id` keeps gradient ids unique per instance. ----
export function treeSVG(stage, speciesKey = 'oak', { size = 120, id = 't', muted = false } = {}) {
  const sp = SPECIES[speciesKey] ?? SPECIES.oak;
  const [c1, c2] = sp.canopy;
  const ground = `<ellipse cx="60" cy="108" rx="${16 + stage * 6}" ry="5" fill="#8a6a4a" opacity=".35"/>`;
  let body = '';
  if (stage === 0) {
    body = `<path d="M44 108 q16 -14 32 0z" fill="#9b7653"/><ellipse cx="60" cy="101" rx="5" ry="3.5" fill="#6b4a2e"/>`;
  } else if (stage === 1) {
    body = `<path d="M60 108 V88" stroke="#4f8a3c" stroke-width="3" stroke-linecap="round"/>
      <path d="M60 92 q-12 -2 -14 -12 q11 0 14 12z" fill="#6fb34f"/><path d="M60 89 q11 -3 14 -13 q-12 1 -14 13z" fill="#5aa040"/>`;
  } else {
    const h = [0, 0, 34, 48, 60, 64][stage];               // trunk height
    const r = [0, 0, 16, 24, 31, 34][stage];               // canopy radius
    const top = 108 - h;
    const tw = Math.max(3, stage * 1.6);
    const trunk = `<path d="M${60 - tw} 108 L${60 - tw * 0.55} ${top + r * 0.3} L${60 + tw * 0.55} ${top + r * 0.3} L${60 + tw} 108z" fill="${sp.trunk}"/>`;
    const birchMarks = speciesKey === 'birch' ? [0.3, 0.55, 0.8].map(f => `<rect x="${60 - tw * 0.7}" y="${108 - h * f}" width="${tw * 0.9}" height="2" fill="#3a3a3a" opacity=".55"/>`).join('') : '';
    let canopy;
    if (sp.shape === 'cone') {
      canopy = [0, 1, 2].map(i => { const w = r * (1.15 - i * 0.28), y = top - i * r * 0.55 + r * 0.6;
        return `<path d="M${60 - w} ${y} L60 ${y - r * 1.1} L${60 + w} ${y}z" fill="url(#g${id})"/>`; }).join('');
    } else {
      const ry = sp.shape === 'oval' ? r * 1.2 : r;
      canopy = `<ellipse cx="60" cy="${top}" rx="${r}" ry="${ry}" fill="url(#g${id})"/>
        <ellipse cx="${60 - r * 0.55}" cy="${top + r * 0.35}" rx="${r * 0.55}" ry="${r * 0.5}" fill="${c2}"/>
        <ellipse cx="${60 + r * 0.6}" cy="${top + r * 0.3}" rx="${r * 0.5}" ry="${r * 0.45}" fill="${c2}"/>`;
    }
    let deco = '';
    if (stage === 5) {
      const bloom = sp.bloom ?? '#e94b4b'; // blossoms, or red fruit on species without blossoms
      const spots = [[-0.5, -0.3], [0.35, -0.5], [0.1, 0.15], [-0.15, -0.65], [0.6, 0.1], [-0.6, 0.25], [0.3, 0.45]];
      deco = spots.map(([dx, dy]) => `<circle cx="${60 + dx * r}" cy="${top + dy * r}" r="${sp.bloom ? 2.6 : 3}" fill="${bloom}"/>`).join('');
    }
    body = trunk + birchMarks + canopy + deco;
  }
  return `<svg viewBox="0 0 120 116" width="${size}" height="${size * 116 / 120}" class="tree${muted ? ' tree-muted' : ''}" aria-hidden="true">
    <defs><linearGradient id="g${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${c1}"/><stop offset="1" stop-color="${c2}"/></linearGradient></defs>
    ${ground}${body}</svg>`;
}
