(() => {
    const GLOBAL_FLAG = '__ipocket_tag_row_actions_bound__';
    const POSITION_MARGIN = 12;

    const positionMenuPanel = (toggle, panel) => {
      const triggerRect = toggle.getBoundingClientRect();
      panel.style.top = '0px';
      panel.style.left = '0px';
      panel.style.bottom = 'auto';
      panel.style.visibility = 'hidden';
      panel.hidden = false;

      const panelRect = panel.getBoundingClientRect();
      let top = triggerRect.bottom + 6;
      let left = triggerRect.right - panelRect.width;

      if (left < POSITION_MARGIN) {
        left = POSITION_MARGIN;
      }

      if (left + panelRect.width > window.innerWidth - POSITION_MARGIN) {
        left = Math.max(POSITION_MARGIN, window.innerWidth - panelRect.width - POSITION_MARGIN);
      }

      if (top + panelRect.height > window.innerHeight - POSITION_MARGIN) {
        top = triggerRect.top - panelRect.height - 6;
      }

      if (top < POSITION_MARGIN) {
        top = POSITION_MARGIN;
      }

      panel.style.top = `${top}px`;
      panel.style.left = `${left}px`;
      panel.style.visibility = 'visible';
    };

    const closeAllMenus = () => {
      const actionMenus = document.querySelectorAll('[data-row-actions]');
      actionMenus.forEach((menu) => {
        const toggle = menu.querySelector('[data-row-actions-toggle]');
        const panel = menu.querySelector('[data-row-actions-panel]');
        if (toggle && panel) {
          toggle.setAttribute('aria-expanded', 'false');
          panel.hidden = true;
          panel.style.visibility = '';
          menu.classList.remove('is-open');
        }
      });
    };

    const bindRowActions = (root = document) => {
      const actionMenus = root.querySelectorAll('[data-row-actions]');
      actionMenus.forEach((menu) => {
        if (menu.dataset.rowActionsBound) {
          return;
        }
        const toggle = menu.querySelector('[data-row-actions-toggle]');
        const panel = menu.querySelector('[data-row-actions-panel]');
        if (!toggle || !panel) {
          return;
        }
        menu.dataset.rowActionsBound = 'true';

        toggle.addEventListener('click', (event) => {
          event.stopPropagation();
          const isOpen = toggle.getAttribute('aria-expanded') === 'true';
          closeAllMenus();
          if (!isOpen) {
            toggle.setAttribute('aria-expanded', 'true');
            positionMenuPanel(toggle, panel);
            menu.classList.add('is-open');
          }
        });

        panel.addEventListener('click', (event) => {
          event.stopPropagation();
        });
      });
    };

    const bindTagDeleteConfirm = (root = document) => {
      const deleteForms = root.querySelectorAll('[data-tag-delete-form]');
      deleteForms.forEach((form) => {
        if (form.dataset.confirmBound) {
          return;
        }

        form.dataset.confirmBound = 'true';
        form.addEventListener('submit', (event) => {
          const tagName = form.dataset.tagName || 'this tag';
          const confirmed = window.confirm(`Delete tag "${tagName}"?`);
          if (!confirmed) {
            event.preventDefault();
          }
        });
      });
    };

    if (!window[GLOBAL_FLAG]) {
      window[GLOBAL_FLAG] = true;
      document.addEventListener('click', () => {
        closeAllMenus();
      });

      document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
          closeAllMenus();
        }
      });

      window.addEventListener(
        'scroll',
        () => {
          closeAllMenus();
        },
        true,
      );

      const tableWrapper = document.querySelector('.table-wrapper');
      if (tableWrapper) {
        tableWrapper.addEventListener('scroll', () => {
          closeAllMenus();
        });
      }

      window.addEventListener('resize', () => {
        closeAllMenus();
      });
    }

    bindRowActions();
    bindTagDeleteConfirm();
  })();
