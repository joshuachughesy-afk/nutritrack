// Pacing engine: "am I on track for THIS time of day?" — not just "how much is left?".
import { MICROS, fmt } from './nutrition.js';

export const DEFAULT_SCHEDULE = { wake: '07:00', sleep: '23:00', breakfast: '08:00', lunch: '12:30', dinner: '18:30' };

export const toMin = hhmm => { const [h, m] = String(hhmm).split(':').map(Number); return h * 60 + (m || 0); };
export const fromMin = m => `${String(Math.floor(m / 60) % 24).padStart(2, '0')}:${String(Math.round(m % 60)).padStart(2, '0')}`;

function interpolate(points, x) {
  if (x <= points[0][0]) return points[0][1];
  for (let i = 1; i < points.length; i++) {
    const [x1, y1] = points[i], [x0, y0] = points[i - 1];
    if (x <= x1) return x1 === x0 ? y1 : y0 + ((y1 - y0) * (x - x0)) / (x1 - x0);
  }
  return points[points.length - 1][1];
}

// Share of the day's food you'd expect to have eaten by `nowMin`, based on your meal times.
// Each meal is "done" ~30–45 min after it starts; snacks fill the gaps between.
export function expectedFoodShare(sched, nowMin) {
  const pts = [
    [toMin(sched.wake), 0],
    [toMin(sched.breakfast) + 30, 0.25],
    [toMin(sched.lunch) + 30, 0.55],
    [toMin(sched.dinner) + 45, 0.9],
    [Math.max(toMin(sched.dinner) + 46, toMin(sched.sleep) - 60), 1],
  ];
  return interpolate(pts, nowMin);
}

// Water: spread evenly from waking until an hour before bed (so you're not up all night).
export function expectedWaterShare(sched, nowMin) {
  return interpolate([[toMin(sched.wake), 0], [toMin(sched.sleep) - 60, 1]], nowMin);
}

/*
 * Returns a row per tracked item with a neutral status:
 *   'early'  – too early in the day to judge
 *   'behind' – below ~80% of where you'd expect to be by now
 *   'on'     – on pace
 *   'ahead'  – noticeably ahead (for calories/carbs/fat this means "go lighter later"; for protein/water it's fine)
 */
export function computePace({ targets, totals, waterMl, sched, nowMin }) {
  const food = expectedFoodShare(sched, nowMin);
  const water = expectedWaterShare(sched, nowMin);
  const items = [
    { key: 'kcal', label: 'Calories', unit: 'kcal', target: targets.kcal, actual: totals.kcal, share: food, aheadOk: false },
    { key: 'protein', label: 'Protein', unit: 'g', target: targets.protein, actual: totals.protein, share: food, aheadOk: true },
    { key: 'carbs', label: 'Carbs', unit: 'g', target: targets.carbs, actual: totals.carbs, share: food, aheadOk: false },
    { key: 'fat', label: 'Fat', unit: 'g', target: targets.fat, actual: totals.fat, share: food, aheadOk: false },
    { key: 'water', label: 'Water', unit: 'ml', target: targets.waterMl, actual: waterMl, share: water, aheadOk: true },
  ];
  return items.map(it => {
    const expected = it.target * it.share;
    const status = it.share < 0.12 ? 'early'
      : it.actual < expected * 0.8 ? 'behind'
      : it.actual > expected * 1.2 && it.actual > it.target * 0.3 ? 'ahead'
      : 'on';
    return { ...it, expected, gap: expected - it.actual, status };
  });
}

// Micronutrients still under half their target late in the day, with foods that close the gap.
export function microGaps({ targets, totals, foods, limit = 4 }) {
  return MICROS.filter(m => !m.limit)
    .map(m => ({ m, pct: totals[m.key] / targets.micros[m.key].target }))
    .filter(x => x.pct < 0.5)
    .sort((a, b) => a.pct - b.pct)
    .slice(0, limit)
    .map(({ m, pct }) => {
      const target = targets.micros[m.key].target;
      const best = foods
        .map(f => { const g = f.servings[0].g; return { f, amt: (f.per100[m.key] * g) / 100, kcal: (f.per100.kcal * g) / 100 }; })
        .filter(x => x.amt > 0)
        .sort((a, b) => b.amt - a.amt)
        .slice(0, 3)
        .map(x => ({ name: x.f.name, serving: x.f.servings[0].label, pct: x.amt / target }));
      return { def: m, pct, foods: best };
    });
}

const unitFmt = (v, unit, waterFmt) => (unit === 'ml' ? waterFmt(v) : `${fmt(v)} ${unit === 'kcal' ? 'kcal' : unit}`);

// One-line, non-judgmental summary for a notification.
export function paceSummary(rows, waterFmt) {
  const relevant = rows.filter(r => r.status !== 'early');
  if (!relevant.length) return { onTrack: true, text: 'Early in the day. Your targets are set.' };
  const behind = relevant.filter(r => r.status === 'behind');
  const ahead = relevant.filter(r => r.status === 'ahead' && !r.aheadOk);
  const parts = [];
  if (behind.length) parts.push('Behind pace: ' + behind.map(r => `${r.label.toLowerCase()} (~${unitFmt(Math.max(0, r.gap), r.unit, waterFmt)})`).join(', '));
  if (ahead.length) parts.push('Ahead: ' + ahead.map(r => r.label.toLowerCase()).join(', ') + '. Go lighter later.');
  if (!parts.length) return { onTrack: true, text: 'Everything is on pace. Nice work.' };
  return { onTrack: false, text: parts.join('. ') + '.' };
}
