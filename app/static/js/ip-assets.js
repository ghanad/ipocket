(() => {
    const GLOBAL_FLAG = 'ipocketIpAssetsInitialized';
    const SCROLL_KEY = 'ipocket.ip-assets.scrollY';
    const overlay = document.querySelector('[data-ip-drawer-overlay]');
    const drawer = document.querySelector('[data-ip-drawer]');
    const drawerSubtitle = document.querySelector('[data-ip-drawer-subtitle]');
    const closeButton = document.querySelector('[data-ip-drawer-close]');
    const cancelButton = document.querySelector('[data-ip-drawer-cancel]');
    const saveButton = document.querySelector('[data-ip-drawer-save]');
    const form = document.querySelector('[data-ip-edit-form]');
    const projectPill = document.querySelector('[data-ip-drawer-project]');
    const hostPill = document.querySelector('[data-ip-drawer-host]');
    const dirtyStatus = document.querySelector('[data-ip-drawer-dirty]');
    const autoHostWrapper = document.querySelector('[data-ip-auto-host]');
    const autoHostButton = document.querySelector('[data-ip-auto-host-button]');
    const autoHostName = document.querySelector('[data-ip-auto-host-name]');
    const autoHostStatus = document.querySelector('[data-ip-auto-host-status]');
    const inputs = form ? form.querySelectorAll('[data-ip-input]') : [];
    const filterForm = document.querySelector('.filters-grid');
    const tagFilterInput = filterForm ? filterForm.querySelector('[data-tag-filter-input]') : null;
    const tagFilterSelected = filterForm ? filterForm.querySelector('[data-tag-filter-selected]') : null;
    const hostField = form ? form.querySelector('[data-ip-host-field]') : null;
    let initialValues = {};
    let currentAsset = null;
    let isOpen = false;

    const shouldShowHostField = (typeValue) => ['OS', 'BMC'].includes((typeValue || '').toUpperCase());
    const shouldShowAutoHost = (typeValue, hostValue) =>
      (typeValue || '').toUpperCase() === 'BMC' && !(hostValue || '').trim();

    const updateHostVisibility = () => {
      if (!hostField || !form) {
        return;
      }
      const typeInput = form.querySelector('[data-ip-input="type"]');
      const typeValue = typeInput ? typeInput.value : '';
      const showHost = shouldShowHostField(typeValue);
      hostField.style.display = showHost ? '' : 'none';
      if (!showHost) {
        const hostSelect = form.querySelector('[data-ip-input="host_id"]');
        if (hostSelect) {
          hostSelect.value = '';
        }
      }
      updateAutoHostVisibility();
    };

    const updateAutoHostVisibility = () => {
      if (!autoHostWrapper || !form) {
        return;
      }
      const typeInput = form.querySelector('[data-ip-input="type"]');
      const hostSelect = form.querySelector('[data-ip-input="host_id"]');
      const typeValue = typeInput ? typeInput.value : '';
      const hostValue = hostSelect ? hostSelect.value : '';
      const showAutoHost = shouldShowAutoHost(typeValue, hostValue);
      autoHostWrapper.classList.toggle('is-visible', showAutoHost);
      if (autoHostStatus) {
        autoHostStatus.textContent = '';
      }
    };

    const updateSaveState = () => {
      if (!dirtyStatus || !saveButton) {
        return;
      }
      const dirty = Array.from(inputs).some((input) => {
        const key = input.dataset.ipInput;
        return (input.value || '').trim() !== (initialValues[key] || '');
      });
      saveButton.disabled = !dirty;
      dirtyStatus.textContent = dirty ? 'Unsaved changes' : 'No changes';
    };

    const openDrawer = (assetData) => {
      if (!overlay || !drawer || !form || !drawerSubtitle || !projectPill || !hostPill) {
        return;
      }
      currentAsset = assetData;
      inputs.forEach((input) => {
        const key = input.dataset.ipInput;
        input.value = assetData[key] || '';
      });
      form.action = `/ui/ip-assets/${assetData.id}/edit`;
      drawerSubtitle.textContent = assetData.ip_address || '—';
      projectPill.textContent = `Project: ${assetData.project_label || 'Unassigned'}`;
      hostPill.textContent = `Host: ${assetData.host_label || '—'}`;
      updateHostVisibility();
      initialValues = {
        ip_address: assetData.ip_address || '',
        type: assetData.type || '',
        project_id: assetData.project_id || '',
        host_id: assetData.host_id || '',
        tags: assetData.tags || '',
        notes: assetData.notes || '',
      };
      updateSaveState();
      overlay.classList.add('is-open');
      drawer.classList.add('is-open');
      isOpen = true;
      if (autoHostName) {
        autoHostName.textContent = `server_${assetData.ip_address || 'IP'}`;
      }
      if (autoHostButton) {
        autoHostButton.disabled = false;
      }
      if (autoHostStatus) {
        autoHostStatus.textContent = '';
      }
    };

    const closeDrawer = () => {
      if (!overlay || !drawer) {
        return;
      }
      overlay.classList.remove('is-open');
      drawer.classList.remove('is-open');
      isOpen = false;
    };

    const confirmClose = () => {
      const dirty = Array.from(inputs).some((input) => {
        const key = input.dataset.ipInput;
        return (input.value || '').trim() !== (initialValues[key] || '');
      });
      if (!dirty) {
        closeDrawer();
        return;
      }
      if (window.confirm('Discard changes?')) {
        closeDrawer();
      }
    };

    const bindEditButtons = (root = document) => {
      const editButtons = root.querySelectorAll('[data-ip-edit]');
      editButtons.forEach((button) => {
        if (button.dataset.ipEditBound) {
          return;
        }
        button.dataset.ipEditBound = 'true';
        button.addEventListener('click', () => {
          const assetData = {
            id: button.dataset.ipEdit,
            ip_address: button.dataset.ipAddress || '',
            type: button.dataset.ipType || '',
            project_id: button.dataset.ipProjectId || '',
            project_label: button.dataset.ipProjectName || 'Unassigned',
            host_id: button.dataset.ipHostId || '',
            host_label: button.dataset.ipHostName || '—',
            notes: button.dataset.ipNotes || '',
            tags: button.dataset.ipTags || '',
          };
          openDrawer(assetData);
        });
      });
    };

    const bindDeleteDialogs = (root = document) => {
      const openButtons = root.querySelectorAll('[data-delete-dialog-id]');
      openButtons.forEach((button) => {
        if (button.dataset.deleteDialogBound) {
          return;
        }
        button.dataset.deleteDialogBound = 'true';
        button.addEventListener('click', () => {
          const dialog = document.getElementById(button.dataset.deleteDialogId);
          if (dialog && typeof dialog.showModal === 'function') {
            dialog.showModal();
          }
        });
      });

      const closeButtons = root.querySelectorAll('[data-close-delete-dialog]');
      closeButtons.forEach((button) => {
        if (button.dataset.closeDialogBound) {
          return;
        }
        button.dataset.closeDialogBound = 'true';
        button.addEventListener('click', () => {
          const dialog = button.closest('dialog');
          if (dialog) {
            dialog.close();
          }
        });
      });
    };

    const bindBulkEdit = (root = document) => {
      const bulkForm = root.querySelector('[data-bulk-form]');
      if (!bulkForm || bulkForm.dataset.bulkBound) {
        return;
      }
      bulkForm.dataset.bulkBound = 'true';
      const selectAll = bulkForm.querySelector('[data-bulk-select-all]');
      const checkboxes = Array.from(bulkForm.querySelectorAll('[data-bulk-select]'));
      const countLabel = bulkForm.querySelector('[data-selected-count]');
      const submitButton = bulkForm.querySelector('[data-bulk-submit]');
      const bulkControls = bulkForm.querySelector('[data-bulk-controls]');

      const updateCount = () => {
        const selectedCount = checkboxes.filter((checkbox) => checkbox.checked).length;
        if (countLabel) {
          countLabel.textContent = `${selectedCount} selected`;
        }
        if (submitButton) {
          submitButton.disabled = selectedCount === 0;
        }
        if (bulkControls) {
          bulkControls.classList.toggle('bulk-edit-controls-hidden', selectedCount === 0);
        }
        if (selectAll) {
          selectAll.indeterminate = selectedCount > 0 && selectedCount < checkboxes.length;
          selectAll.checked = selectedCount > 0 && selectedCount === checkboxes.length;
        }
      };

      if (selectAll) {
        selectAll.addEventListener('change', () => {
          const shouldCheck = selectAll.checked;
          checkboxes.forEach((checkbox) => {
            checkbox.checked = shouldCheck;
          });
          updateCount();
        });
      }

      checkboxes.forEach((checkbox) => {
        checkbox.addEventListener('change', () => {
          updateCount();
        });
      });

      updateCount();
    };

    const normalizeTagValue = (rawValue) => {
      const normalized = (rawValue || '').trim().toLowerCase();
      if (!normalized) {
        return '';
      }
      if (!/^[a-z0-9_-]+$/.test(normalized)) {
        return '';
      }
      return normalized;
    };

    const listSelectedTags = () => {
      if (!tagFilterSelected) {
        return [];
      }
      return Array.from(tagFilterSelected.querySelectorAll('input[name="tag"]')).map((input) => input.value);
    };

    const addTagFilter = (rawValue) => {
      if (!tagFilterSelected) {
        return false;
      }
      const value = normalizeTagValue(rawValue);
      if (!value) {
        return false;
      }
      if (listSelectedTags().includes(value)) {
        return false;
      }
      const entry = document.createElement('span');
      entry.className = 'tag-filter-entry';
      entry.dataset.tagFilterEntry = value;
      entry.innerHTML = `<input type="hidden" name="tag" value="${value}" /><button class="tag tag-color tag-filter-chip" type="button" data-remove-tag-filter="${value}">${value} ×</button>`;
      tagFilterSelected.appendChild(entry);
      return true;
    };

    const removeTagFilter = (value) => {
      if (!tagFilterSelected) {
        return false;
      }
      const entry = tagFilterSelected.querySelector(`[data-tag-filter-entry="${value}"]`);
      if (!entry) {
        return false;
      }
      entry.remove();
      return true;
    };

    const submitTagFilter = () => {
      if (!filterForm) {
        return;
      }
      if (window.htmx && typeof window.htmx.ajax === 'function') {
        const url = new URL(filterForm.action || '/ui/ip-assets', window.location.origin);
        const params = new URLSearchParams(new FormData(filterForm));
        url.search = params.toString();
        window.htmx.ajax('GET', url.toString(), {
          target: '#ip-table-container',
          swap: 'innerHTML',
          pushURL: url.pathname + (url.search ? `?${url.searchParams.toString()}` : ''),
        });
        return;
      }
      filterForm.submit();
    };

    const applyQuickFilter = (fieldName, value) => {
      if (!filterForm) {
        return;
      }
      const filterInput = filterForm.querySelector(`[name="${fieldName}"]`);
      if (!filterInput && fieldName !== 'tag') {
        return;
      }
      if (fieldName === 'tag') {
        const normalizedValue = normalizeTagValue(value);
        if (!normalizedValue) {
          return;
        }
        const changed = listSelectedTags().includes(normalizedValue)
          ? removeTagFilter(normalizedValue)
          : addTagFilter(normalizedValue);
        if (changed) {
          submitTagFilter();
        }
        return;
      }
      filterInput.value = value || '';
      if (window.htmx && typeof window.htmx.trigger === 'function') {
        window.htmx.trigger(filterInput, 'change');
        return;
      }
      filterForm.submit();
    };

    const createAutoHost = async () => {
      if (!currentAsset || !form || !autoHostButton) {
        return;
      }
      autoHostButton.disabled = true;
      if (autoHostStatus) {
        autoHostStatus.textContent = '';
      }
      try {
        const response = await fetch(`/ui/ip-assets/${currentAsset.id}/auto-host`, {
          method: 'POST',
          headers: {
            Accept: 'application/json',
          },
        });
        let payload = {};
        try {
          payload = await response.json();
        } catch (error) {
          payload = {};
        }
        if (!response.ok) {
          throw new Error(payload.error || 'Unable to create host.');
        }
        const hostSelect = form.querySelector('[data-ip-input="host_id"]');
        if (hostSelect) {
          const hostId = String(payload.host_id);
          let option = Array.from(hostSelect.options).find((entry) => entry.value === hostId);
          if (!option) {
            option = document.createElement('option');
            option.value = hostId;
            option.textContent = payload.host_name || `Host ${hostId}`;
            hostSelect.appendChild(option);
          }
          hostSelect.value = hostId;
        }
        if (hostPill) {
          hostPill.textContent = `Host: ${payload.host_name || '—'}`;
        }
        updateSaveState();
        updateAutoHostVisibility();
      } catch (error) {
        if (autoHostStatus) {
          autoHostStatus.textContent = error.message;
        }
      } finally {
        autoHostButton.disabled = false;
      }
    };

    if (!window[GLOBAL_FLAG]) {
      window[GLOBAL_FLAG] = true;
      if (typeof window !== 'undefined' && window.sessionStorage) {
        const storedScroll = window.sessionStorage.getItem(SCROLL_KEY);
        if (storedScroll) {
          window.scrollTo(0, Number.parseInt(storedScroll, 10) || 0);
          window.sessionStorage.removeItem(SCROLL_KEY);
        }
      }
      if (closeButton) {
        closeButton.addEventListener('click', confirmClose);
      }
      if (cancelButton) {
        cancelButton.addEventListener('click', confirmClose);
      }
      if (overlay) {
        overlay.addEventListener('click', confirmClose);
      }
      document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && isOpen) {
          confirmClose();
        }
      });
      inputs.forEach((input) => {
        input.addEventListener('input', () => {
          if (input.dataset.ipInput === 'type') {
            updateHostVisibility();
          }
          if (input.dataset.ipInput === 'host_id') {
            updateAutoHostVisibility();
          }
          updateSaveState();
        });
      });
      if (autoHostButton) {
        autoHostButton.addEventListener('click', createAutoHost);
      }
      updateHostVisibility();
      if (form && window.sessionStorage) {
        form.addEventListener('submit', () => {
          window.sessionStorage.setItem(SCROLL_KEY, String(window.scrollY || 0));
        });
      }
      if (tagFilterInput) {
        tagFilterInput.addEventListener('change', () => {
          if (addTagFilter(tagFilterInput.value)) {
            tagFilterInput.value = '';
            submitTagFilter();
          }
        });
        tagFilterInput.addEventListener('keydown', (event) => {
          if (event.key === 'Enter' || event.key === ',') {
            event.preventDefault();
            if (addTagFilter(tagFilterInput.value)) {
              tagFilterInput.value = '';
              submitTagFilter();
            }
          }
        });
      }

      document.body.addEventListener('htmx:afterSwap', (event) => {
        if (event.target && event.target.id === 'ip-table-container') {
          bindEditButtons(event.target);
          bindDeleteDialogs(event.target);
          bindBulkEdit(event.target);
        }
      });
      document.body.addEventListener('click', (event) => {
        const removeTagButton = event.target.closest('[data-remove-tag-filter]');
        if (removeTagButton) {
          event.preventDefault();
          if (removeTagFilter(removeTagButton.dataset.removeTagFilter || '')) {
            submitTagFilter();
          }
          return;
        }
        const trigger = event.target.closest('[data-quick-filter]');
        if (!trigger) {
          return;
        }
        event.preventDefault();
        applyQuickFilter(trigger.dataset.quickFilter, trigger.dataset.quickFilterValue || '');
      });
    }

    bindEditButtons();
    bindDeleteDialogs();
    bindBulkEdit();
  })();
