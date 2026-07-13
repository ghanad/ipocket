import { SCROLL_KEY } from './shared.js';

export const createBulkEditController = ({ closeDrawer, isDrawerOpen }) => {
  const overlay = document.querySelector('[data-bulk-drawer-overlay]');
  const drawer = document.querySelector('[data-bulk-drawer]');
  const selection = document.querySelector('[data-bulk-drawer-selection]');
  const status = document.querySelector('[data-bulk-drawer-status]');
  const applyButton = document.querySelector('[data-bulk-drawer-apply]');
  const closeButton = document.querySelector('[data-bulk-drawer-close]');
  const cancelButton = document.querySelector('[data-bulk-drawer-cancel]');
  const commonTagsList = document.querySelector('[data-bulk-common-tags-list]');
  const commonTagsEmpty = document.querySelector('[data-bulk-common-tags-empty]');
  const removeHidden = document.querySelector('[data-bulk-remove-hidden]');
  const inputs = drawer ? drawer.querySelectorAll('[data-bulk-input]') : [];
  let isOpen = false;
  let removeTags = new Set();

  const syncRemoveHiddenInputs = () => {
    if (!removeHidden) {
      return;
    }
    removeHidden.replaceChildren();
    Array.from(removeTags).sort().forEach((tag) => {
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'remove_tags';
      input.value = tag;
      removeHidden.appendChild(input);
    });
  };

  const resetInputs = () => {
    inputs.forEach((input) => {
      if (input instanceof HTMLSelectElement) {
        if (input.multiple) {
          Array.from(input.options).forEach((option) => {
            option.selected = false;
          });
        } else {
          input.value = '';
        }
      } else if (input instanceof HTMLTextAreaElement) {
        input.value = '';
      } else if (input instanceof HTMLInputElement && input.type === 'checkbox') {
        input.checked = false;
      }
      input.dispatchEvent(new Event('change', { bubbles: true }));
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });
    removeTags = new Set();
    syncRemoveHiddenInputs();
  };

  const computeCommonBulkTags = (checkboxes) => {
    if (!checkboxes.length) {
      return [];
    }
    const tagSets = checkboxes.map((checkbox) => new Set(
      String(checkbox?.dataset?.bulkTags || '')
        .split(',')
        .map((tag) => tag.trim().toLowerCase())
        .filter(Boolean)
    ));
    const [first, ...rest] = tagSets;
    if (!first || first.size === 0) {
      return [];
    }
    return Array.from(first).filter((tag) => rest.every((entry) => entry.has(tag))).sort();
  };

  const renderCommonTags = (commonTags) => {
    if (!commonTagsList || !commonTagsEmpty) {
      return;
    }
    const commonSet = new Set(commonTags);
    removeTags = new Set(Array.from(removeTags).filter((tag) => commonSet.has(tag)));
    commonTagsList.replaceChildren();
    if (!commonTags.length) {
      commonTagsList.hidden = true;
      commonTagsEmpty.hidden = false;
      syncRemoveHiddenInputs();
      return;
    }
    commonTagsList.hidden = false;
    commonTagsEmpty.hidden = true;
    commonTags.forEach((tag) => {
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'tag tag-color bulk-common-tag-chip';
      chip.dataset.bulkRemoveTag = tag;
      chip.textContent = removeTags.has(tag) ? `${tag} ×` : tag;
      chip.classList.toggle('is-marked', removeTags.has(tag));
      commonTagsList.appendChild(chip);
    });
    syncRemoveHiddenInputs();
  };

  const close = () => {
    if (!overlay || !drawer) {
      return;
    }
    overlay.classList.remove('is-open');
    drawer.classList.remove('is-open');
    isOpen = false;
  };

  const open = () => {
    if (!overlay || !drawer) {
      return;
    }
    overlay.classList.add('is-open');
    drawer.classList.add('is-open');
    isOpen = true;
  };

  const bind = (root = document) => {
    const bulkForm = root.querySelector('[data-bulk-form]');
    if (!bulkForm || bulkForm.dataset.bulkBound) {
      return;
    }
    bulkForm.dataset.bulkBound = 'true';
    const selectAll = bulkForm.querySelector('[data-bulk-select-all]');
    const checkboxes = Array.from(bulkForm.querySelectorAll('[data-bulk-select]'));
    const countLabel = bulkForm.querySelector('[data-selected-count]');
    const openButton = bulkForm.querySelector('[data-bulk-open]');
    const controls = bulkForm.querySelector('[data-bulk-controls]');

    const updateCount = () => {
      const selected = checkboxes.filter((checkbox) => checkbox.checked);
      const selectedCount = selected.length;
      renderCommonTags(computeCommonBulkTags(selected));
      if (countLabel) countLabel.textContent = `${selectedCount} selected`;
      if (openButton) openButton.disabled = selectedCount === 0;
      if (applyButton) applyButton.disabled = selectedCount === 0;
      if (selection) selection.textContent = `${selectedCount} selected`;
      if (status) {
        status.textContent = selectedCount > 0
          ? `Select fields to update${removeTags.size ? ` • Remove ${removeTags.size} common tag(s)` : ''}`
          : 'Select at least one row';
      }
      controls?.classList.toggle('bulk-edit-controls-hidden', selectedCount === 0);
      if (selectedCount === 0 && isOpen) close();
      if (selectAll) {
        selectAll.indeterminate = selectedCount > 0 && selectedCount < checkboxes.length;
        selectAll.checked = selectedCount > 0 && selectedCount === checkboxes.length;
      }
    };

    selectAll?.addEventListener('change', () => {
      checkboxes.forEach((checkbox) => {
        checkbox.checked = selectAll.checked;
      });
      updateCount();
    });
    checkboxes.forEach((checkbox) => checkbox.addEventListener('change', updateCount));
    openButton?.addEventListener('click', () => {
      if (openButton.disabled) return;
      if (isDrawerOpen()) closeDrawer();
      resetInputs();
      open();
      const firstInput = drawer ? drawer.querySelector('.select, .input') : null;
      if (firstInput instanceof HTMLElement) {
        window.setTimeout(() => firstInput.focus(), 80);
      }
    });
    updateCount();
  };

  const handleRemoveTagClick = (trigger) => {
    const tag = (trigger.dataset.bulkRemoveTag || '').trim().toLowerCase();
    if (!tag) {
      return;
    }
    removeTags.has(tag) ? removeTags.delete(tag) : removeTags.add(tag);
    const bulkForm = document.querySelector('[data-bulk-form]');
    const selected = bulkForm
      ? Array.from(bulkForm.querySelectorAll('[data-bulk-select]')).filter((entry) => entry.checked)
      : [];
    renderCommonTags(computeCommonBulkTags(selected));
    if (status) {
      status.textContent = selected.length > 0
        ? `Select fields to update${removeTags.size ? ` • Remove ${removeTags.size} common tag(s)` : ''}`
        : 'Select at least one row';
    }
  };

  const bindGlobal = () => {
    overlay?.addEventListener('click', close);
    closeButton?.addEventListener('click', close);
    cancelButton?.addEventListener('click', close);
    const bulkForm = document.querySelector('[data-bulk-form]');
    if (bulkForm && window.sessionStorage) {
      bulkForm.addEventListener('submit', () => {
        window.sessionStorage.setItem(SCROLL_KEY, String(window.scrollY || 0));
      });
    }
  };

  return { bind, bindGlobal, close, handleRemoveTagClick, isOpen: () => isOpen };
};
