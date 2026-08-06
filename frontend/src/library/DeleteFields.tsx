export function DeleteFields({
  entityLabel,
  name,
  usageCount,
  acknowledged,
  confirmName,
  onAcknowledge,
  onConfirmName,
}: {
  entityLabel: string;
  name: string;
  usageCount: number;
  acknowledged: boolean;
  confirmName: string;
  onAcknowledge: (value: boolean) => void;
  onConfirmName: (value: string) => void;
}) {
  return (
    <section className="ip-drawer-section">
      <h3 className="ip-drawer-delete-heading">Delete this {entityLabel}?</h3>
      <p className="ip-drawer-delete-warning">
        This action permanently removes the {entityLabel}.
      </p>
      <dl className="ip-drawer-delete-details">
        <div>
          <dt>Name</dt>
          <dd>{name || "—"}</dd>
        </div>
        <div>
          <dt>Active IP usage</dt>
          <dd>{usageCount}</dd>
        </div>
      </dl>
      <label className="field field-inline">
        <input
          className="checkbox"
          type="checkbox"
          checked={acknowledged}
          onChange={(event) => onAcknowledge(event.target.checked)}
        />
        <span>I understand this cannot be undone</span>
      </label>
      <label className="field">
        <span>
          Type the {entityLabel} name to confirm: <strong>{name || "—"}</strong>
        </span>
        <input
          className="input"
          type="text"
          autoComplete="off"
          data-library-confirm
          value={confirmName}
          onChange={(event) => onConfirmName(event.target.value)}
        />
      </label>
    </section>
  );
}
