export const createTagsPopover = () => {
  let activeTrigger = null;
  let popover = null;
  let openTimer = null;
  let closeTimer = null;

  const parseItems = () => {
    if (!popover) {
      return [];
    }
    try {
      const parsed = JSON.parse(popover.dataset.tagsPopoverItems || '[]');
      return Array.isArray(parsed) ? parsed : [];
    } catch (error) {
      return [];
    }
  };

  const renderList = () => {
    if (!popover) {
      return;
    }
    const list = popover.querySelector('[data-tags-popover-list]');
    const searchInput = popover.querySelector('[data-tags-popover-search]');
    if (!list) {
      return;
    }
    const term = ((searchInput && searchInput.value) || '').trim().toLowerCase();
    const items = parseItems().filter((item) => {
      const name = String(item?.name || '').toLowerCase();
      return !term || name.includes(term);
    });
    list.replaceChildren();
    if (!items.length) {
      const emptyMessage = document.createElement('p');
      emptyMessage.className = 'muted ip-tags-popover-empty';
      emptyMessage.textContent = 'No matching tags.';
      list.appendChild(emptyMessage);
      return;
    }
    items.forEach((item) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'tag tag-color tag-filter-chip';
      button.dataset.quickFilter = 'tag';
      button.dataset.quickFilterValue = String(item?.name || '');
      button.style.setProperty('--tag-color', String(item?.color || '#94a3b8'));
      if (typeof window.ipocketApplyTagContrast === 'function') {
        window.ipocketApplyTagContrast(button);
      }
      button.textContent = String(item?.name || '');
      list.appendChild(button);
    });
  };

  const close = () => {
    if (openTimer) {
      window.clearTimeout(openTimer);
      openTimer = null;
    }
    if (closeTimer) {
      window.clearTimeout(closeTimer);
      closeTimer = null;
    }
    if (activeTrigger) {
      activeTrigger.setAttribute('aria-expanded', 'false');
    }
    activeTrigger = null;
    if (popover) {
      popover.hidden = true;
      popover.dataset.tagsPopoverItems = '[]';
    }
  };

  const scheduleClose = (delay = 180) => {
    if (openTimer) {
      window.clearTimeout(openTimer);
      openTimer = null;
    }
    if (closeTimer) {
      window.clearTimeout(closeTimer);
      closeTimer = null;
    }
    closeTimer = window.setTimeout(() => {
      close();
      closeTimer = null;
    }, delay);
  };

  const ensurePopover = () => {
    if (popover) {
      return popover;
    }
    popover = document.createElement('section');
    popover.className = 'ip-tags-popover';
    popover.setAttribute('role', 'dialog');
    popover.setAttribute('aria-modal', 'false');
    popover.hidden = true;
    popover.innerHTML = `
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
    document.body.appendChild(popover);
    popover.querySelector('[data-tags-popover-close]')?.addEventListener('click', close);
    popover.querySelector('[data-tags-popover-search]')?.addEventListener('input', renderList);
    popover.addEventListener('mouseenter', () => {
      if (closeTimer) {
        window.clearTimeout(closeTimer);
        closeTimer = null;
      }
    });
    popover.addEventListener('mouseleave', () => scheduleClose());
    return popover;
  };

  const position = () => {
    if (!popover || !activeTrigger || popover.hidden) {
      return;
    }
    const gutter = 12;
    const rect = activeTrigger.getBoundingClientRect();
    const popoverWidth = Math.min(
      window.innerWidth - gutter * 2,
      window.innerWidth < 640 ? window.innerWidth - 16 : 340
    );
    popover.style.width = `${popoverWidth}px`;
    popover.style.maxWidth = `${popoverWidth}px`;
    const popoverRect = popover.getBoundingClientRect();
    const availableBelow = window.innerHeight - rect.bottom;
    const top = availableBelow > popoverRect.height + gutter
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
    popover.style.top = `${clampedTop + window.scrollY}px`;
    popover.style.left = `${left + window.scrollX}px`;
  };

  const open = (trigger, { focusSearch = true } = {}) => {
    if (!trigger) {
      return;
    }
    ensurePopover();
    let items = [];
    try {
      const parsed = JSON.parse(trigger.dataset.tagsJson || '[]');
      if (Array.isArray(parsed)) {
        items = parsed;
      }
    } catch (error) {
      items = [];
    }
    if (activeTrigger && activeTrigger !== trigger) {
      activeTrigger.setAttribute('aria-expanded', 'false');
    }
    activeTrigger = trigger;
    activeTrigger.setAttribute('aria-expanded', 'true');
    popover.dataset.tagsPopoverItems = JSON.stringify(items);
    const title = popover.querySelector('[data-tags-popover-title]');
    const searchInput = popover.querySelector('[data-tags-popover-search]');
    if (title) {
      title.textContent = `Tags for ${trigger.dataset.tagsIp || 'IP'}`;
    }
    if (searchInput) {
      searchInput.value = '';
    }
    popover.hidden = false;
    renderList();
    position();
    if (searchInput && focusSearch) {
      searchInput.focus();
    }
  };

  const scheduleOpen = (trigger, delay = 120) => {
    if (!trigger) {
      return;
    }
    if (closeTimer) {
      window.clearTimeout(closeTimer);
      closeTimer = null;
    }
    if (openTimer) {
      window.clearTimeout(openTimer);
      openTimer = null;
    }
    openTimer = window.setTimeout(() => {
      open(trigger, { focusSearch: false });
      openTimer = null;
    }, delay);
  };

  const bind = (root = document) => {
    root.querySelectorAll('[data-tags-more-toggle]').forEach((trigger) => {
      if (trigger.dataset.tagsMoreBound) {
        return;
      }
      trigger.dataset.tagsMoreBound = 'true';
      trigger.addEventListener('mouseenter', () => {
        if (activeTrigger === trigger && popover && !popover.hidden) {
          if (closeTimer) {
            window.clearTimeout(closeTimer);
            closeTimer = null;
          }
          return;
        }
        scheduleOpen(trigger);
      });
      trigger.addEventListener('mouseleave', (event) => {
        const nextTarget = event.relatedTarget;
        if (nextTarget && (trigger.contains(nextTarget) || (popover && popover.contains(nextTarget)))) {
          return;
        }
        scheduleClose();
      });
      trigger.addEventListener('focus', () => open(trigger));
      trigger.addEventListener('blur', (event) => {
        if (event.relatedTarget && popover && popover.contains(event.relatedTarget)) {
          return;
        }
        scheduleClose(0);
      });
    });
  };

  return {
    bind,
    close,
    closeIfOutside: (target) => {
      if (activeTrigger && popover && !popover.contains(target)) {
        close();
      }
    },
    hasActiveTrigger: () => Boolean(activeTrigger),
    position,
    toggle: (trigger) => activeTrigger === trigger ? close() : open(trigger),
  };
};
