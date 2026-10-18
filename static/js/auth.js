// Greenhand auth pages (login.html / register.html):
// password visibility toggle, password strength meter, inline validation, submit state.

(function () {
  // Forms post to Django (accounts:login / accounts:signup), which re-validates server-side.
  // Set DEMO_MODE to true only to preview the static prototype without a backend.
  const DEMO_MODE = false;

  const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
  const USERNAME_RE = /^[A-Za-z0-9_]{3,30}$/;

  // ---------- Password show / hide ----------
  document.querySelectorAll('[data-toggle-password]').forEach((btn) => {
    const input = document.getElementById(btn.dataset.togglePassword);
    const icon = btn.querySelector('use');
    btn.addEventListener('click', () => {
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      icon.setAttribute('href', show ? '#i-eye-off' : '#i-eye');
      btn.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
      btn.setAttribute('aria-pressed', String(show));
    });
  });

  // ---------- Password strength (register) ----------
  const strengthInput = document.querySelector('[data-strength]');
  const STRENGTH = [
    { label: '—', color: 'bg-line' },
    { label: 'Weak', color: 'bg-rose-500' },
    { label: 'Fair', color: 'bg-amber-500' },
    { label: 'Good', color: 'bg-lime-500' },
    { label: 'Strong', color: 'bg-leaf' },
  ];

  function passwordChecks(value) {
    return {
      length: value.length >= 8,
      letter: /[A-Za-z]/.test(value),
      number: /\d/.test(value),
      symbol: /[^A-Za-z0-9]/.test(value),
    };
  }

  function updateStrength() {
    const value = strengthInput.value;
    const checks = passwordChecks(value);

    document.querySelectorAll('.req').forEach((li) => {
      li.dataset.met = String(checks[li.dataset.req]);
    });

    let score = 0;
    if (value.length) {
      score = Object.values(checks).filter(Boolean).length;
      if (value.length >= 12 && score >= 3) score = 4;
      if (!checks.length) score = Math.min(score, 1);
    }

    const bars = document.querySelectorAll('.strength-bar span');
    bars.forEach((bar, i) => {
      STRENGTH.forEach((s) => bar.classList.remove(s.color));
      bar.classList.add(i < score ? STRENGTH[score].color : 'bg-line');
    });
    document.getElementById('strengthLabel').textContent = STRENGTH[score].label;
  }

  if (strengthInput) {
    strengthInput.addEventListener('input', updateStrength);
    updateStrength();
  }

  // ---------- Validation ----------
  function validate(input, formType) {
    const value = input.type === 'checkbox' ? input.checked : input.value.trim();

    switch (input.name) {
      case 'username':
        if (!value) return 'Choose a username.';
        if (!USERNAME_RE.test(value)) return 'Use 3–30 letters, numbers, or underscores.';
        return '';
      case 'email':
        if (!value) return 'Enter your email address.';
        if (!EMAIL_RE.test(value)) return 'That email doesn’t look right.';
        return '';
      case 'password': {
        if (!input.value) return formType === 'login' ? 'Enter your password.' : 'Create a password.';
        if (formType === 'register') {
          const c = passwordChecks(input.value);
          if (!c.length || !c.letter || !c.number) return 'Use 8+ characters with at least one letter and one number.';
        }
        return '';
      }
      case 'terms':
        return value ? '' : 'Please accept the Terms and Privacy Policy to continue.';
      default:
        return '';
    }
  }

  function showError(input, message) {
    const errorEl = document.getElementById(input.id + '-error');
    input.setAttribute('aria-invalid', message ? 'true' : 'false');
    if (!errorEl) return;
    errorEl.querySelector('span').textContent = message;
    errorEl.classList.toggle('is-shown', Boolean(message));
  }

  function setLoading(button, loading, text) {
    const label = button.querySelector('.btn-label');
    const arrow = button.querySelector('.btn-arrow');
    button.dataset.loading = String(loading);
    button.disabled = loading;
    if (loading) {
      button.dataset.original = label.textContent;
      label.textContent = text;
      arrow.classList.add('hidden');
      const spinner = document.createElement('span');
      spinner.className = 'btn-spinner';
      spinner.setAttribute('aria-hidden', 'true');
      button.prepend(spinner);
    } else {
      label.textContent = button.dataset.original || label.textContent;
      arrow.classList.remove('hidden');
      button.querySelector('.btn-spinner')?.remove();
    }
  }

  document.querySelectorAll('[data-auth-form]').forEach((form) => {
    const formType = form.dataset.authForm;
    const fields = Array.from(form.querySelectorAll('input[required]'));
    const submitBtn = form.querySelector('button[type="submit"]');
    const formError = document.getElementById('formError');

    fields.forEach((input) => {
      // Validate when leaving a field; once it has shown an error, re-check as the user types
      input.addEventListener('blur', () => {
        if (input.type !== 'checkbox' && !input.value) return;
        showError(input, validate(input, formType));
      });
      input.addEventListener(input.type === 'checkbox' ? 'change' : 'input', () => {
        if (input.getAttribute('aria-invalid') === 'true') showError(input, validate(input, formType));
        formError?.classList.add('hidden');
      });
    });

    form.addEventListener('submit', (e) => {
      let firstInvalid = null;
      fields.forEach((input) => {
        const message = validate(input, formType);
        showError(input, message);
        if (message && !firstInvalid) firstInvalid = input;
      });

      if (firstInvalid) {
        e.preventDefault();
        firstInvalid.focus();
        return;
      }

      if (!DEMO_MODE) {
        // Valid: show progress while the browser posts the form to Django
        setLoading(submitBtn, true, formType === 'login' ? 'Signing in…' : 'Creating account…');
        return;
      }

      e.preventDefault();
      setLoading(submitBtn, true, formType === 'login' ? 'Signing in…' : 'Creating account…');
      setTimeout(() => {
        window.location.href = formType === 'login' ? 'dashboard.html' : 'login.html?registered=1';
      }, 900);
    });
  });

  // Restore the button if the page is shown again from the back/forward cache
  window.addEventListener('pageshow', (e) => {
    if (!e.persisted) return;
    document.querySelectorAll('button[data-loading="true"]').forEach((b) => setLoading(b, false));
  });

  document.querySelectorAll('[data-year]').forEach((el) => (el.textContent = new Date().getFullYear()));
})();
