(() => {
  const overlay = document.querySelector("[data-range-create-overlay]");
  const drawer = document.querySelector("[data-range-create-drawer]");
  const form = document.querySelector("[data-range-create-form]");
  const addButton = document.querySelector("[data-range-add]");
  const closeButton = document.querySelector("[data-range-create-close]");
  const cancelButton = document.querySelector("[data-range-create-cancel]");
  const saveButton = document.querySelector("[data-range-create-save]");
  const dirtyStatus = document.querySelector("[data-range-create-dirty]");

  if (!overlay || !drawer || !form || !addButton || !closeButton || !cancelButton || !saveButton || !dirtyStatus) {
    return;
  }

  const inputs = form.querySelectorAll("[data-range-input]");
  const nameInput = form.querySelector('[data-range-input="name"]');
  const cidrInput = form.querySelector('[data-range-input="cidr"]');
  const shouldOpenByDefault = drawer.dataset.rangeOpen === "true";

  let initialValues = {};

  const normalizeValue = (value) => value.trim();

  const setInitialValues = () => {
    initialValues = {};
    inputs.forEach((input) => {
      initialValues[input.dataset.rangeInput] = normalizeValue(input.value || "");
    });
  };

  const isDirty = () =>
    Array.from(inputs).some((input) => {
      const key = input.dataset.rangeInput;
      return normalizeValue(input.value || "") !== (initialValues[key] || "");
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
    dirtyStatus.textContent = dirty ? "Ready to create" : "Enter details";
  };

  const drawerController = window.ipocketCreateDrawerController
    ? window.ipocketCreateDrawerController({
      overlay,
      drawer,
      onBeforeClose: () => {
        if (!isDirty()) {
          return true;
        }
        return window.confirm("Discard changes?");
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

  addButton.addEventListener("click", openDrawer);
  closeButton.addEventListener("click", handleClose);
  cancelButton.addEventListener("click", handleClose);
  overlay.addEventListener("click", handleClose);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && drawerController?.isOpen()) {
      handleClose();
    }
  });

  inputs.forEach((input) => {
    input.addEventListener("input", updateSaveState);
  });

  form.addEventListener("submit", (event) => {
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
