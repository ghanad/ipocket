export const createTableController = ({ bulkEdit, drawer, tagsPopover }) => {
  const bindEditButtons = (root = document) => {
    root.querySelectorAll('[data-ip-edit]').forEach((button) => {
      if (button.dataset.ipEditBound) return;
      button.dataset.ipEditBound = 'true';
      button.addEventListener('click', () => drawer.open({
        id: button.dataset.ipEdit,
        ip_address: button.dataset.ipAddress || '',
        type: button.dataset.ipType || '',
        project_id: button.dataset.ipProjectId || '',
        project_label: button.dataset.ipProjectName || 'Unassigned',
        host_id: button.dataset.ipHostId || '',
        host_label: button.dataset.ipHostName || '—',
        notes: button.dataset.ipNotes || '',
        tags: button.dataset.ipTags || '',
      }));
    });
  };

  const bindDeleteButtons = (root = document) => {
    root.querySelectorAll('[data-ip-delete]').forEach((button) => {
      if (button.dataset.ipDeleteBound) return;
      button.dataset.ipDeleteBound = 'true';
      button.addEventListener('click', () => drawer.openForDelete({
        id: button.dataset.ipDelete,
        ip_address: button.dataset.ipAddress || '',
        type: button.dataset.ipType || '',
        project_label: button.dataset.ipProjectName || 'Unassigned',
        host_label: button.dataset.ipHostName || '—',
        tags: button.dataset.ipTags || '',
        project_id: button.dataset.ipProjectId || '',
        host_id: button.dataset.ipHostId || '',
      }));
    });
  };

  const bindAddButtons = (root = document) => {
    root.querySelectorAll('[data-ip-add]').forEach((button) => {
      if (button.dataset.ipAddBound) return;
      button.dataset.ipAddBound = 'true';
      button.addEventListener('click', drawer.openForAdd);
    });
  };

  const bindPerPageControl = (root = document) => {
    const select = root.querySelector('[data-per-page-select]');
    if (!select || select.dataset.perPageBound) return;
    select.dataset.perPageBound = 'true';
    ['click', 'mousedown', 'touchstart'].forEach((eventName) => {
      select.addEventListener(eventName, (event) => event.stopPropagation());
    });
  };

  const bind = (root = document) => {
    bindEditButtons(root);
    bindDeleteButtons(root);
    bulkEdit.bind(root);
    tagsPopover.bind(root);
    bindPerPageControl(root);
    bindAddButtons();
  };

  return { bind };
};

export const getIpTableContainerFromEvent = (event) => {
  const explicitTarget = event?.detail?.target;
  if (explicitTarget instanceof Element) {
    if (explicitTarget.id === 'ip-table-container') return explicitTarget;
    const nested = explicitTarget.closest('#ip-table-container');
    if (nested) return nested;
  }
  const fallbackTarget = event?.target;
  if (fallbackTarget instanceof Element) {
    if (fallbackTarget.id === 'ip-table-container') return fallbackTarget;
    const nested = fallbackTarget.closest('#ip-table-container');
    if (nested) return nested;
  }
  return null;
};
