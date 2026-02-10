(() => {
  const overlay = document.querySelector("[data-range-drawer-overlay]");
  const drawer = document.querySelector("[data-range-drawer]");
  const form = document.querySelector("[data-range-drawer-form]");
  const title = document.querySelector("[data-range-drawer-title]");
  const subtitle = document.querySelector("[data-range-drawer-subtitle]");
  const statusLabel = document.querySelector("[data-range-drawer-status]");
  const saveButton = document.querySelector("[data-range-drawer-save]");
  const closeButton = document.querySelector("[data-range-drawer-close]");
  const cancelButton = document.querySelector("[data-range-drawer-cancel]");

  if (!overlay || !drawer || !form || !title || !subtitle || !statusLabel || !saveButton) {
    return;
  }

  const inputs = form.querySelectorAll("[data-range-input]");
  const state = { open: false, initialValues: {} };

  const getInput = (name) => form.querySelector(`[data-range-input="${name}"]`);

  const updateSaveState = () => {
    const isDirty = Array.from(inputs).some((input) => {
      const key = input.dataset.rangeInput;
      return (input.value || "").trim() !== (state.initialValues[key] || "");
    });
    saveButton.disabled = !isDirty;
    statusLabel.textContent = isDirty ? "Unsaved changes" : "No changes";
  };

  const closeDrawer = () => {
    state.open = false;
    drawer.classList.remove("is-open");
    overlay.classList.remove("is-open");
    document.body.style.overflow = "";
  };

  const openDrawer = ({ mode, assetId, ipAddress, assetType, projectId, notes, tags }) => {
    const ipInput = getInput("ip_address");
    const ipDisplay = getInput("ip_display");
    const typeInput = getInput("type");
    const projectInput = getInput("project_id");
    const notesInput = getInput("notes");
    const tagsInput = getInput("tags");

    if (!ipInput || !ipDisplay || !typeInput || !projectInput || !notesInput || !tagsInput) {
      return;
    }

    const values = {
      ip_address: ipAddress || "",
      ip_display: ipAddress || "",
      type: assetType || "VM",
      project_id: projectId || "",
      notes: notes || "",
      tags: tags || "",
    };

    ipInput.value = values.ip_address;
    ipDisplay.value = values.ip_display;
    typeInput.value = values.type;
    projectInput.value = values.project_id;
    notesInput.value = values.notes;
    tagsInput.value = values.tags;

    const rangeId = window.location.pathname.split("/")[3];
    if (mode === "edit") {
      form.action = `/ui/ranges/${rangeId}/addresses/${assetId}/edit`;
      title.textContent = "Edit IP asset";
      saveButton.textContent = "Save changes";
    } else {
      form.action = `/ui/ranges/${rangeId}/addresses/add`;
      title.textContent = "Add IP asset";
      saveButton.textContent = "Allocate";
    }

    subtitle.textContent = ipAddress || "—";
    state.initialValues = values;
    updateSaveState();

    state.open = true;
    drawer.classList.add("is-open");
    overlay.classList.add("is-open");
    document.body.style.overflow = "hidden";
  };

  document.querySelectorAll("[data-range-address-add]").forEach((button) => {
    button.addEventListener("click", () => {
      openDrawer({
        mode: "add",
        ipAddress: button.dataset.ipAddress,
      });
    });
  });

  document.querySelectorAll("[data-range-address-edit]").forEach((button) => {
    button.addEventListener("click", () => {
      openDrawer({
        mode: "edit",
        assetId: button.dataset.assetId,
        ipAddress: button.dataset.ipAddress,
        assetType: button.dataset.type,
        projectId: button.dataset.projectId,
        notes: button.dataset.notes,
        tags: button.dataset.tags,
      });
    });
  });

  [overlay, closeButton, cancelButton].forEach((element) => {
    if (!element) {
      return;
    }
    element.addEventListener("click", closeDrawer);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && state.open) {
      closeDrawer();
    }
  });

  inputs.forEach((input) => {
    input.addEventListener("input", updateSaveState);
    input.addEventListener("change", updateSaveState);
  });
})();
