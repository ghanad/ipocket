(() => {
  const GLOBAL_FLAG = 'ipocketIpAssetsInitialized';
  const SCROLL_KEY = 'ipocket.ip-assets.scrollY';
  const overlay = document.querySelector('[data-ip-drawer-overlay]');
  const drawer = document.querySelector('[data-ip-drawer]');
  const drawerTitle = document.querySelector('[data-ip-drawer-title]');
  const drawerSubtitle = document.querySelector('[data-ip-drawer-subtitle]');
  const closeButton = document.querySelector('[data-ip-drawer-close]');
  const cancelButton = document.querySelector('[data-ip-drawer-cancel]');
  const saveButton = document.querySelector('[data-ip-drawer-save]');
  const deleteButton = document.querySelector('[data-ip-drawer-delete]');
  const form = document.querySelector('[data-ip-edit-form]');
  const deleteForm = document.querySelector('[data-ip-delete-form]');
  const deleteReturnTo = document.querySelector('[data-ip-delete-return-to]');
  const deleteAddress = document.querySelector('[data-ip-delete-address]');
  const deleteProject = document.querySelector('[data-ip-delete-project]');
  const deleteType = document.querySelector('[data-ip-delete-type]');
  const deleteHost = document.querySelector('[data-ip-delete-host]');
  const deleteAck = document.querySelector('[data-ip-delete-ack]');
  const deleteConfirmWrap = document.querySelector('[data-ip-delete-confirm-wrap]');
  const deleteConfirmInput = document.querySelector('[data-ip-delete-confirm-input]');
  const deleteError = document.querySelector('[data-ip-delete-error]');
  const bulkOverlay = document.querySelector('[data-bulk-drawer-overlay]');
  const bulkDrawer = document.querySelector('[data-bulk-drawer]');
  const bulkDrawerSelection = document.querySelector('[data-bulk-drawer-selection]');
  const bulkDrawerStatus = document.querySelector('[data-bulk-drawer-status]');
  const bulkDrawerApply = document.querySelector('[data-bulk-drawer-apply]');
  const bulkDrawerClose = document.querySelector('[data-bulk-drawer-close]');
  const bulkDrawerCancel = document.querySelector('[data-bulk-drawer-cancel]');
  const bulkCommonTagsList = document.querySelector('[data-bulk-common-tags-list]');
  const bulkCommonTagsEmpty = document.querySelector('[data-bulk-common-tags-empty]');
  const bulkRemoveHidden = document.querySelector('[data-bulk-remove-hidden]');
  const bulkInputs = bulkDrawer ? bulkDrawer.querySelectorAll('[data-bulk-input]') : [];
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
  const tagFilterSuggestions = filterForm
    ? filterForm.querySelector('[data-tag-filter-suggestions]')
    : null;
  const hostField = form ? form.querySelector('[data-ip-host-field]') : null;
  const ipAddressInput = form ? form.querySelector('[data-ip-input="ip_address"]') : null;
  const toastContainer = document.querySelector('[data-toast-container]');
  let initialValues = {};
  let currentAsset = null;
  let isOpen = false;
  let isBulkDrawerOpen = false;
  let bulkRemoveTags = new Set();
  let isAddMode = false;
  let isDeleteMode = false;
  let activeTagsPopoverTrigger = null;
  let tagsPopover = null;
  let tagsPopoverOpenTimer = null;
  let tagsPopoverCloseTimer = null;
  const getCurrentListUrl = () => window.location.pathname + window.location.search;

  const syncEditReturnTo = () => {
    if (!form) {
      return;
    }
    const returnToInput = form.querySelector('input[name="return_to"]');
    if (returnToInput) {
      returnToInput.value = getCurrentListUrl();
    }
  };

  const shouldShowHostField = (typeValue) => ['OS', 'BMC'].includes((typeValue || '').toUpperCase());
  const shouldShowAutoHost = (typeValue, hostValue) =>
    (typeValue || '').toUpperCase() === 'BMC' && !(hostValue || '').trim();

  const isHighRiskDelete = (assetData) => {
    const normalizedTags = (assetData.tags || '')
      .split(',')
      .map((tag) => tag.trim().toLowerCase())
      .filter(Boolean);
    return Boolean(
      (assetData.project_id || '').trim() ||
      (assetData.host_id || '').trim() ||
      (assetData.type || '').toUpperCase() === 'VIP' ||
      normalizedTags.some((tag) => ['prod', 'production', 'critical', 'flagged'].includes(tag))
    );
  };

  const showToast = (message, type = 'info') => {
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

  const readInputValue = (input) => {
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

  const writeInputValue = (input, value) => {
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

  const ensureTagsPopover = () => {
    if (tagsPopover) {
      return tagsPopover;
    }
    tagsPopover = document.createElement('section');
    tagsPopover.className = 'ip-tags-popover';
    tagsPopover.setAttribute('role', 'dialog');
    tagsPopover.setAttribute('aria-modal', 'false');
    tagsPopover.hidden = true;
    tagsPopover.innerHTML = `
      <header class="ip-tags-popover-header">
        <h3 class="ip-tags-popover-title" data-tags-popover-title></h3>
        <button type="button" class="ip-tags-popover-close" data-tags-popover-close aria-label="Close tags popover">✕</button>
      </header>
      <label class="field ip-tags-popover-search-field">
        <span class="visually-hidden">Search tags</span>
        <input class="input" type="search" placeholder="Filter tags" data-tags-popover-search />
      </label>
      <div class="ip-tags-popover-list" data-tags-popover-list></div>
    `;
    document.body.appendChild(tagsPopover);
    const closeButton = tagsPopover.querySelector('[data-tags-popover-close]');
    if (closeButton) {
      closeButton.addEventListener('click', () => closeTagsPopover());
    }
    const searchInput = tagsPopover.querySelector('[data-tags-popover-search]');
    if (searchInput) {
      searchInput.addEventListener('input', renderTagsPopoverList);
    }
    tagsPopover.addEventListener('mouseenter', () => {
      if (tagsPopoverCloseTimer) {
        window.clearTimeout(tagsPopoverCloseTimer);
        tagsPopoverCloseTimer = null;
      }
    });
    tagsPopover.addEventListener('mouseleave', () => {
      scheduleCloseTagsPopover();
    });
    return tagsPopover;
  };

  const scheduleOpenTagsPopover = (trigger, delay = 120) => {
    if (!trigger) {
      return;
    }
    if (tagsPopoverCloseTimer) {
      window.clearTimeout(tagsPopoverCloseTimer);
      tagsPopoverCloseTimer = null;
    }
    if (tagsPopoverOpenTimer) {
      window.clearTimeout(tagsPopoverOpenTimer);
      tagsPopoverOpenTimer = null;
    }
    tagsPopoverOpenTimer = window.setTimeout(() => {
      openTagsPopover(trigger, { focusSearch: false });
      tagsPopoverOpenTimer = null;
    }, delay);
  };

  const scheduleCloseTagsPopover = (delay = 180) => {
    if (tagsPopoverOpenTimer) {
      window.clearTimeout(tagsPopoverOpenTimer);
      tagsPopoverOpenTimer = null;
    }
    if (tagsPopoverCloseTimer) {
      window.clearTimeout(tagsPopoverCloseTimer);
      tagsPopoverCloseTimer = null;
    }
    tagsPopoverCloseTimer = window.setTimeout(() => {
      closeTagsPopover();
      tagsPopoverCloseTimer = null;
    }, delay);
  };

  const closeTagsPopover = () => {
    if (tagsPopoverOpenTimer) {
      window.clearTimeout(tagsPopoverOpenTimer);
      tagsPopoverOpenTimer = null;
    }
    if (tagsPopoverCloseTimer) {
      window.clearTimeout(tagsPopoverCloseTimer);
      tagsPopoverCloseTimer = null;
    }
    if (activeTagsPopoverTrigger) {
      activeTagsPopoverTrigger.setAttribute('aria-expanded', 'false');
    }
    activeTagsPopoverTrigger = null;
    if (tagsPopover) {
      tagsPopover.hidden = true;
      tagsPopover.dataset.tagsPopoverItems = '[]';
    }
  };

  const parseTagsPopoverItems = () => {
    if (!tagsPopover) {
      return [];
    }
    try {
      const parsed = JSON.parse(tagsPopover.dataset.tagsPopoverItems || '[]');
      return Array.isArray(parsed) ? parsed : [];
    } catch (error) {
      return [];
    }
  };

  const renderTagsPopoverList = () => {
    if (!tagsPopover) {
      return;
    }
    const list = tagsPopover.querySelector('[data-tags-popover-list]');
    const searchInput = tagsPopover.querySelector('[data-tags-popover-search]');
    if (!list) {
      return;
    }
    const term = ((searchInput && searchInput.value) || '').trim().toLowerCase();
    const items = parseTagsPopoverItems().filter((item) => {
      const name = String(item?.name || '').toLowerCase();
      return !term || name.includes(term);
    });
    list.replaceChildren();
    if (!items.length) {
      const emptyMessage = document.createElement('p');
      emptyMessage.className = 'muted ip-tags-popover-empty';
      emptyMessage.textContent = 'No matching tags.';
      list.appendChild(emptyMessage);
      return;
    }
    items.forEach((item) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'tag tag-color tag-filter-chip';
      button.dataset.quickFilter = 'tag';
      button.dataset.quickFilterValue = String(item?.name || '');
      button.style.setProperty('--tag-color', String(item?.color || '#94a3b8'));
      if (typeof window.ipocketApplyTagContrast === 'function') {
        window.ipocketApplyTagContrast(button);
      }
      button.textContent = String(item?.name || '');
      list.appendChild(button);
    });
  };

  const positionTagsPopover = () => {
    if (!tagsPopover || !activeTagsPopoverTrigger || tagsPopover.hidden) {
      return;
    }
    const gutter = 12;
    const rect = activeTagsPopoverTrigger.getBoundingClientRect();
    const popoverWidth = Math.min(window.innerWidth - gutter * 2, window.innerWidth < 640 ? window.innerWidth - 16 : 340);
    tagsPopover.style.width = `${popoverWidth}px`;
    tagsPopover.style.maxWidth = `${popoverWidth}px`;
    const popoverRect = tagsPopover.getBoundingClientRect();
    const availableBelow = window.innerHeight - rect.bottom;
    const top = availableBelow > popoverRect.height + gutter
      ? rect.bottom + 6
      : rect.top - popoverRect.height - 6;
    const clampedTop = Math.min(window.innerHeight - popoverRect.height - gutter, Math.max(gutter, top));
    const left = Math.min(window.innerWidth - popoverRect.width - gutter, Math.max(gutter, rect.left));
    tagsPopover.style.top = `${clampedTop + window.scrollY}px`;
    tagsPopover.style.left = `${left + window.scrollX}px`;
  };

  const openTagsPopover = (trigger, { focusSearch = true } = {}) => {
    if (!trigger) {
      return;
    }
    ensureTagsPopover();
    if (!tagsPopover) {
      return;
    }
    const rawItems = trigger.dataset.tagsJson || '[]';
    let items = [];
    try {
      const parsed = JSON.parse(rawItems);
      if (Array.isArray(parsed)) {
        items = parsed;
      }
    } catch (error) {
      items = [];
    }
    const ipAddress = trigger.dataset.tagsIp || 'IP';
    const title = tagsPopover.querySelector('[data-tags-popover-title]');
    const searchInput = tagsPopover.querySelector('[data-tags-popover-search]');
    if (activeTagsPopoverTrigger && activeTagsPopoverTrigger !== trigger) {
      activeTagsPopoverTrigger.setAttribute('aria-expanded', 'false');
    }
    activeTagsPopoverTrigger = trigger;
    activeTagsPopoverTrigger.setAttribute('aria-expanded', 'true');
    tagsPopover.dataset.tagsPopoverItems = JSON.stringify(items);
    if (title) {
      title.textContent = `Tags for ${ipAddress}`;
    }
    if (searchInput) {
      searchInput.value = '';
    }
    tagsPopover.hidden = false;
    renderTagsPopoverList();
    positionTagsPopover();
    if (searchInput && focusSearch) {
      searchInput.focus();
    }
  };

  const setDrawerMode = (mode) => {
    const normalizedMode = mode === 'delete' ? 'delete' : 'edit';
    isDeleteMode = normalizedMode === 'delete';
    if (drawer) {
      drawer.dataset.ipDrawerMode = normalizedMode;
      drawer.setAttribute('aria-label', normalizedMode === 'delete' ? 'Delete IP asset' : 'Edit IP asset');
    }
    if (form) {
      form.hidden = isDeleteMode;
      form.style.display = isDeleteMode ? 'none' : 'flex';
    }
    if (deleteForm) {
      deleteForm.hidden = !isDeleteMode;
      deleteForm.style.display = isDeleteMode ? 'flex' : 'none';
    }
    if (saveButton) {
      saveButton.hidden = isDeleteMode;
      saveButton.style.display = isDeleteMode ? 'none' : '';
      saveButton.disabled = isDeleteMode ? true : saveButton.disabled;
    }
    if (deleteButton) {
      deleteButton.hidden = !isDeleteMode;
      deleteButton.style.display = isDeleteMode ? '' : 'none';
    }
  };

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
      return readInputValue(input) !== (initialValues[key] || '');
    });
    saveButton.disabled = !dirty;
    if (isAddMode) {
      dirtyStatus.textContent = dirty ? 'Ready to create' : 'Enter details';
      return;
    }
    dirtyStatus.textContent = dirty ? 'Unsaved changes' : 'No changes';
  };

  const openBaseDrawer = () => {
    if (!overlay || !drawer) {
      return;
    }
    overlay.classList.add('is-open');
    drawer.classList.add('is-open');
    isOpen = true;
  };

  const openBulkDrawer = () => {
    if (!bulkOverlay || !bulkDrawer) {
      return;
    }
    bulkOverlay.classList.add('is-open');
    bulkDrawer.classList.add('is-open');
    isBulkDrawerOpen = true;
  };

  const resetBulkInputs = () => {
    bulkInputs.forEach((input) => {
      if (!(input instanceof HTMLSelectElement)) {
        return;
      }
      if (input.multiple) {
        Array.from(input.options).forEach((option) => {
          option.selected = false;
        });
      } else {
        input.value = '';
      }
      input.dispatchEvent(new Event('change', { bubbles: true }));
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });
    bulkRemoveTags = new Set();
    syncBulkRemoveHiddenInputs();
  };

  const parseBulkTags = (checkbox) =>
    String(checkbox?.dataset?.bulkTags || '')
      .split(',')
      .map((tag) => tag.trim().toLowerCase())
      .filter(Boolean);

  const computeCommonBulkTags = (checkboxes) => {
    if (!checkboxes.length) {
      return [];
    }
    const tagSets = checkboxes.map((checkbox) => new Set(parseBulkTags(checkbox)));
    const [first, ...rest] = tagSets;
    if (!first || first.size === 0) {
      return [];
    }
    const common = Array.from(first).filter((tag) =>
      rest.every((entry) => entry.has(tag))
    );
    return common.sort();
  };

  const syncBulkRemoveHiddenInputs = () => {
    if (!bulkRemoveHidden) {
      return;
    }
    bulkRemoveHidden.replaceChildren();
    Array.from(bulkRemoveTags)
      .sort()
      .forEach((tag) => {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'remove_tags';
        input.value = tag;
        bulkRemoveHidden.appendChild(input);
      });
  };

  const renderBulkCommonTags = (commonTags) => {
    if (!bulkCommonTagsList || !bulkCommonTagsEmpty) {
      return;
    }
    const commonSet = new Set(commonTags);
    bulkRemoveTags = new Set(Array.from(bulkRemoveTags).filter((tag) => commonSet.has(tag)));
    bulkCommonTagsList.replaceChildren();
    if (!commonTags.length) {
      bulkCommonTagsList.hidden = true;
      bulkCommonTagsEmpty.hidden = false;
      syncBulkRemoveHiddenInputs();
      return;
    }
    bulkCommonTagsList.hidden = false;
    bulkCommonTagsEmpty.hidden = true;
    commonTags.forEach((tag) => {
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'tag tag-color bulk-common-tag-chip';
      chip.dataset.bulkRemoveTag = tag;
      chip.textContent = bulkRemoveTags.has(tag) ? `${tag} ×` : tag;
      chip.classList.toggle('is-marked', bulkRemoveTags.has(tag));
      bulkCommonTagsList.appendChild(chip);
    });
    syncBulkRemoveHiddenInputs();
  };

  const closeBulkDrawer = () => {
    if (!bulkOverlay || !bulkDrawer) {
      return;
    }
    bulkOverlay.classList.remove('is-open');
    bulkDrawer.classList.remove('is-open');
    isBulkDrawerOpen = false;
  };

  const openDrawer = (assetData) => {
    if (!form || !drawerSubtitle || !projectPill || !hostPill || !drawerTitle) {
      return;
    }
    closeBulkDrawer();
    setDrawerMode('edit');
    isAddMode = false;
    currentAsset = assetData;
    inputs.forEach((input) => {
      const key = input.dataset.ipInput;
      writeInputValue(input, assetData[key] || '');
    });
    form.action = `/ui/ip-assets/${assetData.id}/edit`;
    syncEditReturnTo();
    if (ipAddressInput) {
      ipAddressInput.readOnly = true;
    }
    saveButton.textContent = 'Save changes';
    drawerTitle.textContent = 'Edit IP asset';
    drawerSubtitle.textContent = assetData.ip_address || '—';
    projectPill.textContent = `Project: ${assetData.project_label || 'Unassigned'}`;
    hostPill.textContent = `Host: ${assetData.host_label || '—'}`;
    updateHostVisibility();
    initialValues = {
      ip_address: assetData.ip_address || '',
      type: assetData.type || '',
      project_id: assetData.project_id || '',
      host_id: assetData.host_id || '',
      tags: String(assetData.tags || '')
        .split(',')
        .map((tag) => tag.trim())
        .filter(Boolean)
        .sort()
        .join(','),
      notes: assetData.notes || '',
    };
    updateSaveState();
    openBaseDrawer();
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

  const openDrawerForDelete = (assetData) => {
    if (!drawerTitle || !drawerSubtitle || !projectPill || !hostPill || !deleteForm || !deleteButton) {
      return;
    }
    closeBulkDrawer();
    setDrawerMode('delete');
    isAddMode = false;
    currentAsset = assetData;
    drawerTitle.textContent = 'Delete IP asset?';
    drawerSubtitle.textContent = 'Permanent and cannot be undone.';
    projectPill.textContent = `Project: ${assetData.project_label || 'Unassigned'}`;
    hostPill.textContent = `Host: ${assetData.host_label || '—'}`;
    if (deleteAddress) {
      deleteAddress.textContent = assetData.ip_address || '—';
    }
    if (deleteProject) {
      deleteProject.textContent = assetData.project_label || 'Unassigned';
    }
    if (deleteType) {
      deleteType.textContent = assetData.type || '—';
    }
    if (deleteHost) {
      deleteHost.textContent = assetData.host_label || '—';
    }
    deleteForm.action = `/ui/ip-assets/${assetData.id}/delete`;
    if (deleteReturnTo) {
      deleteReturnTo.value = getCurrentListUrl();
    }
    if (deleteAck) {
      deleteAck.checked = false;
    }
    if (deleteConfirmInput) {
      deleteConfirmInput.value = '';
    }
    if (deleteError) {
      deleteError.textContent = '';
    }
    const needsTypedConfirmation = isHighRiskDelete(assetData);
    if (deleteConfirmWrap) {
      deleteConfirmWrap.hidden = !needsTypedConfirmation;
    }
    deleteButton.disabled = true;
    dirtyStatus.textContent = 'Confirm deletion';
    openBaseDrawer();
  };

  const openDrawerForAdd = () => {
    if (!form || !drawerSubtitle || !projectPill || !hostPill || !drawerTitle) {
      return;
    }
    closeBulkDrawer();
    setDrawerMode('edit');
    isAddMode = true;
    currentAsset = null;
    inputs.forEach((input) => {
      const key = input.dataset.ipInput;
      if (key === 'type') {
        input.value = 'VM';
        return;
      }
      writeInputValue(input, '');
    });
    if (ipAddressInput) {
      ipAddressInput.readOnly = false;
    }
    form.action = '/ui/ip-assets/new';
    syncEditReturnTo();
    drawerTitle.textContent = 'Add IP asset';
    drawerSubtitle.textContent = 'Create a new IP assignment';
    projectPill.textContent = 'Project: Unassigned';
    hostPill.textContent = 'Host: —';
    saveButton.textContent = 'Create IP';
    initialValues = {
      ip_address: '',
      type: 'VM',
      project_id: '',
      host_id: '',
      tags: '',
      notes: '',
    };
    updateHostVisibility();
    updateSaveState();
    openBaseDrawer();
    if (autoHostName) {
      autoHostName.textContent = 'server_IP';
    }
    if (autoHostStatus) {
      autoHostStatus.textContent = '';
    }
    if (ipAddressInput) {
      setTimeout(() => ipAddressInput.focus(), 100);
    }
  };

  const closeDrawer = () => {
    if (!overlay || !drawer) {
      return;
    }
    overlay.classList.remove('is-open');
    drawer.classList.remove('is-open');
    isOpen = false;
    isAddMode = false;
    setDrawerMode('edit');
  };

  const confirmClose = () => {
    if (isDeleteMode) {
      closeDrawer();
      return;
    }
    const dirty = Array.from(inputs).some((input) => {
      const key = input.dataset.ipInput;
      return readInputValue(input) !== (initialValues[key] || '');
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

  const bindDeleteButtons = (root = document) => {
    const deleteButtons = root.querySelectorAll('[data-ip-delete]');
    deleteButtons.forEach((button) => {
      if (button.dataset.ipDeleteBound) {
        return;
      }
      button.dataset.ipDeleteBound = 'true';
      button.addEventListener('click', () => {
        openDrawerForDelete({
          id: button.dataset.ipDelete,
          ip_address: button.dataset.ipAddress || '',
          type: button.dataset.ipType || '',
          project_label: button.dataset.ipProjectName || 'Unassigned',
          host_label: button.dataset.ipHostName || '—',
          tags: button.dataset.ipTags || '',
          project_id: button.dataset.ipProjectId || '',
          host_id: button.dataset.ipHostId || '',
        });
      });
    });
  };

  const bindAddButtons = (root = document) => {
    const addButtons = root.querySelectorAll('[data-ip-add]');
    addButtons.forEach((button) => {
      if (button.dataset.ipAddBound) {
        return;
      }
      button.dataset.ipAddBound = 'true';
      button.addEventListener('click', () => {
        openDrawerForAdd();
      });
    });
  };

  const bindTagsMoreTriggers = (root = document) => {
    const triggers = root.querySelectorAll('[data-tags-more-toggle]');
    triggers.forEach((trigger) => {
      if (trigger.dataset.tagsMoreBound) {
        return;
      }
      trigger.dataset.tagsMoreBound = 'true';
      trigger.addEventListener('mouseenter', () => {
        if (activeTagsPopoverTrigger === trigger && tagsPopover && !tagsPopover.hidden) {
          if (tagsPopoverCloseTimer) {
            window.clearTimeout(tagsPopoverCloseTimer);
            tagsPopoverCloseTimer = null;
          }
          return;
        }
        scheduleOpenTagsPopover(trigger);
      });
      trigger.addEventListener('mouseleave', (event) => {
        const nextTarget = event.relatedTarget;
        if (
          nextTarget &&
          (trigger.contains(nextTarget) || (tagsPopover && tagsPopover.contains(nextTarget)))
        ) {
          return;
        }
        scheduleCloseTagsPopover();
      });
      trigger.addEventListener('focus', () => {
        openTagsPopover(trigger);
      });
      trigger.addEventListener('blur', (event) => {
        const nextTarget = event.relatedTarget;
        if (nextTarget && tagsPopover && tagsPopover.contains(nextTarget)) {
          return;
        }
        scheduleCloseTagsPopover(0);
      });
    });
  };

  const updateDeleteState = () => {
    if (!deleteButton || !deleteAck || !currentAsset) {
      return;
    }
    const needsTypedConfirmation = Boolean(deleteConfirmWrap && !deleteConfirmWrap.hidden);
    const hasTypedIp = !needsTypedConfirmation || ((deleteConfirmInput?.value || '').trim() === (currentAsset?.ip_address || ''));
    deleteButton.disabled = !(deleteAck.checked && hasTypedIp);
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
    const openButton = bulkForm.querySelector('[data-bulk-open]');
    const bulkControls = bulkForm.querySelector('[data-bulk-controls]');

    const updateCount = () => {
      const selected = checkboxes.filter((checkbox) => checkbox.checked);
      const selectedCount = selected.length;
      const commonTags = computeCommonBulkTags(selected);
      if (countLabel) {
        countLabel.textContent = `${selectedCount} selected`;
      }
      if (openButton) {
        openButton.disabled = selectedCount === 0;
      }
      if (bulkDrawerApply) {
        bulkDrawerApply.disabled = selectedCount === 0;
      }
      if (bulkDrawerSelection) {
        bulkDrawerSelection.textContent = `${selectedCount} selected`;
      }
      renderBulkCommonTags(commonTags);
      if (bulkDrawerStatus) {
        bulkDrawerStatus.textContent = selectedCount > 0
          ? `Select fields to update${bulkRemoveTags.size ? ` • Remove ${bulkRemoveTags.size} common tag(s)` : ''}`
          : 'Select at least one row';
      }
      if (bulkControls) {
        bulkControls.classList.toggle('bulk-edit-controls-hidden', selectedCount === 0);
      }
      if (selectedCount === 0 && isBulkDrawerOpen) {
        closeBulkDrawer();
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

    if (openButton) {
      openButton.addEventListener('click', () => {
        if (openButton.disabled) {
          return;
        }
        if (isOpen) {
          closeDrawer();
        }
        resetBulkInputs();
        openBulkDrawer();
        const firstInput = bulkDrawer ? bulkDrawer.querySelector('.select, .input') : null;
        if (firstInput instanceof HTMLElement) {
          window.setTimeout(() => firstInput.focus(), 80);
        }
      });
    }

    updateCount();
  };

  const bindTableInteractions = (root = document) => {
    bindEditButtons(root);
    bindDeleteButtons(root);
    bindBulkEdit(root);
    bindTagsMoreTriggers(root);
    bindPerPageControl(root);
    bindAddButtons();
  };

  const bindPerPageControl = (root = document) => {
    const perPageSelect = root.querySelector('[data-per-page-select]');
    if (!perPageSelect || perPageSelect.dataset.perPageBound) {
      return;
    }
    perPageSelect.dataset.perPageBound = 'true';
    ['click', 'mousedown', 'touchstart'].forEach((eventName) => {
      perPageSelect.addEventListener(eventName, (event) => {
        event.stopPropagation();
      });
    });
  };

  const getIpTableContainerFromEvent = (event) => {
    const explicitTarget = event?.detail?.target;
    if (explicitTarget instanceof Element) {
      if (explicitTarget.id === 'ip-table-container') {
        return explicitTarget;
      }
      const nested = explicitTarget.closest('#ip-table-container');
      if (nested) {
        return nested;
      }
    }
    const fallbackTarget = event?.target;
    if (fallbackTarget instanceof Element) {
      if (fallbackTarget.id === 'ip-table-container') {
        return fallbackTarget;
      }
      const nested = fallbackTarget.closest('#ip-table-container');
      if (nested) {
        return nested;
      }
    }
    return null;
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

  const getTagColor = (rawValue) => {
    if (!tagFilterSuggestions) {
      return '';
    }
    const normalizedValue = normalizeTagValue(rawValue);
    if (!normalizedValue) {
      return '';
    }
    const option = Array.from(tagFilterSuggestions.options).find(
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
    const chip = entry.querySelector(`[data-remove-tag-filter="${value}"]`);
    applyTagFilterChipColor(chip, value);
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
    if (bulkOverlay) {
      bulkOverlay.addEventListener('click', closeBulkDrawer);
    }
    if (bulkDrawerClose) {
      bulkDrawerClose.addEventListener('click', closeBulkDrawer);
    }
    if (bulkDrawerCancel) {
      bulkDrawerCancel.addEventListener('click', closeBulkDrawer);
    }
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && activeTagsPopoverTrigger) {
        closeTagsPopover();
      }
      if (event.key === 'Escape' && isBulkDrawerOpen) {
        closeBulkDrawer();
        return;
      }
      if (event.key === 'Escape' && isOpen) {
        confirmClose();
      }
    });
    window.addEventListener('resize', positionTagsPopover);
    window.addEventListener('scroll', positionTagsPopover, true);
    inputs.forEach((input) => {
      input.addEventListener('input', () => {
        if (input.dataset.ipInput === 'ip_address' && autoHostName) {
          autoHostName.textContent = `server_${input.value.trim() || 'IP'}`;
        }
        if (input.dataset.ipInput === 'type') {
          updateHostVisibility();
        }
        if (input.dataset.ipInput === 'host_id') {
          updateAutoHostVisibility();
        }
        updateSaveState();
      });
    });
    if (deleteAck) {
      deleteAck.addEventListener('change', updateDeleteState);
    }
    if (deleteConfirmInput) {
      deleteConfirmInput.addEventListener('input', updateDeleteState);
    }
    if (deleteForm && window.sessionStorage) {
      deleteForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (deleteError) {
          deleteError.textContent = '';
        }
        deleteButton.disabled = true;
        try {
          const response = await fetch(deleteForm.action, {
            method: 'POST',
            headers: {
              Accept: 'application/json',
            },
            body: new FormData(deleteForm),
          });
          const payload = await response.json();
          if (!response.ok) {
            throw new Error(payload.error || 'Delete failed.');
          }
          const row = document.querySelector(`[data-ip-asset-row-id="${payload.asset_id}"]`);
          if (row) {
            row.remove();
          }
          closeDrawer();
          showToast(payload.message || 'IP asset deleted.', 'success');
        } catch (error) {
          if (deleteError) {
            deleteError.textContent = error.message;
          }
          showToast(error.message || 'Delete failed.', 'error');
        } finally {
          updateDeleteState();
        }
      });
    }
    if (autoHostButton) {
      autoHostButton.addEventListener('click', createAutoHost);
    }
    updateHostVisibility();
    if (form && window.sessionStorage) {
      form.addEventListener('submit', () => {
        syncEditReturnTo();
        window.sessionStorage.setItem(SCROLL_KEY, String(window.scrollY || 0));
      });
    }
    const bulkForm = document.querySelector('[data-bulk-form]');
    if (bulkForm && window.sessionStorage) {
      bulkForm.addEventListener('submit', () => {
        window.sessionStorage.setItem(SCROLL_KEY, String(window.scrollY || 0));
      });
    }
    if (tagFilterSelected) {
      tagFilterSelected.querySelectorAll('[data-remove-tag-filter]').forEach((chip) => {
        applyTagFilterChipColor(chip, chip.getAttribute('data-remove-tag-filter') || '');
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
      const container = getIpTableContainerFromEvent(event);
      if (!container) {
        return;
      }
      closeTagsPopover();
      closeBulkDrawer();
      bindTableInteractions(container);
    });
    document.body.addEventListener('htmx:afterSettle', (event) => {
      const container = getIpTableContainerFromEvent(event);
      if (!container) {
        return;
      }
      bindTableInteractions(container);
    });
    document.body.addEventListener('click', (event) => {
      if (event.target.closest('[data-per-page-control]')) {
        return;
      }
      const removeTagButton = event.target.closest('[data-remove-tag-filter]');
      if (removeTagButton) {
        event.preventDefault();
        if (removeTagFilter(removeTagButton.dataset.removeTagFilter || '')) {
          submitTagFilter();
        }
        return;
      }
      const removeCommonTagButton = event.target.closest('[data-bulk-remove-tag]');
      if (removeCommonTagButton) {
        event.preventDefault();
        const tag = (removeCommonTagButton.dataset.bulkRemoveTag || '').trim().toLowerCase();
        if (!tag) {
          return;
        }
        if (bulkRemoveTags.has(tag)) {
          bulkRemoveTags.delete(tag);
        } else {
          bulkRemoveTags.add(tag);
        }
        const bulkFormRoot = document.querySelector('[data-bulk-form]');
        const selectedCheckboxes = bulkFormRoot
          ? Array.from(bulkFormRoot.querySelectorAll('[data-bulk-select]')).filter((checkbox) => checkbox.checked)
          : [];
        renderBulkCommonTags(computeCommonBulkTags(selectedCheckboxes));
        if (bulkDrawerStatus) {
          bulkDrawerStatus.textContent = selectedCheckboxes.length > 0
            ? `Select fields to update${bulkRemoveTags.size ? ` • Remove ${bulkRemoveTags.size} common tag(s)` : ''}`
            : 'Select at least one row';
        }
        return;
      }
      const tagsMoreTrigger = event.target.closest('[data-tags-more-toggle]');
      if (tagsMoreTrigger) {
        event.preventDefault();
        if (activeTagsPopoverTrigger === tagsMoreTrigger) {
          closeTagsPopover();
        } else {
          openTagsPopover(tagsMoreTrigger);
        }
        return;
      }
      if (activeTagsPopoverTrigger && tagsPopover && !tagsPopover.contains(event.target)) {
        closeTagsPopover();
      }
      const trigger = event.target.closest('[data-quick-filter]');
      if (!trigger) {
        return;
      }
      event.preventDefault();
      applyQuickFilter(trigger.dataset.quickFilter, trigger.dataset.quickFilterValue || '');
    });
  }

  bindTableInteractions();
})();
