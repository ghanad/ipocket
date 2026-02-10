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
