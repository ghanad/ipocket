(() => {
  const createDrawerController = ({ overlay, drawer, onBeforeClose }) => {
    const externalFactory = window.ipocketCreateDrawerController;
    if (typeof externalFactory === 'function') {
      return externalFactory({ overlay, drawer, onBeforeClose });
    }

    if (!overlay || !drawer) {
      return null;
    }

    let isOpen = false;

    const open = () => {
      overlay.classList.add('is-open');
      drawer.classList.add('is-open');
      isOpen = true;
    };

    const close = () => {
      overlay.classList.remove('is-open');
      drawer.classList.remove('is-open');
      isOpen = false;
    };

    const requestClose = () => {
      if (!isOpen) {
        return;
      }
      if (typeof onBeforeClose === 'function') {
        const canClose = onBeforeClose();
        if (canClose === false) {
          return;
        }
      }
      close();
    };

    return {
      open,
      close,
      requestClose,
      isOpen: () => isOpen,
    };
  };

  const initCreateDrawer = () => {
    const overlay = document.querySelector('[data-tag-create-overlay]');
    const drawer = document.querySelector('[data-tag-create-drawer]');
    const form = document.querySelector('[data-tag-create-form]');
    const addButton = document.querySelector('[data-tag-add]');
    const closeButton = document.querySelector('[data-tag-create-close]');
    const cancelButton = document.querySelector('[data-tag-create-cancel]');
    const saveButton = document.querySelector('[data-tag-create-save]');
    const dirtyStatus = document.querySelector('[data-tag-create-dirty]');

    if (!overlay || !drawer || !form || !addButton || !closeButton || !cancelButton || !saveButton || !dirtyStatus) {
      return;
    }

    const inputs = form.querySelectorAll('[data-tag-input]');
    const nameInput = form.querySelector('[data-tag-input="name"]');
    const shouldOpenByDefault = drawer.dataset.tagOpen === 'true';

    let initialValues = {};

    const normalizeValue = (value) => value.trim();

    const setInitialValues = () => {
      initialValues = {};
      inputs.forEach((input) => {
        initialValues[input.dataset.tagInput] = normalizeValue(input.value || '');
      });
    };

    const isDirty = () =>
      Array.from(inputs).some((input) => {
        const key = input.dataset.tagInput;
        return normalizeValue(input.value || '') !== (initialValues[key] || '');
      });

    const validate = () => Boolean(nameInput && nameInput.value.trim());

    const updateSaveState = () => {
      const dirty = isDirty();
      const valid = validate();
      saveButton.disabled = !(dirty && valid);
      dirtyStatus.textContent = dirty ? 'Ready to create' : 'Enter details';
    };

    const drawerController = createDrawerController({
      overlay,
      drawer,
      onBeforeClose: () => {
        if (!isDirty()) {
          return true;
        }
        return window.confirm('Discard changes?');
      },
    });

    const openDrawer = () => {
      if (drawerController) {
        drawerController.open();
      }
      window.setTimeout(() => {
        if (nameInput) {
          nameInput.focus();
        }
      }, 100);
    };

    const closeDrawer = () => {
      if (drawerController) {
        drawerController.requestClose();
      }
    };

    addButton.addEventListener('click', openDrawer);
    closeButton.addEventListener('click', closeDrawer);
    cancelButton.addEventListener('click', closeDrawer);
    overlay.addEventListener('click', closeDrawer);

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && drawerController && drawerController.isOpen()) {
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
  };

  const initEditDrawer = () => {
    const overlay = document.querySelector('[data-tag-edit-overlay]');
    const drawer = document.querySelector('[data-tag-edit-drawer]');
    const form = document.querySelector('[data-tag-edit-form]');
    const closeButton = document.querySelector('[data-tag-edit-close]');
    const cancelButton = document.querySelector('[data-tag-edit-cancel]');
    const saveButton = document.querySelector('[data-tag-edit-save]');
    const dirtyStatus = document.querySelector('[data-tag-edit-dirty]');

    if (!overlay || !drawer || !form || !closeButton || !cancelButton || !saveButton || !dirtyStatus) {
      return;
    }

    const editButtons = document.querySelectorAll('[data-tag-edit]');
    const inputs = form.querySelectorAll('[data-tag-edit-input]');
    const nameInput = form.querySelector('[data-tag-edit-input="name"]');
    const colorInput = form.querySelector('[data-tag-edit-input="color"]');
    const shouldOpenByDefault = drawer.dataset.tagEditOpen === 'true';

    let initialValues = {};
    let activeTagId = form.dataset.tagEditId || '';

    const normalizeValue = (value) => value.trim();

    const setInitialValues = () => {
      initialValues = {};
      inputs.forEach((input) => {
        initialValues[input.dataset.tagEditInput] = normalizeValue(input.value || '');
      });
    };

    const isDirty = () =>
      Array.from(inputs).some((input) => {
        const key = input.dataset.tagEditInput;
        return normalizeValue(input.value || '') !== (initialValues[key] || '');
      });

    const validate = () => Boolean(activeTagId) && Boolean(nameInput && nameInput.value.trim());

    const updateSaveState = () => {
      const dirty = isDirty();
      const valid = validate();
      saveButton.disabled = !(dirty && valid);
      if (!activeTagId) {
        dirtyStatus.textContent = 'Choose tag';
        return;
      }
      dirtyStatus.textContent = dirty ? 'Ready to save' : 'No changes yet';
    };

    const drawerController = createDrawerController({
      overlay,
      drawer,
      onBeforeClose: () => {
        if (!isDirty()) {
          return true;
        }
        return window.confirm('Discard changes?');
      },
    });

    const openDrawer = () => {
      if (drawerController) {
        drawerController.open();
      }
      window.setTimeout(() => {
        if (nameInput) {
          nameInput.focus();
        }
      }, 100);
    };

    const closeDrawer = () => {
      if (drawerController) {
        drawerController.requestClose();
      }
    };

    const setTagFormData = ({ id, name, color }) => {
      activeTagId = id || '';
      form.dataset.tagEditId = activeTagId;
      form.action = activeTagId ? `/ui/tags/${activeTagId}/edit` : '#';
      if (nameInput) {
        nameInput.value = name || '';
      }
      if (colorInput) {
        colorInput.value = color || '#64748b';
      }
      setInitialValues();
      updateSaveState();
    };

    editButtons.forEach((button) => {
      button.addEventListener('click', () => {
        setTagFormData({
          id: button.dataset.tagEdit || '',
          name: button.dataset.tagName || '',
          color: button.dataset.tagColor || '#64748b',
        });
        openDrawer();
      });
    });

    closeButton.addEventListener('click', closeDrawer);
    cancelButton.addEventListener('click', closeDrawer);
    overlay.addEventListener('click', closeDrawer);

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && drawerController && drawerController.isOpen()) {
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
  };

  const initDeleteDrawer = () => {
    const overlay = document.querySelector('[data-tag-delete-overlay]');
    const drawer = document.querySelector('[data-tag-delete-drawer]');
    const form = document.querySelector('[data-tag-delete-form]');
    const closeButton = document.querySelector('[data-tag-delete-close]');
    const cancelButton = document.querySelector('[data-tag-delete-cancel]');
    const submitButton = document.querySelector('[data-tag-delete-submit]');
    const dirtyStatus = document.querySelector('[data-tag-delete-dirty]');
    const subtitle = document.querySelector('[data-tag-delete-subtitle]');
    const nameDisplay = document.querySelector('[data-tag-delete-name-display]');
    const nameInline = document.querySelector('[data-tag-delete-name-inline]');
    const colorDisplay = document.querySelector('[data-tag-delete-color-display]');
    const ackInput = document.querySelector('[data-tag-delete-ack]');
    const confirmInput = document.querySelector('[data-tag-delete-confirm]');

    if (
      !overlay || !drawer || !form || !closeButton || !cancelButton || !submitButton || !dirtyStatus || !subtitle
      || !nameDisplay || !nameInline || !colorDisplay || !ackInput || !confirmInput
    ) {
      return;
    }

    const deleteButtons = document.querySelectorAll('[data-tag-delete]');
    const shouldOpenByDefault = drawer.dataset.tagDeleteOpen === 'true';
    let activeTag = {
      id: form.dataset.tagDeleteId || '',
      name: form.dataset.tagDeleteName || '',
      color: colorDisplay.textContent || '—',
    };

    const isValid = () => {
      if (!activeTag.id || !activeTag.name) {
        return false;
      }
      if (!ackInput.checked) {
        return false;
      }
      return confirmInput.value.trim() === activeTag.name;
    };

    const updateSubmitState = () => {
      const valid = isValid();
      submitButton.disabled = !valid;
      if (!activeTag.id) {
        dirtyStatus.textContent = 'Choose tag';
        return;
      }
      if (!ackInput.checked) {
        dirtyStatus.textContent = 'Acknowledge delete';
        return;
      }
      dirtyStatus.textContent = valid ? 'Ready to delete' : 'Type exact tag name';
    };

    const applyTag = ({ id, name, color }) => {
      activeTag = {
        id: id || '',
        name: name || '',
        color: color || '—',
      };
      form.dataset.tagDeleteId = activeTag.id;
      form.dataset.tagDeleteName = activeTag.name;
      form.action = activeTag.id ? `/ui/tags/${activeTag.id}/delete` : '#';
      subtitle.textContent = activeTag.name || 'Permanent removal';
      nameDisplay.textContent = activeTag.name || '—';
      nameInline.textContent = activeTag.name || '—';
      colorDisplay.textContent = activeTag.color || '—';
      if (!shouldOpenByDefault) {
        confirmInput.value = '';
      }
      ackInput.checked = false;
      updateSubmitState();
    };

    const drawerController = createDrawerController({
      overlay,
      drawer,
      onBeforeClose: () => true,
    });

    const openDrawer = () => {
      if (drawerController) {
        drawerController.open();
      }
      window.setTimeout(() => {
        confirmInput.focus();
      }, 100);
    };

    const closeDrawer = () => {
      if (drawerController) {
        drawerController.requestClose();
      }
    };

    deleteButtons.forEach((button) => {
      button.addEventListener('click', () => {
        applyTag({
          id: button.dataset.tagDelete || '',
          name: button.dataset.tagDeleteName || '',
          color: button.dataset.tagDeleteColor || '—',
        });
        openDrawer();
      });
    });

    closeButton.addEventListener('click', closeDrawer);
    cancelButton.addEventListener('click', closeDrawer);
    overlay.addEventListener('click', closeDrawer);

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && drawerController && drawerController.isOpen()) {
        closeDrawer();
      }
    });

    ackInput.addEventListener('change', updateSubmitState);
    confirmInput.addEventListener('input', updateSubmitState);

    applyTag(activeTag);

    if (shouldOpenByDefault) {
      openDrawer();
    }
  };

  initCreateDrawer();
  initEditDrawer();
  initDeleteDrawer();
})();
