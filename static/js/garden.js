// Greenhand "My Garden" page (templates/garden/my_garden.html; PRD 3.3, FR-20 – FR-27). Loads after shell.js.
// Server data arrives via {{ garden_data|json_script:"garden-data" }} (apps/garden/services.garden_payload):
//   plants  -> UserPlant + TimelineEntry, CareLog, Problem/Diagnosis, Harvest, Reminder/ReminderOccurrence
//   catalog -> plants.Plant subset keyed by slug        weather -> rain-skip / frost info
// Edits made on the page stay in memory until the DRF endpoints (PRD 6.5) are wired up.

(function () {
  const { TODAY, $, $$, toast } = window.GH;

  // ---------- Helpers ----------
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const parse = (iso) => { const [y, m, d] = iso.split('-').map(Number); return new Date(y, m - 1, d); };
  const iso = (dt) => `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`;
  const addDays = (isoDate, n) => { const dt = parse(isoDate); dt.setDate(dt.getDate() + n); return iso(dt); };
  const diffDays = (a, b) => Math.round((parse(b) - parse(a)) / 86400000);
  const TODAY_ISO = iso(TODAY);
  const fmt = (isoDate, opts = { month: 'short', day: 'numeric' }) => parse(isoDate).toLocaleDateString('en-US', opts);
  function rel(isoDate) {
    const n = diffDays(TODAY_ISO, isoDate);
    if (n === 0) return 'today';
    if (n === 1) return 'tomorrow';
    if (n === -1) return 'yesterday';
    if (n > 1 && n < 7) return parse(isoDate).toLocaleDateString('en-US', { weekday: 'long' });
    if (n < 0 && n > -7) return `${-n} days ago`;
    return fmt(isoDate);
  }
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
  let uid = 100;
  const nextId = (p) => `${p}${++uid}`;

  // ---------- Reference data ----------
  const STAGES = [
    { key: 'seed', label: 'Seed', icon: 'i-seed', status: 'sprouting' },
    { key: 'seedling', label: 'Seedling', icon: 'i-sprout', status: 'sprouting' },
    { key: 'vegetative', label: 'Vegetative', icon: 'i-leaf', status: 'growing' },
    { key: 'flowering', label: 'Flowering', icon: 'i-flower', status: 'flowering' },
    { key: 'fruiting', label: 'Fruiting', icon: 'i-apple', status: 'fruiting' },
    { key: 'harvest', label: 'Harvest', icon: 'i-basket', status: null },
  ];
  const stageIndex = (k) => STAGES.findIndex((s) => s.key === k);

  const STATUS = {
    planned:   { label: 'Planned',   cls: 'bg-white text-muted ring-1 ring-line' },
    sprouting: { label: 'Sprouting', cls: 'bg-lime-100 text-lime-800' },
    growing:   { label: 'Growing',   cls: 'bg-emerald-100 text-emerald-800' },
    flowering: { label: 'Flowering', cls: 'bg-pink-100 text-pink-800' },
    fruiting:  { label: 'Fruiting',  cls: 'bg-orange-100 text-orange-800' },
    harvested: { label: 'Harvested', cls: 'bg-amber-100 text-amber-800' },
    failed:    { label: 'Failed',    cls: 'bg-rose-100 text-rose-700' },
    archived:  { label: 'Archived',  cls: 'bg-slate-100 text-slate-600' },
  };
  const ACTIVE = ['sprouting', 'growing', 'flowering', 'fruiting'];
  const STATUS_TO_STAGE = { planned: -1, sprouting: 1, growing: 2, flowering: 3, fruiting: 4, harvested: 5 };

  const ACTIONS = {
    water:      { label: 'Water',      past: 'Watered',          icon: 'i-drop',     tint: 'bg-sky-100 text-sky-700' },
    fertilize:  { label: 'Fertilize',  past: 'Fertilized',       icon: 'i-flask',    tint: 'bg-lime-100 text-lime-800' },
    prune:      { label: 'Prune',      past: 'Pruned',           icon: 'i-scissors', tint: 'bg-emerald-100 text-emerald-800' },
    treat_pest: { label: 'Treat pest', past: 'Treated pests',    icon: 'i-bug',      tint: 'bg-rose-100 text-rose-700' },
    repot:      { label: 'Repot',      past: 'Repotted',         icon: 'i-pot',      tint: 'bg-amber-100 text-amber-800' },
    transplant: { label: 'Transplant', past: 'Transplanted',     icon: 'i-shovel',   tint: 'bg-orange-100 text-orange-800' },
    other:      { label: 'Other',      past: 'Other care',       icon: 'i-plus',     tint: 'bg-mist text-muted' },
  };
  const SOURCE = { manual: 'Manual', reminder: 'From reminder', tutor_suggestion: 'Tutor suggestion' };

  const REMINDER_TYPES = {
    water:         { label: 'Watering',        icon: 'i-drop',   tint: 'bg-sky-100 text-sky-700' },
    fertilize:     { label: 'Feeding',         icon: 'i-flask',  tint: 'bg-lime-100 text-lime-800' },
    check_problem: { label: 'Problem check',   icon: 'i-alert',  tint: 'bg-amber-100 text-amber-700' },
    harvest_check: { label: 'Harvest check',   icon: 'i-basket', tint: 'bg-amber-100 text-amber-800' },
    custom:        { label: 'Custom',          icon: 'i-bell',   tint: 'bg-mist text-forest' },
  };
  const OCC = {
    done:         { label: 'Done',            cls: 'bg-emerald-100 text-emerald-800', icon: 'i-check' },
    skipped_rain: { label: 'Skipped · rain',  cls: 'bg-sky-100 text-sky-800',         icon: 'i-rain' },
    skipped_user: { label: 'Skipped',         cls: 'bg-mist text-muted',              icon: 'i-x' },
    missed:       { label: 'Missed',          cls: 'bg-rose-100 text-rose-700',       icon: 'i-x-circle' },
  };

  const CONF = { high: 'bg-emerald-100 text-emerald-800', medium: 'bg-amber-100 text-amber-800', low: 'bg-slate-100 text-slate-700' };
  const SEV = { low: 'bg-slate-100 text-slate-700', medium: 'bg-amber-100 text-amber-800', high: 'bg-rose-100 text-rose-700' };
  const PSTATUS = { open: 'bg-rose-100 text-rose-700', monitoring: 'bg-amber-100 text-amber-800', resolved: 'bg-emerald-100 text-emerald-800' };

  const SERVER = JSON.parse(document.getElementById('garden-data').textContent);
  const WEATHER = SERVER.weather;   // { rainToday, rainMm, frostDate, frostLow, frostThreshold }
  const CATALOG = SERVER.catalog;   // { slug: { name, sci, water, harvest:[min,max], frostOk, icon, grad, suit, suitLabel } }
  const PLANTS = SERVER.plants;     // UserPlant records (type = plant slug)
  const SUIT_CLS = { great: 'text-emerald-700', care: 'text-amber-700', no: 'text-rose-700' };

  // ---------- Derived values ----------
  const cat = (p) => CATALOG[p.type];
  // Days since planting (planting day = day 0), matching the dashboard
  const day = (p) => diffDays(p.planted_on, TODAY_ISO);
  const isActive = (p) => ACTIVE.includes(p.status);
  const openProblems = (p) => p.problems.filter((x) => x.status !== 'resolved');
  function currentStage(p) {
    const fromTimeline = Math.max(-1, ...p.timeline.map((t) => stageIndex(t.stage)));
    if (p.status === 'harvested') return 5;
    return Math.max(fromTimeline, STATUS_TO_STAGE[p.status] ?? -1);
  }
  function nextTask(p) {
    const r = p.reminders.filter((x) => x.active && x.next_due >= TODAY_ISO).sort((a, b) => a.next_due.localeCompare(b.next_due))[0];
    if (!r) return null;
    const verb = { water: 'Water', fertilize: 'Feed', check_problem: 'Check problem', harvest_check: 'Harvest check' }[r.type] || r.title;
    return `${verb} ${rel(r.next_due)}`;
  }
  function weatherBadges(p) {
    const out = [];
    if (p.setting !== 'outdoor') {
      if (isActive(p)) out.push({ icon: 'i-home', text: 'Indoor · weather-proof', cls: 'bg-mist text-muted' });
      return out;
    }
    if (!['planned', 'failed', 'archived'].includes(p.status)) {
      const skipped = p.reminders.some((r) => r.history.some((h) => h.date === TODAY_ISO && h.status === 'skipped_rain'));
      if (skipped) out.push({ icon: 'i-rain', text: 'Watering skipped — rain', cls: 'bg-sky-50 text-sky-800' });
      if (!cat(p).frostOk && WEATHER.frostDate) out.push({ icon: 'i-snow', text: `Frost risk ${fmt(WEATHER.frostDate, { weekday: 'short' })} (${WEATHER.frostLow} °C)`, cls: 'bg-indigo-50 text-indigo-800' });
    }
    return out;
  }
  // "300 g", "12 picked", "2 bunches"
  function qty(q, unit) {
    const n = +Number(q).toFixed(2);
    if (unit === 'count') return `${n} picked`;
    if (unit === 'bunch') return `${n} bunch${n === 1 ? '' : 'es'}`;
    return `${n} ${unit}`;
  }
  function harvestTotals(p) {
    const byUnit = {};
    p.harvests.forEach((h) => { if (h.quantity) byUnit[h.unit] = (byUnit[h.unit] || 0) + Number(h.quantity); });
    return Object.entries(byUnit).map(([u, q]) => qty(q, u)).join(' + ');
  }
  const statusPill = (status, extra = '') => `<span class="inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${STATUS[status].cls} ${extra}">${STATUS[status].label}</span>`;
  const avatar = (p, size = 'h-11 w-11', icon = 'h-5 w-5') =>
    `<span class="grid ${size} shrink-0 place-items-center rounded-xl bg-gradient-to-br ${cat(p).grad}"><svg class="ic ${icon}"><use href="#${cat(p).icon}"/></svg></span>`;

  // ---------- State ----------
  let selectedId = 'basil';
  let currentTab = 'timeline';
  let statusFilter = 'all';
  let settingFilter = 'all';
  let calScope = 'plant';
  let calMonth = new Date(TODAY.getFullYear(), TODAY.getMonth(), 1);
  let careFilter = 'all';
  const selected = () => PLANTS.find((p) => p.id === selectedId) || PLANTS[0];

  // ---------- Summary + list ----------
  const STATUS_TABS = [
    { key: 'all', label: 'All', test: (p) => p.status !== 'archived' },
    { key: 'active', label: 'Active', test: isActive },
    { key: 'planned', label: 'Planned', test: (p) => p.status === 'planned' },
    { key: 'harvested', label: 'Harvested', test: (p) => p.status === 'harvested' },
    { key: 'failed', label: 'Failed', test: (p) => p.status === 'failed' },
  ];

  function renderSummary() {
    $('#sumActive').textContent = PLANTS.filter(isActive).length;
    $('#sumPlanned').textContent = PLANTS.filter((p) => p.status === 'planned').length;
    $('#sumHarvested').textContent = PLANTS.filter((p) => p.status === 'harvested').length;
    $('#sumProblems').textContent = PLANTS.reduce((n, p) => n + openProblems(p).length, 0);
  }

  function renderStatusTabs() {
    $('#statusTabs').innerHTML = STATUS_TABS.map((t) => {
      const n = PLANTS.filter(t.test).length;
      return `<button type="button" class="status-chip flex items-center gap-1.5 rounded-full border border-line bg-white px-3 py-1" data-status="${t.key}" aria-pressed="${t.key === statusFilter}">${t.label}<span class="chip-count rounded-full bg-mist px-1.5 text-[11px] text-muted">${n}</span></button>`;
    }).join('');
  }

  function renderList() {
    const q = $('#plantSearch').value.trim().toLowerCase();
    const test = STATUS_TABS.find((t) => t.key === statusFilter).test;
    const items = PLANTS.filter((p) => test(p))
      .filter((p) => settingFilter === 'all' || (settingFilter === 'indoor' ? p.setting !== 'outdoor' : p.setting === 'outdoor'))
      .filter((p) => !q || `${p.nickname} ${cat(p).name} ${p.variety}`.toLowerCase().includes(q));

    $('#listCount').textContent = `(${items.length})`;
    $('#listEmpty').classList.toggle('hidden', items.length > 0);
    $('#plantList').innerHTML = items.map((p) => {
      const sub =
        p.status === 'planned' ? `Planned for ${fmt(p.planted_on)}`
        : p.status === 'failed' ? esc(p.failure_reason || 'Failed')
        : p.status === 'harvested' ? `${p.harvests.length} harvest${p.harvests.length === 1 ? '' : 's'} · ${harvestTotals(p)}`
        : `${cat(p).name} · Day ${day(p)}`;
      const task = isActive(p) || p.status === 'planned' ? nextTask(p) : null;
      const badges = [
        ...weatherBadges(p).filter((b) => b.icon !== 'i-home').map((b) => `<span class="grid h-6 w-6 place-items-center rounded-md ${b.cls}" title="${esc(b.text)}"><svg class="ic h-3.5 w-3.5"><use href="#${b.icon}"/></svg></span>`),
        openProblems(p).length ? `<span class="grid h-6 w-6 place-items-center rounded-md bg-amber-100 text-amber-700" title="${openProblems(p).length} open problem"><svg class="ic h-3.5 w-3.5"><use href="#i-alert"/></svg></span>` : '',
      ].join('');
      return `<li>
        <button type="button" class="plant-item flex w-full items-center gap-3 px-4 py-3.5 text-left" data-id="${p.id}" aria-current="${p.id === selectedId}">
          ${avatar(p)}
          <span class="min-w-0 flex-1">
            <span class="flex items-center gap-2"><span class="truncate text-[14.5px] font-medium">${esc(p.nickname)}</span>${statusPill(p.status)}</span>
            <span class="mt-0.5 block truncate text-[12.5px] text-muted">${sub}</span>
            ${task ? `<span class="mt-1 flex items-center gap-1 text-[12px] text-forest"><svg class="ic h-3 w-3"><use href="#i-clock"/></svg><span class="truncate">${esc(cap(task))}</span></span>` : ''}
          </span>
          <span class="flex shrink-0 gap-1">${badges}</span>
        </button></li>`;
    }).join('');
  }

  // ---------- Detail ----------
  const TABS = [
    { key: 'timeline', label: 'Timeline', icon: 'i-camera', count: (p) => p.timeline.length },
    { key: 'care', label: 'Care log', icon: 'i-drop', count: (p) => p.care.length },
    { key: 'problems', label: 'Problems', icon: 'i-alert', count: (p) => openProblems(p).length, alert: true },
    { key: 'harvests', label: 'Harvests', icon: 'i-basket', count: (p) => p.harvests.length },
    { key: 'calendar', label: 'Calendar', icon: 'i-calendar' },
    { key: 'reminders', label: 'Reminders', icon: 'i-bell', count: (p) => p.reminders.filter((r) => r.active).length },
  ];

  function renderDetail() {
    const p = selected();
    const c = cat(p);
    const stage = currentStage(p);
    const d = day(p);
    const planned = p.status === 'planned';
    const ended = ['harvested', 'failed', 'archived'].includes(p.status);
    const [hMin, hMax] = c.harvest;
    const progress = planned ? 0 : Math.min(100, Math.round((d / hMax) * 100));
    const progressText = planned
      ? `Starts ${rel(p.planted_on)} · harvest in about ${hMin}–${hMax} days after sowing`
      : p.status === 'harvested' ? `Harvested · ${harvestTotals(p) || 'quantity not logged'}`
      : p.status === 'failed' ? `Ended on day ${p.timeline.length ? diffDays(p.planted_on, p.timeline.at(-1).date) : d}`
      : d >= hMin ? `Day ${d} · in the harvest window (day ${hMin}–${hMax})`
      : `Day ${d} · about ${hMin - d}–${hMax - d} days to harvest`;
    const badges = weatherBadges(p);
    const statusMenu = Object.keys(STATUS)
      .map((s) => `<button type="button" role="menuitemradio" aria-checked="${s === p.status}" data-set-status="${s}" class="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-[13.5px] hover:bg-mist">${statusPill(s)}${s === p.status ? '<svg class="ic ml-auto h-4 w-4 text-forest"><use href="#i-check"/></svg>' : ''}</button>`)
      .join('');

    $('#plantDetail').innerHTML = `
      <div class="overflow-hidden rounded-2xl bg-white shadow-card">
        <!-- Header -->
        <div class="canvas-gradient p-5">
          <div class="flex flex-col gap-4 sm:flex-row sm:items-start">
            ${avatar(p, 'h-16 w-16', 'h-8 w-8')}
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <h2 class="font-display text-[24px] font-semibold leading-tight tracking-tight">${esc(p.nickname)}</h2>
                <div class="relative" data-popover>
                  <button type="button" data-popover-trigger aria-expanded="false" aria-haspopup="menu" class="inline-flex items-center gap-1 rounded-full bg-white/80 py-0.5 pl-0.5 pr-2 text-[11px] text-muted shadow-card hover:bg-white" aria-label="Change status, currently ${STATUS[p.status].label}">
                    ${statusPill(p.status)}<svg class="ic h-3 w-3"><use href="#i-chev-down"/></svg>
                  </button>
                  <div class="popover absolute left-0 top-full z-20 mt-2 hidden w-48 rounded-xl bg-white p-1.5 shadow-float" role="menu" aria-label="Plant status">${statusMenu}</div>
                </div>
              </div>
              <p class="mt-0.5 text-[13px] text-forest/75">${esc(c.name)}${p.variety ? ` · ‘${esc(p.variety)}’` : ''} · <em>${esc(c.sci)}</em></p>
              <div class="mt-3 flex flex-wrap gap-1.5 text-[12px]">
                <span class="inline-flex items-center gap-1 rounded-md bg-white/75 px-2 py-1"><svg class="ic h-3.5 w-3.5 text-forest"><use href="#i-calendar"/></svg>${planned ? 'Planned' : 'Planted'} ${fmt(p.planted_on, { month: 'short', day: 'numeric', year: 'numeric' })}</span>
                <span class="inline-flex items-center gap-1 rounded-md bg-white/75 px-2 py-1"><svg class="ic h-3.5 w-3.5 text-forest"><use href="#${p.start_method === 'seed' ? 'i-seed' : p.start_method === 'cutting' ? 'i-scissors' : 'i-sprout'}"/></svg>From ${p.start_method}</span>
                <span class="inline-flex items-center gap-1 rounded-md bg-white/75 px-2 py-1"><svg class="ic h-3.5 w-3.5 text-forest"><use href="#${p.setting === 'outdoor' ? 'i-sun' : 'i-home'}"/></svg>${cap(p.setting)}${p.container ? ` · ${esc(p.container)}` : ''}</span>
                <span class="inline-flex items-center gap-1 rounded-md bg-white/75 px-2 py-1">Qty ${p.quantity}</span>
                <span class="inline-flex items-center gap-1 rounded-md bg-white/75 px-2 py-1"><svg class="ic h-3.5 w-3.5 text-sky-600"><use href="#i-drop"/></svg>Every ${p.watering_interval_days} days</span>
              </div>
            </div>
            <div class="flex shrink-0 gap-2 sm:flex-col">
              <button type="button" data-ask class="inline-flex h-9 items-center gap-1.5 rounded-lg bg-[#0d1f14] px-3 text-[13px] font-medium text-lime-300 hover:bg-forest-900"><svg class="ic h-4 w-4"><use href="#i-sparkles"/></svg>Ask tutor</button>
              <button type="button" data-share class="inline-flex h-9 items-center gap-1.5 rounded-lg bg-white px-3 text-[13px] font-medium shadow-card hover:bg-mist"><svg class="ic h-4 w-4"><use href="#i-share"/></svg>Share</button>
            </div>
          </div>
          ${badges.length ? `<div class="mt-4 flex flex-wrap gap-1.5 text-[12px]">${badges.map((b) => `<span class="inline-flex items-center gap-1 rounded-md px-2 py-1 ${b.cls}"><svg class="ic h-3.5 w-3.5"><use href="#${b.icon}"/></svg>${b.text}</span>`).join('')}</div>` : ''}
          ${p.status === 'failed' ? `<div class="mt-4 rounded-xl bg-white/80 p-3 text-[13px]"><span class="font-medium text-rose-700">What happened:</span> ${esc(p.failure_reason)}</div>` : ''}
        </div>

        <!-- Lifecycle -->
        <div class="border-b border-line px-5 py-5">
          <ol class="stepper flex" aria-label="Growth stages">
            ${STAGES.map((s, i) => `<li class="step ${i < stage ? 'is-done' : i === stage ? 'is-current' : ''}" ${i === stage ? 'aria-current="step"' : ''}>
              <span class="step-dot"><svg class="ic h-4 w-4"><use href="#${i < stage ? 'i-check' : s.icon}"/></svg></span>
              <span class="step-label block">${s.label}</span></li>`).join('')}
          </ol>
          <div class="mt-4 flex items-center justify-between gap-3 text-[12.5px]"><span class="text-muted">${progressText}</span></div>
          <div class="progress mt-1.5"><span style="width:${p.status === 'harvested' ? 100 : progress}%"></span></div>
        </div>

        <!-- Quick actions -->
        <div class="grid grid-cols-2 gap-2 border-b border-line p-4 sm:grid-cols-4">
          ${[
            ['careDialog', 'i-drop', 'Log care', 'bg-sky-50 text-sky-700'],
            ['timelineDialog', 'i-camera', 'Add photo / note', 'bg-lime-50 text-lime-800'],
            ['problemDialog', 'i-alert', 'Log problem', 'bg-amber-50 text-amber-700'],
            ['harvestDialog', 'i-basket', 'Log harvest', 'bg-orange-50 text-orange-700'],
          ].map(([dlg, icon, label, tint]) => `<button type="button" data-open="${dlg}" ${planned && dlg !== 'timelineDialog' ? 'disabled title="Available once planted"' : ''} class="flex items-center gap-2.5 rounded-xl border border-line p-2.5 text-left text-[13.5px] font-medium transition hover:border-leaf hover:bg-leaf-soft/30 disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:border-line disabled:hover:bg-transparent">
              <span class="grid h-8 w-8 shrink-0 place-items-center rounded-lg ${tint}"><svg class="ic h-4 w-4"><use href="#${icon}"/></svg></span>${label}</button>`).join('')}
        </div>

        <!-- Tabs -->
        <div class="scroll-thin flex gap-1 overflow-x-auto border-b border-line px-3 text-[13.5px]" role="tablist" aria-label="Plant records">
          ${TABS.map((t) => {
            const n = t.count ? t.count(p) : null;
            return `<button type="button" role="tab" id="dtab-${t.key}" aria-controls="dpanel" aria-selected="${t.key === currentTab}" tabindex="${t.key === currentTab ? 0 : -1}" data-tab="${t.key}" class="dtab flex items-center gap-1.5 px-2.5 py-3">
              ${t.label}${n ? `<span class="rounded-full px-1.5 text-[11px] ${t.alert ? 'bg-rose-100 text-rose-700' : 'bg-mist text-muted'}">${n}</span>` : ''}</button>`;
          }).join('')}
        </div>
        <div id="dpanel" role="tabpanel" aria-labelledby="dtab-${currentTab}" class="tab-body p-5" tabindex="0">${renderTab(p)}</div>
      </div>`;
  }

  function renderTab(p) {
    switch (currentTab) {
      case 'timeline': return tabTimeline(p);
      case 'care': return tabCare(p);
      case 'problems': return tabProblems(p);
      case 'harvests': return tabHarvests(p);
      case 'calendar': return tabCalendar(p);
      case 'reminders': return tabReminders(p);
      default: return '';
    }
  }

  const emptyState = (icon, title, text, action) => `
    <div class="flex flex-col items-center rounded-xl border border-dashed border-[#cfd8cf] px-6 py-10 text-center">
      <span class="grid h-11 w-11 place-items-center rounded-full bg-mist text-forest"><svg class="ic h-5 w-5"><use href="#${icon}"/></svg></span>
      <p class="mt-3 text-[14.5px] font-medium">${title}</p>
      <p class="mt-1 max-w-sm text-[13px] text-muted">${text}</p>
      ${action || ''}
    </div>`;
  const tabHeader = (title, sub, btn) => `
    <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
      <div><h3 class="text-[15px] font-medium">${title}</h3>${sub ? `<p class="text-[12.5px] text-muted">${sub}</p>` : ''}</div>${btn || ''}
    </div>`;
  const addBtn = (dlg, label, disabled) => `<button type="button" data-open="${dlg}" ${disabled ? 'disabled' : ''} class="inline-flex h-9 items-center gap-1.5 rounded-lg bg-ink px-3 text-[13px] font-medium text-white hover:bg-forest-900 disabled:opacity-40"><svg class="ic h-4 w-4"><use href="#i-plus"/></svg>${label}</button>`;
  const photoTile = (photo, size = 'h-24 w-32') =>
    typeof photo === 'string'
      ? `<img src="${photo}" alt="Plant photo" class="${size} shrink-0 rounded-lg object-cover" />`
      : photo ? `<span class="photo-ph grid ${size} shrink-0 place-items-center rounded-lg text-forest/60" role="img" aria-label="Plant photo"><svg class="ic h-6 w-6"><use href="#i-image"/></svg></span>` : '';

  // Timeline (FR-21)
  function tabTimeline(p) {
    const entries = [...p.timeline].sort((a, b) => b.date.localeCompare(a.date));
    if (!entries.length) return tabHeader('Lifecycle timeline', '', '') + emptyState('i-camera', 'No entries yet', p.status === 'planned' ? `Once you sow your ${esc(cat(p).name.toLowerCase())}, add a photo and note here to start its story.` : 'Add a photo and a short note at each growth stage.', `<button type="button" data-open="timelineDialog" class="mt-4 inline-flex h-9 items-center gap-1.5 rounded-lg bg-ink px-3 text-[13px] font-medium text-white">Add first entry</button>`);
    return tabHeader('Lifecycle timeline', `${entries.length} entries · photo + note by growth stage`, addBtn('timelineDialog', 'Add entry')) + `
      <ol class="tl space-y-5">${entries.map((t) => {
        const s = STAGES[stageIndex(t.stage)];
        return `<li class="relative flex gap-4">
          <span class="relative z-10 grid h-9 w-9 shrink-0 place-items-center rounded-full bg-white text-forest ring-2 ring-leaf/40"><svg class="ic h-4 w-4"><use href="#${s.icon}"/></svg></span>
          <div class="min-w-0 flex-1 rounded-xl border border-line p-3.5">
            <div class="flex flex-wrap items-center gap-2 text-[12.5px]"><span class="rounded-full bg-leaf-soft px-2 py-0.5 font-medium text-forest">${s.label}</span><span class="text-muted">${fmt(t.date, { month: 'short', day: 'numeric', year: 'numeric' })} · ${t.date === p.planted_on ? 'Planting day' : `Day ${diffDays(p.planted_on, t.date)}`}</span></div>
            <div class="mt-2 flex flex-col gap-3 sm:flex-row">${photoTile(t.photo)}<p class="text-[14px] leading-relaxed">${esc(t.note) || '<span class="text-muted">No note</span>'}</p></div>
          </div></li>`;
      }).join('')}</ol>`;
  }

  // Care log (FR-22)
  function tabCare(p) {
    const logs = [...p.care].sort((a, b) => b.date.localeCompare(a.date)).filter((l) => careFilter === 'all' || l.action === careFilter);
    const used = [...new Set(p.care.map((l) => l.action))];
    const chips = used.length > 1 ? `<div class="mb-4 flex flex-wrap gap-1.5 text-[12.5px]">${['all', ...used].map((a) => `<button type="button" data-care-filter="${a}" class="status-chip rounded-full border border-line bg-white px-3 py-1" aria-pressed="${a === careFilter}">${a === 'all' ? 'All' : ACTIONS[a].label}</button>`).join('')}</div>` : '';
    if (!p.care.length) return tabHeader('Care log', '', '') + emptyState('i-drop', 'Nothing logged yet', 'Log watering, feeding, pruning, pest treatments, and more. It helps your tutor give better advice.', p.status === 'planned' ? '' : `<button type="button" data-open="careDialog" class="mt-4 inline-flex h-9 items-center gap-1.5 rounded-lg bg-ink px-3 text-[13px] font-medium text-white">Log care</button>`);
    return tabHeader('Care log', `${p.care.length} actions logged`, addBtn('careDialog', 'Log care', p.status === 'planned')) + chips + `
      <ul class="divide-y divide-line rounded-xl border border-line">${logs.map((l) => {
        const a = ACTIONS[l.action];
        return `<li class="flex items-start gap-3 p-3.5">
          <span class="grid h-9 w-9 shrink-0 place-items-center rounded-lg ${a.tint}"><svg class="ic h-4 w-4"><use href="#${a.icon}"/></svg></span>
          <div class="min-w-0 flex-1">
            <div class="text-[14px] font-medium">${a.past}${l.amount ? ` <span class="font-normal text-muted">· ${esc(l.amount)}</span>` : ''}</div>
            ${l.note ? `<div class="text-[13px] text-muted">${esc(l.note)}</div>` : ''}
          </div>
          <div class="shrink-0 text-right text-[12px]"><div>${cap(rel(l.date))}</div><div class="text-muted">${SOURCE[l.source]}</div></div></li>`;
      }).join('')}</ul>`;
  }

  // Problems (FR-25, FR-26)
  function diagnosisBox(dx) {
    if (!dx) return '';
    return `<div class="mt-3 rounded-xl bg-[#0d1f14] p-4 text-emerald-50">
      <div class="flex items-center gap-1.5 text-[11.5px] font-semibold uppercase tracking-wide text-lime-300"><svg class="ic h-3.5 w-3.5"><use href="#i-sparkles"/></svg>AI suggestion</div>
      <ul class="mt-2 space-y-2">${dx.issues.map((i) => `<li class="text-[13.5px]"><span class="font-medium text-white">${esc(i.name)}</span> <span class="ml-1 rounded-full px-2 py-0.5 text-[10.5px] font-medium ${CONF[i.confidence]}">${cap(i.confidence)} confidence</span><div class="mt-0.5 text-emerald-50/70">${esc(i.reasoning)}</div></li>`).join('')}</ul>
      <div class="mt-3 grid gap-3 sm:grid-cols-2">
        <div class="rounded-lg bg-white/[0.06] p-3"><div class="text-[11px] font-semibold uppercase tracking-wide text-lime-300">Do now</div><ul class="mt-1.5 space-y-1 text-[12.5px] text-emerald-50/85">${dx.immediate_actions.map((a) => `<li class="flex gap-1.5"><svg class="ic mt-0.5 h-3.5 w-3.5 shrink-0 text-lime-300"><use href="#i-check"/></svg>${esc(a)}</li>`).join('')}</ul></div>
        <div class="rounded-lg bg-white/[0.06] p-3"><div class="text-[11px] font-semibold uppercase tracking-wide text-amber-300">Watch for</div><ul class="mt-1.5 space-y-1 text-[12.5px] text-emerald-50/85">${dx.watch_for.map((a) => `<li class="flex gap-1.5"><svg class="ic mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-300"><use href="#i-alert"/></svg>${esc(a)}</li>`).join('')}</ul></div>
      </div>
    </div>`;
  }

  function tabProblems(p) {
    const order = { open: 0, monitoring: 1, resolved: 2 };
    const list = [...p.problems].sort((a, b) => order[a.status] - order[b.status] || b.opened.localeCompare(a.opened));
    if (!list.length) return tabHeader('Problems', '', '') + emptyState('i-check-circle', 'No problems logged', 'Something look off? Describe it (a photo helps) and the tutor will suggest likely causes and fixes.', p.status === 'planned' ? '' : `<button type="button" data-open="problemDialog" class="mt-4 inline-flex h-9 items-center gap-1.5 rounded-lg bg-ink px-3 text-[13px] font-medium text-white">Log a problem</button>`);
    return tabHeader('Problems', `${openProblems(p).length} open · ${p.problems.filter((x) => x.status === 'resolved').length} resolved`, addBtn('problemDialog', 'Log problem', p.status === 'planned')) + `
      <div class="space-y-4">${list.map((x) => `
        <article class="rounded-xl border ${x.status === 'resolved' ? 'border-line' : 'border-amber-200'} p-4" data-problem="${x.id}">
          <div class="flex flex-wrap items-start justify-between gap-2">
            <div>
              <h4 class="text-[15px] font-medium">${esc(x.title)}</h4>
              <div class="mt-1 flex flex-wrap gap-1.5 text-[11px]">
                <span class="rounded-full px-2 py-0.5 font-medium ${PSTATUS[x.status]}">${cap(x.status)}</span>
                <span class="rounded-full bg-mist px-2 py-0.5 text-muted">${cap(x.category)}</span>
                <span class="rounded-full px-2 py-0.5 ${SEV[x.severity]}">${cap(x.severity)} severity</span>
                <span class="px-1 py-0.5 text-muted">Logged ${fmt(x.opened)}${x.resolved ? ` · resolved ${fmt(x.resolved)}` : ''}</span>
              </div>
            </div>
            ${x.shared ? '<span class="inline-flex items-center gap-1 rounded-full bg-violet-100 px-2 py-0.5 text-[11px] text-violet-800"><svg class="ic h-3 w-3"><use href="#i-share"/></svg>Shared to Posts</span>' : ''}
          </div>
          <div class="mt-3 flex flex-col gap-3 sm:flex-row">${photoTile(x.photo, 'h-20 w-28')}<p class="text-[13.5px] leading-relaxed text-ink/85">${esc(x.description) || '<span class="text-muted">No description</span>'}</p></div>
          ${diagnosisBox(x.diagnosis)}
          ${x.status === 'resolved'
            ? (x.resolution_note ? `<div class="mt-3 rounded-lg bg-emerald-50 p-3 text-[13px] text-emerald-900"><span class="font-medium">How it was resolved:</span> ${esc(x.resolution_note)}</div>` : '')
            : `<div class="resolve-box mt-3 hidden">
                <label class="mb-1.5 block text-[13px] font-medium" for="res-${x.id}">What fixed it? <span class="font-normal text-muted">(optional)</span></label>
                <textarea id="res-${x.id}" rows="2" class="dash-input" placeholder="e.g. Let the soil dry out for 4 days"></textarea>
                <div class="mt-2 flex justify-end gap-2"><button type="button" data-cancel-resolve class="h-9 rounded-lg border border-line px-3 text-[13px] font-medium hover:bg-mist">Cancel</button><button type="button" data-confirm-resolve="${x.id}" class="h-9 rounded-lg bg-forest px-3 text-[13px] font-medium text-white hover:bg-forest-900">Mark resolved</button></div>
              </div>`}
          <div class="problem-actions mt-3 flex flex-wrap gap-2 text-[13px]">
            ${x.status === 'open' ? `<button type="button" data-pstatus="monitoring" data-pid="${x.id}" class="rounded-lg border border-line px-3 py-1.5 font-medium hover:bg-mist">Monitoring</button>` : ''}
            ${x.status !== 'resolved' ? `<button type="button" data-resolve="${x.id}" class="rounded-lg bg-forest px-3 py-1.5 font-medium text-white hover:bg-forest-900">Mark resolved</button>` : `<button type="button" data-pstatus="open" data-pid="${x.id}" class="rounded-lg border border-line px-3 py-1.5 font-medium hover:bg-mist">Reopen</button>`}
            ${x.shared ? '' : `<button type="button" data-share-problem="${x.id}" class="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 font-medium hover:bg-mist"><svg class="ic h-3.5 w-3.5"><use href="#i-share"/></svg>Ask the community</button>`}
            <button type="button" data-ask="${esc(`What should I do about the ${x.title.toLowerCase()}?`)}" class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 font-medium text-forest hover:bg-leaf-soft"><svg class="ic h-3.5 w-3.5"><use href="#i-sparkles"/></svg>Ask tutor</button>
          </div>
        </article>`).join('')}</div>`;
  }

  // Harvests (FR-27)
  function tabHarvests(p) {
    const c = cat(p);
    if (!p.harvests.length) {
      const d = day(p);
      const hint = p.status === 'planned' ? `Expect your first harvest about ${c.harvest[0]}–${c.harvest[1]} days after sowing.`
        : p.status === 'failed' ? 'This plant didn’t make it to harvest. Your notes will help next time.'
        : d >= c.harvest[0] ? `You’re in the harvest window (day ${c.harvest[0]}–${c.harvest[1]}). Log what you pick here.`
        : `About ${c.harvest[0] - d} days until the harvest window opens (day ${c.harvest[0]}–${c.harvest[1]}).`;
      return tabHeader('Harvests', '', '') + emptyState('i-basket', 'No harvests yet', hint, ['planned', 'failed'].includes(p.status) ? '' : `<button type="button" data-open="harvestDialog" class="mt-4 inline-flex h-9 items-center gap-1.5 rounded-lg bg-ink px-3 text-[13px] font-medium text-white">Log a harvest</button>`);
    }
    const list = [...p.harvests].sort((a, b) => b.date.localeCompare(a.date));
    return tabHeader('Harvests', 'Every harvest counts toward your growing goals', addBtn('harvestDialog', 'Log harvest')) + `
      <div class="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <div class="rounded-xl bg-amber-50 p-4"><div class="text-[12px] text-amber-800/80">Total</div><div class="mt-1 font-display text-[22px] font-semibold text-amber-900">${harvestTotals(p) || '—'}</div></div>
        <div class="rounded-xl bg-mist p-4"><div class="text-[12px] text-muted">Harvests</div><div class="mt-1 font-display text-[22px] font-semibold">${p.harvests.length}</div></div>
        <div class="col-span-2 rounded-xl bg-mist p-4 sm:col-span-1"><div class="text-[12px] text-muted">Latest</div><div class="mt-1 font-display text-[22px] font-semibold">${fmt(list[0].date)}</div></div>
      </div>
      <ul class="divide-y divide-line rounded-xl border border-line">${list.map((h) => `
        <li class="flex items-center gap-3 p-3.5">
          <span class="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-amber-100 text-amber-700"><svg class="ic h-4 w-4"><use href="#i-basket"/></svg></span>
          <div class="min-w-0 flex-1"><div class="text-[14px] font-medium">${h.quantity ? qty(h.quantity, h.unit) : 'Quantity not logged'}</div>${h.note ? `<div class="text-[13px] text-muted">${esc(h.note)}</div>` : ''}</div>
          <div class="shrink-0 text-[12.5px] text-muted">${fmt(h.date, { month: 'short', day: 'numeric', year: 'numeric' })}</div>
        </li>`).join('')}</ul>
      <button type="button" data-share class="mt-4 inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-2 text-[13px] font-medium hover:bg-mist"><svg class="ic h-4 w-4"><use href="#i-share"/></svg>Share this harvest to Posts</button>`;
  }

  // Calendar (FR-23): icon-based, per plant or garden-wide
  const EV = {
    water:   { dot: 'bg-sky-500',    tint: 'bg-sky-50 text-sky-600',       icon: 'i-drop' },
    care:    { dot: 'bg-emerald-600', tint: 'bg-emerald-50 text-emerald-700', icon: 'i-scissors' },
    growth:  { dot: 'bg-lime-500',   tint: 'bg-lime-50 text-lime-700',     icon: 'i-sprout' },
    harvest: { dot: 'bg-amber-500',  tint: 'bg-amber-50 text-amber-700',   icon: 'i-basket' },
    weather: { dot: 'bg-indigo-500', tint: 'bg-indigo-50 text-indigo-700', icon: 'i-snow' },
    problem: { dot: 'bg-rose-500',   tint: 'bg-rose-50 text-rose-600',     icon: 'i-alert' },
    reminder:{ dot: 'bg-slate-400',  tint: 'bg-mist text-forest',          icon: 'i-bell' },
  };
  function eventsFor(plants) {
    const ev = {};
    const add = (date, type, label, icon) => (ev[date] ||= []).push({ type, label, icon });
    const multi = plants.length > 1;
    plants.forEach((p) => {
      const who = multi ? `${p.nickname}: ` : '';
      if (p.status !== 'planned') add(p.planted_on, 'growth', `${who}${p.start_method === 'seed' ? 'Sowed' : 'Planted'}`, p.start_method === 'seed' ? 'i-seed' : 'i-sprout');
      p.timeline.forEach((t) => { if (t.date !== p.planted_on) add(t.date, 'growth', `${who}${STAGES[stageIndex(t.stage)].label} — timeline entry`, STAGES[stageIndex(t.stage)].icon); });
      p.care.forEach((l) => add(l.date, l.action === 'water' ? 'water' : 'care', `${who}${ACTIONS[l.action].past}`, ACTIONS[l.action].icon));
      p.harvests.forEach((h) => add(h.date, 'harvest', `${who}Harvested${h.quantity ? ` · ${qty(h.quantity, h.unit)}` : ''}`));
      p.problems.forEach((x) => add(x.opened, 'problem', `${who}${x.title}`));
      p.reminders.forEach((r) => {
        r.history.forEach((h) => { if (h.status === 'skipped_rain') add(h.date, 'weather', `${who}Watering skipped — rain`, 'i-rain'); });
        if (!r.active) return;
        const limit = addDays(TODAY_ISO, 60);
        for (let dte = r.next_due; dte <= limit; dte = addDays(dte, r.every || 9999)) {
          add(dte, r.type === 'water' ? 'water' : 'reminder', `${who}${r.title} (reminder)`, REMINDER_TYPES[r.type].icon);
          if (!r.every) break;
        }
      });
      if (WEATHER.frostDate && p.setting === 'outdoor' && !cat(p).frostOk && isActive(p)) add(WEATHER.frostDate, 'weather', `${who}Frost risk · ${WEATHER.frostLow} °C`);
    });
    return ev;
  }
  let calSelected = TODAY_ISO;
  function tabCalendar(p) {
    const events = eventsFor(calScope === 'plant' ? [p] : PLANTS.filter((x) => x.status !== 'archived'));
    const y = calMonth.getFullYear(), m = calMonth.getMonth();
    const start = new Date(y, m, 1 - new Date(y, m, 1).getDay());
    let cells = '';
    for (let i = 0; i < 42; i++) {
      const dt = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
      if (i >= 35 && dt.getMonth() !== m) break;
      const key = iso(dt);
      const list = events[key] || [];
      const icons = [...new Map(list.map((e) => [e.type, e])).values()].slice(0, 3);
      const today = key === TODAY_ISO;
      cells += `<button type="button" data-cal-day="${key}" class="relative flex min-h-[64px] flex-col items-start gap-1 rounded-lg border p-1.5 text-left text-[12px] transition sm:min-h-[76px] ${dt.getMonth() !== m ? 'border-transparent text-[#c0c9c2]' : 'border-line hover:border-leaf'} ${key === calSelected ? 'ring-2 ring-forest' : ''}" aria-label="${fmt(key, { month: 'long', day: 'numeric' })}${list.length ? `, ${list.length} events` : ''}">
        <span class="${today ? 'grid h-5 w-5 place-items-center rounded-full bg-forest font-semibold text-white' : ''}">${dt.getDate()}</span>
        <span class="flex flex-wrap gap-0.5">${icons.map((e) => `<span class="grid h-5 w-5 place-items-center rounded ${EV[e.type].tint}" title="${esc(e.label)}"><svg class="ic h-3 w-3"><use href="#${e.icon || EV[e.type].icon}"/></svg></span>`).join('')}${list.length > 3 ? `<span class="text-[10px] text-muted">+${list.length - 3}</span>` : ''}</span>
      </button>`;
    }
    const dayList = events[calSelected] || [];
    return `
      <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center gap-2">
          <button type="button" data-cal-nav="-1" class="grid h-8 w-8 place-items-center rounded-lg bg-mist hover:bg-leaf-soft" aria-label="Previous month"><svg class="ic h-4 w-4"><use href="#i-chev-left"/></svg></button>
          <h3 class="min-w-[130px] text-center text-[15px] font-medium">${calMonth.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}</h3>
          <button type="button" data-cal-nav="1" class="grid h-8 w-8 place-items-center rounded-lg bg-mist hover:bg-leaf-soft" aria-label="Next month"><svg class="ic h-4 w-4"><use href="#i-chev-right"/></svg></button>
        </div>
        <div class="flex gap-1 rounded-lg bg-mist p-0.5 text-[12px] ring-1 ring-line" role="group" aria-label="Calendar scope">
          <button type="button" class="set-chip rounded-md px-2.5 py-1" data-cal-scope="plant" aria-pressed="${calScope === 'plant'}">This plant</button>
          <button type="button" class="set-chip rounded-md px-2.5 py-1" data-cal-scope="garden" aria-pressed="${calScope === 'garden'}">Whole garden</button>
        </div>
      </div>
      <div class="grid grid-cols-7 gap-1 text-center text-[11px] font-medium uppercase tracking-wide text-muted"><span>Sun</span><span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span><span>Sat</span></div>
      <div class="mt-1 grid grid-cols-7 gap-1">${cells}</div>
      <div class="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-[11.5px] text-muted">${[['water', 'Watering'], ['care', 'Care'], ['growth', 'Growth'], ['harvest', 'Harvest'], ['weather', 'Weather'], ['problem', 'Problem'], ['reminder', 'Reminder']].map(([k, l]) => `<span class="flex items-center gap-1"><i class="block h-2 w-2 rounded-full ${EV[k].dot}"></i>${l}</span>`).join('')}</div>
      <div class="mt-4 rounded-xl border border-line p-4">
        <h4 class="text-[13.5px] font-medium">${calSelected === TODAY_ISO ? 'Today' : fmt(calSelected, { weekday: 'long', month: 'long', day: 'numeric' })}</h4>
        <ul class="mt-2 space-y-2 text-[13px]">${dayList.length ? dayList.map((e) => `<li class="flex items-center gap-2.5"><span class="grid h-7 w-7 shrink-0 place-items-center rounded-lg ${EV[e.type].tint}"><svg class="ic h-3.5 w-3.5"><use href="#${e.icon || EV[e.type].icon}"/></svg></span>${esc(e.label)}</li>`).join('') : '<li class="text-muted">Nothing on this day.</li>'}</ul>
      </div>`;
  }

  // Reminders (FR-24): recurring, in-app + email, weather-aware for outdoor watering
  function recurrence(r) {
    const t = new Date(`2000-01-01T${r.time}`).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
    return r.every ? `Every ${r.every === 1 ? 'day' : `${r.every} days`} at ${t}` : `Once on ${fmt(r.next_due)} at ${t}`;
  }
  function tabReminders(p) {
    const list = [...p.reminders].sort((a, b) => Number(b.active) - Number(a.active) || a.next_due.localeCompare(b.next_due));
    return tabHeader('Reminders', 'Delivered in the app and by email. Outdoor watering adjusts to rain.', '') + `
      <ul class="space-y-3">${list.map((r) => {
        const t = REMINDER_TYPES[r.type];
        return `<li class="rounded-xl border border-line p-4 ${r.active ? '' : 'opacity-60'}" data-reminder="${r.id}">
          <div class="flex items-start gap-3">
            <span class="grid h-9 w-9 shrink-0 place-items-center rounded-lg ${t.tint}"><svg class="ic h-4 w-4"><use href="#${t.icon}"/></svg></span>
            <div class="min-w-0 flex-1">
              <div class="text-[14px] font-medium">${esc(r.title)}</div>
              <div class="flex flex-wrap items-center gap-x-2 text-[12.5px] text-muted"><span class="inline-flex items-center gap-1"><svg class="ic h-3.5 w-3.5"><use href="#${r.every ? 'i-repeat' : 'i-clock'}"/></svg>${recurrence(r)}</span>${r.active && r.next_due >= TODAY_ISO ? `<span>· ${r.next_due === TODAY_ISO ? 'due today' : `next ${rel(r.next_due)}`}</span>` : ''}</div>
            </div>
            <label class="flex items-center gap-2 text-[12.5px] text-muted"><span class="hidden sm:inline">${r.active ? 'On' : 'Off'}</span><input type="checkbox" class="switch" data-rem-toggle="active" ${r.active ? 'checked' : ''} aria-label="Reminder on" /></label>
          </div>
          <div class="mt-3 flex flex-wrap gap-x-5 gap-y-2 border-t border-line pt-3 text-[12.5px]">
            <label class="flex items-center gap-2"><input type="checkbox" class="switch" data-rem-toggle="inapp" ${r.inapp ? 'checked' : ''} />In-app</label>
            <label class="flex items-center gap-2"><input type="checkbox" class="switch" data-rem-toggle="email" ${r.email ? 'checked' : ''} /><svg class="ic h-3.5 w-3.5 text-muted"><use href="#i-mail"/></svg>Email</label>
            ${r.type === 'water' && p.setting === 'outdoor' ? `<label class="flex items-center gap-2"><input type="checkbox" class="switch" data-rem-toggle="weather_aware" ${r.weather_aware ? 'checked' : ''} /><svg class="ic h-3.5 w-3.5 text-sky-600"><use href="#i-rain"/></svg>Skip after rain</label>` : ''}
          </div>
          ${r.history.length ? `<div class="mt-3 flex flex-wrap gap-1.5">${r.history.slice(0, 5).map((h) => `<span class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] ${OCC[h.status].cls}" title="${esc(h.reason || '')}"><svg class="ic h-3 w-3"><use href="#${OCC[h.status].icon}"/></svg>${fmt(h.date)} · ${OCC[h.status].label}</span>`).join('')}</div>` : ''}
        </li>`;
      }).join('')}</ul>
      <form id="addReminder" class="mt-4 rounded-xl border border-dashed border-[#cfd8cf] p-4" ${p.status === 'failed' ? 'hidden' : ''}>
        <h4 class="text-[13.5px] font-medium">Add a reminder</h4>
        <div class="mt-3 grid gap-3 sm:grid-cols-[1.2fr_1fr_1fr_auto] sm:items-end">
          <div><label for="remType" class="mb-1 block text-[12.5px] text-muted">Type</label>
            <select id="remType" name="type" class="dash-input">${Object.entries(REMINDER_TYPES).map(([k, v]) => `<option value="${k}">${v.label}</option>`).join('')}</select></div>
          <div><label for="remEvery" class="mb-1 block text-[12.5px] text-muted">Repeat</label>
            <select id="remEvery" name="every" class="dash-input"><option value="0">Once</option><option value="1">Every day</option><option value="2">Every 2 days</option><option value="3" selected>Every 3 days</option><option value="7">Every week</option><option value="14">Every 2 weeks</option></select></div>
          <div><label for="remTime" class="mb-1 block text-[12.5px] text-muted">Time</label>
            <input id="remTime" name="time" type="time" value="08:00" class="dash-input" /></div>
          <button type="submit" class="h-[2.6rem] rounded-lg bg-ink px-4 text-[13.5px] font-medium text-white hover:bg-forest-900">Add</button>
        </div>
      </form>`;
  }

  // ---------- Render all ----------
  function renderAll() {
    renderSummary();
    renderStatusTabs();
    renderList();
    renderDetail();
  }
  function refreshDetail() {
    renderSummary();
    renderStatusTabs();
    renderList();
    renderDetail();
  }
  function select(id, { scroll } = {}) {
    selectedId = id;
    calSelected = TODAY_ISO;
    careFilter = 'all';
    history.replaceState(null, '', `#plant=${id}&tab=${currentTab}`);
    renderList();
    renderDetail();
    if (scroll && !window.matchMedia('(min-width: 1280px)').matches) $('#plantDetail').scrollIntoView({ behavior: 'smooth' });
  }
  function setTab(tab, focus) {
    currentTab = tab;
    history.replaceState(null, '', `#plant=${selectedId}&tab=${tab}`);
    renderDetail();
    if (focus) $(`#dtab-${tab}`)?.focus();
  }

  // ---------- Events: list ----------
  $('#plantList').addEventListener('click', (e) => {
    const item = e.target.closest('.plant-item');
    if (item) select(item.dataset.id, { scroll: true });
  });
  $('#statusTabs').addEventListener('click', (e) => {
    const b = e.target.closest('[data-status]');
    if (!b) return;
    statusFilter = b.dataset.status;
    renderStatusTabs();
    renderList();
  });
  $$('.set-chip[data-setting]').forEach((b) =>
    b.addEventListener('click', () => {
      settingFilter = b.dataset.setting;
      $$('.set-chip[data-setting]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
      renderList();
    })
  );
  $('#plantSearch').addEventListener('input', renderList);

  // ---------- Events: detail (delegated) ----------
  const detail = $('#plantDetail');
  detail.addEventListener('click', (e) => {
    const t = e.target;
    const p = selected();

    const tab = t.closest('[data-tab]');
    if (tab) return setTab(tab.dataset.tab);

    const status = t.closest('[data-set-status]');
    if (status) return changeStatus(p, status.dataset.setStatus);

    const ask = t.closest('[data-ask]');
    if (ask) return openTutor(ask.dataset.ask || '');

    if (t.closest('[data-share]')) return sharePost(p);

    const cf = t.closest('[data-care-filter]');
    if (cf) { careFilter = cf.dataset.careFilter; return renderDetail(); }

    const nav = t.closest('[data-cal-nav]');
    if (nav) { calMonth = new Date(calMonth.getFullYear(), calMonth.getMonth() + Number(nav.dataset.calNav), 1); return renderDetail(); }
    const scope = t.closest('[data-cal-scope]');
    if (scope) { calScope = scope.dataset.calScope; return renderDetail(); }
    const cd = t.closest('[data-cal-day]');
    if (cd) {
      calSelected = cd.dataset.calDay;
      const dt = parse(calSelected);
      if (dt.getMonth() !== calMonth.getMonth()) calMonth = new Date(dt.getFullYear(), dt.getMonth(), 1);
      return renderDetail();
    }

    // Problems
    const ps = t.closest('[data-pstatus]');
    if (ps) {
      const x = p.problems.find((y) => y.id === ps.dataset.pid);
      const prev = { status: x.status, resolved: x.resolved };
      x.status = ps.dataset.pstatus;
      if (x.status !== 'resolved') delete x.resolved;
      refreshDetail();
      return toast(x.status === 'open' ? 'Problem reopened' : 'Marked as monitoring', { icon: 'i-alert', undo: () => { Object.assign(x, prev); refreshDetail(); } });
    }
    const rs = t.closest('[data-resolve]');
    if (rs) {
      const card = rs.closest('[data-problem]');
      $('.resolve-box', card).classList.remove('hidden');
      $('.problem-actions', card).classList.add('hidden');
      return $('textarea', card).focus();
    }
    if (t.closest('[data-cancel-resolve]')) {
      const card = t.closest('[data-problem]');
      $('.resolve-box', card).classList.add('hidden');
      return $('.problem-actions', card).classList.remove('hidden');
    }
    const cr = t.closest('[data-confirm-resolve]');
    if (cr) {
      const x = p.problems.find((y) => y.id === cr.dataset.confirmResolve);
      x.status = 'resolved';
      x.resolved = TODAY_ISO;
      x.resolution_note = $('textarea', cr.closest('[data-problem]')).value.trim();
      p.reminders.filter((r) => r.type === 'check_problem' && r.active).forEach((r) => (r.active = false));
      refreshDetail();
      return toast('Problem resolved — nice work', { icon: 'i-check-circle' });
    }
    const sp = t.closest('[data-share-problem]');
    if (sp) {
      const x = p.problems.find((y) => y.id === sp.dataset.shareProblem);
      x.shared = true;
      renderDetail();
      return toast('Posted to the community as a Question', { icon: 'i-share', undo: () => { x.shared = false; renderDetail(); } });
    }
  });

  // Keyboard support for the tablist (arrow keys)
  detail.addEventListener('keydown', (e) => {
    const tab = e.target.closest('[role="tab"]');
    if (!tab || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
    e.preventDefault();
    const keys = TABS.map((t) => t.key);
    let i = keys.indexOf(tab.dataset.tab);
    i = e.key === 'Home' ? 0 : e.key === 'End' ? keys.length - 1 : (i + (e.key === 'ArrowRight' ? 1 : -1) + keys.length) % keys.length;
    setTab(keys[i], true);
  });

  // Reminder toggles + add form
  detail.addEventListener('change', (e) => {
    const sw = e.target.closest('[data-rem-toggle]');
    if (!sw) return;
    const r = selected().reminders.find((x) => x.id === sw.closest('[data-reminder]').dataset.reminder);
    const field = sw.dataset.remToggle;
    r[field] = sw.checked;
    if (field === 'active' && sw.checked && r.next_due < TODAY_ISO) r.next_due = r.every ? addDays(TODAY_ISO, r.every) : TODAY_ISO;
    renderDetail();
    renderList();
    const msg = { active: sw.checked ? 'Reminder turned on' : 'Reminder paused', inapp: `In-app notifications ${sw.checked ? 'on' : 'off'}`, email: `Email ${sw.checked ? 'on' : 'off'}`, weather_aware: sw.checked ? 'Will skip watering after rain' : 'Will remind even after rain' }[field];
    toast(msg, { icon: 'i-bell' });
  });
  detail.addEventListener('submit', (e) => {
    if (e.target.id !== 'addReminder') return;
    e.preventDefault();
    const p = selected();
    const f = new FormData(e.target);
    const type = f.get('type');
    const every = Number(f.get('every'));
    const titles = { water: `Water ${p.nickname}`, fertilize: `Feed ${p.nickname}`, check_problem: `Check ${p.nickname}`, harvest_check: `Check ${p.nickname} for harvest`, custom: `${p.nickname} reminder` };
    p.reminders.push({ id: nextId('r'), type, title: titles[type], every, time: f.get('time') || '08:00', weather_aware: type === 'water' && p.setting === 'outdoor', active: true, inapp: true, email: true, next_due: every ? addDays(TODAY_ISO, every) : addDays(TODAY_ISO, 1), history: [] });
    refreshDetail();
    toast('Reminder added', { icon: 'i-bell' });
  });

  // ---------- Status changes ----------
  function changeStatus(p, status) {
    window.GH.closePopovers();
    if (status === p.status) return;
    if (status === 'harvested' && !p.harvests.length) {
      openDialog('harvestDialog', { final: true });
      return toast('Log the harvest to mark this plant as harvested', { icon: 'i-basket' });
    }
    if (status === 'failed') return openDialog('failDialog');
    const prev = p.status;
    p.status = status;
    refreshDetail();
    toast(`Status changed to ${STATUS[status].label}`, { undo: () => { p.status = prev; refreshDetail(); } });
  }

  function sharePost(p) {
    toast(`Draft post created for ${p.nickname}`, { icon: 'i-share' });
  }

  // ---------- Dialogs ----------
  const STAGE_PICK = STAGES.map((s) => `<div class="relative"><input type="radio" name="stage" id="st-${s.key}" value="${s.key}" /><label for="st-${s.key}" class="flex cursor-pointer flex-col items-center gap-1 rounded-xl border border-line py-2"><svg class="ic h-4 w-4"><use href="#${s.icon}"/></svg>${s.label}</label></div>`).join('');
  $('#stagePicker').innerHTML = STAGE_PICK;
  $('#actionPicker').innerHTML = Object.entries(ACTIONS).map(([k, a], i) => `<div class="relative"><input type="radio" name="action" id="ac-${k}" value="${k}" ${i === 0 ? 'checked' : ''} /><label for="ac-${k}" class="flex cursor-pointer flex-col items-center gap-1 rounded-xl border border-line px-1 py-2 text-center"><svg class="ic h-4 w-4"><use href="#${a.icon}"/></svg>${a.label}</label></div>`).join('');
  $('#addType').innerHTML = Object.entries(CATALOG).map(([k, c]) => `<option value="${k}">${c.name}</option>`).join('');
  const showSuit = () => {
    const c = CATALOG[$('#addType').value];
    $('#addSuit').className = `mt-1.5 text-[12.5px] font-medium ${SUIT_CLS[c.suit]}`;
    $('#addSuit').textContent = c.suitLabel;
  };
  $('#addType').addEventListener('change', showSuit);

  function openDialog(id, opts = {}) {
    const dlg = $(`#${id}`);
    const form = $('form', dlg);
    const p = selected();
    form.reset();
    $$('.photo-preview', dlg).forEach((pv) => (pv.innerHTML = '<svg class="ic h-5 w-5"><use href="#i-camera"/></svg>'));
    $$('[data-plant-name]', dlg).forEach((el) => (el.textContent = p.nickname));
    $$('input[type="date"]', dlg).forEach((inp) => { inp.value = TODAY_ISO; inp.max = id === 'addPlantDialog' ? '' : TODAY_ISO; });
    if (id === 'timelineDialog') {
      const cur = Math.max(0, currentStage(p));
      $(`#st-${STAGES[Math.min(cur, 5)].key}`).checked = true;
    }
    if (id === 'harvestDialog') {
      $('[name="final"]', dlg).checked = Boolean(opts.final);
      $('#harvUnit').value = p.harvests[0]?.unit || 'g';
    }
    if (id === 'problemDialog') {
      $('#diagnosisPreview').textContent = 'Describe the problem, then ask the tutor for likely causes and fixes.';
      pendingDiagnosis = null;
    }
    if (id === 'addPlantDialog') showSuit();
    dlg.showModal();
  }

  document.addEventListener('click', (e) => {
    const opener = e.target.closest('[data-open]');
    if (opener && !opener.disabled) openDialog(opener.dataset.open);
    const closer = e.target.closest('dialog [data-close]');
    if (closer) closer.closest('dialog').close();
  });
  $$('dialog.sheet').forEach((dlg) => dlg.addEventListener('click', (e) => { if (e.target === dlg) dlg.close(); }));

  // Photo previews (local only; the real upload strips EXIF GPS server-side)
  $$('.photo-drop input[type="file"]').forEach((inp) =>
    inp.addEventListener('change', () => {
      const file = inp.files[0];
      const pv = $('.photo-preview', inp.closest('.photo-drop'));
      if (!file) return;
      pv.innerHTML = `<img src="${URL.createObjectURL(file)}" alt="Selected photo preview" class="h-full w-full object-cover" />`;
    })
  );
  const photoOf = (form) => {
    const file = form.querySelector('input[type="file"]')?.files[0];
    return file ? URL.createObjectURL(file) : false;
  };

  // Timeline entry
  $('[data-form="timeline"]').addEventListener('submit', (e) => {
    const p = selected();
    const f = new FormData(e.target);
    const stage = f.get('stage');
    p.timeline.push({ id: nextId('t'), stage, date: f.get('date'), note: f.get('note').trim(), photo: photoOf(e.target) });
    const target = STAGES[stageIndex(stage)].status;
    let msg = 'Timeline entry added';
    if (f.get('updateStatus') && target && !['harvested', 'failed'].includes(p.status) && stageIndex(stage) >= currentStage(p) - 0 && p.status !== target) {
      p.status = target;
      msg = `Entry added · status now ${STATUS[target].label}`;
    }
    if (p.status === 'planned' && stageIndex(stage) >= 0) p.status = target || 'sprouting';
    currentTab = 'timeline';
    refreshDetail();
    toast(msg, { icon: 'i-camera' });
    if (stage === 'harvest') setTimeout(() => openDialog('harvestDialog'), 250);
  });

  // Care log
  $('[data-form="care"]').addEventListener('submit', (e) => {
    const p = selected();
    const f = new FormData(e.target);
    const action = f.get('action');
    const date = f.get('date');
    p.care.push({ action, amount: f.get('amount').trim(), note: f.get('note').trim(), date, source: 'manual' });
    // Logging watering satisfies today's watering reminder occurrence
    if (action === 'water') {
      const r = p.reminders.find((x) => x.type === 'water' && x.active);
      if (r && r.next_due <= addDays(date, 1)) {
        r.history.unshift({ date, status: 'done' });
        r.next_due = addDays(date, r.every || p.watering_interval_days);
      }
    }
    currentTab = 'care';
    refreshDetail();
    toast(`${ACTIONS[action].past} ${p.nickname}`, { icon: ACTIONS[action].icon });
  });

  // Problem + AI suggestion (mock of the vision/LLM diagnosis)
  let pendingDiagnosis = null;
  function diagnose(text, p, severity) {
    const t = text.toLowerCase();
    const wateredRecently = p.care.some((l) => l.action === 'water' && diffDays(l.date, TODAY_ISO) <= 7);
    let dx;
    if (/yellow|pale/.test(t)) {
      dx = {
        issues: [
          { name: 'Overwatering', confidence: wateredRecently && p.setting === 'outdoor' ? 'high' : 'medium', reasoning: `Yellowing often means roots sit in wet soil${wateredRecently ? ' — you watered in the last week' : ''}${p.setting === 'outdoor' ? ' and 12 mm of rain fell yesterday' : ''}.` },
          { name: 'Nitrogen deficiency', confidence: 'low', reasoning: 'Likely if older leaves yellow evenly and the soil is dry.' },
        ],
        immediate_actions: ['Check the top 2 cm of soil before watering again', 'Make sure the container drains', 'Remove the worst leaves'],
        watch_for: ['Soft or black stems at the base', 'Yellowing spreading to new growth'],
      };
    } else if (/spot|brown|black|mold|mould|mildew|powder|fuzz/.test(t)) {
      dx = {
        issues: [{ name: 'Fungal leaf disease', confidence: 'medium', reasoning: 'Spots or powdery patches usually come from damp leaves and poor airflow, common in cool, wet weeks.' }],
        immediate_actions: ['Remove affected leaves and bin them (not compost)', 'Water at the base, in the morning', 'Give the plant more space for airflow'],
        watch_for: ['Spots spreading to new leaves within days', 'Stems turning brown'],
      };
    } else if (/hole|bug|aphid|insect|chew|eaten|sticky|web|mite|caterpillar|slug/.test(t)) {
      dx = {
        issues: [{ name: /aphid|sticky/.test(t) ? 'Aphids' : /web|mite/.test(t) ? 'Spider mites' : 'Chewing pests', confidence: /aphid|web|mite/.test(t) ? 'high' : 'medium', reasoning: 'The damage pattern you describe matches common soft-bodied or chewing pests.' }],
        immediate_actions: ['Check the undersides of leaves', 'Spray with mild soapy water, repeat in 2–3 days', 'Hand-pick any caterpillars or slugs in the evening'],
        watch_for: ['Curling or speckled leaves', 'Ants on the stems'],
      };
    } else if (/wilt|droop|limp/.test(t)) {
      dx = {
        issues: [
          { name: 'Underwatering', confidence: 'medium', reasoning: 'Wilting with dry soil means the roots can’t keep up.' },
          { name: 'Root rot', confidence: 'low', reasoning: 'If the soil is wet and the plant still wilts, roots may be damaged.' },
        ],
        immediate_actions: ['Feel the soil: water deeply only if dry', 'Move out of harsh afternoon sun for a day'],
        watch_for: ['No recovery by evening', 'Mushy, dark roots'],
      };
    } else if (/leggy|tall|stretch|thin stem/.test(t)) {
      dx = {
        issues: [{ name: 'Not enough light', confidence: 'high', reasoning: 'Stretched, pale stems reach for light. Common on windowsills in autumn.' }],
        immediate_actions: ['Move to the brightest window you have', 'Pinch the top to encourage bushier growth'],
        watch_for: ['New leaves getting smaller and paler'],
      };
    } else if (/bolt|flower stalk|seed/.test(t)) {
      dx = {
        issues: [{ name: 'Bolting', confidence: 'high', reasoning: 'Heat or long days make leafy crops and herbs flower early.' }],
        immediate_actions: ['Harvest usable leaves now', 'Pinch off flower stalks on herbs'],
        watch_for: ['Leaves turning bitter'],
      };
    } else {
      dx = {
        issues: [{ name: 'Not sure yet', confidence: 'low', reasoning: 'There isn’t enough detail to narrow it down. A clear photo of the affected leaves helps a lot.' }],
        immediate_actions: ['Add a close-up photo', 'Note when it started and anything you changed recently'],
        watch_for: ['How fast it spreads over the next 2–3 days'],
      };
    }
    if (severity === 'high') dx.watch_for.push('If it spreads fast, contact your local extension office');
    return dx;
  }
  $('#diagnoseBtn').addEventListener('click', () => {
    const form = $('[data-form="problem"]');
    const text = `${form.title.value} ${form.description.value}`.trim();
    const box = $('#diagnosisPreview');
    if (!text) { box.textContent = 'Add a title or description first.'; form.title.focus(); return; }
    box.innerHTML = '<span class="typing" aria-label="Tutor is thinking"><span></span><span></span><span></span></span>';
    setTimeout(() => {
      pendingDiagnosis = diagnose(text, selected(), form.severity.value);
      const top = pendingDiagnosis.issues[0];
      box.innerHTML = `<div class="text-emerald-50"><span class="font-medium text-white">Likely: ${esc(top.name)}</span> <span class="ml-1 rounded-full px-2 py-0.5 text-[10.5px] font-medium ${CONF[top.confidence]}">${cap(top.confidence)} confidence</span></div><div class="mt-1">${esc(top.reasoning)}</div><div class="mt-1.5 text-emerald-50/60">Full steps are saved with the problem.</div>`;
    }, 800);
  });
  $('[data-form="problem"]').addEventListener('submit', (e) => {
    const p = selected();
    const f = new FormData(e.target);
    const title = f.get('title').trim();
    const description = f.get('description').trim();
    const x = {
      id: nextId('p'), title, description, category: f.get('category'), severity: f.get('severity'), status: 'open', opened: TODAY_ISO,
      photo: photoOf(e.target), diagnosis: pendingDiagnosis || diagnose(`${title} ${description}`, p, f.get('severity')),
    };
    p.problems.push(x);
    // Follow-up reminder (PRD 4.2: diagnosis → problem log → follow-up reminder)
    p.reminders.push({ id: nextId('r'), type: 'check_problem', title: `Check: ${title}`, every: 0, time: '09:00', weather_aware: false, active: true, inapp: true, email: false, next_due: addDays(TODAY_ISO, 3), history: [] });
    currentTab = 'problems';
    refreshDetail();
    toast('Problem logged · follow-up reminder set for 3 days', { icon: 'i-alert' });
  });

  // Harvest
  $('[data-form="harvest"]').addEventListener('submit', (e) => {
    const p = selected();
    const f = new FormData(e.target);
    const q = f.get('quantity');
    p.harvests.push({ date: f.get('date'), quantity: q ? Number(q) : null, unit: f.get('unit'), note: f.get('note').trim() });
    if (f.get('final')) {
      p.status = 'harvested';
      p.harvested_at = f.get('date');
      p.reminders.forEach((r) => { if (r.type !== 'custom') r.active = false; });
    }
    currentTab = 'harvests';
    refreshDetail();
    toast(f.get('final') ? `${p.nickname} harvested — congratulations!` : 'Harvest logged', { icon: 'i-basket' });
  });

  // Failed
  $('[data-form="fail"]').addEventListener('submit', (e) => {
    const p = selected();
    const prev = { status: p.status, reason: p.failure_reason };
    p.status = 'failed';
    p.failure_reason = new FormData(e.target).get('reason').trim();
    p.reminders.forEach((r) => (r.active = false));
    refreshDetail();
    toast('Marked as failed. Your notes will help next time.', { icon: 'i-x-circle', undo: () => { p.status = prev.status; p.failure_reason = prev.reason; refreshDetail(); } });
  });

  // Add plant (auto-generated care schedule)
  $('[data-form="add"]').addEventListener('submit', (e) => {
    const f = new FormData(e.target);
    const type = f.get('type');
    const c = CATALOG[type];
    const date = f.get('date');
    const method = f.get('method');
    const setting = f.get('setting');
    const nickname = f.get('nickname').trim() || c.name;
    const future = date > TODAY_ISO;
    const id = `${type}-${++uid}`;
    PLANTS.unshift({
      id, type, nickname, variety: '', planted_on: date, start_method: method, setting, container: f.get('container').trim(), quantity: Number(f.get('quantity')) || 1,
      status: future ? 'planned' : method === 'seed' ? 'sprouting' : 'growing', watering_interval_days: c.water,
      tip: `Your tutor will tailor tips for ${nickname} as you log its progress.`,
      timeline: future ? [] : [{ id: nextId('t'), stage: method === 'seed' ? 'seed' : 'seedling', date, note: `${method === 'seed' ? 'Sowed' : 'Planted'} ${nickname}.`, photo: false }],
      care: [], problems: [], harvests: [],
      reminders: [{ id: nextId('r'), type: 'water', title: `Water ${nickname}`, every: c.water, time: '08:00', weather_aware: setting === 'outdoor', active: true, inapp: true, email: true, next_due: future ? date : addDays(TODAY_ISO, 1), history: [] }],
    });
    statusFilter = 'all';
    currentTab = 'timeline';
    selectedId = id;
    renderAll();
    history.replaceState(null, '', `#plant=${id}&tab=timeline`);
    toast(`${nickname} added · watering every ${c.water} days`, { icon: 'i-sprout' });
  });

  // ---------- Tutor drawer (mock answers grounded in this plant's data) ----------
  const drawer = $('#tutorDrawer');
  const drawerLog = $('#drawerLog');
  function answerFor(p, q) {
    const c = cat(p);
    const d = day(p);
    const water = p.reminders.find((r) => r.type === 'water' && r.active);
    const open = openProblems(p)[0];
    if (/water|dry|thirst/i.test(q)) {
      if (p.setting !== 'outdoor') return `${p.nickname} is indoors, so rain doesn’t count. It’s on a ${water ? `${water.every}-day` : `${p.watering_interval_days}-day`} schedule${water ? ` and the next watering is ${rel(water.next_due)}` : ''}. Push a finger 2 cm into the soil first — only water if it feels dry.`;
      if (weatherBadges(p).some((b) => b.icon === 'i-rain')) return `Skip it today: ${WEATHER.rainMm} mm of rain fell in the last 24 hours, so the soil is still moist. ${water ? `Your next watering is ${rel(water.next_due)}.` : ''}`;
      return `${water ? `Next watering is ${rel(water.next_due)}.` : 'There’s no active watering reminder.'} In cool October weather, check the top 2 cm of soil first and only water when it’s dry.`;
    }
    if (/harvest|ripe|pick|ready/i.test(q)) {
      const ripe = { 'cherry-tomato': 'Cherry tomatoes are ready when they turn fully coloured and come off with a gentle tug.', basil: 'Pick the top leaves just above a leaf pair once the plant is about 20 cm tall.', lettuce: 'Start picking outer leaves once they’re about 10 cm long.', spinach: 'Pick outer leaves when they’re 8–10 cm long.', mint: 'Cut stems back by a third — it regrows quickly.' }[p.type] || '';
      if (p.status === 'planned') return `After sowing on ${fmt(p.planted_on)}, expect the first harvest in about ${c.harvest[0]}–${c.harvest[1]} days. ${ripe}`;
      if (p.harvests.length) return `You’ve harvested ${harvestTotals(p)} so far across ${p.harvests.length} pickings. ${ripe}`;
      return d >= c.harvest[0] ? `It’s day ${d}, so you’re in the harvest window. ${ripe}` : `It’s day ${d}. The harvest window opens in about ${c.harvest[0] - d} days (day ${c.harvest[0]}–${c.harvest[1]}). ${ripe}`;
    }
    if (/frost|cold|freez/i.test(q)) {
      if (!WEATHER.frostDate) return `No frost is forecast this week. ${c.frostOk ? `${c.name} handles light frost anyway.` : 'You’ll get an alert 48 hours ahead if that changes.'}`;
      const frostDay = fmt(WEATHER.frostDate, { weekday: 'long' });
      if (p.setting !== 'outdoor') return `${p.nickname} is indoors, so ${frostDay}’s ${WEATHER.frostLow} °C low won’t affect it. Just keep it away from cold window glass at night.`;
      return c.frostOk
        ? `${c.name} handles light frost well, so ${frostDay}’s ${WEATHER.frostLow} °C low shouldn’t harm it.`
        : `${frostDay}’s low is ${WEATHER.frostLow} °C, below the ${WEATHER.frostThreshold} °C frost threshold. Water the soil the afternoon before, cover the plant at sunset with frost cloth or an old sheet, and uncover it the next morning.`;
    }
    if (/problem|wrong|healthy|yellow|sick|do about/i.test(q)) {
      if (open) return `The open problem is “${open.title}”. Most likely: ${open.diagnosis.issues[0].name.toLowerCase()} (${open.diagnosis.issues[0].confidence} confidence). Right now: ${open.diagnosis.immediate_actions.join('; ').toLowerCase()}. Watch for ${open.diagnosis.watch_for[0].toLowerCase()}.`;
      return `No open problems on ${p.nickname} — nice. ${p.tip}`;
    }
    return p.tip;
  }
  function drawerMsg(role, text) {
    const wrap = document.createElement('div');
    wrap.className = `chat-msg ${role === 'user' ? 'ml-auto max-w-[85%]' : 'max-w-[95%]'}`;
    if (role === 'user') {
      wrap.innerHTML = '<div class="rounded-2xl rounded-br-md bg-lime-300 px-3.5 py-2 text-[13.5px] text-forest-900"></div>';
      wrap.firstChild.textContent = text;
    } else {
      wrap.innerHTML = '<div class="mb-1 flex items-center gap-1.5 text-[11px] font-medium text-lime-300"><svg class="ic h-3 w-3"><use href="#i-sparkles"/></svg>Greenhand Tutor <span class="rounded bg-white/10 px-1 text-[9.5px] uppercase text-emerald-50/70">AI</span></div><div class="msg-body rounded-2xl rounded-tl-md bg-white/[0.07] px-3.5 py-2.5 text-[13.5px] leading-relaxed text-emerald-50/90"></div>';
      $('.msg-body', wrap).textContent = text;
    }
    drawerLog.appendChild(wrap);
    drawerLog.scrollTop = drawerLog.scrollHeight;
    return wrap;
  }
  function askDrawer(q) {
    q = q.trim();
    if (!q) return;
    drawerMsg('user', q);
    $('#drawerInput').value = '';
    const reply = drawerMsg('assistant', '');
    const body = $('.msg-body', reply);
    body.innerHTML = '<span class="typing" aria-label="Tutor is typing"><span></span><span></span><span></span></span>';
    const text = answerFor(selected(), q);
    setTimeout(() => { body.textContent = text; drawerLog.scrollTop = drawerLog.scrollHeight; }, 700);
  }
  let lastFocus = null;
  function openTutor(question) {
    const p = selected();
    lastFocus = document.activeElement;
    $('#drawerScope').textContent = `${p.nickname} · ${p.status === 'planned' ? 'planned' : `day ${day(p)}`} · ${p.setting}`;
    drawerLog.innerHTML = '';
    drawerMsg('assistant', `Hi! I’m looking at ${p.nickname}: ${STATUS[p.status].label.toLowerCase()}, ${p.setting}, with ${p.care.length} care logs and ${openProblems(p).length} open problem${openProblems(p).length === 1 ? '' : 's'}. What would you like to know?`);
    const chips = ['Should I water today?', 'When can I harvest?', 'Is frost a problem?', openProblems(p)[0] ? `What should I do about the ${openProblems(p)[0].title.toLowerCase()}?` : 'Is it healthy?'];
    $('#drawerChips').innerHTML = chips.map((c) => `<button type="button" class="drawer-chip rounded-full bg-white/10 px-3 py-1.5 text-[12.5px] text-emerald-50 hover:bg-white/15">${esc(c)}</button>`).join('');
    drawer.classList.add('is-open');
    drawer.setAttribute('aria-hidden', 'false');
    $('#tutorBackdrop').classList.remove('hidden');
    setTimeout(() => $('#drawerInput').focus(), 250);
    if (question) setTimeout(() => askDrawer(question), 300);
  }
  function closeTutor() {
    drawer.classList.remove('is-open');
    drawer.setAttribute('aria-hidden', 'true');
    $('#tutorBackdrop').classList.add('hidden');
    lastFocus?.focus?.();
  }
  $('#closeTutor').addEventListener('click', closeTutor);
  $('#tutorBackdrop').addEventListener('click', closeTutor);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && drawer.classList.contains('is-open')) closeTutor(); });
  $('#drawerForm').addEventListener('submit', (e) => { e.preventDefault(); askDrawer($('#drawerInput').value); });
  $('#drawerChips').addEventListener('click', (e) => { const b = e.target.closest('.drawer-chip'); if (b) askDrawer(b.textContent); });

  // ---------- Deep links: #plant=basil&tab=problems ----------
  function readHash() {
    const params = new URLSearchParams(location.hash.slice(1));
    const plant = params.get('plant');
    const tab = params.get('tab');
    if (plant && PLANTS.some((p) => p.id === plant)) selectedId = plant;
    if (tab && TABS.some((t) => t.key === tab)) currentTab = tab;
  }
  window.addEventListener('hashchange', () => { readHash(); renderList(); renderDetail(); });
  readHash();
  renderAll();
})();
