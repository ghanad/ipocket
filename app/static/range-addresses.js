const rangeAddContainers = document.querySelectorAll("[data-range-add]");

if (rangeAddContainers.length) {
  const closeAll = () => {
    rangeAddContainers.forEach((container) => {
      container.classList.remove("range-add-open");
      const trigger = container.querySelector("[data-range-add-trigger]");
      if (trigger) {
        trigger.setAttribute("aria-expanded", "false");
      }
    });
  };

  rangeAddContainers.forEach((container) => {
    const trigger = container.querySelector("[data-range-add-trigger]");
    const cancelButton = container.querySelector("[data-range-add-cancel]");
    const popover = container.querySelector("[data-range-add-popover]");
    if (!trigger || !popover) {
      return;
    }

    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const isOpen = container.classList.contains("range-add-open");
      closeAll();
      if (!isOpen) {
        container.classList.add("range-add-open");
        trigger.setAttribute("aria-expanded", "true");
        const focusTarget = popover.querySelector("select, input, button");
        if (focusTarget) {
          focusTarget.focus();
        }
      }
    });

    if (cancelButton) {
      cancelButton.addEventListener("click", (event) => {
        event.preventDefault();
        closeAll();
      });
    }
  });

  document.addEventListener("click", (event) => {
    if (event.target.closest("[data-range-add]")) {
      return;
    }
    closeAll();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeAll();
    }
  });
}
