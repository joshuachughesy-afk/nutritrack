import { store, uid } from './store.js';
import { FOODS } from './foods.js';
import {
  MACROS, MICROS, ACTIVITY, GOALS, computeTargets, scaleNutrients, sumNutrients, emptyNutrients,
  microStatus, fmt, kgToLb, lbToKg, cmToIn, inToCm,
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

const ui = { view: 'today', date: dateKey(new Date()), modal: null };

const allFoods = () => [...store.get().customFoods, ...FOODS];
const findFood = id => allFoods().find(f => f.id === id);

// ---------- Rendering ----------
function render() {
  const s = store.get();
  if (!s.profile && ui.view !== 'profile') ui.view = 'profile';
  document.querySelectorAll('[data-nav]').forEach(b => b.setAttribute('aria-current', b.dataset.nav === ui.view ? 'page' : 'false'));
  const main = $('#main');
  main.innerHTML = ui.view === 'today' ? viewToday() : ui.view === 'foods' ? viewFoods() : viewProfile();
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
  const t = computeTargets(s.profile);
  const entries = store.day(ui.date);
  const tot = sumNutrients(entries.map(e => e.n));
  const remaining = t.kcal - tot.kcal;
  const yesterday = store.day(shiftDate(ui.date, -1));

  const macroRows = MACROS.map(m => {
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
    const { pct, status } = microStatus(def, target, tot[def.key]);
    const label = def.limit ? 'limit' : '';
    return `<li class="micro">
      <div class="micro-head"><span>${def.label}</span>
        <span class="muted num small">${fmt(tot[def.key])} / ${fmt(target.target)} ${def.unit} ${label}</span>
        <span class="pct s-${status}">${Math.round(pct * 100)}%</span></div>
      ${bar(pct, status)}
    </li>`;
  }).join('');

  return `
    <div class="date-nav">
      <button class="icon-btn" data-action="date" data-delta="-1" aria-label="Previous day">‹</button>
      <h2>${prettyDate(ui.date)}</h2>
      <button class="icon-btn" data-action="date" data-delta="1" aria-label="Next day">›</button>
    </div>
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
    </section>
    ${meals}
    <section class="card">
      <header class="meal-head"><h3>Micronutrients</h3><span class="muted small">vs. your DRI targets</span></header>
      <ul class="micros">${micros}</ul>
      <p class="muted small legend"><span class="chip s-low">under 50%</span><span class="chip s-mid">50–99%</span><span class="chip s-met">met</span><span class="chip s-over">above limit</span></p>
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
  const p = s.profile || { sex: 'male', age: 30, heightCm: 178, weightKg: 80, activity: 'moderate', goal: 'maintain', proteinPerKg: 1.8, fatPct: 30, overrides: {} };
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
        <label><input type="radio" name="units" value="imperial" ${imp ? 'checked' : ''}> lb / ft</label>
        <label><input type="radio" name="units" value="metric" ${!imp ? 'checked' : ''}> kg / cm</label>
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
      <label>Protein (g per kg body weight)<input name="proteinPerKg" type="number" step="0.1" min="0.8" max="3" value="${p.proteinPerKg}"></label>
      <label>Fat (% of calories)<input name="fatPct" type="number" min="15" max="50" value="${p.fatPct}"></label>
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
        <div><span class="muted small">Protein</span><strong class="num">${t.protein} g</strong></div>
        <div><span class="muted small">Carbs</span><strong class="num">${t.carbs} g</strong></div>
        <div><span class="muted small">Fat</span><strong class="num">${t.fat} g</strong></div>
      </div>
      ${t.floorApplied ? '<p class="note">Your target was raised to the minimum safe floor. Use a manual override only with professional guidance.</p>' : ''}
      <p class="muted small">BMR uses Mifflin-St Jeor. Micronutrient targets are the NIH Dietary Reference Intakes for your age and sex. This is not medical advice.</p>
    </section>
    <section class="card">
      <h3>Your data</h3>
      <div class="row-actions">
        <button class="btn btn-ghost" data-action="export">Export backup</button>
        <label class="btn btn-ghost file-btn">Import backup<input type="file" accept="application/json" id="import-file" hidden></label>
        <button class="btn btn-danger" data-action="reset">Erase all data</button>
      </div>
    </section>` : ''}`;
}

function syncProfileUnits() {
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
  if (el.dataset.nav) { ui.view = el.dataset.nav; render(); window.scrollTo(0, 0); return; }
  const a = el.dataset.action;
  if (a === 'close-modal') { if (el.classList.contains('backdrop') && e.target !== el) return; closeModal(); }
  else if (a === 'date') { ui.date = shiftDate(ui.date, +el.dataset.delta); render(); }
  else if (a === 'open-add') openAdd(el.dataset.meal);
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

  if (form.id === 'profile-form') {
    const imp = form.units.value === 'imperial';
    const profile = {
      sex: form.sex.value,
      age: num('age'),
      weightKg: imp ? lbToKg(num('weightLb')) : num('weightKg'),
      heightCm: imp ? inToCm(num('heightFt') * 12 + num('heightIn')) : num('heightCm'),
      activity: form.activity.value,
      goal: form.goal.value,
      proteinPerKg: num('proteinPerKg') || 1.8,
      fatPct: num('fatPct') || 30,
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

  if (form.id === 'quick-form') {
    const n = emptyNutrients();
    ['kcal', 'protein', 'carbs', 'fat'].forEach(k => (n[k] = num(k)));
    store.addEntry(ui.date, { foodId: null, name: form.name.value.trim() || 'Quick add', meal: ui.modal.meal, grams: 0, amountLabel: 'quick add', n });
    closeModal(); render();
  }
});

function toast(msg) {
  const el = $('#toast');
  el.textContent = msg; el.classList.add('show');
  clearTimeout(toast.t); toast.t = setTimeout(() => el.classList.remove('show'), 2000);
}

render();
