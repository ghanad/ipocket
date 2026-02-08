(() => {
  const container = document.querySelector("[data-toast-container]");
  if (!container) {
    return;
  }

  const defaultTimeout = Number.parseInt(container.dataset.timeout || "4000", 10);

  const buildToast = (message, type = "info", timeout = defaultTimeout) => {
    const toast = document.createElement("div");
    toast.classList.add("toast", `toast-${type}`);
    toast.dataset.timeout = `${timeout}`;

    const text = document.createElement("span");
    text.classList.add("toast-message");
    text.textContent = message;

    const closeButton = document.createElement("button");
    closeButton.type = "button";
    closeButton.classList.add("toast-close");
    closeButton.setAttribute("aria-label", "Dismiss notification");
    closeButton.innerHTML = "&times;";

    toast.append(text, closeButton);
    container.appendChild(toast);
    setupToast(toast, timeout);
  };

  const setupToast = (toast, timeout) => {
    const closeButton = toast.querySelector(".toast-close");
    if (closeButton) {
      closeButton.addEventListener("click", () => toast.remove());
    }

    if (timeout > 0) {
      window.setTimeout(() => {
        toast.remove();
      }, timeout);
    }
  };

  container.querySelectorAll(".toast").forEach((toast) => {
    const timeout = Number.parseInt(toast.dataset.timeout || `${defaultTimeout}`, 10);
    setupToast(toast, Number.isNaN(timeout) ? defaultTimeout : timeout);
  });

  document.querySelectorAll("[data-toast-message]").forEach((trigger) => {
    trigger.addEventListener("click", () => {
      const message = trigger.dataset.toastMessage;
      if (!message) {
        return;
      }
      const type = trigger.dataset.toastType || "info";
      buildToast(message, type, defaultTimeout);
    });
  });
})();
