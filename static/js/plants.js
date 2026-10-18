// Pick a Plant list (templates/plants/plant_list.html). The filter form is a plain GET form
// handled by apps.plants.views.plant_list; this only submits it automatically.
(function () {
  const form = document.getElementById('plantFilters');
  if (!form) return;

  // Drop empty fields so URLs stay short (/plants/?category=herb instead of ?q=&category=herb&…)
  form.addEventListener('submit', () => {
    form.querySelectorAll('input, select').forEach((el) => {
      if ((el.type === 'checkbox' && !el.checked) || (el.type !== 'checkbox' && !el.value)) el.disabled = true;
    });
  });
  const submit = () => form.requestSubmit();

  form.querySelectorAll('select, input[type="checkbox"]').forEach((el) => el.addEventListener('change', submit));

  let timer;
  const q = form.querySelector('input[name="q"]');
  q.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(submit, 450);
  });
  // Keep the caret at the end after the page reloads with a search term
  if (q.value) {
    q.focus();
    q.setSelectionRange(q.value.length, q.value.length);
  }
})();
