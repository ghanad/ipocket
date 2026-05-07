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
  const deleteButton = document.querySelector("[data-host-drawer-delete]");
  const form = document.querySelector("[data-host-edit-form]");
  const deleteForm = document.querySelector("[data-host-delete-form]");
  const deleteNameDisplay = document.querySelector("[data-host-delete-name-display]");
  const deleteLinked = document.querySelector("[data-host-delete-linked-value]");
  const deleteNameInline = document.querySelector("[data-host-delete-name-inline]");
  const deleteAck = document.querySelector("[data-host-delete-ack]");
  const deleteConfirmInput = document.querySelector("[data-host-delete-confirm]");
  const projectPill = document.querySelector("[data-host-drawer-project]");
  const statusPill = document.querySelector("[data-host-drawer-status]");
  const projectSelect = document.querySelector("[data-host-project-select]");
  const dirtyStatus = document.querySelector("[data-host-drawer-dirty]");
  const inputs = form ? form.querySelectorAll("[data-host-input]") : [];
  const errorMessages = form ? form.querySelectorAll("[data-host-error]") : [];
  const filterForm = document.querySelector("[data-host-filters]");
  const tagFilterInput = filterForm
    ? filterForm.querySelector("[data-host-tag-filter-input]")
    : null;
  const tagFilterSelected = filterForm
    ? filterForm.querySelector("[data-host-tag-filter-selected]")
    : null;
  const tagFilterSuggestions = filterForm
    ? filterForm.querySelector("[data-host-tag-filter-suggestions]")
    : null;
  let initialValues = {};
  let isAddMode = false;
  let isDeleteMode = false;
  let currentHost = null;
  let activeTagsPopoverTrigger = null;
  let tagsPopover = null;
  let tagsPopoverOpenTimer = null;
  let tagsPopoverCloseTimer = null;
  const shouldOpenDeleteByDefault = drawer?.dataset.hostDeleteOpen === "true";
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

  const ensureTagsPopover = () => {
    if (tagsPopover) {
      return tagsPopover;
    }
    tagsPopover = document.createElement("section");
    tagsPopover.className = "ip-tags-popover";
    tagsPopover.setAttribute("role", "dialog");
    tagsPopover.setAttribute("aria-modal", "false");
    tagsPopover.hidden = true;
    tagsPopover.innerHTML = `
      <header class="ip-tags-popover-header">
        <h3 class="ip-tags-popover-title" data-tags-popover-title></h3>
        <button type="button" class="ip-tags-popover-close" data-tags-popover-close aria-label="Close tags popover">✕</button>
      </header>
      <label class="field ip-tags-popover-search-field">
        <span class="visually-hidden">Search tags</span>
        <input class="input" type="search" placeholder="Filter tags" data-tags-popover-search />
      </label>
      <div class="ip-tags-popover-list" data-tags-popover-list></div>
    `;
    document.body.appendChild(tagsPopover);
    const closeButton = tagsPopover.querySelector("[data-tags-popover-close]");
    if (closeButton) {
      closeButton.addEventListener("click", () => closeTagsPopover());
    }
    const searchInput = tagsPopover.querySelector("[data-tags-popover-search]");
    if (searchInput) {
      searchInput.addEventListener("input", renderTagsPopoverList);
    }
    tagsPopover.addEventListener("mouseenter", () => {
      if (tagsPopoverCloseTimer) {
        window.clearTimeout(tagsPopoverCloseTimer);
        tagsPopoverCloseTimer = null;
      }
    });
    tagsPopover.addEventListener("mouseleave", () => {
      scheduleCloseTagsPopover();
    });
    return tagsPopover;
  };

  const scheduleOpenTagsPopover = (trigger, delay = 120) => {
    if (!trigger) {
      return;
    }
    if (tagsPopoverCloseTimer) {
      window.clearTimeout(tagsPopoverCloseTimer);
      tagsPopoverCloseTimer = null;
    }
    if (tagsPopoverOpenTimer) {
      window.clearTimeout(tagsPopoverOpenTimer);
      tagsPopoverOpenTimer = null;
    }
    tagsPopoverOpenTimer = window.setTimeout(() => {
      openTagsPopover(trigger, { focusSearch: false });
      tagsPopoverOpenTimer = null;
    }, delay);
  };

  const scheduleCloseTagsPopover = (delay = 180) => {
    if (tagsPopoverOpenTimer) {
      window.clearTimeout(tagsPopoverOpenTimer);
      tagsPopoverOpenTimer = null;
    }
    if (tagsPopoverCloseTimer) {
      window.clearTimeout(tagsPopoverCloseTimer);
      tagsPopoverCloseTimer = null;
    }
    tagsPopoverCloseTimer = window.setTimeout(() => {
      closeTagsPopover();
      tagsPopoverCloseTimer = null;
    }, delay);
  };

  const closeTagsPopover = () => {
    if (tagsPopoverOpenTimer) {
      window.clearTimeout(tagsPopoverOpenTimer);
      tagsPopoverOpenTimer = null;
    }
    if (tagsPopoverCloseTimer) {
      window.clearTimeout(tagsPopoverCloseTimer);
      tagsPopoverCloseTimer = null;
    }
    if (activeTagsPopoverTrigger) {
      activeTagsPopoverTrigger.setAttribute("aria-expanded", "false");
    }
    activeTagsPopoverTrigger = null;
    if (tagsPopover) {
      tagsPopover.hidden = true;
      tagsPopover.dataset.tagsPopoverItems = "[]";
    }
  };

  const parseTagsPopoverItems = () => {
    if (!tagsPopover) {
      return [];
    }
    try {
      const parsed = JSON.parse(tagsPopover.dataset.tagsPopoverItems || "[]");
      return Array.isArray(parsed) ? parsed : [];
    } catch (error) {
      return [];
    }
  };

  const renderTagsPopoverList = () => {
    if (!tagsPopover) {
      return;
    }
    const list = tagsPopover.querySelector("[data-tags-popover-list]");
    const searchInput = tagsPopover.querySelector("[data-tags-popover-search]");
    if (!list) {
      return;
    }
    const term = ((searchInput && searchInput.value) || "").trim().toLowerCase();
    const items = parseTagsPopoverItems().filter((item) => {
      const name = String(item?.name || "").toLowerCase();
      return !term || name.includes(term);
    });
    list.replaceChildren();
    if (!items.length) {
      const emptyMessage = document.createElement("p");
      emptyMessage.className = "muted ip-tags-popover-empty";
      emptyMessage.textContent = "No matching tags.";
      list.appendChild(emptyMessage);
      return;
    }
    items.forEach((item) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "tag tag-color tag-filter-chip";
      button.dataset.hostPopoverTag = String(item?.name || "");
      button.style.setProperty("--tag-color", String(item?.color || "#94a3b8"));
      if (typeof window.ipocketApplyTagContrast === "function") {
        window.ipocketApplyTagContrast(button);
      }
      button.textContent = String(item?.name || "");
      list.appendChild(button);
    });
  };

  const positionTagsPopover = () => {
    if (!tagsPopover || !activeTagsPopoverTrigger || tagsPopover.hidden) {
      return;
    }
    const gutter = 12;
    const rect = activeTagsPopoverTrigger.getBoundingClientRect();
    const popoverWidth = Math.min(
      window.innerWidth - gutter * 2,
      window.innerWidth < 640 ? window.innerWidth - 16 : 340,
    );
    tagsPopover.style.width = `${popoverWidth}px`;
    tagsPopover.style.maxWidth = `${popoverWidth}px`;
    const popoverRect = tagsPopover.getBoundingClientRect();
    const availableBelow = window.innerHeight - rect.bottom;
    const top = availableBelow > popoverRect.height + gutter
      ? rect.bottom + 6
      : rect.top - popoverRect.height - 6;
    const clampedTop = Math.min(
      window.innerHeight - popoverRect.height - gutter,
      Math.max(gutter, top),
    );
    const left = Math.min(
      window.innerWidth - popoverRect.width - gutter,
      Math.max(gutter, rect.left),
    );
    tagsPopover.style.top = `${clampedTop + window.scrollY}px`;
    tagsPopover.style.left = `${left + window.scrollX}px`;
  };

  const openTagsPopover = (trigger, { focusSearch = true } = {}) => {
    if (!trigger) {
      return;
    }
    ensureTagsPopover();
    if (!tagsPopover) {
      return;
    }
    let items = [];
    try {
      const parsed = JSON.parse(trigger.dataset.tagsJson || "[]");
      if (Array.isArray(parsed)) {
        items = parsed;
      }
    } catch (error) {
      items = [];
    }
    const hostName = trigger.dataset.tagsIp || "Host";
    const title = tagsPopover.querySelector("[data-tags-popover-title]");
    const searchInput = tagsPopover.querySelector("[data-tags-popover-search]");
    if (activeTagsPopoverTrigger && activeTagsPopoverTrigger !== trigger) {
      activeTagsPopoverTrigger.setAttribute("aria-expanded", "false");
    }
    activeTagsPopoverTrigger = trigger;
    activeTagsPopoverTrigger.setAttribute("aria-expanded", "true");
    tagsPopover.dataset.tagsPopoverItems = JSON.stringify(items);
    if (title) {
      title.textContent = `IP tags for ${hostName}`;
    }
    if (searchInput) {
      searchInput.value = "";
    }
    tagsPopover.hidden = false;
    renderTagsPopoverList();
    positionTagsPopover();
    if (searchInput && focusSearch) {
      searchInput.focus();
    }
  };

  const bindTagsMoreTriggers = (root = document) => {
    root.querySelectorAll("[data-tags-more-toggle]").forEach((trigger) => {
      if (trigger.dataset.tagsMoreBound) {
        return;
      }
      trigger.dataset.tagsMoreBound = "true";
      trigger.addEventListener("mouseenter", () => {
        if (activeTagsPopoverTrigger === trigger && tagsPopover && !tagsPopover.hidden) {
          if (tagsPopoverCloseTimer) {
            window.clearTimeout(tagsPopoverCloseTimer);
            tagsPopoverCloseTimer = null;
          }
          return;
        }
        scheduleOpenTagsPopover(trigger);
      });
      trigger.addEventListener("mouseleave", (event) => {
        const nextTarget = event.relatedTarget;
        if (
          nextTarget &&
          (trigger.contains(nextTarget) || (tagsPopover && tagsPopover.contains(nextTarget)))
        ) {
          return;
        }
        scheduleCloseTagsPopover();
      });
      trigger.addEventListener("focus", () => {
        openTagsPopover(trigger);
      });
      trigger.addEventListener("blur", (event) => {
        const nextTarget = event.relatedTarget;
        if (nextTarget && tagsPopover && tagsPopover.contains(nextTarget)) {
          return;
        }
        scheduleCloseTagsPopover(0);
      });
    });
  };

  if (
    !overlay ||
    !drawer ||
    !form ||
    !drawerTitle ||
    !drawerSubtitle ||
    !closeButton ||
    !cancelButton ||
    !saveButton ||
    !deleteButton ||
    !projectPill ||
    !statusPill ||
    !projectSelect ||
    !dirtyStatus ||
    !deleteForm ||
    !deleteNameDisplay ||
    !deleteLinked ||
    !deleteNameInline ||
    !deleteAck ||
    !deleteConfirmInput
  ) {
    return;
  }

  const setDrawerMode = (mode) => {
    isDeleteMode = mode === "delete";
    drawer.dataset.hostDrawerMode = isDeleteMode ? "delete" : "edit";
    saveButton.hidden = isDeleteMode;
    saveButton.style.display = isDeleteMode ? "none" : "";
    deleteButton.hidden = !isDeleteMode;
    deleteButton.style.display = isDeleteMode ? "" : "none";
    form.hidden = isDeleteMode;
    form.style.display = isDeleteMode ? "none" : "flex";
    deleteForm.hidden = !isDeleteMode;
    deleteForm.style.display = isDeleteMode ? "flex" : "none";
  };

  const normalizeTagValue = (value) => String(value || "").trim().toLowerCase();

  const getTagColor = (rawValue) => {
    if (!tagFilterSuggestions) {
      return "";
    }
    const normalized = normalizeTagValue(rawValue);
    const option = Array.from(tagFilterSuggestions.options).find(
      (entry) => normalizeTagValue(entry.value) === normalized,
    );
    return option ? option.dataset.tagColor || "" : "";
  };

  const applyTagFilterChipColor = (chip, rawValue) => {
    if (!(chip instanceof HTMLElement)) {
      return;
    }
    const color = getTagColor(rawValue);
    if (color) {
      chip.style.setProperty("--tag-color", color);
    }
    if (typeof window.ipocketApplyTagContrast === "function") {
      window.ipocketApplyTagContrast(chip);
    }
  };

  const listSelectedTags = () => {
    if (!tagFilterSelected) {
      return [];
    }
    return Array.from(tagFilterSelected.querySelectorAll('input[name="tag"]')).map(
      (input) => normalizeTagValue(input.value),
    );
  };

  const submitHostFilters = () => {
    if (!filterForm) {
      return;
    }
    if (window.htmx && typeof window.htmx.ajax === "function") {
      const url = new URL(filterForm.action || "/ui/hosts", window.location.origin);
      const params = new URLSearchParams(new FormData(filterForm));
      url.search = params.toString();
      window.htmx.ajax("GET", url.toString(), {
        target: "#host-table-container",
        swap: "innerHTML",
        pushURL: url.pathname + (url.search ? `?${url.searchParams.toString()}` : ""),
      });
      return;
    }
    filterForm.submit();
  };

  const addTagFilter = (rawValue) => {
    if (!tagFilterSelected) {
      return false;
    }
    const value = normalizeTagValue(rawValue);
    if (!value || listSelectedTags().includes(value)) {
      return false;
    }
    const entry = document.createElement("span");
    entry.className = "tag-filter-entry";
    entry.dataset.hostTagFilterEntry = value;

    const hidden = document.createElement("input");
    hidden.type = "hidden";
    hidden.name = "tag";
    hidden.value = value;

    const chip = document.createElement("button");
    chip.className = "tag tag-color tag-filter-chip";
    chip.type = "button";
    chip.dataset.hostRemoveTagFilter = value;
    chip.textContent = `${value} ×`;
    applyTagFilterChipColor(chip, value);

    entry.append(hidden, chip);
    tagFilterSelected.appendChild(entry);
    return true;
  };

  const removeTagFilter = (value) => {
    if (!tagFilterSelected) {
      return false;
    }
    const normalized = normalizeTagValue(value);
    const entry = tagFilterSelected.querySelector(
      `[data-host-tag-filter-entry="${normalized}"]`,
    );
    if (!entry) {
      return false;
    }
    entry.remove();
    return true;
  };

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
    if (isDeleteMode) {
      return;
    }
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
    currentHost = null;
    clearErrors();
    setDrawerMode("edit");
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
    currentHost = null;
    clearErrors();
    setDrawerMode("edit");
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

  const updateDeleteState = () => {
    if (!isDeleteMode || !currentHost) {
      return;
    }
    const valid = deleteAck.checked && deleteConfirmInput.value.trim() === currentHost.name;
    deleteButton.disabled = !valid;
    if (!deleteAck.checked) {
      dirtyStatus.textContent = "Confirm deletion";
      return;
    }
    dirtyStatus.textContent = valid ? "Ready to delete" : "Type exact host name";
  };

  const openDrawerForDelete = (hostData, options = {}) => {
    isAddMode = false;
    currentHost = hostData;
    clearErrors();
    setDrawerMode("delete");
    drawerTitle.textContent = "Delete host?";
    drawerSubtitle.textContent = "Permanent and cannot be undone.";
    projectPill.textContent = `Project: ${hostData.project_label || "Unassigned"}`;
    statusPill.textContent = `Status: ${hostData.status || "Free"}`;
    deleteNameDisplay.textContent = hostData.name || "—";
    deleteNameInline.textContent = hostData.name || "—";
    deleteLinked.textContent = String(hostData.linked_count || 0);
    deleteForm.action = hostData.id ? `/ui/hosts/${hostData.id}/delete` : "#";
    deleteButton.disabled = true;
    deleteAck.checked = false;
    dirtyStatus.textContent = "Confirm deletion";
    if (!options.keepConfirmation) {
      deleteConfirmInput.value = "";
    }
    updateDeleteState();
    drawerController?.open();
    setTimeout(() => {
      deleteConfirmInput.focus();
    }, 100);
  };

  // Add Host button
  document.querySelectorAll("[data-host-add]").forEach((button) => {
    button.addEventListener("click", () => {
      openDrawerForAdd();
    });
  });

  if (shouldOpenDeleteByDefault) {
    openDrawerForDelete(
      {
        id: deleteForm.dataset.hostDeleteId || "",
        name: deleteForm.dataset.hostDeleteName || "",
        linked_count: Number.parseInt(deleteLinked.textContent || "0", 10) || 0,
      },
      { keepConfirmation: true },
    );
  }

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

  if (tagFilterSelected) {
    tagFilterSelected.querySelectorAll("[data-host-remove-tag-filter]").forEach((chip) => {
      applyTagFilterChipColor(chip, chip.getAttribute("data-host-remove-tag-filter") || "");
    });
  }

  if (tagFilterInput) {
    tagFilterInput.addEventListener("change", () => {
      if (addTagFilter(tagFilterInput.value)) {
        tagFilterInput.value = "";
        submitHostFilters();
      }
    });
    tagFilterInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === ",") {
        event.preventDefault();
        if (addTagFilter(tagFilterInput.value)) {
          tagFilterInput.value = "";
          submitHostFilters();
        }
      }
    });
  }

  if (filterForm && !window.htmx) {
    filterForm.querySelectorAll("select").forEach((select) => {
      select.addEventListener("change", submitHostFilters);
    });
  }

  document.body.addEventListener("click", (event) => {
    const moreTagsButton = event.target.closest("[data-tags-more-toggle]");
    if (moreTagsButton) {
      event.preventDefault();
      openTagsPopover(moreTagsButton);
      return;
    }
    if (activeTagsPopoverTrigger && tagsPopover && !tagsPopover.contains(event.target)) {
      closeTagsPopover();
    }

    const popoverTag = event.target.closest("[data-host-popover-tag]");
    if (popoverTag) {
      event.preventDefault();
      if (addTagFilter(popoverTag.dataset.hostPopoverTag || "")) {
        submitHostFilters();
      }
      closeTagsPopover();
      return;
    }

    const editButton = event.target.closest("[data-host-edit]");
    if (editButton) {
      event.preventDefault();
      const hostData = {
        id: editButton.dataset.hostEdit,
        name: editButton.dataset.hostName || "",
        vendor_id: editButton.dataset.hostVendorId || "",
        project_label: (() => {
          const count = Number.parseInt(editButton.dataset.hostProjectCount || "0", 10);
          if (Number.isNaN(count) || count === 0) {
            return "Unassigned";
          }
          if (count > 1) {
            return "Multiple";
          }
          return editButton.dataset.hostProjectName || "Unassigned";
        })(),
        os_ips: editButton.dataset.hostOsIps || "",
        bmc_ips: editButton.dataset.hostBmcIps || "",
        notes: editButton.dataset.hostNotes || "",
        status: editButton.dataset.hostStatus || "Free",
      };
      openDrawerForEdit(hostData);
      return;
    }

    const deleteHostButton = event.target.closest("[data-host-delete]");
    if (deleteHostButton) {
      event.preventDefault();
      openDrawerForDelete({
        id: deleteHostButton.dataset.hostDelete || "",
        name: deleteHostButton.dataset.hostDeleteName || "",
        linked_count: Number.parseInt(deleteHostButton.dataset.hostDeleteLinked || "0", 10) || 0,
      });
      return;
    }

    const removeTagButton = event.target.closest("[data-host-remove-tag-filter]");
    if (!removeTagButton) {
      return;
    }
    event.preventDefault();
    if (removeTagFilter(removeTagButton.dataset.hostRemoveTagFilter || "")) {
      submitHostFilters();
    }
  });

  bindTagsMoreTriggers();
  document.body.addEventListener("htmx:afterSwap", (event) => {
    bindTagsMoreTriggers(event.target);
  });
  window.addEventListener("resize", positionTagsPopover);
  window.addEventListener("scroll", positionTagsPopover, true);

  form.addEventListener("submit", (event) => {
    if (!validate()) {
      event.preventDefault();
      updateSaveState();
    }
  });

  deleteAck.addEventListener("change", updateDeleteState);
  deleteConfirmInput.addEventListener("input", updateDeleteState);
})();
