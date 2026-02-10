(() => {
  const createDrawerController = ({ overlay, drawer, onBeforeClose }) => {
    if (!overlay || !drawer) {
      return null;
    }

    let isOpen = false;

    const open = () => {
      overlay.classList.add("is-open");
      drawer.classList.add("is-open");
      isOpen = true;
    };

    const close = () => {
      overlay.classList.remove("is-open");
      drawer.classList.remove("is-open");
      isOpen = false;
    };

    const requestClose = () => {
      if (!isOpen) {
        return;
      }
      if (typeof onBeforeClose === "function") {
        const canClose = onBeforeClose();
        if (canClose === false) {
          return;
        }
      }
      close();
    };

    return {
      open,
      close,
      requestClose,
      isOpen: () => isOpen,
    };
  };

  window.ipocketCreateDrawerController = createDrawerController;
})();
