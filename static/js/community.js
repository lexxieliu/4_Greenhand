// Posts feed (templates/community/post_list.html). Loads after shell.js.
// Like/save call the Django JSON endpoints (community:like / community:save);
// posting, commenting and reporting are regular POST forms.
(function () {
  const { $, $$, toast, csrfToken } = window.GH;

  // ---------- Composer ----------
  const body = $('#postBody');
  const count = $('#charCount');
  const autosize = () => { body.style.height = 'auto'; body.style.height = `${Math.min(body.scrollHeight, 320)}px`; };
  body.addEventListener('input', () => { count.textContent = `${body.value.length} / 2000`; autosize(); });

  const images = $('#postImages');
  const preview = $('#imagePreview');
  images.addEventListener('change', () => {
    const files = [...images.files].slice(0, 4);
    if (images.files.length > 4) toast('Only the first 4 photos will be posted', { icon: 'i-image' });
    preview.innerHTML = files.map((f) => `<img src="${URL.createObjectURL(f)}" alt="Selected photo preview" class="h-20 w-full rounded-lg object-cover" />`).join('');
    preview.classList.toggle('hidden', !files.length);
    preview.classList.toggle('grid', files.length > 0);
  });

  $$('[data-focus-composer]').forEach((a) => a.addEventListener('click', () => setTimeout(() => body.focus(), 300)));

  // ---------- Like / save (FR-52) ----------
  $$('[data-toggle-url]').forEach((btn) =>
    btn.addEventListener('click', async () => {
      const wasOn = btn.getAttribute('aria-pressed') === 'true';
      const counter = $('[data-count]', btn);
      // Optimistic update, rolled back if the request fails
      btn.setAttribute('aria-pressed', String(!wasOn));
      if (counter) counter.textContent = Number(counter.textContent) + (wasOn ? -1 : 1);
      try {
        const res = await fetch(btn.dataset.toggleUrl, { method: 'POST', headers: { 'X-CSRFToken': csrfToken(), 'X-Requested-With': 'fetch' } });
        if (!res.ok) throw new Error(res.status);
        const data = await res.json();
        btn.setAttribute('aria-pressed', String(data.active));
        if (counter) counter.textContent = data.count;
        if (btn.classList.contains('save-btn')) toast(data.active ? 'Saved to your posts' : 'Removed from saved', { icon: 'i-bookmark' });
      } catch {
        btn.setAttribute('aria-pressed', String(wasOn));
        if (counter) counter.textContent = Number(counter.textContent) + (wasOn ? 1 : -1);
        toast('Couldn’t update — check your connection', { icon: 'i-alert' });
      }
    })
  );

  // ---------- Comments ----------
  function setComments(post, open) {
    const panel = $('.comments', post);
    const btn = $('[data-toggle-comments]', post);
    panel.classList.toggle('hidden', !open);
    btn.setAttribute('aria-expanded', String(open));
  }
  $$('[data-toggle-comments]').forEach((btn) =>
    btn.addEventListener('click', () => {
      const post = btn.closest('[data-post]');
      const open = $('.comments', post).classList.contains('hidden');
      setComments(post, open);
      if (open) $('input[name="body"]', post).focus();
    })
  );
  // Open the thread when arriving at #post-N (e.g. after adding a comment)
  const target = location.hash.startsWith('#post-') && document.getElementById(location.hash.slice(1));
  if (target) setComments(target, true);

  // ---------- Copy link ----------
  $$('[data-copy-link]').forEach((btn) =>
    btn.addEventListener('click', async () => {
      const url = `${location.origin}${location.pathname}#${btn.closest('[data-post]').id}`;
      window.GH.closePopovers();
      try { await navigator.clipboard.writeText(url); toast('Link copied', { icon: 'i-share' }); }
      catch { toast('Couldn’t copy the link', { icon: 'i-alert' }); }
    })
  );

  // ---------- Report (FR-56) ----------
  const dialog = $('#reportDialog');
  const form = $('form', dialog);
  $$('[data-report]').forEach((btn) =>
    btn.addEventListener('click', () => {
      window.GH.closePopovers();
      form.reset();
      form.action = btn.dataset.report;
      dialog.showModal();
    })
  );
  $$('[data-close]', dialog).forEach((b) => b.addEventListener('click', () => dialog.close()));
  dialog.addEventListener('click', (e) => { if (e.target === dialog) dialog.close(); });
})();
