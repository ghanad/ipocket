(() => {
  const overlay = document.querySelector('[data-range-create-overlay]');
  const drawer = document.querySelector('[data-range-create-drawer]');
  const form = document.querySelector('[data-range-create-form]');
  const addButton = document.querySelector('[data-range-add]');
  const closeButton = document.querySelector('[data-range-create-close]');
  const cancelButton = document.querySelector('[data-range-create-cancel]');
  const saveButton = document.querySelector('[data-range-create-save]');
  const dirtyStatus = document.querySelector('[data-range-create-dirty]');

  if (!overlay || !drawer || !form || !addButton || !closeButton || !cancelButton || !saveButton || !dirtyStatus) {
    return;
  }

  const inputs = form.querySelectorAll('[data-range-input]');
  const nameInput = form.querySelector('[data-range-input="name"]');
  const cidrInput = form.querySelector('[data-range-input="cidr"]');
  const shouldOpenByDefault = drawer.dataset.rangeOpen === 'true';

  let initialValues = {};

  const normalizeValue = (value) => value.trim();

  const setInitialValues = () => {
    initialValues = {};
    inputs.forEach((input) => {
      initialValues[input.dataset.rangeInput] = normalizeValue(input.value || '');
    });
  };

  const isDirty = () =>
    Array.from(inputs).some((input) => {
      const key = input.dataset.rangeInput;
      return normalizeValue(input.value || '') !== (initialValues[key] || '');
    });

  const validate = () => {
    const nameValid = Boolean(nameInput?.value.trim());
    const cidrValid = Boolean(cidrInput?.value.trim());
    return nameValid && cidrValid;
  };

  const updateSaveState = () => {
    const dirty = isDirty();
    const valid = validate();
    saveButton.disabled = !(dirty && valid);
    dirtyStatus.textContent = dirty ? 'Ready to create' : 'Enter details';
  };

  const drawerController = window.ipocketCreateDrawerController
    ? window.ipocketCreateDrawerController({
      overlay,
      drawer,
      onBeforeClose: () => {
        if (!isDirty()) {
          return true;
        }
        return window.confirm('Discard changes?');
      },
    })
    : null;

  const openDrawer = () => {
    drawerController?.open();
    setTimeout(() => {
      nameInput?.focus();
    }, 100);
  };

  const handleClose = () => {
    drawerController?.requestClose();
  };

  addButton.addEventListener('click', openDrawer);
  closeButton.addEventListener('click', handleClose);
  cancelButton.addEventListener('click', handleClose);
  overlay.addEventListener('click', handleClose);

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && drawerController?.isOpen()) {
      handleClose();
    }
  });

  inputs.forEach((input) => {
    input.addEventListener('input', updateSaveState);
  });

  form.addEventListener('submit', (event) => {
    if (!validate()) {
      event.preventDefault();
      updateSaveState();
    }
  });

  setInitialValues();
  updateSaveState();

  if (shouldOpenByDefault) {
    openDrawer();
  }
})();

(() => {
  const overlay = document.querySelector('[data-range-delete-overlay]');
  const drawer = document.querySelector('[data-range-delete-drawer]');
  const form = document.querySelector('[data-range-delete-form]');
  const closeButton = document.querySelector('[data-range-delete-close]');
  const cancelButton = document.querySelector('[data-range-delete-cancel]');
  const submitButton = document.querySelector('[data-range-delete-submit]');
  const dirtyStatus = document.querySelector('[data-range-delete-dirty]');
  const subtitle = document.querySelector('[data-range-delete-subtitle]');
  const nameDisplay = document.querySelector('[data-range-delete-name-display]');
  const nameInline = document.querySelector('[data-range-delete-name-inline]');
  const cidrDisplay = document.querySelector('[data-range-delete-cidr]');
  const usedDisplay = document.querySelector('[data-range-delete-used]');
  const ackInput = document.querySelector('[data-range-delete-ack]');
  const confirmInput = document.querySelector('[data-range-delete-confirm]');

  if (
    !overlay || !drawer || !form || !closeButton || !cancelButton || !submitButton || !dirtyStatus || !subtitle ||
    !nameDisplay || !nameInline || !cidrDisplay || !usedDisplay || !ackInput || !confirmInput
  ) {
    return;
  }

  const deleteButtons = document.querySelectorAll('[data-range-delete]');
  const shouldOpenByDefault = drawer.dataset.rangeDeleteOpen === 'true';
  let activeRange = {
    id: form.dataset.rangeDeleteId || '',
    name: form.dataset.rangeDeleteName || '',
    cidr: cidrDisplay.textContent || '—',
    used: usedDisplay.textContent || '—',
  };

  const isValid = () => {
    if (!activeRange.id || !activeRange.name) {
      return false;
    }
    if (!ackInput.checked) {
      return false;
    }
    return confirmInput.value.trim() === activeRange.name;
  };

  const updateSubmitState = () => {
    const valid = isValid();
    submitButton.disabled = !valid;
    if (!activeRange.id) {
      dirtyStatus.textContent = 'Choose range';
      return;
    }
    if (!ackInput.checked) {
      dirtyStatus.textContent = 'Acknowledge delete';
      return;
    }
    dirtyStatus.textContent = valid ? 'Ready to delete' : 'Type exact range name';
  };

  const applyRange = ({ id, name, cidr, used }) => {
    activeRange = {
      id: id || '',
      name: name || '',
      cidr: cidr || '—',
      used: used || '—',
    };
    form.dataset.rangeDeleteId = activeRange.id;
    form.dataset.rangeDeleteName = activeRange.name;
    form.action = activeRange.id ? `/ui/ranges/${activeRange.id}/delete` : '#';
    subtitle.textContent = activeRange.name || 'Permanent removal';
    nameDisplay.textContent = activeRange.name || '—';
    nameInline.textContent = activeRange.name || '—';
    cidrDisplay.textContent = activeRange.cidr || '—';
    usedDisplay.textContent = activeRange.used || '—';
    if (!shouldOpenByDefault) {
      confirmInput.value = '';
    }
    ackInput.checked = false;
    updateSubmitState();
  };

  const drawerController = window.ipocketCreateDrawerController
    ? window.ipocketCreateDrawerController({
      overlay,
      drawer,
      onBeforeClose: () => true,
    })
    : null;

  const openDrawer = () => {
    drawerController?.open();
    setTimeout(() => {
      confirmInput.focus();
    }, 100);
  };

  const closeDrawer = () => {
    drawerController?.requestClose();
  };

  deleteButtons.forEach((button) => {
    button.addEventListener('click', () => {
      applyRange({
        id: button.dataset.rangeDelete || '',
        name: button.dataset.rangeDeleteName || '',
        cidr: button.dataset.rangeDeleteCidr || '—',
        used: button.dataset.rangeDeleteUsed || '—',
      });
      openDrawer();
    });
  });

  closeButton.addEventListener('click', closeDrawer);
  cancelButton.addEventListener('click', closeDrawer);
  overlay.addEventListener('click', closeDrawer);

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && drawerController?.isOpen()) {
      closeDrawer();
    }
  });

  ackInput.addEventListener('change', updateSubmitState);
  confirmInput.addEventListener('input', updateSubmitState);

  applyRange(activeRange);

  if (shouldOpenByDefault) {
    openDrawer();
  }
})();

(() => {
  const overlay = document.querySelector('[data-range-edit-overlay]');
  const drawer = document.querySelector('[data-range-edit-drawer]');
  const form = document.querySelector('[data-range-edit-form]');
  const closeButton = document.querySelector('[data-range-edit-close]');
  const cancelButton = document.querySelector('[data-range-edit-cancel]');
  const saveButton = document.querySelector('[data-range-edit-save]');
  const dirtyStatus = document.querySelector('[data-range-edit-dirty]');

  if (!overlay || !drawer || !form || !closeButton || !cancelButton || !saveButton || !dirtyStatus) {
    return;
  }

  const editButtons = document.querySelectorAll('[data-range-edit]');
  const inputs = form.querySelectorAll('[data-range-edit-input]');
  const nameInput = form.querySelector('[data-range-edit-input="name"]');
  const cidrInput = form.querySelector('[data-range-edit-input="cidr"]');
  const shouldOpenByDefault = drawer.dataset.rangeEditOpen === 'true';

  let initialValues = {};
  let activeRangeId = form.dataset.rangeEditId || '';

  const normalizeValue = (value) => value.trim();

  const setInitialValues = () => {
    initialValues = {};
    inputs.forEach((input) => {
      initialValues[input.dataset.rangeEditInput] = normalizeValue(input.value || '');
    });
  };

  const isDirty = () =>
    Array.from(inputs).some((input) => {
      const key = input.dataset.rangeEditInput;
      return normalizeValue(input.value || '') !== (initialValues[key] || '');
    });

  const validate = () => {
    const nameValid = Boolean(nameInput?.value.trim());
    const cidrValid = Boolean(cidrInput?.value.trim());
    return Boolean(activeRangeId) && nameValid && cidrValid;
  };

  const updateSaveState = () => {
    const dirty = isDirty();
    const valid = validate();
    saveButton.disabled = !(dirty && valid);
    if (!activeRangeId) {
      dirtyStatus.textContent = 'Choose range';
      return;
    }
    dirtyStatus.textContent = dirty ? 'Ready to save' : 'No changes yet';
  };

  const drawerController = window.ipocketCreateDrawerController
    ? window.ipocketCreateDrawerController({
      overlay,
      drawer,
      onBeforeClose: () => {
        if (!isDirty()) {
          return true;
        }
        return window.confirm('Discard changes?');
      },
    })
    : null;

  const openDrawer = () => {
    drawerController?.open();
    setTimeout(() => {
      nameInput?.focus();
    }, 100);
  };

  const closeDrawer = () => {
    drawerController?.requestClose();
  };

  const setRangeFormData = ({ id, name, cidr, notes }) => {
    activeRangeId = id || '';
    form.dataset.rangeEditId = activeRangeId;
    form.action = activeRangeId ? `/ui/ranges/${activeRangeId}/edit` : '#';
    if (nameInput) {
      nameInput.value = name || '';
    }
    if (cidrInput) {
      cidrInput.value = cidr || '';
    }
    const notesInput = form.querySelector('[data-range-edit-input="notes"]');
    if (notesInput) {
      notesInput.value = notes || '';
    }
    setInitialValues();
    updateSaveState();
  };

  editButtons.forEach((button) => {
    button.addEventListener('click', () => {
      setRangeFormData({
        id: button.dataset.rangeEdit || '',
        name: button.dataset.rangeName || '',
        cidr: button.dataset.rangeCidr || '',
        notes: button.dataset.rangeNotes || '',
      });
      openDrawer();
    });
  });

  closeButton.addEventListener('click', closeDrawer);
  cancelButton.addEventListener('click', closeDrawer);
  overlay.addEventListener('click', closeDrawer);

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && drawerController?.isOpen()) {
      closeDrawer();
    }
  });

  inputs.forEach((input) => {
    input.addEventListener('input', updateSaveState);
  });

  form.addEventListener('submit', (event) => {
    if (!validate()) {
      event.preventDefault();
      updateSaveState();
    }
  });

  setInitialValues();
  updateSaveState();

  if (shouldOpenByDefault) {
    openDrawer();
  }
})();
