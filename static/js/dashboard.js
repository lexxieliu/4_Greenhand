// Greenhand dashboard page (templates/garden/dashboard.html). Loads after shell.js.
// Server data arrives via {{ dashboard_data|json_script:"dashboard-data" }}:
//   care   -> weekly/daily care counts for the chart     height -> featured plant growth
//   events -> garden-wide calendar events by ISO date
// Tutor answers below are canned until /api/tutor/sessions/{id}/messages/ exists.

(function () {
  const { TODAY, $, $$, toast } = window.GH;
  const esc = (v) => String(v).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const DATA = JSON.parse(document.getElementById('dashboard-data').textContent);

  // ---------- Care activity data ----------
  const CATS = [
    { key: 'water', label: 'Watering', color: '#0ea5e9' },
    { key: 'feed', label: 'Feeding', color: '#84cc16' },
    { key: 'prune', label: 'Pruning', color: '#047857' },
    { key: 'harvest', label: 'Harvest', color: '#f59e0b' },
  ];

  const WEEKS = { ...DATA.care.weeks, long: (l) => `Week of ${l}` };
  const dayLabels = [];
  for (let i = 13; i >= 0; i--) {
    const d = new Date(TODAY);
    d.setDate(d.getDate() - i);
    dayLabels.push(d);
  }
  const DAYS = {
    ...DATA.care.days,
    labels: dayLabels.map((d) => (d.getDate() === 1 || d === dayLabels[0] ? d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : String(d.getDate()))),
    long: (_, i) => dayLabels[i].toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }),
  };

  // Logging care today updates the latest bar in both views.
  function bumpCare(cat, delta) {
    if (!cat) return;
    WEEKS[cat][WEEKS[cat].length - 1] = Math.max(0, WEEKS[cat].at(-1) + delta);
    DAYS[cat][DAYS[cat].length - 1] = Math.max(0, DAYS[cat].at(-1) + delta);
    renderChart();
    renderCareCard();
  }

  const totalsOf = (set) => set.labels.map((_, i) => CATS.reduce((s, c) => s + set[c.key][i], 0));

  // ---------- Stacked bar chart ----------
  const chartRange = $('#chartRange');
  const bars = $('#chartBars');
  const grid = $('#chartGrid');
  const labelsRow = $('#chartLabels');
  const tip = $('#chartTip');
  const chart = $('#careChart');
  const CHART_H = 320;

  $('#chartLegend').innerHTML = CATS.map(
    (c) => `<li class="flex items-center gap-1.5"><i class="block h-2.5 w-2.5 rounded-[3px]" style="background:${c.color}"></i>${c.label}</li>`
  ).join('');

  // Smallest "nice" step that fits the tallest bar into 4 gridline intervals
  function niceMax(v) {
    const step = [1, 2, 3, 4, 5, 10, 15, 20, 25, 50].find((s) => s * 4 >= v) || Math.ceil(v / 40) * 10;
    return step * 4;
  }

  function renderChart() {
    const set = chartRange.value === 'days' ? DAYS : WEEKS;
    const totals = totalsOf(set);
    const max = niceMax(Math.max(...totals));
    $('#chartTotal').textContent = totals.reduce((a, b) => a + b, 0);

    grid.style.cssText = `top:0;bottom:auto;height:${CHART_H}px`;
    grid.innerHTML = [0, 1, 2, 3, 4]
      .map((i) => {
        const v = (max / 4) * i;
        return `<div class="absolute left-0 right-0 flex items-center gap-2" style="bottom:${(i / 4) * CHART_H}px;transform:translateY(50%)">
          <span class="w-6 text-right text-[11px] text-muted">${v}</span>
          <span class="h-px flex-1 ${i === 0 ? 'bg-[#cfd8cf]' : 'bg-line/70'}"></span></div>`;
      })
      .join('');

    bars.innerHTML = '';
    labelsRow.innerHTML = '';
    set.labels.forEach((label, i) => {
      const col = document.createElement('div');
      col.className = 'bar-col';
      col.tabIndex = 0;
      col.setAttribute('role', 'listitem');
      col.style.height = `${(totals[i] / max) * 100}%`;
      const parts = CATS.filter((c) => set[c.key][i] > 0).map((c) => `${set[c.key][i]} ${c.label.toLowerCase()}`);
      col.setAttribute('aria-label', `${set.long(label, i)}: ${totals[i]} actions${parts.length ? ` (${parts.join(', ')})` : ''}`);
      CATS.forEach((c) => {
        const v = set[c.key][i];
        if (!v) return;
        const seg = document.createElement('span');
        seg.className = 'seg';
        seg.style.background = c.color;
        seg.style.flex = `${v} 1 0`;
        col.appendChild(seg);
      });
      const hit = document.createElement('span');
      hit.className = 'bar-hit';
      col.appendChild(hit);

      const show = () => showTip(col, set, label, i, totals[i]);
      col.addEventListener('mouseenter', show);
      col.addEventListener('focus', show);
      col.addEventListener('mouseleave', hideTip);
      col.addEventListener('blur', hideTip);
      bars.appendChild(col);

      const lab = document.createElement('span');
      lab.className = `flex-1 truncate ${i % 2 ? 'max-sm:invisible' : ''}`;
      lab.textContent = label;
      labelsRow.appendChild(lab);
    });
    renderTable(set, totals);
  }

  function showTip(col, set, label, i, total) {
    tip.innerHTML =
      `<div class="mb-1.5 font-medium">${set.long(label, i)}</div>` +
      CATS.map(
        (c) => `<div class="flex items-center justify-between gap-4 py-0.5"><span class="flex items-center gap-1.5 text-white/75"><i class="block h-2 w-2 rounded-[2px]" style="background:${c.color}"></i>${c.label}</span><span class="tabular-nums">${set[c.key][i]}</span></div>`
      ).join('') +
      `<div class="mt-1.5 flex justify-between border-t border-white/15 pt-1.5 font-medium"><span>Total</span><span class="tabular-nums">${total}</span></div>`;
    const chartBox = chart.getBoundingClientRect();
    const colBox = col.getBoundingClientRect();
    const tipW = tip.offsetWidth;
    const tipH = tip.offsetHeight;
    // Sit beside the bar (flip to the left near the edge) so it never covers the bars
    let left = colBox.right - chartBox.left + 8;
    if (left + tipW > chartBox.width) left = colBox.left - chartBox.left - tipW - 8;
    const top = Math.min(Math.max(0, colBox.top - chartBox.top), CHART_H - tipH);
    tip.style.left = `${left}px`;
    tip.style.top = `${top}px`;
    tip.style.opacity = '1';
  }
  function hideTip() { tip.style.opacity = '0'; }

  // Table view: the accessible, color-free reading of the same data
  const tableBox = $('#chartTable');
  function renderTable(set, totals) {
    tableBox.innerHTML = `<table class="w-full min-w-[420px] text-left text-[12.5px]">
      <thead class="bg-mist text-muted"><tr><th class="px-3 py-2 font-medium">${set === DAYS ? 'Day' : 'Week of'}</th>${CATS.map((c) => `<th class="px-3 py-2 text-right font-medium">${c.label}</th>`).join('')}<th class="px-3 py-2 text-right font-medium">Total</th></tr></thead>
      <tbody class="divide-y divide-line">${set.labels
        .map((l, i) => `<tr><td class="px-3 py-1.5">${set === DAYS ? set.long(l, i) : l}</td>${CATS.map((c) => `<td class="px-3 py-1.5 text-right tabular-nums">${set[c.key][i]}</td>`).join('')}<td class="px-3 py-1.5 text-right font-medium tabular-nums">${totals[i]}</td></tr>`)
        .join('')}</tbody></table>`;
  }
  $('#tableToggle').addEventListener('click', (e) => {
    const open = tableBox.classList.toggle('hidden') === false;
    e.currentTarget.setAttribute('aria-expanded', String(open));
    e.currentTarget.lastChild.textContent = open ? 'Hide table' : 'View as table';
  });
  chartRange.addEventListener('change', renderChart);

  // ---------- Card B: care total + sparkline ----------
  let period = 'week';
  function renderCareCard() {
    const series = period === 'week' ? totalsOf(DAYS).slice(-7) : totalsOf(WEEKS);
    $('#careTotal').textContent = series.reduce((a, b) => a + b, 0);
    const W = 144, H = 56, pad = 4;
    const max = Math.max(...series, 1);
    const pts = series.map((v, i) => [pad + (i / (series.length - 1)) * (W - pad * 2), H - pad - (v / max) * (H - pad * 2)]);
    const line = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ');
    const [lx, ly] = pts.at(-1);
    $('#careSpark').innerHTML =
      `<path d="${line} L${lx} ${H} L${pad} ${H} Z" fill="rgba(255,255,255,.12)"/>` +
      `<path d="${line}" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>` +
      `<circle cx="${lx}" cy="${ly}" r="4" fill="#bef264" stroke="#15803d" stroke-width="2"/>`;
  }
  $$('[data-period]').forEach((btn) =>
    btn.addEventListener('click', () => {
      period = btn.dataset.period;
      $$('[data-period]').forEach((b) => b.setAttribute('aria-pressed', String(b === btn)));
      renderCareCard();
    })
  );

  // ---------- Featured plant: tomato height area chart ----------
  const HEIGHT = DATA.height;
  (function renderHeight() {
    const svg = $('#heightChart');
    const W = 300, H = 96, maxV = Math.max(...HEIGHT.map(([, v]) => v)) * 1.15;
    const pts = HEIGHT.map(([, v], i) => [(i / (HEIGHT.length - 1)) * W, H - 6 - (v / maxV) * (H - 18)]);
    const line = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ');
    const step = W / (HEIGHT.length - 1);
    svg.innerHTML =
      `<defs><linearGradient id="hg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#16a34a" stop-opacity=".35"/><stop offset="1" stop-color="#16a34a" stop-opacity=".04"/></linearGradient></defs>` +
      `<path d="${line} L${W} ${H} L0 ${H} Z" fill="url(#hg)"/>` +
      `<path d="${line}" fill="none" stroke="#15803d" stroke-width="2" vector-effect="non-scaling-stroke" stroke-linejoin="round"/>` +
      `<line id="hgCursor" x1="${W}" x2="${W}" y1="0" y2="${H}" stroke="#14532d" stroke-opacity=".35" stroke-width="1" vector-effect="non-scaling-stroke" stroke-dasharray="3 3"/>` +
      HEIGHT.map((_, i) => `<rect data-i="${i}" x="${Math.max(0, i * step - step / 2)}" y="0" width="${step}" height="${H}" fill="transparent"/>`).join('');
    const cursor = $('#hgCursor');
    const setPoint = (i) => {
      $('#heightValue').textContent = `${HEIGHT[i][1]} cm`;
      $('#heightDate').textContent = HEIGHT[i][0];
      cursor.setAttribute('x1', pts[i][0]);
      cursor.setAttribute('x2', pts[i][0]);
    };
    $$('rect', svg).forEach((r) => r.addEventListener('mouseenter', () => setPoint(+r.dataset.i)));
    svg.addEventListener('mouseleave', () => setPoint(HEIGHT.length - 1));
    setPoint(HEIGHT.length - 1);
  })();

  // ---------- Plant list: filter chips ----------
  const chips = $$('.chip');
  let plantFilter = 'all';
  function applyPlantFilter() {
    let visible = 0;
    $$('.plant-row').forEach((row) => {
      const show = plantFilter === 'all' || row.dataset.attention === 'true';
      row.classList.toggle('is-hidden', !show);
      if (show) visible++;
    });
    $('#plantEmpty').classList.toggle('hidden', visible > 0);
  }
  function styleChips() {
    chips.forEach((c) => {
      const on = c.dataset.filter === plantFilter;
      c.setAttribute('aria-pressed', String(on));
      c.classList.toggle('bg-white', on);
      c.classList.toggle('shadow-card', on);
      c.classList.toggle('font-medium', on);
      c.classList.toggle('text-forest', on);
      c.classList.toggle('text-muted', !on);
    });
  }
  chips.forEach((chip) =>
    chip.addEventListener('click', () => {
      plantFilter = chip.dataset.filter;
      styleChips();
      applyPlantFilter();
    })
  );
  styleChips();

  // Each row opens that plant in My Garden
  $$('.plant-row[data-href]').forEach((row) => {
    row.tabIndex = 0;
    row.setAttribute('role', 'link');
    row.classList.add('cursor-pointer');
    const go = () => (window.location.href = row.dataset.href);
    row.addEventListener('click', go);
    row.addEventListener('keydown', (e) => { if (e.key === 'Enter') go(); });
  });

  // ---------- Today's tasks ----------
  const taskList = $('#taskList');

  function updateTaskStats() {
    const tasks = $$('.task', taskList);
    const done = tasks.filter((t) => t.classList.contains('is-done')).length;
    $('#tasksDone').textContent = done;
    $('#tasksTotal').textContent = tasks.length;
    $('#tasksHint').textContent = done === tasks.length ? 'all done!' : 'done';
    $('#tasksBar').style.width = `${Math.round((done / tasks.length) * 100)}%`;
  }

  function setTaskDone(task, done) {
    if (task.classList.contains('is-done') === done) return;
    task.classList.toggle('is-done', done);
    const title = $('.task-title', task).textContent;
    $('.task-check', task).setAttribute('aria-label', `Mark “${title}” as ${done ? 'not done' : 'done'}`);
    if (task.dataset.care) bumpCare(task.dataset.care, done ? 1 : -1);
    updateTaskStats();
  }

  taskList.addEventListener('click', (e) => {
    const check = e.target.closest('.task-check');
    if (!check) return;
    const task = check.closest('.task');
    const nowDone = !task.classList.contains('is-done');
    setTaskDone(task, nowDone);
    if (nowDone) toast(`Logged: ${$('.task-title', task).textContent}`, { undo: () => setTaskDone(task, false) });
  });

  // ---------- Weather alerts (rendered only when the rule engine raised one) ----------
  const rainAlert = $('#rainAlert');
  const basilTask = $('.task[data-skipped="rain"]') || $('[data-task="water-basil"]');

  if (rainAlert) {
    $('#rainAck').addEventListener('click', () => {
      rainAlert.classList.add('is-dismissed');
      toast('Rain skip acknowledged', { icon: 'i-rain', undo: () => rainAlert.classList.remove('is-dismissed') });
    });
    $('#rainOverride').addEventListener('click', () => {
      rainAlert.classList.add('is-dismissed');
      if (basilTask) {
        const badge = $('.task-badge', basilTask);
        badge.className = 'task-badge inline-flex items-center gap-1 rounded-full bg-mist px-2 py-0.5 text-[11.5px] font-medium text-muted';
        badge.textContent = 'Overridden';
        basilTask.dataset.care = 'water'; // from now on, ticking it counts as watering
        setTaskDone(basilTask, false);
      }
      toast('Watering added back for today', { icon: 'i-drop' });
    });
  }

  const frostAlert = $('#frostAlert');
  if (frostAlert) {
    const frostToggle = $('.alert-toggle', frostAlert);
    frostToggle.addEventListener('click', () => {
      const open = !frostAlert.classList.contains('is-open');
      frostAlert.classList.toggle('is-open', open);
      frostToggle.setAttribute('aria-expanded', String(open));
    });
    $$('.frost-step').forEach((cb) =>
      cb.addEventListener('change', () => {
        $('#frostCount').textContent = $$('.frost-step').filter((c) => c.checked).length;
      })
    );
    $('#frostDone').addEventListener('click', () => {
      frostAlert.classList.add('is-dismissed');
      const coverTask = $('[data-task="frost-cover"]');
      if (coverTask) setTaskDone(coverTask, true);
      toast('Frost plan saved — we’ll remind you Thursday at sunset', { icon: 'i-snow', undo: () => frostAlert.classList.remove('is-dismissed') });
    });
  }

  // ---------- Tutor mini chat (mock answers) ----------
  const ANSWERS = [
    {
      match: /water|rain|thirsty|dry/i,
      text: 'Skip the basil today — 12 mm of rain fell in the last 24 hours, so its soil is still moist. Your lettuce is indoors, so water it as usual until a little drains out the bottom.',
    },
    {
      match: /frost|cold|cover|freez/i,
      text: 'Thursday’s low is 1 °C, below your tomato’s 2 °C frost threshold. Water the soil Wednesday afternoon, cover the plant at sunset with frost cloth or an old sheet (kept off the leaves with stakes), and uncover it Friday morning.',
    },
    {
      match: /harvest|ripe|pick/i,
      text: 'Your tomato started flowering on Oct 12, so expect ripe fruit in about 3 weeks. ‘Sungold’ is ready when it turns deep golden-orange and comes off with a gentle tug. Your mint can be trimmed again now — before the frost.',
    },
    {
      match: /yellow|basil|leaves/i,
      text: 'The yellow lower leaves on your basil most likely come from overwatering (high confidence): you watered Oct 5 and 7, then it rained. Let the pot dry out, make sure it drains, and pinch off the yellow leaves. Watch for black stems near the soil.',
    },
    {
      match: /thin|lettuce|seedling/i,
      text: 'Your lettuce is on day 18 — a good time to thin. Snip (don’t pull) the weaker seedlings at soil level so one plant remains every 15 cm. The thinnings make a tasty micro-salad.',
    },
  ];
  const FALLBACK =
    'Here’s what matters most in your garden this week: protect the cherry tomato before Thursday’s frost, let the basil dry out, and keep the lettuce evenly moist. Ask me about any plant for specifics.';

  const chatLog = $('#chatLog');
  const chatInput = $('#chatInput');
  let tutorUsed = 12;

  function addMessage(role, text) {
    const wrap = document.createElement('div');
    wrap.className = `chat-msg ${role === 'user' ? 'ml-auto max-w-[85%]' : 'max-w-[95%]'}`;
    if (role === 'user') {
      wrap.innerHTML = '<div class="rounded-2xl rounded-br-md bg-lime-300 px-3.5 py-2 text-[13.5px] text-forest-900"></div>';
      wrap.firstChild.textContent = text;
    } else {
      wrap.innerHTML =
        '<div class="mb-1 flex items-center gap-1.5 text-[11px] font-medium text-lime-300"><svg class="ic h-3 w-3"><use href="#i-sparkles"/></svg>Greenhand Tutor <span class="rounded bg-white/10 px-1 text-[9.5px] uppercase text-emerald-50/70">AI</span></div>' +
        '<div class="msg-body rounded-2xl rounded-tl-md bg-white/[0.07] px-3.5 py-2.5 text-[13.5px] leading-relaxed text-emerald-50/90"></div>';
      if (text) $('.msg-body', wrap).textContent = text;
    }
    chatLog.appendChild(wrap);
    chatLog.classList.add('mb-3');
    chatLog.scrollTop = chatLog.scrollHeight;
    return wrap;
  }

  function ask(question) {
    question = question.trim();
    if (!question) return;
    $('#chatChips').classList.add('hidden');
    addMessage('user', question);
    chatInput.value = '';

    tutorUsed = Math.min(50, tutorUsed + 1);
    const pct = Math.round((tutorUsed / 50) * 100);
    $('#tutorUsed').textContent = tutorUsed;
    $('#tutorPct').textContent = `${pct}%`;
    $('#tutorBar').style.width = `${pct}%`;

    const reply = addMessage('assistant', '');
    const body = $('.msg-body', reply);
    body.innerHTML = '<span class="typing" aria-label="Tutor is typing"><span></span><span></span><span></span></span>';

    const answer = (ANSWERS.find((a) => a.match.test(question)) || { text: FALLBACK }).text;
    setTimeout(() => {
      // Reveal word by word to mimic a streamed answer
      const words = answer.split(' ');
      body.textContent = '';
      let i = 0;
      const tick = setInterval(() => {
        body.textContent += (i ? ' ' : '') + words[i++];
        chatLog.scrollTop = chatLog.scrollHeight;
        if (i >= words.length) clearInterval(tick);
      }, 28);
    }, 700);
  }

  $('#chatForm').addEventListener('submit', (e) => {
    e.preventDefault();
    ask(chatInput.value);
  });
  $$('.chat-chip').forEach((chip) => chip.addEventListener('click', () => ask(chip.textContent)));
  $('#floatTutor').addEventListener('click', () => setTimeout(() => chatInput.focus({ preventScroll: true }), 400));

  // ---------- Calendar ----------
  const COLORS = { water: 'bg-sky-500', growth: 'bg-lime-500', harvest: 'bg-amber-500', weather: 'bg-indigo-500', problem: 'bg-rose-500' };
  const ICONS = { water: 'i-drop', growth: 'i-sprout', harvest: 'i-basket', weather: 'i-snow', problem: 'i-alert' };
  const ICON_TINT = { water: 'text-sky-600 bg-sky-50', growth: 'text-lime-700 bg-lime-50', harvest: 'text-amber-700 bg-amber-50', weather: 'text-indigo-700 bg-indigo-50', problem: 'text-rose-600 bg-rose-50' };

  const key = (y, m, d) => `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
  const events = DATA.events; // { "YYYY-MM-DD": [{ type, label, icon? }] }

  let viewYear = TODAY.getFullYear();
  let viewMonth = TODAY.getMonth();
  let selected = new Date(TODAY);
  const sameDay = (a, b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();

  function renderCalendar() {
    const calGrid = $('#calGrid');
    calGrid.innerHTML = '';
    $('#calMonth').textContent = new Date(viewYear, viewMonth, 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' });

    const start = new Date(viewYear, viewMonth, 1 - new Date(viewYear, viewMonth, 1).getDay());
    for (let i = 0; i < 42; i++) {
      const date = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
      if (i >= 35 && date.getMonth() !== viewMonth) break;
      const dayEvents = events[key(date.getFullYear(), date.getMonth(), date.getDate())] || [];
      const types = [...new Set(dayEvents.map((e) => e.type))];

      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'cal-day';
      if (date.getMonth() !== viewMonth) btn.classList.add('is-outside');
      if (sameDay(date, TODAY)) btn.classList.add('is-today');
      if (sameDay(date, selected)) btn.classList.add('is-selected');
      btn.setAttribute('aria-label', `${date.toLocaleDateString('en-US', { month: 'long', day: 'numeric' })}${dayEvents.length ? `, ${dayEvents.length} event${dayEvents.length > 1 ? 's' : ''}` : ''}`);
      btn.innerHTML = `<span>${date.getDate()}</span><span class="cal-dots">${types
        .map((t) => `<i class="${sameDay(date, TODAY) ? 'bg-white' : COLORS[t]}"></i>`)
        .join('')}</span>`;
      btn.addEventListener('click', () => {
        selected = date;
        if (date.getMonth() !== viewMonth) {
          viewYear = date.getFullYear();
          viewMonth = date.getMonth();
        }
        renderCalendar();
      });
      calGrid.appendChild(btn);
    }
    renderDay();
  }

  function renderDay() {
    const list = $('#calDayEvents');
    const dayEvents = events[key(selected.getFullYear(), selected.getMonth(), selected.getDate())] || [];
    $('#calDayTitle').textContent = sameDay(selected, TODAY)
      ? 'Today'
      : selected.toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' });
    list.innerHTML = dayEvents.length
      ? dayEvents
          .map(
            (e) => `<li class="flex items-center gap-2.5"><span class="grid h-7 w-7 shrink-0 place-items-center rounded-lg ${ICON_TINT[e.type]}"><svg class="ic h-3.5 w-3.5"><use href="#${e.icon || ICONS[e.type]}"/></svg></span>${esc(e.label)}</li>`
          )
          .join('')
      : '<li class="text-muted">Nothing scheduled.</li>';
  }

  $('#calPrev').addEventListener('click', () => {
    viewMonth--;
    if (viewMonth < 0) { viewMonth = 11; viewYear--; }
    renderCalendar();
  });
  $('#calNext').addEventListener('click', () => {
    viewMonth++;
    if (viewMonth > 11) { viewMonth = 0; viewYear++; }
    renderCalendar();
  });

  // ---------- Log care dialog ----------
  const dialog = $('#logDialog');
  const logForm = $('#logForm');
  const ACTION_LABELS = { water: 'Watered', fertilize: 'Fertilized', prune: 'Pruned', treat_pest: 'Treated pests on', repot: 'Repotted', other: 'Cared for' };
  const ACTION_ICONS = { water: ['i-drop', 'bg-sky-100 text-sky-700'], fertilize: ['i-flask', 'bg-lime-100 text-lime-800'], prune: ['i-scissors', 'bg-emerald-100 text-emerald-800'], treat_pest: ['i-bug', 'bg-rose-100 text-rose-700'], repot: ['i-pot', 'bg-amber-100 text-amber-800'], other: ['i-plus', 'bg-mist text-muted'] };
  const ACTION_CAT = { water: 'water', fertilize: 'feed', prune: 'prune' };

  $$('[data-open-log]').forEach((btn) => btn.addEventListener('click', () => dialog.showModal()));
  $$('[data-close-log]').forEach((btn) => btn.addEventListener('click', () => dialog.close()));
  dialog.addEventListener('click', (e) => { if (e.target === dialog) dialog.close(); });

  logForm.addEventListener('submit', () => {
    const data = new FormData(logForm);
    const plantId = data.get('plant');
    const plant = $('#logPlant').selectedOptions[0].textContent;
    const action = data.get('action');
    const amount = data.get('amount').trim();
    const when = data.get('when');
    const [icon, tint] = ACTION_ICONS[action];

    const li = document.createElement('li');
    li.className = 'chat-msg flex gap-3 py-3';
    li.innerHTML = `<span class="grid h-8 w-8 shrink-0 place-items-center rounded-full ${tint}"><svg class="ic h-4 w-4"><use href="#${icon}"/></svg></span>
      <div class="flex-1 text-[13.5px]"><div></div><div class="text-muted"></div></div>`;
    const [line1, line2] = $$('div > div', li);
    line1.textContent = `${ACTION_LABELS[action]} ${plant}${amount ? ` · ${amount}` : ''}`;
    line2.textContent = `Care log · ${when}`;
    $('#activityList').prepend(li);

    // Ticking a matching task already counts the action in the chart
    const matchingTask = action === 'water' ? $(`.task[data-plant="${plantId}"][data-task^="water"]`) : null;
    const countsToday = when !== 'Yesterday';
    if (matchingTask && countsToday && !matchingTask.classList.contains('is-done')) {
      matchingTask.dataset.care ||= 'water';
      setTaskDone(matchingTask, true);
    } else if (countsToday) {
      bumpCare(ACTION_CAT[action], 1);
    }

    toast(`${ACTION_LABELS[action]} ${plant}`, { icon, undo: () => li.remove() });
    logForm.reset();
  });

  // ---------- Initial render ----------
  renderChart();
  renderCareCard();
  renderCalendar();
  updateTaskStats();
  window.addEventListener('resize', hideTip);
})();
