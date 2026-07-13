import { createBulkEditController } from './ip-assets/bulk-edit.js';
import { createDrawerController } from './ip-assets/drawer.js';
import { createFiltersController } from './ip-assets/filters.js';
import { SCROLL_KEY } from './ip-assets/shared.js';
import { createTableController, getIpTableContainerFromEvent } from './ip-assets/table.js';
import { createTagsPopover } from './ip-assets/tags-popover.js';

const GLOBAL_FLAG = 'ipocketIpAssetsInitialized';
const tagsPopover = createTagsPopover();
const filters = createFiltersController();
let bulkEdit;
const drawer = createDrawerController({ closeBulkDrawer: () => bulkEdit?.close() });
bulkEdit = createBulkEditController({
  closeDrawer: drawer.close,
  isDrawerOpen: drawer.isOpen,
});
const table = createTableController({ bulkEdit, drawer, tagsPopover });

if (!window[GLOBAL_FLAG]) {
  window[GLOBAL_FLAG] = true;
  if (typeof window !== 'undefined' && window.sessionStorage) {
    const storedScroll = window.sessionStorage.getItem(SCROLL_KEY);
    if (storedScroll) {
      window.scrollTo(0, Number.parseInt(storedScroll, 10) || 0);
      window.sessionStorage.removeItem(SCROLL_KEY);
    }
  }

  drawer.bindGlobal();
  bulkEdit.bindGlobal();
  filters.bind();

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && tagsPopover.hasActiveTrigger()) {
      tagsPopover.close();
    }
    if (event.key === 'Escape' && bulkEdit.isOpen()) {
      bulkEdit.close();
      return;
    }
    if (event.key === 'Escape' && drawer.isOpen()) {
      drawer.confirmClose();
    }
  });
  window.addEventListener('resize', tagsPopover.position);
  window.addEventListener('scroll', tagsPopover.position, true);

  document.body.addEventListener('htmx:afterSwap', (event) => {
    const container = getIpTableContainerFromEvent(event);
    if (!container) return;
    tagsPopover.close();
    bulkEdit.close();
    table.bind(container);
  });
  document.body.addEventListener('htmx:afterSettle', (event) => {
    const container = getIpTableContainerFromEvent(event);
    if (container) table.bind(container);
  });
  document.body.addEventListener('click', (event) => {
    if (event.target.closest('[data-per-page-control]')) return;

    const removeTagButton = event.target.closest('[data-remove-tag-filter]');
    if (removeTagButton) {
      event.preventDefault();
      filters.removeFromTrigger(removeTagButton);
      return;
    }

    const removeCommonTagButton = event.target.closest('[data-bulk-remove-tag]');
    if (removeCommonTagButton) {
      event.preventDefault();
      bulkEdit.handleRemoveTagClick(removeCommonTagButton);
      return;
    }

    const tagsMoreTrigger = event.target.closest('[data-tags-more-toggle]');
    if (tagsMoreTrigger) {
      event.preventDefault();
      tagsPopover.toggle(tagsMoreTrigger);
      return;
    }
    tagsPopover.closeIfOutside(event.target);

    const trigger = event.target.closest('[data-quick-filter]');
    if (!trigger) return;
    event.preventDefault();
    filters.applyQuickFilter(
      trigger.dataset.quickFilter,
      trigger.dataset.quickFilterValue || ''
    );
  });
}

table.bind();
