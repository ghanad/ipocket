(() => {
  const ROOT_ATTR = "data-tag-picker";
  const BOUND_ATTR = "tagPickerBound";

  const normalize = (value) => String(value || "").trim().toLowerCase();

  const getOptions = (select) =>
    Array.from(select.options).map((option) => ({
      value: option.value,
      label: option.textContent || option.value,
      color: option.dataset.tagColor || "#e2e8f0",
      selected: option.selected,
    }));

  const setSelected = (select, value, selected) => {
    const option = Array.from(select.options).find((entry) => entry.value === value);
    if (!option || option.selected === selected) {
      return;
    }
    option.selected = selected;
    select.dispatchEvent(new Event("change", { bubbles: true }));
    select.dispatchEvent(new Event("input", { bubbles: true }));
  };

  const buildPicker = (select) => {
    const placeholder = select.dataset.tagPickerPlaceholder || "Add tags...";
    const picker = document.createElement("div");
    picker.className = "tag-picker";

    const selectedWrap = document.createElement("div");
    selectedWrap.className = "tag-picker-selected";

    const inputWrap = document.createElement("div");
    inputWrap.className = "tag-picker-input-wrap";

    const input = document.createElement("input");
    input.type = "text";
    input.className = "input";
    input.placeholder = placeholder;
    input.autocomplete = "off";

    const dropdown = document.createElement("ul");
    dropdown.className = "tag-picker-dropdown";
    dropdown.hidden = true;
    dropdown.setAttribute("role", "listbox");

    inputWrap.append(input, dropdown);
    picker.append(inputWrap, selectedWrap);
    select.insertAdjacentElement("afterend", picker);

    const closeDropdown = () => {
      dropdown.hidden = true;
      dropdown.replaceChildren();
      delete dropdown.dataset.activeIndex;
    };

    const selectedValues = () =>
      Array.from(select.options)
        .filter((option) => option.selected)
        .map((option) => option.value);

    const renderSelected = () => {
      selectedWrap.replaceChildren();
      const selected = getOptions(select).filter((option) => option.selected);
      selected.forEach((option) => {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "tag tag-color tag-picker-chip";
        chip.style.setProperty("--tag-color", option.color);
        chip.setAttribute("aria-label", `Remove ${option.label}`);
        chip.innerHTML = `<span>${option.label}</span><span class="tag-picker-chip-remove">&times;</span>`;
        chip.addEventListener("click", () => {
          setSelected(select, option.value, false);
          input.focus();
        });
        selectedWrap.appendChild(chip);
      });
    };

    const renderDropdown = (query) => {
      const selected = new Set(selectedValues().map((value) => normalize(value)));
      const filtered = getOptions(select).filter((option) => {
        if (selected.has(normalize(option.value))) {
          return false;
        }
        if (!query) {
          return true;
        }
        const haystack = `${option.label} ${option.value}`.toLowerCase();
        return haystack.includes(normalize(query));
      });
      dropdown.replaceChildren();
      if (!filtered.length) {
        closeDropdown();
        return;
      }

      filtered.forEach((option, index) => {
        const item = document.createElement("li");
        item.className = "tag-picker-option";
        item.dataset.value = option.value;
        item.dataset.index = String(index);
        item.innerHTML = `<span class="tag tag-color" style="--tag-color: ${option.color}">${option.label}</span>`;
        item.addEventListener("mousedown", (event) => {
          event.preventDefault();
          setSelected(select, option.value, true);
          input.value = "";
          renderDropdown("");
          input.focus();
        });
        dropdown.appendChild(item);
      });

      dropdown.hidden = false;
      dropdown.dataset.activeIndex = "0";
      const first = dropdown.querySelector(".tag-picker-option");
      if (first) {
        first.classList.add("is-active");
      }
    };

    const moveActive = (direction) => {
      const options = Array.from(dropdown.querySelectorAll(".tag-picker-option"));
      if (!options.length) {
        return;
      }
      const max = options.length - 1;
      const current = Number.parseInt(dropdown.dataset.activeIndex || "0", 10);
      const next = Math.max(0, Math.min(max, current + direction));
      dropdown.dataset.activeIndex = String(next);
      options.forEach((option, index) => option.classList.toggle("is-active", index === next));
    };

    const selectActive = () => {
      const active = dropdown.querySelector(".tag-picker-option.is-active");
      if (!active) {
        return false;
      }
      const value = active.dataset.value || "";
      if (!value) {
        return false;
      }
      setSelected(select, value, true);
      input.value = "";
      renderDropdown("");
      return true;
    };

    input.addEventListener("focus", () => renderDropdown(input.value));
    input.addEventListener("input", () => renderDropdown(input.value));

    input.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        if (dropdown.hidden) {
          renderDropdown(input.value);
        } else {
          moveActive(1);
        }
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        if (!dropdown.hidden) {
          moveActive(-1);
        }
        return;
      }
      if (event.key === "Enter") {
        if (!dropdown.hidden) {
          event.preventDefault();
          selectActive();
        }
        return;
      }
      if (event.key === "Escape") {
        closeDropdown();
        return;
      }
      if (event.key === "Backspace" && !input.value.trim()) {
        const selected = selectedValues();
        const last = selected[selected.length - 1];
        if (last) {
          event.preventDefault();
          setSelected(select, last, false);
          renderDropdown(input.value);
        }
      }
    });

    select.addEventListener("change", () => {
      renderSelected();
      if (!dropdown.hidden) {
        renderDropdown(input.value);
      }
    });

    document.addEventListener("click", (event) => {
      if (!picker.contains(event.target)) {
        closeDropdown();
      }
    });

    select.classList.add("tag-picker-native");
    renderSelected();
  };

  const init = (root = document) => {
    const selects = root.querySelectorAll(`select[${ROOT_ATTR}]`);
    selects.forEach((select) => {
      if (!(select instanceof HTMLSelectElement) || !select.multiple || select.dataset[BOUND_ATTR]) {
        return;
      }
      select.dataset[BOUND_ATTR] = "true";
      buildPicker(select);
    });
  };

  init(document);
  document.addEventListener("htmx:afterSwap", (event) => {
    if (!(event.target instanceof Element)) {
      return;
    }
    init(event.target);
  });
})();
