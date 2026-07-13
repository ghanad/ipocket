export const SCROLL_KEY = 'ipocket.ip-assets.scrollY';

export const getCurrentListUrl = () => window.location.pathname + window.location.search;

export const showToast = (message, type = 'info') => {
  const toastContainer = document.querySelector('[data-toast-container]');
  if (!toastContainer || !message) {
    return;
  }
  const toast = document.createElement('div');
  toast.classList.add('toast', `toast-${type}`);
  const text = document.createElement('span');
  text.classList.add('toast-message');
  text.textContent = message;
  const close = document.createElement('button');
  close.type = 'button';
  close.classList.add('toast-close');
  close.setAttribute('aria-label', 'Dismiss notification');
  close.innerHTML = '&times;';
  close.addEventListener('click', () => toast.remove());
  toast.append(text, close);
  toastContainer.appendChild(toast);
  window.setTimeout(() => toast.remove(), 4000);
};

export const readInputValue = (input) => {
  if (!input) {
    return '';
  }
  if (input.tagName === 'SELECT' && input.multiple) {
    return Array.from(input.selectedOptions)
      .map((option) => option.value.trim())
      .filter(Boolean)
      .sort()
      .join(',');
  }
  return (input.value || '').trim();
};

export const writeInputValue = (input, value) => {
  if (!input) {
    return;
  }
  if (input.tagName === 'SELECT' && input.multiple) {
    const selected = String(value || '')
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean);
    Array.from(input.options).forEach((option) => {
      option.selected = selected.includes(option.value);
    });
    input.dispatchEvent(new Event('change', { bubbles: true }));
    input.dispatchEvent(new Event('input', { bubbles: true }));
    return;
  }
  input.value = value || '';
};
