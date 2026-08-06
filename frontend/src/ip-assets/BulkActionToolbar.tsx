export function BulkActionToolbar({
  selectedCount,
  selectedOnPage,
  onBulkEdit,
  onAssignProject,
  onManageTags,
}: {
  selectedCount: number;
  selectedOnPage: number;
  onBulkEdit: () => void;
  onAssignProject: () => void;
  onManageTags: () => void;
}) {
  const scope =
    selectedCount === selectedOnPage
      ? "On this page"
      : `${selectedOnPage} on this page`;

  return (
    <section className="bulk-action-bar" aria-label="Selected IP asset actions">
      <div className="bulk-action-summary" aria-live="polite">
        <strong>{selectedCount} selected</strong>
        <span>{scope}</span>
      </div>
      <div className="bulk-action-buttons" role="toolbar" aria-label="Bulk actions">
        <button className="btn btn-primary btn-small" type="button" onClick={onBulkEdit}>
          Bulk Edit
        </button>
        <button className="btn btn-outline btn-small" type="button" onClick={onAssignProject}>
          Assign Project
        </button>
        <button className="btn btn-outline btn-small" type="button" onClick={onManageTags}>
          Manage Tags
        </button>
        <details className="bulk-action-more">
          <summary
            className="row-action-control row-actions-trigger bulk-actions-trigger"
            aria-label="More bulk actions"
            title="More bulk actions"
          >
            <span className="row-actions-icon" aria-hidden="true">⋯</span>
          </summary>
          <div className="row-actions-panel bulk-action-menu" role="menu">
            <button className="row-action-item" type="button" role="menuitem" disabled>
              <span>Delete</span>
              <small>Coming soon</small>
            </button>
          </div>
        </details>
      </div>
    </section>
  );
}
