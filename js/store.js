// Local-first persistence. Everything stays on this device (no account, no server).
const KEY = 'nutritrack.v1';

const blank = () => ({
  version: 1,
  profile: null,          // { sex, age, heightCm, weightKg, activity, goal, proteinPerKg, fatPct, overrides }
  units: 'metric',        // 'metric' | 'imperial' (display only; always stored metric)
  customFoods: [],        // { id, name, category, servings, per100, source:'custom' }
  logs: {},               // { 'YYYY-MM-DD': { entries: [...] } }
  recents: [],            // food ids, most recent first
  supplements: [],        // { id, name, doseLabel, n, times:['HH:MM'], withFood, active }
});

let memory = null;

function load() {
  if (memory) return memory;
  try {
    const raw = localStorage.getItem(KEY);
    memory = raw ? { ...blank(), ...JSON.parse(raw) } : blank();
  } catch {
    memory = blank();
  }
  return memory;
}

function save() {
  try { localStorage.setItem(KEY, JSON.stringify(memory)); } catch { /* storage unavailable: keep in memory */ }
}

export const uid = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4);

export const store = {
  get: load,
  update(fn) { fn(load()); save(); },
  day(date) { return load().logs[date]?.entries ?? []; },
  addEntry(date, entry) {
    this.update(s => {
      (s.logs[date] ??= { entries: [] }).entries.push({ id: uid(), ...entry });
      if (entry.foodId) s.recents = [entry.foodId, ...s.recents.filter(r => r !== entry.foodId)].slice(0, 12);
    });
  },
  removeEntry(date, id) {
    this.update(s => { const d = s.logs[date]; if (d) d.entries = d.entries.filter(e => e.id !== id); });
  },
  dayData(date) { return load().logs[date] ?? {}; },
  ensureDay(s, date) { return (s.logs[date] ??= { entries: [] }); },
  addWater(date, ml) { this.update(s => (this.ensureDay(s, date).water ??= []).push({ id: uid(), ml, at: Date.now() })); },
  undoWater(date) { this.update(s => s.logs[date]?.water?.pop()); },
  setDayType(date, type) { this.update(s => { this.ensureDay(s, date).dayType = type; }); },
  // Toggle a scheduled dose. Snapshot nutrients so editing the supplement later doesn't rewrite history.
  toggleDose(date, supp, time) {
    this.update(s => {
      const d = this.ensureDay(s, date);
      d.supps ??= [];
      const i = d.supps.findIndex(x => x.suppId === supp.id && x.time === time);
      if (i >= 0) d.supps.splice(i, 1);
      else d.supps.push({ id: uid(), suppId: supp.id, name: supp.name, time, at: Date.now(), n: { ...supp.n } });
    });
  },
  saveSupplement(supp) {
    this.update(s => {
      const i = s.supplements.findIndex(x => x.id === supp.id);
      if (i >= 0) s.supplements[i] = supp; else s.supplements.push(supp);
    });
  },
  exportJSON() { return JSON.stringify(load(), null, 2); },
  importJSON(text) {
    const data = JSON.parse(text);
    if (typeof data !== 'object' || !data.logs) throw new Error('Not a NutriTrack backup');
    memory = { ...blank(), ...data };
    save();
  },
  reset() { memory = blank(); save(); },
};
