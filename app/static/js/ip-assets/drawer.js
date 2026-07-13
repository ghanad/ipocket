import {
  SCROLL_KEY,
  getCurrentListUrl,
  readInputValue,
  showToast,
  writeInputValue,
} from './shared.js';

export const createDrawerController = ({ closeBulkDrawer }) => {
  const overlay = document.querySelector('[data-ip-drawer-overlay]');
  const drawer = document.querySelector('[data-ip-drawer]');
  const title = document.querySelector('[data-ip-drawer-title]');
  const subtitle = document.querySelector('[data-ip-drawer-subtitle]');
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
  const projectPill = document.querySelector('[data-ip-drawer-project]');
  const hostPill = document.querySelector('[data-ip-drawer-host]');
  const dirtyStatus = document.querySelector('[data-ip-drawer-dirty]');
  const autoHostWrapper = document.querySelector('[data-ip-auto-host]');
  const autoHostButton = document.querySelector('[data-ip-auto-host-button]');
  const autoHostName = document.querySelector('[data-ip-auto-host-name]');
  const autoHostStatus = document.querySelector('[data-ip-auto-host-status]');
  const inputs = form ? form.querySelectorAll('[data-ip-input]') : [];
  const hostField = form ? form.querySelector('[data-ip-host-field]') : null;
  const ipAddressInput = form ? form.querySelector('[data-ip-input="ip_address"]') : null;
  let initialValues = {};
  let currentAsset = null;
  let isOpen = false;
  let isAddMode = false;
  let isDeleteMode = false;

  const getDeleteReturnUrl = (assetData) => {
    const detailPath = assetData?.id ? `/ui/ip-assets/${assetData.id}` : '';
    return detailPath && window.location.pathname === detailPath
      ? '/ui/ip-assets'
      : getCurrentListUrl();
  };

  const syncEditReturnTo = () => {
    const returnToInput = form?.querySelector('input[name="return_to"]');
    if (returnToInput) {
      returnToInput.value = getCurrentListUrl();
    }
  };

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

  const setMode = (mode) => {
    const normalizedMode = mode === 'delete' ? 'delete' : 'edit';
    isDeleteMode = normalizedMode === 'delete';
    if (drawer) {
      drawer.dataset.ipDrawerMode = normalizedMode;
      drawer.setAttribute(
        'aria-label',
        normalizedMode === 'delete' ? 'Delete IP asset' : 'Edit IP asset'
      );
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

  const resetHostSearch = () => {
    if (hostField && typeof window.ipocketResetHostSearch === 'function') {
      window.ipocketResetHostSearch(hostField);
    }
  };

  const updateAutoHostVisibility = () => {
    if (!autoHostWrapper || !form) {
      return;
    }
    const typeValue = form.querySelector('[data-ip-input="type"]')?.value || '';
    const hostValue = form.querySelector('[data-ip-input="host_id"]')?.value || '';
    const showAutoHost = typeValue.toUpperCase() === 'BMC' && !hostValue.trim();
    autoHostWrapper.classList.toggle('is-visible', showAutoHost);
    if (autoHostStatus) {
      autoHostStatus.textContent = '';
    }
  };

  const updateHostVisibility = () => {
    if (!hostField || !form) {
      return;
    }
    const typeValue = form.querySelector('[data-ip-input="type"]')?.value || '';
    const showHost = ['OS', 'BMC'].includes(typeValue.toUpperCase());
    hostField.style.display = showHost ? '' : 'none';
    if (!showHost) {
      const hostSelect = form.querySelector('[data-ip-input="host_id"]');
      if (hostSelect) {
        hostSelect.value = '';
      }
      resetHostSearch();
    }
    updateAutoHostVisibility();
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

  const openBase = () => {
    if (!overlay || !drawer) {
      return;
    }
    overlay.classList.add('is-open');
    drawer.classList.add('is-open');
    isOpen = true;
  };

  const open = (assetData) => {
    if (!form || !subtitle || !projectPill || !hostPill || !title) {
      return;
    }
    closeBulkDrawer();
    setMode('edit');
    isAddMode = false;
    currentAsset = assetData;
    inputs.forEach((input) => writeInputValue(input, assetData[input.dataset.ipInput] || ''));
    form.action = `/ui/ip-assets/${assetData.id}/edit`;
    syncEditReturnTo();
    if (ipAddressInput) ipAddressInput.readOnly = true;
    saveButton.textContent = 'Save changes';
    title.textContent = 'Edit IP asset';
    subtitle.textContent = assetData.ip_address || '—';
    projectPill.textContent = `Project: ${assetData.project_label || 'Unassigned'}`;
    hostPill.textContent = `Host: ${assetData.host_label || '—'}`;
    updateHostVisibility();
    resetHostSearch();
    initialValues = {
      ip_address: assetData.ip_address || '',
      type: assetData.type || '',
      project_id: assetData.project_id || '',
      host_id: assetData.host_id || '',
      tags: String(assetData.tags || '').split(',').map((tag) => tag.trim()).filter(Boolean).sort().join(','),
      notes: assetData.notes || '',
    };
    updateSaveState();
    openBase();
    if (autoHostName) autoHostName.textContent = `server_${assetData.ip_address || 'IP'}`;
    if (autoHostButton) autoHostButton.disabled = false;
    if (autoHostStatus) autoHostStatus.textContent = '';
  };

  const openForDelete = (assetData) => {
    if (!title || !subtitle || !projectPill || !hostPill || !deleteForm || !deleteButton) {
      return;
    }
    closeBulkDrawer();
    setMode('delete');
    isAddMode = false;
    currentAsset = assetData;
    title.textContent = 'Delete IP asset?';
    subtitle.textContent = 'Permanent and cannot be undone.';
    projectPill.textContent = `Project: ${assetData.project_label || 'Unassigned'}`;
    hostPill.textContent = `Host: ${assetData.host_label || '—'}`;
    if (deleteAddress) deleteAddress.textContent = assetData.ip_address || '—';
    if (deleteProject) deleteProject.textContent = assetData.project_label || 'Unassigned';
    if (deleteType) deleteType.textContent = assetData.type || '—';
    if (deleteHost) deleteHost.textContent = assetData.host_label || '—';
    deleteForm.action = `/ui/ip-assets/${assetData.id}/delete`;
    if (deleteReturnTo) deleteReturnTo.value = getDeleteReturnUrl(assetData);
    if (deleteAck) deleteAck.checked = false;
    if (deleteConfirmInput) deleteConfirmInput.value = '';
    if (deleteError) deleteError.textContent = '';
    if (deleteConfirmWrap) deleteConfirmWrap.hidden = !isHighRiskDelete(assetData);
    deleteButton.disabled = true;
    dirtyStatus.textContent = 'Confirm deletion';
    openBase();
  };

  const openForAdd = () => {
    if (!form || !subtitle || !projectPill || !hostPill || !title) {
      return;
    }
    closeBulkDrawer();
    setMode('edit');
    isAddMode = true;
    currentAsset = null;
    inputs.forEach((input) => {
      if (input.dataset.ipInput === 'type') {
        input.value = 'VM';
      } else {
        writeInputValue(input, '');
      }
    });
    if (ipAddressInput) ipAddressInput.readOnly = false;
    form.action = '/ui/ip-assets/new';
    syncEditReturnTo();
    title.textContent = 'Add IP asset';
    subtitle.textContent = 'Create a new IP assignment';
    projectPill.textContent = 'Project: Unassigned';
    hostPill.textContent = 'Host: —';
    saveButton.textContent = 'Create IP';
    initialValues = { ip_address: '', type: 'VM', project_id: '', host_id: '', tags: '', notes: '' };
    updateHostVisibility();
    resetHostSearch();
    updateSaveState();
    openBase();
    if (autoHostName) autoHostName.textContent = 'server_IP';
    if (autoHostStatus) autoHostStatus.textContent = '';
    if (ipAddressInput) setTimeout(() => ipAddressInput.focus(), 100);
  };

  const close = () => {
    if (!overlay || !drawer) {
      return;
    }
    overlay.classList.remove('is-open');
    drawer.classList.remove('is-open');
    isOpen = false;
    isAddMode = false;
    setMode('edit');
  };

  const confirmClose = () => {
    if (isDeleteMode) {
      close();
      return;
    }
    const dirty = Array.from(inputs).some((input) => {
      const key = input.dataset.ipInput;
      return readInputValue(input) !== (initialValues[key] || '');
    });
    if (!dirty || window.confirm('Discard changes?')) {
      close();
    }
  };

  const updateDeleteState = () => {
    if (!deleteButton || !deleteAck || !currentAsset) {
      return;
    }
    const needsTypedConfirmation = Boolean(deleteConfirmWrap && !deleteConfirmWrap.hidden);
    const hasTypedIp = !needsTypedConfirmation ||
      ((deleteConfirmInput?.value || '').trim() === (currentAsset?.ip_address || ''));
    deleteButton.disabled = !(deleteAck.checked && hasTypedIp);
  };

  const createAutoHost = async () => {
    if (!currentAsset || !form || !autoHostButton) {
      return;
    }
    autoHostButton.disabled = true;
    if (autoHostStatus) autoHostStatus.textContent = '';
    try {
      const response = await fetch(`/ui/ip-assets/${currentAsset.id}/auto-host`, {
        method: 'POST',
        headers: { Accept: 'application/json' },
      });
      let payload = {};
      try {
        payload = await response.json();
      } catch (error) {
        payload = {};
      }
      if (!response.ok) throw new Error(payload.error || 'Unable to create host.');
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
        resetHostSearch();
      }
      if (hostPill) hostPill.textContent = `Host: ${payload.host_name || '—'}`;
      updateSaveState();
      updateAutoHostVisibility();
    } catch (error) {
      if (autoHostStatus) autoHostStatus.textContent = error.message;
    } finally {
      autoHostButton.disabled = false;
    }
  };

  const bindGlobal = () => {
    closeButton?.addEventListener('click', confirmClose);
    cancelButton?.addEventListener('click', confirmClose);
    overlay?.addEventListener('click', confirmClose);
    inputs.forEach((input) => input.addEventListener('input', () => {
      if (input.dataset.ipInput === 'ip_address' && autoHostName) {
        autoHostName.textContent = `server_${input.value.trim() || 'IP'}`;
      }
      if (input.dataset.ipInput === 'type') updateHostVisibility();
      if (input.dataset.ipInput === 'host_id') updateAutoHostVisibility();
      updateSaveState();
    }));
    deleteAck?.addEventListener('change', updateDeleteState);
    deleteConfirmInput?.addEventListener('input', updateDeleteState);
    if (deleteForm && window.sessionStorage) {
      deleteForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (deleteError) deleteError.textContent = '';
        deleteButton.disabled = true;
        try {
          const response = await fetch(deleteForm.action, {
            method: 'POST',
            headers: { Accept: 'application/json' },
            body: new FormData(deleteForm),
          });
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.error || 'Delete failed.');
          const row = document.querySelector(`[data-ip-asset-row-id="${payload.asset_id}"]`);
          if (row) {
            row.remove();
          } else if (window.location.pathname === `/ui/ip-assets/${payload.asset_id}`) {
            const message = encodeURIComponent(payload.message || 'IP asset deleted.');
            window.location.href = `/ui/ip-assets?delete-success=${message}`;
            return;
          }
          close();
          showToast(payload.message || 'IP asset deleted.', 'success');
        } catch (error) {
          if (deleteError) deleteError.textContent = error.message;
          showToast(error.message || 'Delete failed.', 'error');
        } finally {
          updateDeleteState();
        }
      });
    }
    autoHostButton?.addEventListener('click', createAutoHost);
    updateHostVisibility();
    if (form && window.sessionStorage) {
      form.addEventListener('submit', () => {
        syncEditReturnTo();
        window.sessionStorage.setItem(SCROLL_KEY, String(window.scrollY || 0));
      });
    }
  };

  return {
    bindGlobal,
    close,
    confirmClose,
    isOpen: () => isOpen,
    open,
    openForAdd,
    openForDelete,
  };
};
