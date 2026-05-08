(() => {
  const selectedOptionLabel = (hostSelect) => {
    const selected = hostSelect.options[hostSelect.selectedIndex];
    return selected ? selected.textContent || '' : '';
  };

  const bindHostSearch = (field) => {
    const searchInput = field.querySelector('[data-ip-host-search]');
    const hostSelect = field.querySelector('select[name="host_id"]');
    const emptyMessage = field.querySelector('[data-ip-host-search-empty]');
    if (!searchInput || !hostSelect || searchInput.dataset.hostSearchBound) {
      return;
    }

    const wrapper = document.createElement('div');
    const dropdown = document.createElement('div');
    wrapper.className = 'host-select-combobox';
    dropdown.className = 'host-select-dropdown';
    dropdown.setAttribute('role', 'listbox');
    dropdown.hidden = true;
    searchInput.parentNode.insertBefore(wrapper, searchInput);
    wrapper.append(searchInput, dropdown);
    hostSelect.classList.add('host-select-native');
    searchInput.setAttribute('role', 'combobox');
    searchInput.setAttribute('aria-expanded', 'false');
    searchInput.setAttribute('aria-autocomplete', 'list');

    const closeDropdown = () => {
      dropdown.hidden = true;
      searchInput.setAttribute('aria-expanded', 'false');
      if (emptyMessage) {
        emptyMessage.hidden = true;
      }
    };

    const setSelectedValue = (value, label) => {
      hostSelect.value = value;
      searchInput.value = label;
      hostSelect.dispatchEvent(new Event('change', { bubbles: true }));
      hostSelect.dispatchEvent(new Event('input', { bubbles: true }));
      closeDropdown();
    };

    const renderOptions = () => {
      const term = (searchInput.value || '').trim().toLowerCase();
      const matches = Array.from(hostSelect.options).filter((option) => {
        const haystack = `${option.textContent || ''} ${option.value || ''}`.toLowerCase();
        return !term || haystack.includes(term);
      });

      dropdown.replaceChildren();
      matches.forEach((option) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'host-select-option';
        button.setAttribute('role', 'option');
        button.classList.toggle('is-selected', option.selected);
        button.textContent = option.textContent || '';
        button.addEventListener('mousedown', (event) => {
          event.preventDefault();
          setSelectedValue(option.value, option.textContent || '');
        });
        dropdown.appendChild(button);
      });

      const hasMatches = matches.length > 0;
      dropdown.hidden = !hasMatches;
      searchInput.setAttribute('aria-expanded', hasMatches ? 'true' : 'false');
      if (emptyMessage) {
        emptyMessage.hidden = hasMatches || !term;
      }
    };

    const syncSearchToSelection = () => {
      searchInput.value = selectedOptionLabel(hostSelect);
    };

    const selectFirstVisible = () => {
      const firstOption = dropdown.querySelector('.host-select-option');
      if (firstOption) {
        firstOption.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
      }
    };

    const handleKeydown = (event) => {
      if (event.key === 'Escape') {
        syncSearchToSelection();
        closeDropdown();
        return;
      }
      if (event.key === 'Enter') {
        event.preventDefault();
        selectFirstVisible();
      }
    };

    const handleBlur = () => {
      window.setTimeout(() => {
        syncSearchToSelection();
        closeDropdown();
      }, 120);
    };

    searchInput.dataset.hostSearchBound = 'true';
    searchInput.addEventListener('input', renderOptions);
    searchInput.addEventListener('focus', renderOptions);
    searchInput.addEventListener('keydown', handleKeydown);
    searchInput.addEventListener('blur', handleBlur);
    hostSelect.addEventListener('change', () => {
      syncSearchToSelection();
      renderOptions();
    });
    syncSearchToSelection();
  };

  const bindAll = (root = document) => {
    const fields = root.matches && root.matches('[data-ip-host-field]')
      ? [root]
      : Array.from(root.querySelectorAll('[data-ip-host-field]'));
    fields.forEach(bindHostSearch);
  };

  window.ipocketResetHostSearch = (root = document) => {
    bindAll(root);
    const fields = root.matches && root.matches('[data-ip-host-field]')
      ? [root]
      : Array.from(root.querySelectorAll('[data-ip-host-field]'));
    fields.forEach((field) => {
      const searchInput = field.querySelector('[data-ip-host-search]');
      const hostSelect = field.querySelector('select[name="host_id"]');
      if (searchInput && hostSelect) {
        searchInput.value = selectedOptionLabel(hostSelect);
        const emptyMessage = field.querySelector('[data-ip-host-search-empty]');
        const dropdown = field.querySelector('.host-select-dropdown');
        if (dropdown) {
          dropdown.hidden = true;
        }
        searchInput.setAttribute('aria-expanded', 'false');
        if (emptyMessage) {
          emptyMessage.hidden = true;
        }
      }
    });
  };

  bindAll();
})();
