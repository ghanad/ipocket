export const createFiltersController = () => {
  const form = document.querySelector('.filters-grid');
  const input = form ? form.querySelector('[data-tag-filter-input]') : null;
  const selectedGroups = form ? form.querySelectorAll('[data-tag-filter-selected]') : [];
  const modeButtons = form ? form.querySelectorAll('[data-tag-filter-mode]') : [];
  const suggestions = form ? form.querySelector('[data-tag-filter-suggestions]') : null;
  let activeParam = 'tag_any';

  const normalizeTagValue = (rawValue) => {
    const normalized = (rawValue || '').trim().toLowerCase();
    if (!normalized || !/^[a-z0-9_-]+$/.test(normalized)) {
      return '';
    }
    return normalized;
  };

  const getSelectedGroup = (paramName = activeParam) => {
    if (!form) {
      return null;
    }
    return form.querySelector(`[data-tag-filter-selected="${paramName}"]`);
  };

  const listSelectedTags = (paramName = activeParam) => {
    const selectedGroup = getSelectedGroup(paramName);
    if (!selectedGroup) {
      return [];
    }
    return Array.from(selectedGroup.querySelectorAll(`input[name="${paramName}"]`))
      .map((entry) => entry.value);
  };

  const getTagColor = (rawValue) => {
    if (!suggestions) {
      return '';
    }
    const normalizedValue = normalizeTagValue(rawValue);
    if (!normalizedValue) {
      return '';
    }
    const option = Array.from(suggestions.options).find(
      (entry) => normalizeTagValue(entry.value) === normalizedValue
    );
    return option ? String(option.dataset.tagColor || '').trim() : '';
  };

  const applyTagFilterChipColor = (chip, rawValue) => {
    if (!(chip instanceof HTMLElement)) {
      return;
    }
    const color = getTagColor(rawValue);
    if (color) {
      chip.style.setProperty('--tag-color', color);
    }
    if (typeof window.ipocketApplyTagContrast === 'function') {
      window.ipocketApplyTagContrast(chip);
    }
  };

  const setActiveParam = (paramName) => {
    if (!['tag_any', 'tag_all', 'tag_not'].includes(paramName)) {
      return;
    }
    activeParam = paramName;
    modeButtons.forEach((button) => {
      button.classList.toggle('is-active', button.dataset.tagFilterMode === paramName);
    });
  };

  const addTagFilter = (rawValue, paramName = activeParam) => {
    const selectedGroup = getSelectedGroup(paramName);
    const value = normalizeTagValue(rawValue);
    if (!selectedGroup || !value || listSelectedTags(paramName).includes(value)) {
      return false;
    }
    const entry = document.createElement('span');
    entry.className = 'tag-filter-entry';
    entry.dataset.tagFilterEntry = `${paramName}:${value}`;
    entry.innerHTML = `<input type="hidden" name="${paramName}" value="${value}" /><button class="tag tag-color tag-filter-chip" type="button" data-remove-tag-filter="${value}" data-tag-filter-param="${paramName}">${value} ×</button>`;
    const chip = entry.querySelector(
      `[data-remove-tag-filter="${value}"][data-tag-filter-param="${paramName}"]`
    );
    applyTagFilterChipColor(chip, value);
    selectedGroup.appendChild(entry);
    return true;
  };

  const removeTagFilter = (value, paramName = activeParam) => {
    const entry = getSelectedGroup(paramName)?.querySelector(
      `[data-tag-filter-entry="${paramName}:${value}"]`
    );
    if (!entry) {
      return false;
    }
    entry.remove();
    return true;
  };

  const submit = () => {
    if (!form) {
      return;
    }
    if (window.htmx && typeof window.htmx.ajax === 'function') {
      const url = new URL(form.action || '/ui/ip-assets', window.location.origin);
      const params = new URLSearchParams(new FormData(form));
      url.search = params.toString();
      window.htmx.ajax('GET', url.toString(), {
        target: '#ip-table-container',
        swap: 'innerHTML',
        pushURL: url.pathname + (url.search ? `?${url.searchParams.toString()}` : ''),
      });
      return;
    }
    form.submit();
  };

  const applyQuickFilter = (fieldName, value) => {
    if (!form) {
      return;
    }
    const filterInput = form.querySelector(`[name="${fieldName}"]`);
    if (!filterInput && fieldName !== 'tag') {
      return;
    }
    if (fieldName === 'tag') {
      const normalizedValue = normalizeTagValue(value);
      if (!normalizedValue) {
        return;
      }
      const targetParam = activeParam;
      const changed = listSelectedTags(targetParam).includes(normalizedValue)
        ? removeTagFilter(normalizedValue, targetParam)
        : addTagFilter(normalizedValue, targetParam);
      if (changed) {
        submit();
      }
      return;
    }
    filterInput.value = value || '';
    if (window.htmx && typeof window.htmx.trigger === 'function') {
      window.htmx.trigger(filterInput, 'change');
      return;
    }
    form.submit();
  };

  const bind = () => {
    selectedGroups.forEach((group) => group.querySelectorAll('[data-remove-tag-filter]').forEach((chip) => {
      applyTagFilterChipColor(chip, chip.getAttribute('data-remove-tag-filter') || '');
    }));
    modeButtons.forEach((button) => {
      button.addEventListener('click', () => {
        setActiveParam(button.dataset.tagFilterMode || 'tag_any');
        input?.focus();
      });
    });
    if (!input) {
      return;
    }
    input.addEventListener('change', () => {
      if (addTagFilter(input.value)) {
        input.value = '';
        submit();
      }
    });
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ',') {
        event.preventDefault();
        if (addTagFilter(input.value)) {
          input.value = '';
          submit();
        }
      }
    });
  };

  return {
    applyQuickFilter,
    bind,
    removeFromTrigger: (trigger) => {
      const changed = removeTagFilter(
        trigger.dataset.removeTagFilter || '',
        trigger.dataset.tagFilterParam || 'tag_any'
      );
      if (changed) {
        submit();
      }
      return changed;
    },
  };
};
