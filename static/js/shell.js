// Greenhand app shell, shared by every signed-in page (templates/layouts/app.html):
// header popovers, sidebar collapse / mobile drawer, notifications and toasts.
// Page scripts load after this file and use window.GH.

(function () {
  // "Today" comes from the server (<body data-today="YYYY-MM-DD">) so client dates match the data.
  const todayAttr = document.body.dataset.today;
  const TODAY = todayAttr ? new Date(`${todayAttr}T00:00:00`) : new Date();
  TODAY.setHours(0, 0, 0, 0);

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const desktop = window.matchMedia('(min-width: 1024px)');

  // ---------- Greeting & date ----------
  const hour = new Date().getHours();
  if ($('#greeting')) $('#greeting').textContent = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  if ($('#todayLabel')) $('#todayLabel').textContent = TODAY.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });
  $$('[data-year]').forEach((el) => (el.textContent = TODAY.getFullYear()));

  // ---------- Sidebar: collapse on desktop, drawer on mobile ----------
  const sidebarToggle = $('#sidebarToggle');
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch { /* storage unavailable */ } },
  };

  function syncToggleState() {
    const open = desktop.matches
      ? !document.body.classList.contains('sidebar-collapsed')
      : document.body.classList.contains('drawer-open');
    sidebarToggle.setAttribute('aria-expanded', String(open));
  }
  if (store.get('gh-sidebar') === 'collapsed') document.body.classList.add('sidebar-collapsed');

  sidebarToggle.addEventListener('click', () => {
    if (desktop.matches) {
      const collapsed = document.body.classList.toggle('sidebar-collapsed');
      store.set('gh-sidebar', collapsed ? 'collapsed' : 'open');
    } else {
      document.body.classList.toggle('drawer-open');
    }
    syncToggleState();
  });
  function closeDrawer() {
    document.body.classList.remove('drawer-open');
    syncToggleState();
  }
  $$('[data-close-drawer]').forEach((el) => el.addEventListener('click', closeDrawer));
  $$('#sidebar a').forEach((a) => a.addEventListener('click', () => { if (!desktop.matches) closeDrawer(); }));
  desktop.addEventListener('change', () => { document.body.classList.remove('drawer-open'); syncToggleState(); });
  syncToggleState();

  $$('.sub-toggle').forEach((btn) =>
    btn.addEventListener('click', () => {
      const open = btn.closest('.has-sub').classList.toggle('is-open');
      btn.setAttribute('aria-expanded', String(open));
    })
  );

  // ---------- Toasts ----------
  function toast(message, { undo, icon = 'i-check' } = {}) {
    const el = document.createElement('div');
    el.className = 'toast pointer-events-auto flex items-center gap-3 rounded-xl bg-ink py-2.5 pl-3.5 pr-2.5 text-[14px] text-white shadow-float';
    el.innerHTML = `<svg class="ic h-4 w-4 text-lime-300"><use href="#${icon}"/></svg><span></span>`;
    el.querySelector('span').textContent = message;
    if (undo) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'ml-1 inline-flex items-center gap-1 rounded-md px-2 py-1 text-[13px] font-medium text-lime-300 hover:bg-white/10';
      btn.innerHTML = '<svg class="ic h-3.5 w-3.5"><use href="#i-undo"/></svg>Undo';
      btn.addEventListener('click', () => { undo(); dismiss(); });
      el.appendChild(btn);
    }
    $('#toasts').appendChild(el);
    const timer = setTimeout(dismiss, 4500);
    function dismiss() {
      clearTimeout(timer);
      el.classList.add('is-leaving');
      setTimeout(() => el.remove(), 200);
    }
  }

  // ---------- Popovers (notifications, account, card menus) ----------
  function closePopovers(except) {
    $$('[data-popover]').forEach((p) => {
      if (p === except) return;
      $('[data-popover-trigger]', p).setAttribute('aria-expanded', 'false');
      $('.popover', p).classList.add('hidden');
    });
  }
  // Delegated so popovers rendered later by page scripts work too
  document.addEventListener('click', (e) => {
    const trigger = e.target.closest('[data-popover-trigger]');
    const inPanel = e.target.closest('[data-popover] .popover');
    if (inPanel) return;
    if (!trigger) return closePopovers();
    const p = trigger.closest('[data-popover]');
    const panel = $('.popover', p);
    const open = panel.classList.contains('hidden');
    closePopovers(p);
    panel.classList.toggle('hidden', !open);
    trigger.setAttribute('aria-expanded', String(open));
  });
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    closePopovers();
    closeDrawer();
  });

  // Sidebar "Notifications" link opens the header panel
  $$('[data-open-notifications]').forEach((a) =>
    a.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      closeDrawer();
      $('[aria-controls="notifPanel"]')?.click();
    })
  );

  // Server-rendered Django messages fade out on their own
  $$('.toast[data-autodismiss]').forEach((el, i) =>
    setTimeout(() => { el.classList.add('is-leaving'); setTimeout(() => el.remove(), 200); }, 4500 + i * 500)
  );

  // CSRF token for fetch() calls to Django views
  function csrfToken() {
    const m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : ($('[name=csrfmiddlewaretoken]')?.value || '');
  }

  $('#markAllRead')?.addEventListener('click', () => {
    $$('.notif[data-unread="true"]').forEach((n) => {
      n.dataset.unread = 'false';
      n.classList.remove('bg-leaf-soft/40');
      $('.notif-dot', n)?.remove();
    });
    $('#notifBadge')?.remove();
    $('#sideBadge')?.remove();
    $('[aria-controls="notifPanel"]').setAttribute('aria-label', 'Notifications');
  });

  window.GH = { TODAY, $, $$, toast, closePopovers, csrfToken };
})();
