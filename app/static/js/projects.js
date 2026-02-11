(() => {
  const overlay = document.querySelector('[data-project-create-overlay]');
  const drawer = document.querySelector('[data-project-create-drawer]');
  const form = document.querySelector('[data-project-create-form]');
  const addButton = document.querySelector('[data-project-add]');
  const closeButton = document.querySelector('[data-project-create-close]');
  const cancelButton = document.querySelector('[data-project-create-cancel]');
  const saveButton = document.querySelector('[data-project-create-save]');
  const dirtyStatus = document.querySelector('[data-project-create-dirty]');

  if (!overlay || !drawer || !form || !addButton || !closeButton || !cancelButton || !saveButton || !dirtyStatus) {
    return;
  }

  const inputs = form.querySelectorAll('[data-project-input]');
  const nameInput = form.querySelector('[data-project-input="name"]');
  const shouldOpenByDefault = drawer.dataset.projectOpen === 'true';

  let initialValues = {};

  const normalizeValue = (value) => value.trim();

  const setInitialValues = () => {
    initialValues = {};
    inputs.forEach((input) => {
      initialValues[input.dataset.projectInput] = normalizeValue(input.value || '');
    });
  };

  const isDirty = () =>
    Array.from(inputs).some((input) => {
      const key = input.dataset.projectInput;
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
  const overlay = document.querySelector('[data-project-edit-overlay]');
  const drawer = document.querySelector('[data-project-edit-drawer]');
  const form = document.querySelector('[data-project-edit-form]');
  const closeButton = document.querySelector('[data-project-edit-close]');
  const cancelButton = document.querySelector('[data-project-edit-cancel]');
  const saveButton = document.querySelector('[data-project-edit-save]');
  const dirtyStatus = document.querySelector('[data-project-edit-dirty]');

  if (!overlay || !drawer || !form || !closeButton || !cancelButton || !saveButton || !dirtyStatus) {
    return;
  }

  const editButtons = document.querySelectorAll('[data-project-edit]');
  const inputs = form.querySelectorAll('[data-project-edit-input]');
  const nameInput = form.querySelector('[data-project-edit-input="name"]');
  const descriptionInput = form.querySelector('[data-project-edit-input="description"]');
  const colorInput = form.querySelector('[data-project-edit-input="color"]');
  const shouldOpenByDefault = drawer.dataset.projectEditOpen === 'true';

  let initialValues = {};
  let activeProjectId = form.dataset.projectEditId || '';

  const normalizeValue = (value) => value.trim();

  const setInitialValues = () => {
    initialValues = {};
    inputs.forEach((input) => {
      initialValues[input.dataset.projectEditInput] = normalizeValue(input.value || '');
    });
  };

  const isDirty = () =>
    Array.from(inputs).some((input) => {
      const key = input.dataset.projectEditInput;
      return normalizeValue(input.value || '') !== (initialValues[key] || '');
    });

  const validate = () => Boolean(activeProjectId) && Boolean(nameInput?.value.trim());

  const updateSaveState = () => {
    const dirty = isDirty();
    const valid = validate();
    saveButton.disabled = !(dirty && valid);
    if (!activeProjectId) {
      dirtyStatus.textContent = 'Choose project';
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

  const setProjectFormData = ({ id, name, description, color }) => {
    activeProjectId = id || '';
    form.dataset.projectEditId = activeProjectId;
    form.action = activeProjectId ? `/ui/projects/${activeProjectId}/edit` : '#';
    if (nameInput) {
      nameInput.value = name || '';
    }
    if (descriptionInput) {
      descriptionInput.value = description || '';
    }
    if (colorInput) {
      colorInput.value = color || '#94a3b8';
    }
    setInitialValues();
    updateSaveState();
  };

  editButtons.forEach((button) => {
    button.addEventListener('click', () => {
      setProjectFormData({
        id: button.dataset.projectEdit || '',
        name: button.dataset.projectName || '',
        description: button.dataset.projectDescription || '',
        color: button.dataset.projectColor || '#94a3b8',
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
  const overlay = document.querySelector('[data-project-delete-overlay]');
  const drawer = document.querySelector('[data-project-delete-drawer]');
  const form = document.querySelector('[data-project-delete-form]');
  const closeButton = document.querySelector('[data-project-delete-close]');
  const cancelButton = document.querySelector('[data-project-delete-cancel]');
  const submitButton = document.querySelector('[data-project-delete-submit]');
  const dirtyStatus = document.querySelector('[data-project-delete-dirty]');
  const subtitle = document.querySelector('[data-project-delete-subtitle]');
  const nameDisplay = document.querySelector('[data-project-delete-name-display]');
  const nameInline = document.querySelector('[data-project-delete-name-inline]');
  const descriptionDisplay = document.querySelector('[data-project-delete-description-display]');
  const ackInput = document.querySelector('[data-project-delete-ack]');
  const confirmInput = document.querySelector('[data-project-delete-confirm]');

  if (
    !overlay || !drawer || !form || !closeButton || !cancelButton || !submitButton || !dirtyStatus || !subtitle ||
    !nameDisplay || !nameInline || !descriptionDisplay || !ackInput || !confirmInput
  ) {
    return;
  }

  const deleteButtons = document.querySelectorAll('[data-project-delete]');
  const shouldOpenByDefault = drawer.dataset.projectDeleteOpen === 'true';
  let activeProject = {
    id: form.dataset.projectDeleteId || '',
    name: form.dataset.projectDeleteName || '',
    description: descriptionDisplay.textContent || '—',
  };

  const isValid = () => {
    if (!activeProject.id || !activeProject.name) {
      return false;
    }
    if (!ackInput.checked) {
      return false;
    }
    return confirmInput.value.trim() === activeProject.name;
  };

  const updateSubmitState = () => {
    const valid = isValid();
    submitButton.disabled = !valid;
    if (!activeProject.id) {
      dirtyStatus.textContent = 'Choose project';
      return;
    }
    if (!ackInput.checked) {
      dirtyStatus.textContent = 'Acknowledge delete';
      return;
    }
    dirtyStatus.textContent = valid ? 'Ready to delete' : 'Type exact project name';
  };

  const applyProject = ({ id, name, description }) => {
    activeProject = {
      id: id || '',
      name: name || '',
      description: description || '—',
    };
    form.dataset.projectDeleteId = activeProject.id;
    form.dataset.projectDeleteName = activeProject.name;
    form.action = activeProject.id ? `/ui/projects/${activeProject.id}/delete` : '#';
    subtitle.textContent = activeProject.name || 'Permanent removal';
    nameDisplay.textContent = activeProject.name || '—';
    nameInline.textContent = activeProject.name || '—';
    descriptionDisplay.textContent = activeProject.description || '—';
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
      applyProject({
        id: button.dataset.projectDelete || '',
        name: button.dataset.projectDeleteName || '',
        description: button.dataset.projectDeleteDescription || '—',
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

  applyProject(activeProject);

  if (shouldOpenByDefault) {
    openDrawer();
  }
})();
