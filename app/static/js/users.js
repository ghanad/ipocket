(() => {
  const overlay = document.querySelector('[data-user-create-overlay]');
  const drawer = document.querySelector('[data-user-create-drawer]');
  const form = document.querySelector('[data-user-create-form]');
  const addButton = document.querySelector('[data-user-add]');
  const closeButton = document.querySelector('[data-user-create-close]');
  const cancelButton = document.querySelector('[data-user-create-cancel]');
  const saveButton = document.querySelector('[data-user-create-save]');
  const dirtyStatus = document.querySelector('[data-user-create-dirty]');

  if (!overlay || !drawer || !form || !addButton || !closeButton || !cancelButton || !saveButton || !dirtyStatus) {
    return;
  }

  const usernameInput = form.querySelector('[data-user-create-input="username"]');
  const passwordInput = form.querySelector('[data-user-create-input="password"]');
  const checkboxInputs = [
    form.querySelector('[data-user-create-input="can_edit"]'),
    form.querySelector('[data-user-create-input="is_active"]'),
  ].filter(Boolean);
  const shouldOpenByDefault = drawer.dataset.userCreateOpen === 'true';

  const getState = () => ({
    username: (usernameInput?.value || '').trim(),
    password: (passwordInput?.value || '').trim(),
    can_edit: Boolean(checkboxInputs[0]?.checked),
    is_active: Boolean(checkboxInputs[1]?.checked),
  });

  let initialState = getState();

  const isDirty = () => {
    const current = getState();
    return (
      current.username !== initialState.username ||
      current.password !== initialState.password ||
      current.can_edit !== initialState.can_edit ||
      current.is_active !== initialState.is_active
    );
  };

  const isValid = () => Boolean(getState().username) && Boolean(getState().password);

  const updateSaveState = () => {
    const dirty = isDirty();
    saveButton.disabled = !(dirty && isValid());
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
    setTimeout(() => usernameInput?.focus(), 100);
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

  usernameInput?.addEventListener('input', updateSaveState);
  passwordInput?.addEventListener('input', updateSaveState);
  checkboxInputs.forEach((input) => input.addEventListener('change', updateSaveState));

  form.addEventListener('submit', (event) => {
    if (!isValid()) {
      event.preventDefault();
      updateSaveState();
    }
  });

  initialState = getState();
  updateSaveState();

  if (shouldOpenByDefault) {
    openDrawer();
  }
})();

(() => {
  const overlay = document.querySelector('[data-user-delete-overlay]');
  const drawer = document.querySelector('[data-user-delete-drawer]');
  const form = document.querySelector('[data-user-delete-form]');
  const closeButton = document.querySelector('[data-user-delete-close]');
  const cancelButton = document.querySelector('[data-user-delete-cancel]');
  const submitButton = document.querySelector('[data-user-delete-submit]');
  const dirtyStatus = document.querySelector('[data-user-delete-dirty]');
  const subtitle = document.querySelector('[data-user-delete-subtitle]');
  const nameDisplay = document.querySelector('[data-user-delete-name-display]');
  const nameInline = document.querySelector('[data-user-delete-name-inline]');
  const ackInput = document.querySelector('[data-user-delete-ack]');
  const confirmInput = document.querySelector('[data-user-delete-confirm]');

  if (
    !overlay || !drawer || !form || !closeButton || !cancelButton || !submitButton || !dirtyStatus ||
    !subtitle || !nameDisplay || !nameInline || !ackInput || !confirmInput
  ) {
    return;
  }

  const deleteButtons = document.querySelectorAll('[data-user-delete]');
  const shouldOpenByDefault = drawer.dataset.userDeleteOpen === 'true';

  let activeUser = {
    id: form.dataset.userDeleteId || '',
    name: form.dataset.userDeleteName || '',
  };

  const isValid = () => {
    if (!activeUser.id || !activeUser.name) {
      return false;
    }
    if (!ackInput.checked) {
      return false;
    }
    return confirmInput.value.trim() === activeUser.name;
  };

  const updateSubmitState = () => {
    const valid = isValid();
    submitButton.disabled = !valid;
    if (!activeUser.id) {
      dirtyStatus.textContent = 'Choose user';
      return;
    }
    if (!ackInput.checked) {
      dirtyStatus.textContent = 'Acknowledge delete';
      return;
    }
    dirtyStatus.textContent = valid ? 'Ready to delete' : 'Type exact username';
  };

  const applyUser = ({ id, name }) => {
    activeUser = {
      id: id || '',
      name: name || '',
    };
    form.dataset.userDeleteId = activeUser.id;
    form.dataset.userDeleteName = activeUser.name;
    form.action = activeUser.id ? `/ui/users/${activeUser.id}/delete` : '#';
    subtitle.textContent = activeUser.name || 'Permanent removal';
    nameDisplay.textContent = activeUser.name || '—';
    nameInline.textContent = activeUser.name || '—';
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
    setTimeout(() => confirmInput?.focus(), 100);
  };

  const closeDrawer = () => {
    drawerController?.requestClose();
  };

  deleteButtons.forEach((button) => {
    button.addEventListener('click', () => {
      applyUser({
        id: button.dataset.userDelete || '',
        name: button.dataset.userDeleteName || '',
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

  applyUser(activeUser);

  if (shouldOpenByDefault) {
    openDrawer();
  }
})();

(() => {
  const overlay = document.querySelector('[data-user-edit-overlay]');
  const drawer = document.querySelector('[data-user-edit-drawer]');
  const form = document.querySelector('[data-user-edit-form]');
  const closeButton = document.querySelector('[data-user-edit-close]');
  const cancelButton = document.querySelector('[data-user-edit-cancel]');
  const saveButton = document.querySelector('[data-user-edit-save]');
  const dirtyStatus = document.querySelector('[data-user-edit-dirty]');
  const subtitle = document.querySelector('[data-user-edit-subtitle]');

  if (!overlay || !drawer || !form || !closeButton || !cancelButton || !saveButton || !dirtyStatus || !subtitle) {
    return;
  }

  const editButtons = document.querySelectorAll('[data-user-edit]');
  const usernameInput = form.querySelector('[data-user-edit-username]');
  const canEditInput = form.querySelector('[data-user-edit-input="can_edit"]');
  const isActiveInput = form.querySelector('[data-user-edit-input="is_active"]');
  const passwordInput = form.querySelector('[data-user-edit-input="password"]');
  const shouldOpenByDefault = drawer.dataset.userEditOpen === 'true';

  let activeUserId = form.dataset.userEditId || '';
  let activeRole = form.dataset.userEditRole || '';

  const getState = () => ({
    can_edit: Boolean(canEditInput?.checked),
    is_active: Boolean(isActiveInput?.checked),
    password: (passwordInput?.value || '').trim(),
  });

  let initialState = getState();

  const isDirty = () => {
    const current = getState();
    return (
      current.can_edit !== initialState.can_edit ||
      current.is_active !== initialState.is_active ||
      current.password !== initialState.password
    );
  };

  const isValid = () => Boolean(activeUserId);

  const updateSaveState = () => {
    const dirty = isDirty();
    saveButton.disabled = !(dirty && isValid());
    if (!activeUserId) {
      dirtyStatus.textContent = 'Choose user';
      return;
    }
    dirtyStatus.textContent = dirty ? 'Ready to save' : 'No changes yet';
  };

  const setUserFormData = ({ id, username, role, active }) => {
    activeUserId = id || '';
    activeRole = role || '';
    form.dataset.userEditId = activeUserId;
    form.dataset.userEditRole = activeRole;
    form.action = activeUserId ? `/ui/users/${activeUserId}/edit` : '#';

    if (usernameInput) {
      usernameInput.value = username || '';
    }
    if (subtitle) {
      subtitle.textContent = username || 'Select a user';
    }

    const isSuperuser = activeRole === 'Admin';
    if (canEditInput) {
      canEditInput.checked = isSuperuser || role === 'Editor';
      canEditInput.disabled = isSuperuser;
    }
    if (isActiveInput) {
      isActiveInput.checked = active === '1';
    }
    if (passwordInput) {
      passwordInput.value = '';
    }

    initialState = getState();
    updateSaveState();
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
    setTimeout(() => passwordInput?.focus(), 100);
  };

  const closeDrawer = () => {
    drawerController?.requestClose();
  };

  editButtons.forEach((button) => {
    button.addEventListener('click', () => {
      setUserFormData({
        id: button.dataset.userEdit || '',
        username: button.dataset.userName || '',
        role: button.dataset.userRole || '',
        active: button.dataset.userActive || '0',
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

  canEditInput?.addEventListener('change', updateSaveState);
  isActiveInput?.addEventListener('change', updateSaveState);
  passwordInput?.addEventListener('input', updateSaveState);

  form.addEventListener('submit', (event) => {
    if (!isValid()) {
      event.preventDefault();
      updateSaveState();
    }
  });

  if (activeUserId) {
    setUserFormData({
      id: activeUserId,
      username: usernameInput?.value || '',
      role: activeRole,
      active: isActiveInput?.checked ? '1' : '0',
    });
  } else {
    updateSaveState();
  }

  if (shouldOpenByDefault) {
    openDrawer();
  }
})();
