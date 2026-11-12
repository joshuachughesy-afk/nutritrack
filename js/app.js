import { store, uid } from './store.js';
import { FOODS } from './foods.js';
import { TRAINING, LOADS } from './training.js';
import { DEFAULT_SCHEDULE, computePace, microGaps, toMin } from './pacing.js';
import { DEFAULT_REMINDERS, dueEvents, notifSupport, requestNotifications, registerSW, showNotification } from './reminders.js';
import { STAGES, SPECIES, TREE_DAY, stageFor, levelInfo, scoreDay, growthTips, summarizeHistory, treeSVG } from './garden.js';
import { SUPP_TEMPLATES, timingAdvice, analyzeStack, dailyCreatine, creatinePerDose } from './supplements.js';
import {
  MACROS, MICROS, ACTIVITY, GOALS, computeTargets, scaleNutrients, sumNutrients, emptyNutrients,
  microStatus, fmt, kgToLb, lbToKg, cmToIn, inToCm, dayTargets, DEFAULT_TRAINING_DAYS, ML_PER_OZ,
} from './nutrition.js';

const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const MEALS = [['breakfast', 'Breakfast'], ['lunch', 'Lunch'], ['dinner', 'Dinner'], ['snacks', 'Snacks']];

const dateKey = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const shiftDate = (key, days) => { const [y, m, d] = key.split('-').map(Number); return dateKey(new Date(y, m - 1, d + days)); };
const prettyDate = key => {
  const today = dateKey(new Date());
  if (key === today) return 'Today';
  if (key === shiftDate(today, -1)) return 'Yesterday';
  const [y, m, d] = key.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
};

const ui = { view: 'today', date: dateKey(new Date()), modal: null, suppEdit: null, suppDraft: null };

const weekday = key => { const [y, m, d] = key.split('-').map(Number); return new Date(y, m - 1, d).getDay(); };
const isTrainingDay = key => {
  const s = store.get(), dt = store.dayData(key).dayType;
  return dt ? dt === 'training' : (s.profile?.trainingDays ?? DEFAULT_TRAINING_DAYS).includes(weekday(key));
};
const extrasNow = () => ({ creatineG: dailyCreatine(store.get().supplements) });
const targetsFor = key => dayTargets(store.get().profile, isTrainingDay(key), extrasNow());
const imperial = () => store.get().units === 'imperial';
const fmtWater = ml => imperial() ? `${Math.round(ml / ML_PER_OZ)} oz` : ml >= 1000 ? `${Number((ml / 1000).toFixed(2))} L` : `${ml} ml`;
const nowHHMM = () => { const d = new Date(); return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`; };
const fmtTime = hhmm => { const [h, m] = hhmm.split(':').map(Number); return new Date(2000, 0, 1, h, m).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }); };

const schedule = () => ({ ...DEFAULT_SCHEDULE, ...(store.get().schedule ?? {}) });
const reminderSettings = () => ({ ...DEFAULT_REMINDERS, ...(store.get().reminders ?? {}) });
const nowMin = () => { const d = new Date(); return d.getHours() * 60 + d.getMinutes(); };
const dayTotals = key => {
  const day = store.dayData(key);
  return {
    day,
    totals: sumNutrients([...store.day(key).map(e => e.n), ...(day.supps ?? []).map(x => x.n)]),
    waterMl: (day.water ?? []).reduce((a, w) => a + w.ml, 0),
  };
};

// ---- Garden helpers ----
const seed = () => store.get().garden?.seed ?? 'oak';
const speciesFor = key => store.dayData(key).species ?? store.dayData(key).garden?.species ?? seed();
const hasLog = key => store.day(key).length > 0;

function liveScore(key) {
  const t = targetsFor(key);
  const day = store.dayData(key);
  const foodTot = sumNutrients(store.day(key).map(e => e.n));
  const suppTot = sumNutrients((day.supps ?? []).map(x => x.n));
  const totals = sumNutrients([foodTot, suppTot]);
  const waterMl = (day.water ?? []).reduce((a, w) => a + w.ml, 0);
  const active = store.get().supplements.filter(x => x.active !== false);
  const dosesScheduled = active.reduce((a, x) => a + x.times.length, 0);
  const dosesTaken = (day.supps ?? []).filter(x => active.some(a => a.id === x.suppId)).length;
  const res = scoreDay({ targets: t, totals, suppTotals: suppTot, waterMl, dosesScheduled, dosesTaken: Math.min(dosesTaken, dosesScheduled) });
  return { ...res, t, totals, waterMl, dosesScheduled, dosesTaken };
}

// Freeze finished days so later profile changes don't rewrite your garden.
function finalizeGarden() {
  const s = store.get(), today = dateKey(new Date());
  const pending = Object.keys(s.logs).filter(k => k < today && hasLog(k) && !s.logs[k].garden);
  if (!pending.length || !s.profile) return;
  const results = pending.map(k => [k, liveScore(k).score, speciesFor(k)]);
  store.update(st => results.forEach(([k, score, species]) => { st.logs[k].garden = { score, species }; }));
}

function gardenHistory() {
  const s = store.get(), today = dateKey(new Date());
  const logged = Object.keys(s.logs).filter(hasLog).sort();
  const start = logged[0] && logged[0] < today ? logged[0] : today;
  const days = [];
  for (let k = start; k <= today; k = shiftDate(k, 1)) {
    const g = s.logs[k]?.garden;
    days.push({ date: k, score: g ? g.score : k === today ? (hasLog(k) ? liveScore(k).score : null) : null });
  }
  return { days, ...summarizeHistory(days, today) };
}

function celebrate(key, stage) {
  const s = store.get();
  const day = store.dayData(key);
  if (key === dateKey(new Date()) && stage > (day.peakStage ?? 0)) {
    store.update(st => { store.ensureDay(st, key).peakStage = stage; });
    if (stage >= 1) setTimeout(() => toast(`🌱 Your tree grew into a ${STAGES[stage].name.toLowerCase()}!`), 50);
  }
  const lvl = levelInfo(gardenHistory().points).level;
  if (lvl > (s.garden?.lastLevel ?? 1)) {
    store.update(st => { st.garden = { ...(st.garden ?? {}), lastLevel: lvl }; });
    const unlocked = Object.values(SPECIES).filter(x => x.level === lvl).map(x => x.name);
    setTimeout(() => toast(`🎉 Garden level ${lvl}!${unlocked.length ? ' Unlocked: ' + unlocked.join(', ') : ''}`), 1200);
  }
}

const allFoods = () => [...store.get().customFoods, ...FOODS];
const findFood = id => allFoods().find(f => f.id === id);

// ---------- Rendering ----------
function render() {
  const s = store.get();
  if (!s.profile && ui.view !== 'profile') ui.view = 'profile';
  document.querySelectorAll('[data-nav]').forEach(b => b.setAttribute('aria-current', b.dataset.nav === ui.view ? 'page' : 'false'));
  const main = $('#main');
  main.innerHTML = ui.view === 'today' ? viewToday() : ui.view === 'foods' ? viewFoods() : ui.view === 'supps' ? viewSupps() : ui.view === 'garden' ? viewGarden() : viewProfile();
  if (ui.view === 'profile') syncProfileUnits();
}

function ring(value, target) {
  const r = 52, c = 2 * Math.PI * r;
  const pct = target ? Math.min(value / target, 1) : 0;
  const over = target && value > target * 1.05;
  return `<svg class="ring" viewBox="0 0 120 120" aria-hidden="true">
    <circle cx="60" cy="60" r="${r}" class="ring-track"/>
    <circle cx="60" cy="60" r="${r}" class="ring-fill ${over ? 'is-over' : ''}" stroke-dasharray="${c}" stroke-dashoffset="${c * (1 - pct)}"/>
  </svg>`;
}

function bar(pct, status) {
  return `<div class="bar"><div class="bar-fill s-${status}" style="width:${Math.min(pct, 1) * 100}%"></div></div>`;
}

function viewToday() {
  const s = store.get();
  const t = targetsFor(ui.date);
  const entries = store.day(ui.date);
  const day = store.dayData(ui.date);
  const foodTot = sumNutrients(entries.map(e => e.n));
  const suppTot = sumNutrients((day.supps ?? []).map(x => x.n));
  const tot = sumNutrients([foodTot, suppTot]);
  const remaining = t.kcal - tot.kcal;
  const yesterday = store.day(shiftDate(ui.date, -1));

  const carbFirst = t.training.emphasis.startsWith('Carb');
  const macroOrder = carbFirst ? [MACROS[1], MACROS[0], MACROS[2]] : MACROS;
  const macroRows = macroOrder.map(m => {
    const pct = tot[m.key] / t[m.key];
    const status = pct > 1.1 ? 'over' : pct >= 0.9 ? 'met' : pct >= 0.5 ? 'mid' : 'low';
    return `<div class="macro">
      <div class="macro-head"><span class="dot dot-${m.key}"></span>${m.label}
        <span class="muted num">${fmt(tot[m.key])} / ${t[m.key]} g</span></div>
      <div class="bar"><div class="bar-fill fill-${m.key}" style="width:${Math.min(pct, 1) * 100}%"></div></div>
      <div class="macro-sub muted">${status === 'over' ? `${fmt(tot[m.key] - t[m.key])} g over` : `${fmt(Math.max(0, t[m.key] - tot[m.key]))} g left`}</div>
    </div>`;
  }).join('');

  const meals = MEALS.map(([key, label]) => {
    const list = entries.filter(e => e.meal === key);
    const kcal = list.reduce((a, e) => a + e.n.kcal, 0);
    const canCopy = !list.length && yesterday.some(e => e.meal === key);
    return `<section class="card meal">
      <header class="meal-head">
        <h3>${label}</h3><span class="muted num">${fmt(kcal)} kcal</span>
      </header>
      ${list.length ? `<ul class="entries">${list.map(e => `
        <li>
          <div class="entry-main"><span class="entry-name">${esc(e.name)}</span>
            <span class="muted small">${esc(e.amountLabel)} · P ${fmt(e.n.protein)} · C ${fmt(e.n.carbs)} · F ${fmt(e.n.fat)}</span></div>
          <span class="num">${fmt(e.n.kcal)}</span>
          <button class="icon-btn" data-action="remove-entry" data-id="${e.id}" aria-label="Remove ${esc(e.name)}">✕</button>
        </li>`).join('')}</ul>` : ''}
      <div class="meal-actions">
        <button class="btn btn-ghost" data-action="open-add" data-meal="${key}">+ Add food</button>
        ${canCopy ? `<button class="btn btn-ghost" data-action="copy-meal" data-meal="${key}">↻ Copy yesterday</button>` : ''}
      </div>
    </section>`;
  }).join('');

  const micros = MICROS.map(def => {
    const target = t.micros[def.key];
    const { pct, status } = microStatus(def, target, tot[def.key], suppTot[def.key]);
    const label = def.limit ? 'limit' : '';
    const foodPct = Math.min(foodTot[def.key] / target.target, 1);
    const suppPct = Math.min(pct, 1) - foodPct;
    const ulNote = status === 'over' && !def.limit ? `<span class="small over-note">Above the ${fmt(target.ul)} ${def.unit} upper limit${def.ulScope === 'supplement' ? ' from supplements' : ''}</span>` : '';
    return `<li class="micro">
      <div class="micro-head"><span>${def.label}</span>
        <span class="muted num small">${fmt(tot[def.key])} / ${fmt(target.target)} ${def.unit} ${label}</span>
        <span class="pct s-${status}">${Math.round(pct * 100)}%</span></div>
      <div class="bar s-${status}"><div class="bar-fill" style="width:${foodPct * 100}%"></div>${suppPct > 0.001 ? `<div class="bar-fill supp" style="width:${suppPct * 100}%"></div>` : ''}</div>
      ${ulNote}
    </li>`;
  }).join('');

  return `
    <div class="date-nav">
      <button class="icon-btn" data-action="date" data-delta="-1" aria-label="Previous day">‹</button>
      <h2>${prettyDate(ui.date)}</h2>
      <button class="icon-btn" data-action="date" data-delta="1" aria-label="Next day">›</button>
    </div>
    <div class="daytype" role="group" aria-label="Day type">
      <button data-action="daytype" data-type="training" aria-pressed="${t.dayType === 'training'}">🏋️ Training day</button>
      <button data-action="daytype" data-type="rest" aria-pressed="${t.dayType === 'rest'}">🛌 Rest day</button>
    </div>
    ${t.cycling ? `<p class="muted small daytype-note">${t.dayType === 'training' ? 'Training day: extra carbs to fuel the session.' : 'Rest day: carbs drop toward maintenance needs.'} Your weekly average still matches your target.</p>` : ''}
    <section class="card summary">
      <div class="ring-wrap">
        ${ring(tot.kcal, t.kcal)}
        <div class="ring-label"><strong class="num">${fmt(Math.abs(remaining))}</strong><span class="muted small">${remaining >= 0 ? 'kcal left' : 'kcal over'}</span></div>
      </div>
      <div class="summary-stats">
        <div><span class="muted small">Eaten</span><strong class="num">${fmt(tot.kcal)}</strong></div>
        <div><span class="muted small">Target</span><strong class="num">${fmt(t.kcal)}</strong></div>
      </div>
      <div class="macros">${macroRows}</div>
      <button class="training-badge" data-nav="profile"><span class="chip ${emphasisClass(t.training.emphasis)}">${t.training.name} · ${t.training.emphasis}</span>
        <span class="muted small">C ${t.gkg.carbs.toFixed(1)} · P ${t.gkg.protein.toFixed(1)} · F ${t.gkg.fat.toFixed(1)} g/kg</span></button>
    </section>
    ${viewTreeCard()}
    ${ui.date === dateKey(new Date()) ? viewPace(t) : ''}
    <div class="two-col">${viewWater(t, day)}${viewSuppChecklist(day)}</div>
    ${meals}
    <section class="card">
      <header class="meal-head"><h3>Micronutrients</h3><span class="muted small">vs. your DRI targets</span></header>
      <ul class="micros">${micros}</ul>
      <p class="muted small legend"><span class="chip s-low">under 50%</span><span class="chip s-mid">50–99%</span><span class="chip s-met">met</span><span class="chip s-over">above limit</span><span class="chip supp-chip">from supplements</span></p>
    </section>`;
}

function viewWater(t, day) {
  const total = (day.water ?? []).reduce((a, w) => a + w.ml, 0);
  const pct = total / t.waterMl;
  const amounts = imperial() ? [[8, 237], [16, 473], [24, 710]] : [[250, 250], [500, 500], [750, 750]];
  return `<section class="card water">
    <header class="meal-head"><h3>💧 Water</h3><span class="muted num small">${fmtWater(total)} / ${fmtWater(t.waterMl)}</span></header>
    <div class="water-glass" aria-label="${Math.round(pct * 100)}% of water goal"><div class="water-level" style="height:${Math.min(pct, 1) * 100}%"></div>
      <span class="water-pct num">${Math.round(pct * 100)}%</span></div>
    <div class="water-actions">
      ${amounts.map(([label, ml]) => `<button class="btn btn-ghost" data-action="water" data-ml="${ml}">+${label}${imperial() ? ' oz' : ' ml'}</button>`).join('')}
      ${(day.water ?? []).length ? '<button class="link" data-action="undo-water">Undo</button>' : ''}
    </div>
    <ul class="water-parts small">
      <li><span>Baseline <span class="muted">(35 ml/kg)</span></span><span class="num">${fmtWater(t.water.base)}</span></li>
      ${t.water.training ? `<li><span>Training day</span><span class="num">+${fmtWater(t.water.training)}</span></li>` : ''}
      ${t.water.creatine ? `<li><span>Creatine <span class="muted">(${fmt(t.water.creatineG)} g/day${t.water.creatineG >= 15 ? ', loading' : ''})</span></span><span class="num">+${fmtWater(t.water.creatine)}</span></li>` : ''}
    </ul>
    ${t.dayType === 'training' ? `<p class="muted small">During exercise, drink about ${imperial() ? '14–27 oz' : '400–800 ml'} per hour, more in heat.</p>` : ''}
  </section>`;
}

function viewSuppChecklist(day) {
  const supps = store.get().supplements.filter(x => x.active !== false);
  const taken = day.supps ?? [];
  const doses = supps.flatMap(sp => sp.times.map(time => ({ sp, time }))).sort((a, b) => a.time.localeCompare(b.time));
  const isToday = ui.date === dateKey(new Date());
  const now = nowHHMM();
  const done = doses.filter(d => taken.some(x => x.suppId === d.sp.id && x.time === d.time)).length;
  return `<section class="card supps">
    <header class="meal-head"><h3>💊 Supplements</h3><span class="muted num small">${done} / ${doses.length} taken</span></header>
    ${doses.length ? `<ul class="dose-list">${doses.map(({ sp, time }) => {
      const isTaken = taken.some(x => x.suppId === sp.id && x.time === time);
      const due = isToday && !isTaken && time <= now;
      return `<li class="${isTaken ? 'is-taken' : ''}">
        <button class="dose-check" data-action="dose" data-id="${sp.id}" data-time="${time}" aria-pressed="${isTaken}" aria-label="Mark ${esc(sp.name)} at ${fmtTime(time)} ${isTaken ? 'not taken' : 'taken'}">${isTaken ? '✓' : ''}</button>
        <div class="entry-main"><span class="entry-name">${esc(sp.name)}</span>
          <span class="muted small">${fmtTime(time)} · ${esc(sp.doseLabel)}${sp.withFood ? ' · with food' : ''}</span></div>
        ${due ? '<span class="chip s-low">due</span>' : ''}
      </li>`;
    }).join('')}</ul>` : '<p class="muted small">No supplements yet. Add your stack and they\'ll count toward your micronutrients.</p>'}
    <button class="btn btn-ghost" data-nav="supps">${doses.length ? 'Manage stack' : '+ Add supplements'}</button>
  </section>`;
}

function suppForm(sp) {
  const v = k => (sp?.n?.[k] ? +sp.n[k].toFixed(3) : '');
  const times = sp?.times ?? ['08:00'];
  return `<form id="supp-form" class="form-grid" data-id="${sp?.id ?? ''}">
    <label class="span-2">Name<input name="name" required maxlength="80" value="${esc(sp?.name ?? '')}" placeholder="e.g. Vitamin D3"></label>
    <label class="span-2">Dose<input name="doseLabel" maxlength="60" value="${esc(sp?.doseLabel ?? '1 capsule')}"></label>
    <fieldset class="span-2"><legend>Times per day</legend>
      <div class="time-row">${[0, 1, 2].map(i => `<input type="time" name="time${i}" value="${times[i] ?? ''}" aria-label="Dose time ${i + 1}">`).join('')}</div>
      <p class="muted small">Leave extra times blank. Each time is one dose.</p>
    </fieldset>
    <label class="span-2 check"><input type="checkbox" name="withFood" ${sp?.withFood ? 'checked' : ''}> Take with food</label>
    <label>Creatine per dose (g)<input name="creatineG" type="number" step="any" min="0" value="${sp && creatinePerDose(sp) ? creatinePerDose(sp) : ''}" placeholder="0"></label>
    <p class="muted small creatine-hint">If this contains creatine, your water goal goes up about 500 ml/day (about 1 L/day while loading at 15 g+/day).</p>
    <details class="span-2" ${sp ? 'open' : ''}><summary>Nutrients per dose (from the label)</summary>
      <div class="form-grid">${MICROS.filter(m => m.key !== 'fiber').map(m =>
        `<label>${m.label} <span class="muted">(${m.unit})</span><input type="number" step="any" min="0" name="${m.key}" value="${v(m.key)}"></label>`).join('')}</div>
      <p class="muted small">Vitamin D: 1,000 IU = 25 µg. Vitamin A: 1 µg RAE = 3.33 IU retinol.</p>
    </details>
    <div class="span-2 row-actions">
      <button class="btn btn-primary" type="submit">${sp ? 'Save changes' : 'Add to stack'}</button>
      <button class="btn btn-ghost" type="button" data-action="cancel-supp">Cancel</button>
    </div>
  </form>`;
}

function viewSupps() {
  const s = store.get();
  const t = targetsFor(ui.date);
  const editing = ui.suppEdit;
  if (editing) {
    const sp = editing === 'new' ? ui.suppDraft : s.supplements.find(x => x.id === editing);
    return `<h2 class="view-title">${editing === 'new' || !sp?.id ? 'Add supplement' : 'Edit supplement'}</h2><section class="card">${suppForm(sp)}</section>`;
  }
  const { totals, warnings } = analyzeStack(s.supplements, t);
  const list = s.supplements.map(sp => {
    const tips = timingAdvice(sp);
    const contents = MICROS.filter(m => sp.n[m.key] > 0).map(m => `${m.label} ${fmt(sp.n[m.key])} ${m.unit}`).join(' · ');
    return `<li class="supp-item ${sp.active === false ? 'is-paused' : ''}">
      <div class="supp-top">
        <div class="entry-main"><span class="entry-name">${esc(sp.name)}</span>
          <span class="muted small">${esc(sp.doseLabel)} · ${sp.times.map(fmtTime).join(', ')}${sp.withFood ? ' · with food' : ''}</span>
          ${contents ? `<span class="small">${contents}</span>` : ''}</div>
        <div class="supp-btns">
          <button class="btn btn-ghost" data-action="edit-supp" data-id="${sp.id}">Edit</button>
          <button class="btn btn-ghost" data-action="pause-supp" data-id="${sp.id}">${sp.active === false ? 'Resume' : 'Pause'}</button>
          <button class="icon-btn" data-action="delete-supp" data-id="${sp.id}" aria-label="Delete ${esc(sp.name)}">✕</button>
        </div>
      </div>
      ${tips.length ? `<ul class="tips small">${tips.map(x => `<li>${x}</li>`).join('')}</ul>` : ''}
    </li>`;
  }).join('');
  const coverage = MICROS.filter(m => totals[m.key] > 0).map(m => {
    const tg = t.micros[m.key];
    const pct = totals[m.key] / tg.target;
    return `<tr><th scope="row">${m.label}</th><td class="num">${fmt(totals[m.key])} ${m.unit}</td><td class="num">${Math.round(pct * 100)}%</td><td class="num muted">${tg.ul ? fmt(tg.ul) + ' ' + m.unit : '—'}</td></tr>`;
  }).join('');
  const owned = new Set(s.supplements.map(x => x.tid));
  return `
    <h2 class="view-title">Supplements</h2>
    ${warnings.length ? `<section class="card warn-card"><h3>Check your stack</h3>${warnings.map(w => `<p class="note">${esc(w)}</p>`).join('')}</section>` : ''}
    <section class="card">
      <header class="meal-head"><h3>My stack</h3><button class="btn btn-primary" data-action="new-supp">+ Custom</button></header>
      ${list ? `<ul class="supp-list">${list}</ul>` : '<p class="muted">Nothing yet. Start from a common supplement below or add a custom one from your label.</p>'}
    </section>
    ${coverage ? `<section class="card"><h3>Daily stack totals</h3><p class="muted small">If every dose is taken, before food.</p>
      <div class="table-wrap"><table><thead><tr><th></th><th>Amount</th><th>% of target</th><th>Upper limit</th></tr></thead><tbody>${coverage}</tbody></table></div></section>` : ''}
    <section class="card">
      <h3>Common supplements</h3>
      <p class="muted small">These are typical strengths. Tap one, then edit it to match your label.</p>
      <div class="template-grid">${SUPP_TEMPLATES.map(tp => `<button class="template" data-action="template" data-tid="${tp.tid}" ${owned.has(tp.tid) ? 'disabled' : ''}>
        <strong>${tp.name}</strong><span class="muted small">${tp.doseLabel}${owned.has(tp.tid) ? ' · added' : ''}</span></button>`).join('')}</div>
    </section>`;
}

function viewPace(t) {
  const { totals, waterMl } = dayTotals(ui.date);
  const sched = schedule();
  const rows = computePace({ targets: t, totals, waterMl, sched, nowMin: nowMin() });
  const label = { early: 'early', behind: 'behind pace', on: 'on pace', ahead: 'ahead' };
  const cls = r => r.status === 'behind' ? 's-low' : r.status === 'ahead' && !r.aheadOk ? 's-mid' : r.status === 'early' ? 's-none' : 's-met';
  const show = (v, unit) => unit === 'ml' ? fmtWater(v) : `${fmt(v)}${unit === 'kcal' ? '' : ' g'}`;
  const gaps = nowMin() >= toMin(sched.dinner) - 60 ? microGaps({ targets: t, totals, foods: allFoods(), limit: 3 }) : [];
  const n = notifSupport(), rs = reminderSettings();
  return `<section class="card pace">
    <header class="meal-head"><h3>⏱️ Pace check</h3><span class="muted small">where you'd expect to be by ${fmtTime(nowHHMM())}</span></header>
    <ul class="pace-list">${rows.map(r => `
      <li>
        <div class="pace-head"><span>${r.label}</span><span class="muted num small">${show(r.actual, r.unit)} · expected ~${show(r.expected, r.unit)}</span><span class="chip ${cls(r)}">${label[r.status]}</span></div>
        <div class="bar pace-bar"><div class="bar-fill fill-${r.key}" style="width:${Math.min(r.actual / r.target, 1) * 100}%"></div>
          <span class="pace-marker" style="left:${Math.min(r.share, 1) * 100}%" title="Expected by now"></span></div>
      </li>`).join('')}</ul>
    ${gaps.length ? `<div class="gaps"><h4>Close today's gaps</h4>${gaps.map(g => `<p class="small"><strong>${g.def.label}</strong> ${Math.round(g.pct * 100)}%: ${g.foods.map(f => `${esc(f.name)} <span class="muted">(${esc(f.serving)}, +${Math.round(f.pct * 100)}%)</span>`).join(' · ')}</p>`).join('')}</div>` : ''}
    ${!rs.enabled ? `<p class="small reminder-cta">🔔 Get check-ins, water nudges and supplement reminders. <button class="link" data-action="goto-reminders">Turn on reminders</button></p>`
      : n === 'denied' ? '<p class="small muted">Notifications are blocked in your browser settings, so reminders show inside the app instead.</p>' : ''}
  </section>`;
}

function viewReminders() {
  const sched = schedule(), rs = reminderSettings(), n = notifSupport();
  const permText = { granted: '✅ Notifications allowed on this device', denied: '🚫 Blocked. Allow notifications for this site in your browser settings.', default: 'Not yet allowed. You\'ll be asked when you save with reminders on.', unsupported: 'This browser can\'t show notifications. Reminders will appear inside the app.' }[n];
  const ti = (name, v) => `<input type="time" name="${name}" value="${v ?? ''}">`;
  return `<section class="card" id="reminders">
    <h3>Schedule & reminders</h3>
    <p class="muted small">Your meal times set the pace: by about 30 minutes after lunch you'd expect about 55% of the day's food. Water spreads evenly until an hour before bed.</p>
    <form id="reminders-form" class="form-grid">
      <label>Wake up${ti('wake', sched.wake)}</label>
      <label>Bedtime${ti('sleep', sched.sleep)}</label>
      <label>Breakfast${ti('breakfast', sched.breakfast)}</label>
      <label>Lunch${ti('lunch', sched.lunch)}</label>
      <label>Dinner${ti('dinner', sched.dinner)}</label>
      <span></span>
      <label class="span-2 check"><input type="checkbox" name="enabled" ${rs.enabled ? 'checked' : ''}> <strong>Send me reminders</strong></label>
      <label class="span-2 check"><input type="checkbox" name="supplements" ${rs.supplements ? 'checked' : ''}> Supplement doses at their scheduled times</label>
      <label class="check"><input type="checkbox" name="water" ${rs.water ? 'checked' : ''}> Water nudges when I'm behind</label>
      <label>Check water every<select name="waterEveryH">${[1, 1.5, 2, 3].map(h => `<option value="${h}" ${+rs.waterEveryH === h ? 'selected' : ''}>${h} h</option>`).join('')}</select></label>
      <fieldset class="span-2"><legend>Daily check-ins <span class="muted small">(macro and water pace; the evening one also lists micronutrient gaps)</span></legend>
        <div class="time-row">${[0, 1, 2].map(i => ti('check' + i, rs.checkins[i])).join('')}</div>
      </fieldset>
      <p class="span-2 small perm">${permText}</p>
      <div class="span-2 row-actions">
        <button class="btn btn-primary" type="submit">Save reminders</button>
        <button class="btn btn-ghost" type="button" data-action="test-notif">Send a test</button>
      </div>
      <p class="span-2 muted small">Reminders fire while NutriTrack is open or running in the background. Install it to your home screen for the most reliable alerts (on iPhone: Share → Add to Home Screen, iOS 16.4+). A fully closed web app can't wake itself; that would need a push server, which is planned.</p>
    </form>
  </section>`;
}

function viewTreeCard() {
  const key = ui.date, today = dateKey(new Date());
  const isToday = key === today;
  const frozen = store.dayData(key).garden;
  if (!isToday && !frozen && !hasLog(key)) return '';
  const live = liveScore(key);
  const score = frozen ? frozen.score : live.score;
  const stage = stageFor(score);
  const species = speciesFor(key);
  const next = STAGES[stage + 1];
  const h = isToday ? gardenHistory() : null;
  const tips = isToday ? growthTips({ ...live, targets: live.t, gaps: microGaps({ targets: live.t, totals: live.totals, foods: allFoods(), limit: 2 }), waterFmt: fmtWater }) : [];
  if (isToday) celebrate(key, stage);
  return `<section class="card tree-card">
    <button class="tree-stage" data-nav="garden" aria-label="Open your garden">${treeSVG(stage, species, { size: 128, id: 'today' })}</button>
    <div class="tree-info">
      <div class="tree-title"><strong>${STAGES[stage].name}</strong><span class="tree-score num">${score}<span class="muted">/100</span></span></div>
      <div class="stage-track">${STAGES.slice(1).map(st => `<span class="${score >= st.min ? 'done' : ''}" title="${st.name} at ${st.min}"></span>`).join('')}</div>
      <p class="muted small">${isToday ? (next ? `${next.min - score} more points to grow into a ${next.name.toLowerCase()}.` : STAGES[stage].blurb) : `Final tree for this day. ${score >= TREE_DAY ? 'Counted as a tree day.' : ''}`}</p>
      ${h ? `<div class="streak-row"><span>🔥 <strong>${h.streak}</strong>-day streak</span>${h.shields ? `<span title="Each covers one missed day">🛡️ ${h.shields}</span>` : ''}</div>` : ''}
      ${tips.length ? `<ul class="grow-tips">${tips.map(x => `<li><span class="gain">+${Math.round(x.gain)}</span>${esc(x.text)}</li>`).join('')}</ul>` : ''}
    </div>
  </section>`;
}

function viewGarden() {
  finalizeGarden();
  const s = store.get();
  const today = dateKey(new Date());
  const h = gardenHistory();
  const lv = levelInfo(h.points);
  const nextSpecies = Object.entries(SPECIES).filter(([, x]) => x.level > lv.level).sort((a, b) => a[1].level - b[1].level)[0];
  const scores = Object.fromEntries(h.days.map(d => [d.date, d.score]));

  // Forest grid: last 8 weeks, Monday-first rows.
  const end = today;
  let startKey = shiftDate(end, -7 * 7);
  while (weekday(startKey) !== 1) startKey = shiftDate(startKey, -1);
  const cells = [];
  for (let k = startKey; ; k = shiftDate(k, 1)) {
    cells.push(k);
    if (k >= end && weekday(k) === 0) break;
    if (cells.length > 70) break;
  }
  const cell = k => {
    if (k > today) return `<div class="plot future"></div>`;
    const sc = scores[k];
    const mark = h.marks[k];
    const label = `${prettyDate(k)}: ${sc != null ? sc + ' points' : 'no log'}`;
    if (sc != null) return `<button class="plot ${k === today ? 'is-today' : ''}" data-action="goto-day" data-date="${k}" title="${label}" aria-label="${label}">${treeSVG(stageFor(sc), speciesFor(k), { size: 38, id: 'c' + k.replace(/-/g, '') })}</button>`;
    return `<div class="plot empty ${mark === 'shielded' ? 'shielded' : ''}" title="${label}">${mark === 'shielded' ? '🛡️' : ''}</div>`;
  };

  return `
    <h2 class="view-title">Your garden</h2>
    <section class="card garden-hero">
      <div class="level-badge"><span class="small muted">Level</span><strong>${lv.level}</strong></div>
      <div class="level-info">
        <div class="level-row"><strong>${h.points.toLocaleString()} growth points</strong>${lv.next ? `<span class="muted small">${(lv.next - h.points).toLocaleString()} to level ${lv.level + 1}</span>` : '<span class="muted small">Max level</span>'}</div>
        <div class="bar"><div class="bar-fill level-fill" style="width:${lv.progress * 100}%"></div></div>
        ${nextSpecies ? `<p class="small muted">Next unlock: <strong>${nextSpecies[1].name}</strong> at level ${nextSpecies[1].level}</p>` : '<p class="small muted">Every species unlocked 🌳</p>'}
      </div>
    </section>
    <div class="stat-grid">
      <div class="card stat"><span>🔥</span><strong class="num">${h.streak}</strong><span class="muted small">day streak</span></div>
      <div class="card stat"><span>🏆</span><strong class="num">${h.best}</strong><span class="muted small">best streak</span></div>
      <div class="card stat"><span>🌳</span><strong class="num">${h.treeDays}</strong><span class="muted small">tree days</span></div>
      <div class="card stat"><span>🛡️</span><strong class="num">${h.shields}</strong><span class="muted small">shields</span></div>
    </div>
    <section class="card">
      <header class="meal-head"><h3>Forest</h3><span class="muted small">last 8 weeks · tap a tree to open that day</span></header>
      <div class="forest">
        ${['M', 'T', 'W', 'T', 'F', 'S', 'S'].map(d => `<span class="forest-day muted small">${d}</span>`).join('')}
        ${cells.map(cell).join('')}
      </div>
    </section>
    <section class="card">
      <h3>Choose today's seed</h3>
      <p class="muted small">Today's tree grows as this species. Higher garden levels unlock more.</p>
      <div class="seed-grid">${Object.entries(SPECIES).map(([k, x]) => {
        const locked = x.level > lv.level;
        return `<button class="seed ${k === seed() ? 'is-selected' : ''}" data-action="pick-seed" data-seed="${k}" ${locked ? 'disabled' : ''} aria-pressed="${k === seed()}">
          ${treeSVG(4, k, { size: 64, id: 's' + k, muted: locked })}<span>${x.name}</span>${locked ? `<span class="muted small">🔒 Level ${x.level}</span>` : ''}</button>`;
      }).join('')}</div>
    </section>
    <section class="card">
      <h3>How your tree grows</h3>
      <div class="table-wrap"><table><tbody>
        <tr><th scope="row">Calories</th><td>20</td><td class="muted small">full within ±10% of target; more than 25% over caps the day at a sapling</td></tr>
        <tr><th scope="row">Protein</th><td>15</td><td class="muted small">full at 90%+ of target</td></tr>
        <tr><th scope="row">Carbs / Fat</th><td>10 / 5</td><td class="muted small">full within ±15% / ±20%</td></tr>
        <tr><th scope="row">Micronutrients</th><td>20</td><td class="muted small">average coverage; −2 for each upper limit exceeded</td></tr>
        <tr><th scope="row">Water</th><td>15</td><td class="muted small">share of today's water goal</td></tr>
        <tr><th scope="row">Supplements</th><td>10</td><td class="muted small">doses taken (with no stack, the rest scales up to 100)</td></tr>
      </tbody></table></div>
      <p class="small">${STAGES.map((st, i) => `<span class="stage-chip">${st.name} ${st.min}+</span>`).join(' ')}</p>
      <p class="muted small">A day of ${TREE_DAY}+ points is a <strong>tree day</strong> and extends your streak. Every 7-day streak earns a 🛡️ shield (hold up to 2) that covers one missed day, so a busy day doesn't wipe out your progress.</p>
    </section>`;
}

function viewFoods() {
  const s = store.get();
  const list = s.customFoods.map(f => {
    const sv = f.servings[0];
    const n = scaleNutrients(f.per100, sv.g);
    return `<li><div class="entry-main"><span class="entry-name">${esc(f.name)}</span>
      <span class="muted small">${esc(sv.label)} · ${fmt(n.kcal)} kcal · P ${fmt(n.protein)} · C ${fmt(n.carbs)} · F ${fmt(n.fat)}</span></div>
      <button class="icon-btn" data-action="delete-food" data-id="${f.id}" aria-label="Delete ${esc(f.name)}">✕</button></li>`;
  }).join('');
  const microInputs = MICROS.filter(m => m.key !== 'fiber').map(m =>
    `<label>${m.label} <span class="muted">(${m.unit})</span><input type="number" step="any" min="0" name="${m.key}"></label>`).join('');
  return `
    <h2 class="view-title">My foods</h2>
    <section class="card">
      <h3>Create a custom food</h3>
      <p class="muted small">Enter values from the nutrition label, <strong>per serving</strong>. Micronutrients are optional.</p>
      <form id="food-form" class="form-grid">
        <label class="span-2">Name<input name="name" required maxlength="80" placeholder="e.g. Mom's lasagna"></label>
        <label>Serving description<input name="servingLabel" placeholder="1 slice" value="1 serving"></label>
        <label>Serving weight (g)<input name="servingG" type="number" step="any" min="1" value="100" required></label>
        <label>Calories<input name="kcal" type="number" step="any" min="0" required></label>
        <label>Protein (g)<input name="protein" type="number" step="any" min="0" value="0"></label>
        <label>Carbs (g)<input name="carbs" type="number" step="any" min="0" value="0"></label>
        <label>Fat (g)<input name="fat" type="number" step="any" min="0" value="0"></label>
        <label>Fiber (g)<input name="fiber" type="number" step="any" min="0"></label>
        <label>Sugar (g)<input name="sugar" type="number" step="any" min="0"></label>
        <details class="span-2"><summary>Micronutrients (optional)</summary><div class="form-grid">${microInputs}</div></details>
        <button class="btn btn-primary span-2" type="submit">Save food</button>
      </form>
    </section>
    <section class="card">
      <h3>Saved (${s.customFoods.length})</h3>
      ${list ? `<ul class="entries">${list}</ul>` : '<p class="muted">No custom foods yet. The built-in list has ' + FOODS.length + ' common foods with full micronutrient data.</p>'}
    </section>`;
}

function viewProfile() {
  const s = store.get();
  const p = s.profile || { sex: 'male', age: 30, heightCm: 178, weightKg: 80, activity: 'moderate', goal: 'maintain', trainingType: 'general', trainingLoad: 'moderate', overrides: {} };
  const t = computeTargets(p);
  const imp = s.units === 'imperial';
  const totalIn = cmToIn(p.heightCm);
  const o = p.overrides || {};
  const opt = (obj, val) => Object.entries(obj).map(([k, v]) => `<option value="${k}" ${k === val ? 'selected' : ''}>${v.label}</option>`).join('');
  return `
    <h2 class="view-title">${s.profile ? 'Profile & targets' : 'Welcome to NutriTrack'}</h2>
    ${s.profile ? '' : '<p class="intro">Tell us about yourself to calculate calorie, macro and micronutrient targets. Everything is stored only on this device.</p>'}
    <form id="profile-form" class="card form-grid">
      <fieldset class="span-2 seg"><legend>Units</legend>
        <label><input type="radio" name="units" value="metric" ${!imp ? 'checked' : ''}> Metric <span class="muted small">kg · cm · ml</span></label>
        <label><input type="radio" name="units" value="imperial" ${imp ? 'checked' : ''}> Imperial <span class="muted small">lb · ft · oz</span></label>
      </fieldset>
      <fieldset class="span-2 seg"><legend>Sex <span class="muted small">(for BMR & DRIs)</span></legend>
        <label><input type="radio" name="sex" value="male" ${p.sex === 'male' ? 'checked' : ''}> Male</label>
        <label><input type="radio" name="sex" value="female" ${p.sex === 'female' ? 'checked' : ''}> Female</label>
      </fieldset>
      <label>Age<input name="age" type="number" min="18" max="100" value="${p.age}" required></label>
      <label class="u-metric">Weight (kg)<input name="weightKg" type="number" step="0.1" min="30" value="${p.weightKg.toFixed(1)}"></label>
      <label class="u-imperial">Weight (lb)<input name="weightLb" type="number" step="0.1" min="66" value="${kgToLb(p.weightKg).toFixed(1)}"></label>
      <label class="u-metric">Height (cm)<input name="heightCm" type="number" min="120" max="230" value="${Math.round(p.heightCm)}"></label>
      <div class="u-imperial height-imp">
        <label>Height (ft)<input name="heightFt" type="number" min="4" max="7" value="${Math.floor(totalIn / 12)}"></label>
        <label>(in)<input name="heightIn" type="number" min="0" max="11.9" step="0.5" value="${Math.round(totalIn % 12)}"></label>
      </div>
      <label class="span-2">Activity<select name="activity">${opt(ACTIVITY, p.activity)}</select></label>
      <label class="span-2">Goal<select name="goal">${opt(GOALS, p.goal)}</select></label>
      <label class="span-2">Training type<select name="trainingType">${Object.entries(TRAINING).map(([k, v]) =>
        `<option value="${k}" ${k === (p.trainingType || 'general') ? 'selected' : ''}>${v.name}</option>`).join('')}</select></label>
      <p class="span-2 muted small training-desc" id="training-desc"></p>
      <fieldset class="span-2 seg"><legend>Training load</legend>
        ${Object.entries(LOADS).map(([k, v]) => `<label><input type="radio" name="trainingLoad" value="${k}" ${k === (p.trainingLoad || 'moderate') ? 'checked' : ''}> ${v.label} <span class="muted small">${v.detail}</span></label>`).join('')}
      </fieldset>
      <fieldset class="span-2 seg days"><legend>Usual training days <span class="muted small">(you can switch any day on the Today screen)</span></legend>
        ${['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((d, i) => `<label><input type="checkbox" name="trainingDays" value="${i}" ${(p.trainingDays ?? DEFAULT_TRAINING_DAYS).includes(i) ? 'checked' : ''}> ${d}</label>`).join('')}
      </fieldset>
      <label class="span-2 check"><input type="checkbox" name="carbCycling" ${p.carbCycling !== false ? 'checked' : ''}> Carb cycling: more carbs on training days, fewer on rest days, same weekly total</label>
      <details class="span-2"><summary>Manual overrides (leave blank for automatic)</summary>
        <div class="form-grid">
          <label>Calories<input name="o_kcal" type="number" min="800" value="${o.kcal ?? ''}"></label>
          <label>Protein (g)<input name="o_protein" type="number" min="0" value="${o.protein ?? ''}"></label>
          <label>Carbs (g)<input name="o_carbs" type="number" min="0" value="${o.carbs ?? ''}"></label>
          <label>Fat (g)<input name="o_fat" type="number" min="0" value="${o.fat ?? ''}"></label>
        </div>
      </details>
      <button class="btn btn-primary span-2" type="submit">${s.profile ? 'Save changes' : 'Calculate my targets'}</button>
    </form>
    ${s.profile ? `
    <section class="card">
      <h3>Your targets</h3>
      <div class="target-grid">
        <div><span class="muted small">BMR</span><strong class="num">${t.bmr.toLocaleString()}</strong></div>
        <div><span class="muted small">TDEE</span><strong class="num">${t.tdee.toLocaleString()}</strong></div>
        <div><span class="muted small">Daily target</span><strong class="num">${t.kcal.toLocaleString()} kcal</strong></div>
      </div>
      ${t.floorApplied ? '<p class="note">Your target was raised to the minimum safe floor. Use a manual override only with professional guidance.</p>' : ''}
      ${t.notes.map(n => `<p class="note">${esc(n)}</p>`).join('')}
      ${(() => {
        const tt = dayTargets(p, true, extrasNow()), rt = dayTargets(p, false, extrasNow());
        if (!tt.cycling) return '';
        return `<div class="table-wrap"><table><thead><tr><th>Carb cycling</th><th>Calories</th><th>Carbs</th><th>Protein</th><th>Fat</th><th>Water</th></tr></thead><tbody>
          <tr><th scope="row">🏋️ Training day</th><td class="num">${tt.kcal.toLocaleString()}</td><td class="num">${tt.carbs} g <span class="muted">(${tt.gkg.carbs.toFixed(1)}/kg)</span></td><td class="num">${tt.protein} g</td><td class="num">${tt.fat} g</td><td class="num">${fmtWater(tt.waterMl)}</td></tr>
          <tr><th scope="row">🛌 Rest day</th><td class="num">${rt.kcal.toLocaleString()}</td><td class="num">${rt.carbs} g <span class="muted">(${rt.gkg.carbs.toFixed(1)}/kg)</span></td><td class="num">${rt.protein} g</td><td class="num">${rt.fat} g</td><td class="num">${fmtWater(rt.waterMl)}</td></tr>
        </tbody></table></div>`;
      })()}
    </section>
    ${viewReminders()}
    ${viewTrainingCard(t)}
    <section class="card">
      <h3>Your data</h3>
      <div class="row-actions">
        <button class="btn btn-ghost" data-action="export">Export backup</button>
        <label class="btn btn-ghost file-btn">Import backup<input type="file" accept="application/json" id="import-file" hidden></label>
        <button class="btn btn-danger" data-action="reset">Erase all data</button>
      </div>
    </section>` : ''}`;
}

function emphasisClass(e) { return e.startsWith('Carb') ? 'emph-carbs' : e.startsWith('Protein') ? 'emph-protein' : 'emph-balanced'; }

function viewTrainingCard(t) {
  const tr = t.training;
  const row = (key, label) => {
    const g = t[key], gkg = t.gkg[key], [lo, hi] = tr[key];
    const pctKcal = Math.round((g * (key === 'fat' ? 9 : 4) / t.kcal) * 100);
    const inRange = gkg >= lo - 0.05 && gkg <= hi + 0.05;
    return `<tr>
      <th scope="row"><span class="dot dot-${key}"></span> ${label}</th>
      <td class="num"><strong>${g} g</strong></td>
      <td class="num">${gkg.toFixed(1)}</td>
      <td class="num muted">${lo}–${hi}</td>
      <td class="num muted">${pctKcal}%</td>
      <td>${inRange ? '<span class="chip s-met">in range</span>' : `<span class="chip s-low">${gkg < lo ? 'below' : 'above'}</span>`}</td>
    </tr>`;
  };
  const order = tr.emphasis.startsWith('Carb') ? [['carbs', 'Carbs'], ['protein', 'Protein'], ['fat', 'Fat']]
    : [['protein', 'Protein'], ['carbs', 'Carbs'], ['fat', 'Fat']];
  const compare = Object.values(TRAINING).map(x => `<tr class="${x.name === tr.name ? 'is-current' : ''}">
    <th scope="row">${x.name}<div class="muted small">${x.examples}</div></th>
    <td class="num">${x.carbs.join('–')}</td><td class="num">${x.protein.join('–')}</td><td class="num">${x.fat.join('–')}</td>
    <td><span class="chip ${emphasisClass(x.emphasis)}">${x.emphasis}</span></td></tr>`).join('');
  return `
    <section class="card">
      <header class="meal-head"><h3>Macro recommendations</h3><span class="chip ${emphasisClass(tr.emphasis)}">${tr.name} · ${tr.emphasis}</span></header>
      <div class="table-wrap"><table class="macro-table">
        <thead><tr><th></th><th>Target</th><th>g/kg</th><th>Recommended g/kg</th><th>% kcal</th><th></th></tr></thead>
        <tbody>${order.map(([k, l]) => row(k, l)).join('')}</tbody>
      </table></div>
      <h4 class="tips-title">Fueling tips for ${tr.name.toLowerCase()}</h4>
      <ul class="tips">${tr.tips.map(x => `<li>${x}</li>`).join('')}</ul>
      <details><summary>Compare all training types (g/kg/day)</summary>
        <div class="table-wrap"><table class="compare-table">
          <thead><tr><th>Training type</th><th>Carbs</th><th>Protein</th><th>Fat</th><th>Emphasis</th></tr></thead>
          <tbody>${compare}</tbody>
        </table></div>
      </details>
      <p class="muted small">Ranges are based on the ACSM/AND/DC joint position on athletic nutrition (2016), ISSN position stands on protein (2017) and nutrient timing (2017), and Helms et al. (2014). Hybrid ranges combine the endurance carb guidance with resistance-training protein guidance. BMR uses Mifflin-St Jeor. Micronutrient targets are the NIH Dietary Reference Intakes. This is not medical advice.</p>
    </section>`;
}

function syncTrainingDesc() {
  const form = $('#profile-form'), el = $('#training-desc');
  if (!form || !el) return;
  const tr = TRAINING[form.trainingType.value];
  el.innerHTML = `${esc(tr.examples)}. <span class="chip ${emphasisClass(tr.emphasis)}">${tr.emphasis}</span> Carbs ${tr.carbs.join('–')} · Protein ${tr.protein.join('–')} · Fat ${tr.fat.join('–')} g/kg`;
}

function syncProfileUnits() {
  syncTrainingDesc();
  const form = $('#profile-form');
  if (!form) return;
  const imp = form.units.value === 'imperial';
  form.querySelectorAll('.u-imperial').forEach(el => (el.hidden = !imp));
  form.querySelectorAll('.u-metric').forEach(el => (el.hidden = imp));
}

// ---------- Add food modal ----------
function openAdd(meal) {
  ui.modal = { meal, foodId: null, quick: false };
  const label = MEALS.find(m => m[0] === meal)[1];
  $('#modal').innerHTML = `
    <div class="backdrop" data-action="close-modal">
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <header class="modal-head"><h2 id="modal-title">Add to ${label}</h2>
          <button class="icon-btn" data-action="close-modal" aria-label="Close">✕</button></header>
        <div id="modal-body"></div>
      </div>
    </div>`;
  renderPicker();
  document.body.classList.add('modal-open');
}

function closeModal() {
  ui.modal = null;
  $('#modal').innerHTML = '';
  document.body.classList.remove('modal-open');
}

function renderPicker() {
  $('#modal-body').innerHTML = `
    <input id="food-search" type="search" placeholder="Search ${allFoods().length} foods…" autocomplete="off">
    <div class="picker-links"><button class="link" data-action="quick-add">Quick add calories</button></div>
    <div id="food-results" class="results"></div>`;
  renderResults('');
  $('#food-search').focus();
}

function renderResults(q) {
  const s = store.get();
  const tokens = q.toLowerCase().split(/\s+/).filter(Boolean);
  const item = f => {
    const sv = f.servings[0];
    return `<li><button class="result" data-action="pick-food" data-id="${f.id}">
      <span>${esc(f.name)}${f.source === 'custom' ? ' <span class="tag">custom</span>' : ''}</span>
      <span class="muted small">${esc(sv.label)} · ${fmt(f.per100.kcal * sv.g / 100)} kcal</span></button></li>`;
  };
  let html = '';
  if (!tokens.length) {
    const recents = s.recents.map(findFood).filter(Boolean);
    if (recents.length) html += `<h4>Recent</h4><ul>${recents.map(item).join('')}</ul>`;
    html += `<h4>All foods</h4><ul>${[...allFoods()].sort((a, b) => a.name.localeCompare(b.name)).map(item).join('')}</ul>`;
  } else {
    const hits = allFoods().filter(f => tokens.every(t => f.name.toLowerCase().includes(t) || f.category.toLowerCase().includes(t)));
    html = hits.length ? `<ul>${hits.map(item).join('')}</ul>` : `<p class="muted">No match for “${esc(q)}”. <button class="link" data-action="goto-foods">Create a custom food</button></p>`;
  }
  $('#food-results').innerHTML = html;
}

function renderDetail() {
  const f = findFood(ui.modal.foodId);
  const opts = [...f.servings.map((sv, i) => `<option value="${i}">${esc(sv.label)}</option>`), '<option value="g">grams</option>'].join('');
  $('#modal-body').innerHTML = `
    <button class="link" data-action="back-picker">‹ Back to search</button>
    <h3 class="detail-name">${esc(f.name)}</h3>
    <div class="amount-row">
      <label>Amount<input id="qty" type="number" min="0" step="any" value="1" inputmode="decimal"></label>
      <label>Unit<select id="unit">${opts}</select></label>
    </div>
    <div id="preview"></div>
    <button class="btn btn-primary full" data-action="confirm-add">Add</button>`;
  updatePreview();
  $('#qty').select();
}

function currentAmount() {
  const f = findFood(ui.modal.foodId);
  const qty = parseFloat($('#qty').value) || 0;
  const unit = $('#unit').value;
  if (unit === 'g') return { grams: qty, label: `${fmt(qty)} g` };
  const sv = f.servings[+unit];
  return { grams: qty * sv.g, label: `${qty === 1 ? '' : fmt(qty) + ' × '}${sv.label}` };
}

function updatePreview() {
  const f = findFood(ui.modal.foodId);
  const { grams } = currentAmount();
  const n = scaleNutrients(f.per100, grams);
  const t = computeTargets(store.get().profile);
  const top = MICROS.filter(m => !m.limit)
    .map(m => ({ m, pct: n[m.key] / t.micros[m.key].target }))
    .filter(x => x.pct >= 0.1).sort((a, b) => b.pct - a.pct).slice(0, 4);
  $('#preview').innerHTML = `
    <div class="preview-grid">
      <div><strong class="num">${fmt(n.kcal)}</strong><span class="muted small">kcal</span></div>
      <div><strong class="num">${fmt(n.protein)}</strong><span class="muted small">protein</span></div>
      <div><strong class="num">${fmt(n.carbs)}</strong><span class="muted small">carbs</span></div>
      <div><strong class="num">${fmt(n.fat)}</strong><span class="muted small">fat</span></div>
    </div>
    ${top.length ? `<p class="small">Good source of: ${top.map(x => `<span class="chip s-met">${x.m.label} ${Math.round(x.pct * 100)}%</span>`).join(' ')}</p>` : ''}`;
}

function renderQuickAdd() {
  $('#modal-body').innerHTML = `
    <button class="link" data-action="back-picker">‹ Back to search</button>
    <form id="quick-form" class="form-grid">
      <label class="span-2">Description<input name="name" value="Quick add" maxlength="80"></label>
      <label>Calories<input name="kcal" type="number" min="0" step="any" required></label>
      <label>Protein (g)<input name="protein" type="number" min="0" step="any" value="0"></label>
      <label>Carbs (g)<input name="carbs" type="number" min="0" step="any" value="0"></label>
      <label>Fat (g)<input name="fat" type="number" min="0" step="any" value="0"></label>
      <p class="muted small span-2">Good for restaurant meals. Quick adds don't include micronutrients.</p>
      <button class="btn btn-primary span-2" type="submit">Add</button>
    </form>`;
  $('#quick-form').kcal.focus();
}

// ---------- Events ----------
document.addEventListener('click', e => {
  const el = e.target.closest('[data-action], [data-nav]');
  if (!el) return;
  if (el.dataset.nav) { ui.view = el.dataset.nav; ui.suppEdit = null; render(); window.scrollTo(0, 0); return; }
  const a = el.dataset.action;
  if (a === 'close-modal') { if (el.classList.contains('backdrop') && e.target !== el) return; closeModal(); }
  else if (a === 'date') { ui.date = shiftDate(ui.date, +el.dataset.delta); render(); }
  else if (a === 'open-add') openAdd(el.dataset.meal);
  else if (a === 'daytype') { store.setDayType(ui.date, el.dataset.type); render(); }
  else if (a === 'water') { store.addWater(ui.date, +el.dataset.ml); render(); }
  else if (a === 'undo-water') { store.undoWater(ui.date); render(); }
  else if (a === 'dose') {
    const sp = store.get().supplements.find(x => x.id === el.dataset.id);
    if (sp) { store.toggleDose(ui.date, sp, el.dataset.time); render(); }
  }
  else if (a === 'new-supp') { ui.suppEdit = 'new'; ui.suppDraft = null; render(); window.scrollTo(0, 0); }
  else if (a === 'template') {
    const tp = SUPP_TEMPLATES.find(x => x.tid === el.dataset.tid);
    ui.suppEdit = 'new'; ui.suppDraft = structuredClone(tp); render(); window.scrollTo(0, 0);
  }
  else if (a === 'edit-supp') { ui.suppEdit = el.dataset.id; render(); window.scrollTo(0, 0); }
  else if (a === 'cancel-supp') { ui.suppEdit = null; render(); }
  else if (a === 'pause-supp') {
    const sp = store.get().supplements.find(x => x.id === el.dataset.id);
    store.saveSupplement({ ...sp, active: sp.active === false }); render();
  }
  else if (a === 'delete-supp') {
    if (confirm('Remove this supplement from your stack? Doses already logged are kept.')) {
      store.update(s => { s.supplements = s.supplements.filter(x => x.id !== el.dataset.id); }); render();
    }
  }
  else if (a === 'remove-entry') { store.removeEntry(ui.date, el.dataset.id); render(); }
  else if (a === 'copy-meal') {
    const meal = el.dataset.meal;
    store.day(shiftDate(ui.date, -1)).filter(x => x.meal === meal)
      .forEach(({ id, ...rest }) => store.addEntry(ui.date, rest));
    render();
  }
  else if (a === 'pick-food') { ui.modal.foodId = el.dataset.id; renderDetail(); }
  else if (a === 'back-picker') renderPicker();
  else if (a === 'quick-add') renderQuickAdd();
  else if (a === 'goto-foods') { closeModal(); ui.view = 'foods'; render(); }
  else if (a === 'confirm-add') {
    const f = findFood(ui.modal.foodId);
    const { grams, label } = currentAmount();
    if (grams <= 0) return;
    store.addEntry(ui.date, { foodId: f.id, name: f.name, meal: ui.modal.meal, grams, amountLabel: label, n: scaleNutrients(f.per100, grams) });
    closeModal(); render();
  }
  else if (a === 'delete-food') {
    if (confirm('Delete this custom food? Past log entries keep their values.')) {
      store.update(s => { s.customFoods = s.customFoods.filter(f => f.id !== el.dataset.id); });
      render();
    }
  }
  else if (a === 'pick-seed') {
    const k = el.dataset.seed;
    store.update(st => { st.garden = { ...(st.garden ?? {}), seed: k }; store.ensureDay(st, dateKey(new Date())).species = k; });
    render(); toast(`🌱 Planting ${SPECIES[k].name.toLowerCase()} today`);
  }
  else if (a === 'goto-day') { ui.date = el.dataset.date; ui.view = 'today'; render(); window.scrollTo(0, 0); }
  else if (a === 'goto-reminders') { ui.view = 'profile'; render(); document.getElementById('reminders')?.scrollIntoView({ behavior: 'smooth' }); }
  else if (a === 'test-notif') {
    (async () => {
      if (notifSupport() === 'default') await requestNotifications();
      const shown = await showNotification({ title: '🌱 NutriTrack', body: 'Reminders are working. You\'ll get check-ins like this through the day.', key: 'test' });
      if (!shown) banner('🌱 Test reminder: system notifications aren\'t available here, so reminders will appear like this inside the app.');
      render(); document.getElementById('reminders')?.scrollIntoView();
    })();
  }
  else if (a === 'dismiss-banner') el.closest('.banner-item')?.remove();
  else if (a === 'export') {
    const blob = new Blob([store.exportJSON()], { type: 'application/json' });
    const link = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: `nutritrack-${dateKey(new Date())}.json` });
    link.click(); URL.revokeObjectURL(link.href);
  }
  else if (a === 'reset') {
    if (confirm('Erase all NutriTrack data on this device? This cannot be undone.')) { store.reset(); ui.view = 'profile'; render(); }
  }
});

document.addEventListener('input', e => {
  if (e.target.id === 'food-search') renderResults(e.target.value);
  if (e.target.id === 'qty' || e.target.id === 'unit') updatePreview();
  if (e.target.name === 'units') syncProfileUnits();
  if (e.target.name === 'trainingType') syncTrainingDesc();
});
document.addEventListener('change', e => {
  if (e.target.id === 'unit') updatePreview();
  if (e.target.id === 'import-file' && e.target.files[0]) {
    e.target.files[0].text().then(txt => {
      try { store.importJSON(txt); ui.view = 'today'; render(); }
      catch (err) { alert('Import failed: ' + err.message); }
    });
  }
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && ui.modal) closeModal();
  if (e.key === 'Enter' && e.target.id === 'qty') { e.preventDefault(); $('[data-action="confirm-add"]').click(); }
});

document.addEventListener('submit', e => {
  e.preventDefault();
  const form = e.target;
  const num = name => { const v = parseFloat(form[name]?.value); return isNaN(v) ? 0 : v; };
  const opt = name => { const v = parseFloat(form[name]?.value); return isNaN(v) || v <= 0 ? undefined : v; };

  if (form.id === 'reminders-form') {
    const enabled = form.enabled.checked;
    store.update(s => {
      s.schedule = { wake: form.wake.value, sleep: form.sleep.value, breakfast: form.breakfast.value, lunch: form.lunch.value, dinner: form.dinner.value };
      s.reminders = {
        enabled, supplements: form.supplements.checked, water: form.water.checked, waterEveryH: +form.waterEveryH.value,
        checkins: [0, 1, 2].map(i => form['check' + i].value).filter(Boolean).sort(),
      };
    });
    (async () => {
      if (enabled && notifSupport() === 'default') await requestNotifications();
      render(); document.getElementById('reminders')?.scrollIntoView();
      toast(enabled ? 'Reminders on' : 'Reminders saved');
      tick();
    })();
    return;
  }

  if (form.id === 'profile-form') {
    const imp = form.units.value === 'imperial';
    const profile = {
      sex: form.sex.value,
      age: num('age'),
      weightKg: imp ? lbToKg(num('weightLb')) : num('weightKg'),
      heightCm: imp ? inToCm(num('heightFt') * 12 + num('heightIn')) : num('heightCm'),
      activity: form.activity.value,
      goal: form.goal.value,
      trainingType: form.trainingType.value,
      trainingLoad: form.trainingLoad.value,
      trainingDays: [...form.querySelectorAll('[name=trainingDays]:checked')].map(x => +x.value),
      carbCycling: form.carbCycling.checked,
      overrides: { kcal: opt('o_kcal'), protein: opt('o_protein'), carbs: opt('o_carbs'), fat: opt('o_fat') },
    };
    if (profile.age < 18 || profile.weightKg < 30 || profile.heightCm < 120) { alert('Please check your age, weight and height.'); return; }
    const first = !store.get().profile;
    store.update(s => { s.profile = profile; s.units = form.units.value; });
    ui.view = first ? 'today' : 'profile';
    render();
    if (!first) toast('Targets updated');
  }

  if (form.id === 'food-form') {
    const g = num('servingG');
    const per100 = emptyNutrients();
    for (const k of Object.keys(per100)) per100[k] = (num(k) * 100) / g;
    store.update(s => s.customFoods.unshift({
      id: 'c-' + uid(), name: form.name.value.trim(), category: 'Custom', source: 'custom',
      servings: [{ label: form.servingLabel.value.trim() || '1 serving', g }], per100,
    }));
    render(); toast('Food saved');
  }

  if (form.id === 'supp-form') {
    const times = [0, 1, 2].map(i => form[`time${i}`].value).filter(Boolean);
    if (!times.length) { alert('Add at least one time.'); return; }
    const nn = emptyNutrients();
    for (const m of MICROS) nn[m.key] = num(m.key);
    const existing = store.get().supplements.find(x => x.id === form.dataset.id);
    const keep = existing?.n ?? ui.suppDraft?.n;
    if (keep) { nn.kcal = keep.kcal || 0; nn.fat = keep.fat || 0; }
    store.saveSupplement({
      ...(existing ?? {}), id: existing?.id ?? 's-' + uid(), tid: existing?.tid ?? ui.suppDraft?.tid,
      name: form.name.value.trim(), doseLabel: form.doseLabel.value.trim() || '1 dose',
      times: [...new Set(times)].sort(), withFood: form.withFood.checked, creatineG: num('creatineG'), n: nn, active: existing?.active ?? true,
    });
    ui.suppEdit = null; ui.suppDraft = null; render(); toast('Stack updated');
  }

  if (form.id === 'quick-form') {
    const n = emptyNutrients();
    ['kcal', 'protein', 'carbs', 'fat'].forEach(k => (n[k] = num(k)));
    store.addEntry(ui.date, { foodId: null, name: form.name.value.trim() || 'Quick add', meal: ui.modal.meal, grams: 0, amountLabel: 'quick add', n });
    closeModal(); render();
  }
});

// ---- Reminder loop ----
// In-app reminders stack (newest on top) until dismissed or ~30 s pass.
function banner(text) {
  const el = $('#banner');
  const item = document.createElement('div');
  item.className = 'banner-item';
  item.innerHTML = `<span>${esc(text)}</span><button class="icon-btn" data-action="dismiss-banner" aria-label="Dismiss">✕</button>`;
  el.prepend(item);
  while (el.children.length > 4) el.lastChild.remove();
  setTimeout(() => item.remove(), 30000);
}

async function tick() {
  const s = store.get();
  const rs = reminderSettings();
  if (!s.profile || !rs.enabled) return;
  const today = dateKey(new Date());
  const t = targetsFor(today);
  const { day, totals, waterMl } = dayTotals(today);
  const sent = new Set(day.notified ?? []);
  const events = dueEvents({
    settings: rs, sched: schedule(), nowMin: nowMin(), supps: s.supplements, taken: day.supps ?? [],
    targets: t, totals, waterMl, foods: allFoods(), waterFmt: fmtWater,
  }).filter(e => !sent.has(e.key));
  for (const ev of events) {
    store.update(st => { const d = store.ensureDay(st, today); (d.notified ??= []).push(ev.key); });
    const shown = await showNotification(ev);
    if (!shown || document.visibilityState === 'visible') banner(`${ev.title}: ${ev.body}`);
  }
}

// Keep the Today view's pace current, without interrupting typing or an open dialog.
function refreshIfIdle() {
  const typing = document.activeElement && /INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName);
  if (ui.view === 'today' && !ui.modal && !typing) render();
}

setInterval(() => { tick(); refreshIfIdle(); }, 60_000);
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') { tick(); refreshIfIdle(); } });
registerSW();

function toast(msg) {
  const el = $('#toast');
  el.textContent = msg; el.classList.add('show');
  clearTimeout(toast.t); toast.t = setTimeout(() => el.classList.remove('show'), 2000);
}

finalizeGarden();
render();
tick();
