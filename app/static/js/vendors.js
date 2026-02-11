(() => {
  const overlay = document.querySelector('[data-vendor-create-overlay]');
  const drawer = document.querySelector('[data-vendor-create-drawer]');
  const form = document.querySelector('[data-vendor-create-form]');
  const addButton = document.querySelector('[data-vendor-add]');
  const closeButton = document.querySelector('[data-vendor-create-close]');
  const cancelButton = document.querySelector('[data-vendor-create-cancel]');
  const saveButton = document.querySelector('[data-vendor-create-save]');
  const dirtyStatus = document.querySelector('[data-vendor-create-dirty]');

  if (!overlay || !drawer || !form || !addButton || !closeButton || !cancelButton || !saveButton || !dirtyStatus) {
    return;
  }

  const inputs = form.querySelectorAll('[data-vendor-input]');
  const nameInput = form.querySelector('[data-vendor-input="name"]');
  const shouldOpenByDefault = drawer.dataset.vendorOpen === 'true';

  let initialValues = {};

  const normalizeValue = (value) => value.trim();

  const setInitialValues = () => {
    initialValues = {};
    inputs.forEach((input) => {
      initialValues[input.dataset.vendorInput] = normalizeValue(input.value || '');
    });
  };

  const isDirty = () =>
    Array.from(inputs).some((input) => {
      const key = input.dataset.vendorInput;
      return normalizeValue(input.value || '') !== (initialValues[key] || '');
    });

  const validate = () => Boolean(nameInput?.value.trim());

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

  const closeDrawer = () => {
    drawerController?.requestClose();
  };

  addButton.addEventListener('click', openDrawer);
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

(() => {
  const overlay = document.querySelector('[data-vendor-edit-overlay]');
  const drawer = document.querySelector('[data-vendor-edit-drawer]');
  const form = document.querySelector('[data-vendor-edit-form]');
  const closeButton = document.querySelector('[data-vendor-edit-close]');
  const cancelButton = document.querySelector('[data-vendor-edit-cancel]');
  const saveButton = document.querySelector('[data-vendor-edit-save]');
  const dirtyStatus = document.querySelector('[data-vendor-edit-dirty]');

  if (!overlay || !drawer || !form || !closeButton || !cancelButton || !saveButton || !dirtyStatus) {
    return;
  }

  const editButtons = document.querySelectorAll('[data-vendor-edit]');
  const inputs = form.querySelectorAll('[data-vendor-edit-input]');
  const nameInput = form.querySelector('[data-vendor-edit-input="name"]');
  const shouldOpenByDefault = drawer.dataset.vendorEditOpen === 'true';

  let initialValues = {};
  let activeVendorId = form.dataset.vendorEditId || '';

  const normalizeValue = (value) => value.trim();

  const setInitialValues = () => {
    initialValues = {};
    inputs.forEach((input) => {
      initialValues[input.dataset.vendorEditInput] = normalizeValue(input.value || '');
    });
  };

  const isDirty = () =>
    Array.from(inputs).some((input) => {
      const key = input.dataset.vendorEditInput;
      return normalizeValue(input.value || '') !== (initialValues[key] || '');
    });

  const validate = () => Boolean(activeVendorId) && Boolean(nameInput?.value.trim());

  const updateSaveState = () => {
    const dirty = isDirty();
    const valid = validate();
    saveButton.disabled = !(dirty && valid);
    if (!activeVendorId) {
      dirtyStatus.textContent = 'Choose vendor';
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

  const setVendorFormData = ({ id, name }) => {
    activeVendorId = id || '';
    form.dataset.vendorEditId = activeVendorId;
    form.action = activeVendorId ? `/ui/vendors/${activeVendorId}/edit` : '#';
    if (nameInput) {
      nameInput.value = name || '';
    }
    setInitialValues();
    updateSaveState();
  };

  editButtons.forEach((button) => {
    button.addEventListener('click', () => {
      setVendorFormData({
        id: button.dataset.vendorEdit || '',
        name: button.dataset.vendorName || '',
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

(() => {
  const overlay = document.querySelector('[data-vendor-delete-overlay]');
  const drawer = document.querySelector('[data-vendor-delete-drawer]');
  const form = document.querySelector('[data-vendor-delete-form]');
  const closeButton = document.querySelector('[data-vendor-delete-close]');
  const cancelButton = document.querySelector('[data-vendor-delete-cancel]');
  const submitButton = document.querySelector('[data-vendor-delete-submit]');
  const dirtyStatus = document.querySelector('[data-vendor-delete-dirty]');
  const subtitle = document.querySelector('[data-vendor-delete-subtitle]');
  const nameDisplay = document.querySelector('[data-vendor-delete-name-display]');
  const nameInline = document.querySelector('[data-vendor-delete-name-inline]');
  const ackInput = document.querySelector('[data-vendor-delete-ack]');
  const confirmInput = document.querySelector('[data-vendor-delete-confirm]');

  if (
    !overlay || !drawer || !form || !closeButton || !cancelButton || !submitButton || !dirtyStatus || !subtitle ||
    !nameDisplay || !nameInline || !ackInput || !confirmInput
  ) {
    return;
  }

  const deleteButtons = document.querySelectorAll('[data-vendor-delete]');
  const shouldOpenByDefault = drawer.dataset.vendorDeleteOpen === 'true';

  let activeVendor = {
    id: form.dataset.vendorDeleteId || '',
    name: form.dataset.vendorDeleteName || '',
  };

  const isValid = () => {
    if (!activeVendor.id || !activeVendor.name) {
      return false;
    }
    if (!ackInput.checked) {
      return false;
    }
    return confirmInput.value.trim() === activeVendor.name;
  };

  const updateSubmitState = () => {
    const valid = isValid();
    submitButton.disabled = !valid;
    if (!activeVendor.id) {
      dirtyStatus.textContent = 'Choose vendor';
      return;
    }
    if (!ackInput.checked) {
      dirtyStatus.textContent = 'Acknowledge delete';
      return;
    }
    dirtyStatus.textContent = valid ? 'Ready to delete' : 'Type exact vendor name';
  };

  const applyVendor = ({ id, name }) => {
    activeVendor = {
      id: id || '',
      name: name || '',
    };
    form.dataset.vendorDeleteId = activeVendor.id;
    form.dataset.vendorDeleteName = activeVendor.name;
    form.action = activeVendor.id ? `/ui/vendors/${activeVendor.id}/delete` : '#';
    subtitle.textContent = activeVendor.name || 'Permanent removal';
    nameDisplay.textContent = activeVendor.name || '—';
    nameInline.textContent = activeVendor.name || '—';
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
      confirmInput?.focus();
    }, 100);
  };

  const closeDrawer = () => {
    drawerController?.requestClose();
  };

  deleteButtons.forEach((button) => {
    button.addEventListener('click', () => {
      applyVendor({
        id: button.dataset.vendorDelete || '',
        name: button.dataset.vendorDeleteName || '',
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

  applyVendor(activeVendor);

  if (shouldOpenByDefault) {
    openDrawer();
  }
})();
