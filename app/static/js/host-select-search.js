(() => {
  const bindHostSearch = (field) => {
    const searchInput = field.querySelector('[data-ip-host-search]');
    const hostSelect = field.querySelector('select[name="host_id"]');
    const emptyMessage = field.querySelector('[data-ip-host-search-empty]');
    if (!searchInput || !hostSelect || searchInput.dataset.hostSearchBound) {
      return;
    }

    const filterOptions = () => {
      const term = (searchInput.value || '').trim().toLowerCase();
      let visibleHosts = 0;
      Array.from(hostSelect.options).forEach((option) => {
        const isBlank = option.value === '';
        const isSelected = option.selected;
        const haystack = `${option.textContent || ''} ${option.value || ''}`.toLowerCase();
        const matches = !term || haystack.includes(term);
        option.hidden = !isBlank && !isSelected && !matches;
        if (!isBlank && !option.hidden) {
          visibleHosts += 1;
        }
      });
      if (emptyMessage) {
        emptyMessage.hidden = visibleHosts > 0 || !term;
      }
    };

    searchInput.dataset.hostSearchBound = 'true';
    searchInput.addEventListener('input', filterOptions);
    hostSelect.addEventListener('change', filterOptions);
    filterOptions();
  };

  window.ipocketResetHostSearch = (root = document) => {
    const fields = root.matches && root.matches('[data-ip-host-field]')
      ? [root]
      : Array.from(root.querySelectorAll('[data-ip-host-field]'));
    fields.forEach((field) => {
      const searchInput = field.querySelector('[data-ip-host-search]');
      if (searchInput) {
        searchInput.value = '';
        searchInput.dispatchEvent(new Event('input', { bubbles: true }));
      }
    });
  };

  document.querySelectorAll('[data-ip-host-field]').forEach(bindHostSearch);
})();
