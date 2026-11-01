// Calls the AI tutor (POST /tutor/api/ask/) for the dashboard chat and the My Garden drawer, and
// renders a result into a chat bubble. Load with data-endpoint="{% url 'tutor:api_ask' %}" on a page
// that has a {% csrf_token %}. Model text is only ever inserted with textContent.

(function () {
  const ENDPOINT = document.currentScript.dataset.endpoint;

  function csrfToken() {
    const field = document.querySelector('[name=csrfmiddlewaretoken]');
    return field ? field.value : '';
  }

  async function ask(question, plant) {
    try {
      const response = await fetch(ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
        body: JSON.stringify({ question, plant: plant || '' }),
      });
      return await response.json();
    } catch (err) {
      return { status: 'error', message: 'Could not reach the tutor. Check your connection and try again.' };
    }
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function fill(body, result) {
    body.textContent = '';
    if (result.status === 'refused') {
      body.append(el('p', '', `I can only help with plants and gardening. ${result.reason || ''}`));
      return;
    }
    if (result.status !== 'answer') {
      body.append(el('p', 'text-amber-200', result.message || 'Something went wrong. Please try again.'));
      return;
    }
    body.append(el('p', '', result.answer));
    if (result.steps.length) {
      const steps = el('ol', 'mt-2 list-decimal space-y-1 pl-5');
      result.steps.forEach((step) => steps.append(el('li', '', step)));
      body.append(steps);
    }
    if (result.safety_warning) body.append(el('p', 'mt-2 rounded-lg bg-amber-300/15 p-2 text-[12px] text-amber-100', `Safety: ${result.safety_warning}`));
    const cited = result.sources.filter((s) => s.cited);
    const basedOn = (cited.length ? cited : result.sources).map((s) => s.title).join(' · ');
    body.append(el('p', 'mt-2 text-[11.5px] text-emerald-50/55', result.grounded ? `Based on: ${basedOn}` : 'No Greenhand guide matched — general advice, please double-check.'));
    body.append(el('p', 'mt-1 text-[11px] text-emerald-50/40', `${result.disclaimer} · ${(result.latency_ms / 1000).toFixed(1)} s`));
  }

  window.GHTutor = { ask, fill };
})();
