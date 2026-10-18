// Weather page (templates/weather/weather.html). Loads after shell.js.
// Hourly data arrives via {{ chart_data|json_script:"weather-data" }} → { hourly: [...], frost_c }.
// Temperature and rain are two charts sharing one time axis (no dual y-axis).

(function () {
  const { $, $$, toast } = window.GH;
  const DATA = JSON.parse(document.getElementById('weather-data').textContent);
  const H = DATA.hourly;
  const FROST = DATA.frost_c;
  const NS = 'http://www.w3.org/2000/svg';

  const tempSvg = $('#tempChart');
  const rainSvg = $('#rainChart');
  const tip = $('#wxTip');
  const box = $('#wxCharts');
  const PAD = { l: 34, r: 12 };

  const xAt = (i, w) => PAD.l + (i / (H.length - 1)) * (w - PAD.l - PAD.r);

  function draw() {
    const w = tempSvg.getBoundingClientRect().width;
    if (!w) return;

    // ---- Temperature ----
    const th = 200, top = 10, bottom = 24;
    const temps = H.map((p) => p.temp);
    const lo = Math.floor(Math.min(...temps, FROST) - 1);
    const hi = Math.ceil(Math.max(...temps) + 1);
    const y = (v) => top + (1 - (v - lo) / (hi - lo)) * (th - top - bottom);
    tempSvg.setAttribute('viewBox', `0 0 ${w} ${th}`);

    const ticks = [];
    const step = hi - lo > 12 ? 4 : 2;
    for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) ticks.push(v);

    const pts = H.map((p, i) => [xAt(i, w), y(p.temp)]);
    const line = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ');
    const base = th - bottom;

    // Day boundaries: label each midnight and the first point
    const dayMarks = H.map((p, i) => ({ i, p })).filter(({ p, i }) => i === 0 || p.label === 'Midnight');

    tempSvg.innerHTML = `
      <defs><linearGradient id="tg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f59e0b" stop-opacity=".22"/><stop offset="1" stop-color="#f59e0b" stop-opacity=".02"/></linearGradient></defs>
      ${ticks.map((v) => `<line x1="${PAD.l}" x2="${w - PAD.r}" y1="${y(v)}" y2="${y(v)}" stroke="#e4e9e4" stroke-width="1"/><text x="${PAD.l - 8}" y="${y(v) + 4}" text-anchor="end" font-size="11" fill="#5b6b60">${v}°</text>`).join('')}
      ${dayMarks.map(({ i, p }) => `<line x1="${xAt(i, w)}" x2="${xAt(i, w)}" y1="${top}" y2="${base}" stroke="#e4e9e4" stroke-dasharray="2 3"/><text x="${xAt(i, w) + 4}" y="${th - 6}" font-size="11" fill="#5b6b60">${p.day}${i === 0 ? ` ${p.label}` : ''}</text>`).join('')}
      <path d="${line} L${pts.at(-1)[0]} ${base} L${pts[0][0]} ${base} Z" fill="url(#tg)"/>
      <line x1="${PAD.l}" x2="${w - PAD.r}" y1="${y(FROST)}" y2="${y(FROST)}" stroke="#4f46e5" stroke-width="1.5" stroke-dasharray="5 4"/>
      <text x="${PAD.l + 6}" y="${y(FROST) - 6}" font-size="11" font-weight="500" fill="#4338ca">Frost ${FROST}°C</text>
      <path d="${line}" fill="none" stroke="#d97706" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
      ${pts.map((p, i) => (H[i].temp <= FROST + 0.5 ? `<circle cx="${p[0]}" cy="${p[1]}" r="4.5" fill="#4f46e5" stroke="#fff" stroke-width="2"/>` : '')).join('')}
      <line id="tCursor" x1="0" x2="0" y1="${top}" y2="${base}" stroke="#0b1a10" stroke-opacity=".35" visibility="hidden"/>
      <circle id="tDot" r="4.5" fill="#d97706" stroke="#fff" stroke-width="2" visibility="hidden"/>
    `;

    // ---- Rain ----
    const rh = 80, rTop = 6, rBottom = 4;
    const maxRain = Math.max(2, ...H.map((p) => p.precip_mm));
    rainSvg.setAttribute('viewBox', `0 0 ${w} ${rh}`);
    const bw = Math.max(4, ((w - PAD.l - PAD.r) / H.length) * 0.6);
    rainSvg.innerHTML = `
      <line x1="${PAD.l}" x2="${w - PAD.r}" y1="${rh - rBottom}" y2="${rh - rBottom}" stroke="#cfd8cf"/>
      <text x="${PAD.l - 8}" y="${rTop + 8}" text-anchor="end" font-size="11" fill="#5b6b60">${maxRain}</text>
      <text x="${PAD.l - 8}" y="${rh - rBottom}" text-anchor="end" font-size="11" fill="#5b6b60">0</text>
      ${H.map((p, i) => {
        if (!p.precip_mm) return '';
        const hgt = (p.precip_mm / maxRain) * (rh - rTop - rBottom);
        return `<rect x="${xAt(i, w) - bw / 2}" y="${rh - rBottom - hgt}" width="${bw}" height="${hgt}" rx="3" fill="#0ea5e9"/>`;
      }).join('')}
      <line id="rCursor" x1="0" x2="0" y1="${rTop}" y2="${rh - rBottom}" stroke="#0b1a10" stroke-opacity=".35" visibility="hidden"/>
    `;

    // ---- Shared hover (crosshair + tooltip) ----
    const step2 = (w - PAD.l - PAD.r) / (H.length - 1);
    [tempSvg, rainSvg].forEach((svg) => {
      const hit = document.createElementNS(NS, 'g');
      H.forEach((_, i) => {
        const r = document.createElementNS(NS, 'rect');
        r.setAttribute('x', xAt(i, w) - step2 / 2);
        r.setAttribute('y', 0);
        r.setAttribute('width', step2);
        r.setAttribute('height', svg === tempSvg ? th : rh);
        r.setAttribute('fill', 'transparent');
        r.addEventListener('mouseenter', () => show(i, w, y));
        hit.appendChild(r);
      });
      svg.appendChild(hit);
      svg.addEventListener('mouseleave', hide);
    });
  }

  function show(i, w, y) {
    const p = H[i];
    const x = xAt(i, w);
    ['#tCursor', '#rCursor'].forEach((id) => { const c = $(id); c.setAttribute('x1', x); c.setAttribute('x2', x); c.setAttribute('visibility', 'visible'); });
    const dot = $('#tDot');
    dot.setAttribute('cx', x);
    dot.setAttribute('cy', y(p.temp));
    dot.setAttribute('visibility', 'visible');
    tip.innerHTML = `<div class="font-medium">${p.day} · ${p.label}</div>
      <div class="mt-1 flex justify-between gap-4"><span class="text-white/70">Temperature</span><span class="tabular-nums">${p.temp} °C</span></div>
      <div class="flex justify-between gap-4"><span class="text-white/70">Rain</span><span class="tabular-nums">${p.precip_mm} mm</span></div>
      ${p.temp <= FROST ? '<div class="mt-1 text-indigo-200">Below frost threshold</div>' : ''}`;
    const bw = box.getBoundingClientRect().width;
    let left = x + 12;
    if (left + tip.offsetWidth > bw) left = x - tip.offsetWidth - 12;
    tip.style.left = `${left}px`;
    tip.style.top = '24px';
    tip.style.opacity = '1';
  }
  function hide() {
    tip.style.opacity = '0';
    ['#tCursor', '#rCursor', '#tDot'].forEach((id) => $(id)?.setAttribute('visibility', 'hidden'));
  }

  draw();
  let resizeTimer;
  window.addEventListener('resize', () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(draw, 120); });

  // Table view toggle (accessible reading of the same data)
  $('#wxTableToggle').addEventListener('click', (e) => {
    const table = $('#wxTable');
    const open = table.classList.toggle('hidden') === false;
    e.currentTarget.setAttribute('aria-expanded', String(open));
    e.currentTarget.querySelector('span').textContent = open ? 'Hide table' : 'View as table';
  });

  // ---------- 7-day low–high range bars ----------
  const rows = $$('#weekList [data-low]');
  const lows = rows.map((r) => +r.dataset.low);
  const highs = rows.map((r) => +r.dataset.high);
  const min = Math.min(...lows), max = Math.max(...highs);
  rows.forEach((r) => {
    const fill = $('.range-fill', r);
    fill.style.left = `${((+r.dataset.low - min) / (max - min)) * 100}%`;
    fill.style.width = `${Math.max(6, ((+r.dataset.high - +r.dataset.low) / (max - min)) * 100)}%`;
  });

  // ---------- Alerts ----------
  $$('[data-alert]').forEach((alert) => {
    const toggle = $('.alert-toggle', alert);
    toggle?.addEventListener('click', () => {
      const open = !alert.classList.contains('is-open');
      alert.classList.toggle('is-open', open);
      toggle.setAttribute('aria-expanded', String(open));
    });
    $$('.alert-step', alert).forEach((cb) =>
      cb.addEventListener('change', () => { $('.step-count', alert).textContent = $$('.alert-step', alert).filter((c) => c.checked).length; })
    );
    // Real endpoints: PATCH /api/weather/alerts/{id}/ (acknowledged_at / user_overrode)
    $('[data-alert-done]', alert)?.addEventListener('click', () => {
      alert.classList.add('is-dismissed');
      toast('Frost plan saved — we’ll remind you at sunset', { icon: 'i-snow', undo: () => alert.classList.remove('is-dismissed') });
    });
    $('[data-alert-ack]', alert)?.addEventListener('click', () => {
      alert.classList.add('is-dismissed');
      toast('Rain skip acknowledged', { icon: 'i-rain', undo: () => alert.classList.remove('is-dismissed') });
    });
    $('[data-alert-override]', alert)?.addEventListener('click', () => {
      alert.classList.add('is-dismissed');
      toast('Watering added back for today', { icon: 'i-drop', undo: () => alert.classList.remove('is-dismissed') });
    });
  });
})();
