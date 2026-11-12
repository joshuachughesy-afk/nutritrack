// Reminder engine + notification delivery.
import { toMin, fromMin, computePace, paceSummary, microGaps } from './pacing.js';

export const DEFAULT_REMINDERS = {
  enabled: false,          // user has opted in
  supplements: true,       // remind at each scheduled dose
  water: true,             // nudge at intervals, only when behind pace
  waterEveryH: 2,
  checkins: ['11:00', '15:00', '19:30'],
};

const WINDOW_DOSE = 20;    // minutes after a dose time we'll still remind
const WINDOW_CHECKIN = 30;

/*
 * Pure: given today's state and the clock, which reminders are due right now?
 * Each event has a stable `key`; the caller records sent keys so nothing fires twice.
 */
export function dueEvents({ settings, sched, nowMin, supps, taken, targets, totals, waterMl, foods, waterFmt }) {
  const events = [];
  const within = (t, win) => nowMin >= t && nowMin < t + win;

  if (settings.supplements) {
    for (const sp of supps.filter(s => s.active !== false)) {
      for (const time of sp.times) {
        const isTaken = taken.some(x => x.suppId === sp.id && x.time === time);
        if (!isTaken && within(toMin(time), WINDOW_DOSE))
          events.push({ key: `supp:${sp.id}:${time}`, kind: 'supplement', title: `💊 Time for ${sp.name}`,
            body: `${sp.doseLabel}${sp.withFood ? ' · take with food' : ''}. Tap to open your checklist.` });
      }
    }
  }

  const pace = computePace({ targets, totals, waterMl, sched, nowMin });

  if (settings.water) {
    const step = Math.max(30, (settings.waterEveryH || 2) * 60);
    const first = toMin(sched.wake) + 120, last = toMin(sched.sleep) - 60;
    for (let t = first; t <= last; t += step) {
      if (!within(t, WINDOW_CHECKIN)) continue;
      const w = pace.find(r => r.key === 'water');
      if (w.status === 'behind')
        events.push({ key: `water:${fromMin(t)}`, kind: 'water', title: '💧 Hydration check',
          body: `${waterFmt(waterMl)} of ${waterFmt(targets.waterMl)} so far, about ${waterFmt(Math.max(0, w.gap))} behind pace. A glass now gets you back on track.` });
    }
  }

  for (const time of settings.checkins || []) {
    if (!time || !within(toMin(time), WINDOW_CHECKIN)) continue;
    const sum = paceSummary(pace, waterFmt);
    let body = sum.text;
    // Evening check-ins also point out micronutrient gaps, with foods that fill them.
    if (toMin(time) >= toMin(sched.dinner) - 60) {
      const gaps = microGaps({ targets, totals, foods, limit: 2 });
      if (gaps.length) body += ' Low today: ' + gaps.map(g => `${g.def.label} (try ${g.foods[0]?.name.toLowerCase() ?? 'a varied meal'})`).join(', ') + '.';
    }
    events.push({ key: `check:${time}`, kind: 'checkin', title: sum.onTrack ? '✅ On track' : '📊 Check-in', body });
  }
  // A check-in already reports water pace, so skip a separate water nudge in the same window.
  return events.some(e => e.kind === 'checkin') ? events.filter(e => e.kind !== 'water') : events;
}

// ---- Delivery ----
export const notifSupport = () => ('Notification' in window ? Notification.permission : 'unsupported');

export async function requestNotifications() {
  if (!('Notification' in window)) return 'unsupported';
  try { return await Notification.requestPermission(); } catch { return Notification.permission; }
}

let swReg = null;
export async function registerSW() {
  if (!('serviceWorker' in navigator) || location.protocol === 'file:') return null;
  try { swReg = await navigator.serviceWorker.register('sw.js'); } catch { swReg = null; }
  return swReg;
}

// Returns true if a system notification was shown; false means the caller should show it in-app.
export async function showNotification({ title, body, key }) {
  if (notifSupport() !== 'granted') return false;
  const opts = { body, tag: key, icon: 'icons/icon-192.png', badge: 'icons/icon-192.png', data: { url: './' } };
  try {
    const reg = swReg || (await navigator.serviceWorker?.getRegistration());
    if (reg) { await reg.showNotification(title, opts); return true; }
    new Notification(title, opts);
    return true;
  } catch { return false; }
}
