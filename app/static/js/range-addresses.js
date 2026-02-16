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
  const filterForm = document.querySelector(".filters-grid");
  const tagFilterInput = filterForm
    ? filterForm.querySelector("[data-range-tag-filter-input]")
    : null;
  const tagFilterSelected = filterForm
    ? filterForm.querySelector("[data-range-tag-filter-selected]")
    : null;
  const tagFilterSuggestions = filterForm
    ? filterForm.querySelector("[data-range-tag-filter-suggestions]")
    : null;
  let activeTagsPopoverTrigger = null;
  let tagsPopover = null;
  let tagsPopoverOpenTimer = null;
  let tagsPopoverCloseTimer = null;

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
    const closePopoverButton = tagsPopover.querySelector("[data-tags-popover-close]");
    if (closePopoverButton) {
      closePopoverButton.addEventListener("click", () => closeTagsPopover());
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
      const tag = document.createElement("button");
      tag.type = "button";
      tag.className = "tag tag-color tag-filter-chip";
      tag.dataset.rangeQuickFilterTag = String(item?.name || "");
      tag.style.setProperty("--tag-color", String(item?.color || "#94a3b8"));
      if (typeof window.ipocketApplyTagContrast === "function") {
        window.ipocketApplyTagContrast(tag);
      }
      tag.textContent = String(item?.name || "");
      list.appendChild(tag);
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
      window.innerWidth < 640 ? window.innerWidth - 16 : 340
    );
    tagsPopover.style.width = `${popoverWidth}px`;
    tagsPopover.style.maxWidth = `${popoverWidth}px`;
    const popoverRect = tagsPopover.getBoundingClientRect();
    const availableBelow = window.innerHeight - rect.bottom;
    const top =
      availableBelow > popoverRect.height + gutter
        ? rect.bottom + 6
        : rect.top - popoverRect.height - 6;
    const clampedTop = Math.min(
      window.innerHeight - popoverRect.height - gutter,
      Math.max(gutter, top)
    );
    const left = Math.min(
      window.innerWidth - popoverRect.width - gutter,
      Math.max(gutter, rect.left)
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
    const rawItems = trigger.dataset.tagsJson || "[]";
    let items = [];
    try {
      const parsed = JSON.parse(rawItems);
      if (Array.isArray(parsed)) {
        items = parsed;
      }
    } catch (error) {
      items = [];
    }
    const ipAddress = trigger.dataset.tagsIp || "IP";
    const popoverTitle = tagsPopover.querySelector("[data-tags-popover-title]");
    const searchInput = tagsPopover.querySelector("[data-tags-popover-search]");
    if (activeTagsPopoverTrigger && activeTagsPopoverTrigger !== trigger) {
      activeTagsPopoverTrigger.setAttribute("aria-expanded", "false");
    }
    activeTagsPopoverTrigger = trigger;
    activeTagsPopoverTrigger.setAttribute("aria-expanded", "true");
    tagsPopover.dataset.tagsPopoverItems = JSON.stringify(items);
    if (popoverTitle) {
      popoverTitle.textContent = `Tags for ${ipAddress}`;
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

  const hashToStatus = {
    "#used": "used",
    "#free": "free",
  };
  const mappedStatus = hashToStatus[window.location.hash || ""];
  if (mappedStatus) {
    const url = new URL(window.location.href);
    const currentStatus = (url.searchParams.get("status") || "").trim().toLowerCase();
    if (!currentStatus) {
      url.searchParams.set("status", mappedStatus);
      window.location.replace(`${url.pathname}?${url.searchParams.toString()}${url.hash}`);
      return;
    }
  }

  if (!overlay || !drawer || !form || !title || !subtitle || !statusLabel || !saveButton) {
    return;
  }

  const inputs = form.querySelectorAll("[data-range-input]");
  const state = { open: false, initialValues: {} };

  const getInput = (name) => form.querySelector(`[data-range-input="${name}"]`);

  const normalizeTagValue = (rawValue) => {
    const normalized = (rawValue || "").trim().toLowerCase();
    if (!normalized) {
      return "";
    }
    if (!/^[a-z0-9_-]+$/.test(normalized)) {
      return "";
    }
    return normalized;
  };

  const listSelectedTags = () => {
    if (!tagFilterSelected) {
      return [];
    }
    return Array.from(tagFilterSelected.querySelectorAll('input[name="tag"]')).map(
      (input) => input.value
    );
  };

  const getTagColor = (rawValue) => {
    if (!tagFilterSuggestions) {
      return "";
    }
    const normalizedValue = normalizeTagValue(rawValue);
    if (!normalizedValue) {
      return "";
    }
    const option = Array.from(tagFilterSuggestions.options).find(
      (entry) => normalizeTagValue(entry.value) === normalizedValue
    );
    return option ? String(option.dataset.tagColor || "").trim() : "";
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

  const addTagFilter = (rawValue) => {
    if (!tagFilterSelected) {
      return false;
    }
    const value = normalizeTagValue(rawValue);
    if (!value) {
      return false;
    }
    if (listSelectedTags().includes(value)) {
      return false;
    }
    const entry = document.createElement("span");
    entry.className = "tag-filter-entry";
    entry.dataset.rangeTagFilterEntry = value;
    entry.innerHTML = `<input type="hidden" name="tag" value="${value}" /><button class="tag tag-color tag-filter-chip" type="button" data-range-remove-tag-filter="${value}">${value} ×</button>`;
    const chip = entry.querySelector(`[data-range-remove-tag-filter="${value}"]`);
    applyTagFilterChipColor(chip, value);
    tagFilterSelected.appendChild(entry);
    return true;
  };

  const removeTagFilter = (value) => {
    if (!tagFilterSelected) {
      return false;
    }
    const entry = tagFilterSelected.querySelector(
      `[data-range-tag-filter-entry="${value}"]`
    );
    if (!entry) {
      return false;
    }
    entry.remove();
    return true;
  };

  const submitTagFilter = () => {
    if (!filterForm) {
      return;
    }
    if (window.htmx && typeof window.htmx.ajax === "function") {
      const url = new URL(
        filterForm.action || window.location.pathname,
        window.location.origin
      );
      const params = new URLSearchParams(new FormData(filterForm));
      url.search = params.toString();
      window.htmx.ajax("GET", url.toString(), {
        target: "#range-addresses-table-container",
        swap: "innerHTML",
        pushURL: url.pathname + (url.search ? `?${url.searchParams.toString()}` : ""),
      });
      return;
    }
    filterForm.submit();
  };

  const readInputValue = (input) => {
    if (!input) {
      return "";
    }
    if (input.tagName === "SELECT" && input.multiple) {
      return Array.from(input.selectedOptions)
        .map((option) => option.value.trim())
        .filter(Boolean)
        .sort()
        .join(",");
    }
    return (input.value || "").trim();
  };

  const writeInputValue = (input, value) => {
    if (!input) {
      return;
    }
    if (input.tagName === "SELECT" && input.multiple) {
      const selected = Array.isArray(value)
        ? value.map((item) => String(item).trim()).filter(Boolean)
        : String(value || "")
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean);
      Array.from(input.options).forEach((option) => {
        option.selected = selected.includes(option.value);
      });
      input.dispatchEvent(new Event("change", { bubbles: true }));
      input.dispatchEvent(new Event("input", { bubbles: true }));
      return;
    }
    input.value = value || "";
  };

  const updateSaveState = () => {
    const isDirty = Array.from(inputs).some((input) => {
      const key = input.dataset.rangeInput;
      return readInputValue(input) !== (state.initialValues[key] || "");
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
      tags: Array.isArray(tags) ? tags.join(",") : (tags || ""),
    };

    writeInputValue(ipInput, values.ip_address);
    writeInputValue(ipDisplay, values.ip_display);
    writeInputValue(typeInput, values.type);
    writeInputValue(projectInput, values.project_id);
    writeInputValue(notesInput, values.notes);
    writeInputValue(tagsInput, values.tags);

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

  document.addEventListener("click", (event) => {
    const quickFilterTag = event.target.closest("[data-range-quick-filter-tag]");
    if (quickFilterTag) {
      event.preventDefault();
      const tagValue = quickFilterTag.dataset.rangeQuickFilterTag || "";
      if (addTagFilter(tagValue)) {
        submitTagFilter();
      }
      return;
    }

    const tagsMoreTrigger = event.target.closest("[data-tags-more-toggle]");
    if (tagsMoreTrigger) {
      if (activeTagsPopoverTrigger === tagsMoreTrigger && tagsPopover && !tagsPopover.hidden) {
        closeTagsPopover();
      } else {
        openTagsPopover(tagsMoreTrigger);
      }
      return;
    }
    if (activeTagsPopoverTrigger && tagsPopover && !tagsPopover.contains(event.target)) {
      closeTagsPopover();
    }

    const removeTagButton = event.target.closest("[data-range-remove-tag-filter]");
    if (removeTagButton) {
      event.preventDefault();
      if (removeTagFilter(removeTagButton.dataset.rangeRemoveTagFilter || "")) {
        submitTagFilter();
      }
      return;
    }

    const addButton = event.target.closest("[data-range-address-add]");
    if (addButton) {
      openDrawer({
        mode: "add",
        ipAddress: addButton.dataset.ipAddress,
      });
      return;
    }

    const editButton = event.target.closest("[data-range-address-edit]");
    if (!editButton) {
      return;
    }

    let tags = [];
    try {
      const parsed = JSON.parse(editButton.dataset.tagsJson || "[]");
      tags = Array.isArray(parsed) ? parsed : [];
    } catch (error) {
      tags = [];
    }
    openDrawer({
      mode: "edit",
      assetId: editButton.dataset.assetId,
      ipAddress: editButton.dataset.ipAddress,
      assetType: editButton.dataset.type,
      projectId: editButton.dataset.projectId,
      notes: editButton.dataset.notes,
      tags,
    });
  });

  [overlay, closeButton, cancelButton].forEach((element) => {
    if (!element) {
      return;
    }
    element.addEventListener("click", closeDrawer);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && activeTagsPopoverTrigger) {
      closeTagsPopover();
      return;
    }
    if (event.key === "Escape" && state.open) {
      closeDrawer();
    }
  });

  document.addEventListener("mouseover", (event) => {
    const trigger = event.target.closest("[data-tags-more-toggle]");
    if (!trigger) {
      return;
    }
    if (activeTagsPopoverTrigger === trigger && tagsPopover && !tagsPopover.hidden) {
      if (tagsPopoverCloseTimer) {
        window.clearTimeout(tagsPopoverCloseTimer);
        tagsPopoverCloseTimer = null;
      }
      return;
    }
    scheduleOpenTagsPopover(trigger);
  });

  document.addEventListener("mouseout", (event) => {
    const trigger = event.target.closest("[data-tags-more-toggle]");
    if (!trigger) {
      return;
    }
    const nextTarget = event.relatedTarget;
    if (
      nextTarget &&
      (trigger.contains(nextTarget) || (tagsPopover && tagsPopover.contains(nextTarget)))
    ) {
      return;
    }
    scheduleCloseTagsPopover();
  });

  document.addEventListener(
    "focusin",
    (event) => {
      const trigger = event.target.closest("[data-tags-more-toggle]");
      if (!trigger) {
        return;
      }
      openTagsPopover(trigger);
    },
    true
  );

  document.addEventListener(
    "focusout",
    (event) => {
      const trigger = event.target.closest("[data-tags-more-toggle]");
      if (!trigger) {
        return;
      }
      const nextTarget = event.relatedTarget;
      if (nextTarget && tagsPopover && tagsPopover.contains(nextTarget)) {
        return;
      }
      scheduleCloseTagsPopover(0);
    },
    true
  );

  window.addEventListener("resize", positionTagsPopover);
  window.addEventListener("scroll", positionTagsPopover, true);
  document.body.addEventListener("htmx:afterSwap", () => {
    closeTagsPopover();
  });

  inputs.forEach((input) => {
    input.addEventListener("input", updateSaveState);
    input.addEventListener("change", updateSaveState);
  });

  if (tagFilterSelected) {
    tagFilterSelected
      .querySelectorAll("[data-range-remove-tag-filter]")
      .forEach((chip) => {
        applyTagFilterChipColor(
          chip,
          chip.getAttribute("data-range-remove-tag-filter") || ""
        );
      });
  }

  if (tagFilterInput) {
    tagFilterInput.addEventListener("change", () => {
      if (addTagFilter(tagFilterInput.value)) {
        tagFilterInput.value = "";
        submitTagFilter();
      }
    });
    tagFilterInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === ",") {
        event.preventDefault();
        if (addTagFilter(tagFilterInput.value)) {
          tagFilterInput.value = "";
          submitTagFilter();
        }
      }
    });
  }
})();
