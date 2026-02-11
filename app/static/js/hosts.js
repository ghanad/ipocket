(() => {
  const overlay = document.querySelector("[data-host-drawer-overlay]");
  const drawer = document.querySelector("[data-host-drawer]");
  const drawerTitle = document.querySelector("[data-host-drawer-title]");
  const drawerSubtitle = document.querySelector("[data-host-drawer-subtitle]");
  const drawerMeta = document.querySelector("[data-host-drawer-meta]");
  const projectField = document.querySelector("[data-host-project-field]");
  const closeButton = document.querySelector("[data-host-drawer-close]");
  const cancelButton = document.querySelector("[data-host-drawer-cancel]");
  const saveButton = document.querySelector("[data-host-drawer-save]");
  const form = document.querySelector("[data-host-edit-form]");
  const projectPill = document.querySelector("[data-host-drawer-project]");
  const statusPill = document.querySelector("[data-host-drawer-status]");
  const projectSelect = document.querySelector("[data-host-project-select]");
  const dirtyStatus = document.querySelector("[data-host-drawer-dirty]");
  const inputs = form ? form.querySelectorAll("[data-host-input]") : [];
  const errorMessages = form ? form.querySelectorAll("[data-host-error]") : [];
  let initialValues = {};
  let isAddMode = false;
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

  if (
    !overlay ||
    !drawer ||
    !form ||
    !drawerTitle ||
    !drawerSubtitle ||
    !closeButton ||
    !cancelButton ||
    !saveButton ||
    !projectPill ||
    !statusPill ||
    !projectSelect ||
    !dirtyStatus
  ) {
    return;
  }

  const isValidIPv4 = (value) => {
    if (!value) return true;
    const trimmed = value.trim();
    const regex = /^(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)){3}$/;
    return regex.test(trimmed);
  };

  const setError = (field, message) => {
    const error = form.querySelector(`[data-host-error="${field}"]`);
    if (!error) return;
    if (message) {
      error.textContent = message;
      error.style.display = "block";
    } else {
      error.textContent = "";
      error.style.display = "none";
    }
  };

  const clearErrors = () => {
    errorMessages.forEach((error) => {
      error.textContent = "";
      error.style.display = "none";
    });
  };

  const normalizeValue = (value) => value.trim();

  const isDirty = () =>
    Array.from(inputs).some((input) => {
      const key = input.dataset.hostInput;
      return normalizeValue(input.value) !== (initialValues[key] || "");
    });

  const validate = () => {
    let valid = true;
    const nameInput = form.querySelector('[data-host-input="name"]');
    const osInput = form.querySelector('[data-host-input="os_ips"]');
    const bmcInput = form.querySelector('[data-host-input="bmc_ips"]');

    if (nameInput && !nameInput.value.trim()) {
      setError("name", "Host name is required.");
      valid = false;
    } else {
      setError("name", "");
    }

    if (osInput && osInput.value.trim() && !isValidIPv4(osInput.value)) {
      setError("os_ips", "Enter a valid IPv4 address.");
      valid = false;
    } else {
      setError("os_ips", "");
    }

    if (bmcInput && bmcInput.value.trim() && !isValidIPv4(bmcInput.value)) {
      setError("bmc_ips", "Enter a valid IPv4 address.");
      valid = false;
    } else {
      setError("bmc_ips", "");
    }

    return valid;
  };

  const updateSaveState = () => {
    const dirty = isDirty();
    const valid = validate();
    saveButton.disabled = !(dirty && valid);
    if (isAddMode) {
      dirtyStatus.textContent = dirty ? "Ready to create" : "Enter details";
    } else {
      dirtyStatus.textContent = dirty ? "Unsaved changes" : "No changes";
    }
  };

  const openDrawerForAdd = () => {
    isAddMode = true;
    clearErrors();
    inputs.forEach((input) => {
      input.value = "";
    });
    form.action = "/ui/hosts";
    drawerTitle.textContent = "Add Host";
    drawerSubtitle.textContent = "Create a new host";
    drawerMeta.style.display = "none";
    if (projectField) {
      projectField.style.display = "";
    }
    const defaultOption = projectSelect.querySelector('option[value=""]');
    if (defaultOption) {
      defaultOption.textContent = "Unassigned";
    }
    projectSelect.value = "";
    initialValues = {
      name: "",
      vendor_id: "",
      project_id: "",
      os_ips: "",
      bmc_ips: "",
      notes: "",
    };
    updateSaveState();
    saveButton.textContent = "Create Host";
    drawerController?.open();
    // Focus the name input
    const nameInput = form.querySelector('[data-host-input="name"]');
    if (nameInput) {
      setTimeout(() => nameInput.focus(), 100);
    }
  };

  const openDrawerForEdit = (hostData) => {
    isAddMode = false;
    clearErrors();
    inputs.forEach((input) => {
      const key = input.dataset.hostInput;
      input.value = hostData[key] || "";
    });
    form.action = `/ui/hosts/${hostData.id}/edit`;
    drawerTitle.textContent = "Edit Host";
    drawerSubtitle.textContent = hostData.name || "—";
    drawerMeta.style.display = "flex";
    if (projectField) {
      projectField.style.display = "";
    }
    projectPill.textContent = `Project: ${hostData.project_label || "Unassigned"}`;
    statusPill.textContent = `Status: ${hostData.status || "Free"}`;
    const defaultOption = projectSelect.querySelector('option[value=""]');
    if (defaultOption) {
      defaultOption.textContent = hostData.project_label || "Unassigned";
    }
    if (hostData.project_label && hostData.project_label !== "Unassigned" && hostData.project_label !== "Multiple") {
      const match = Array.from(projectSelect.options).find(
        (option) => option.dataset.projectName === hostData.project_label,
      );
      projectSelect.value = match ? match.value : "";
    } else {
      projectSelect.value = "";
    }
    initialValues = {
      name: hostData.name || "",
      vendor_id: hostData.vendor_id || "",
      project_id: projectSelect.value || "",
      os_ips: hostData.os_ips || "",
      bmc_ips: hostData.bmc_ips || "",
      notes: hostData.notes || "",
    };
    updateSaveState();
    saveButton.textContent = "Save changes";
    drawerController?.open();
  };

  // Add Host button
  document.querySelectorAll("[data-host-add]").forEach((button) => {
    button.addEventListener("click", () => {
      openDrawerForAdd();
    });
  });

  // Edit buttons
  document.querySelectorAll("[data-host-edit]").forEach((button) => {
    button.addEventListener("click", () => {
      const hostData = {
        id: button.dataset.hostEdit,
        name: button.dataset.hostName || "",
        vendor_id: button.dataset.hostVendorId || "",
        project_label: (() => {
          const count = Number.parseInt(button.dataset.hostProjectCount || "0", 10);
          if (Number.isNaN(count) || count === 0) {
            return "Unassigned";
          }
          if (count > 1) {
            return "Multiple";
          }
          return button.dataset.hostProjectName || "Unassigned";
        })(),
        os_ips: button.dataset.hostOsIps || "",
        bmc_ips: button.dataset.hostBmcIps || "",
        notes: button.dataset.hostNotes || "",
        status: button.dataset.hostStatus || "Free",
      };
      openDrawerForEdit(hostData);
    });
  });

  const handleClose = () => {
    if (!drawerController) {
      return;
    }
    drawerController.requestClose();
    if (!drawerController.isOpen()) {
      isAddMode = false;
    }
  };

  closeButton.addEventListener("click", handleClose);
  cancelButton.addEventListener("click", handleClose);
  overlay.addEventListener("click", handleClose);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && drawerController?.isOpen()) {
      handleClose();
    }
  });

  inputs.forEach((input) => {
    input.addEventListener("input", () => {
      updateSaveState();
    });
  });

  form.addEventListener("submit", (event) => {
    if (!validate()) {
      event.preventDefault();
      updateSaveState();
    }
  });
})();
