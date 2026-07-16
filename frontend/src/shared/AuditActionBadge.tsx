export function AuditActionBadge({ action }: { action: string }) {
  const tone =
    action === "DELETE"
      ? "pill-danger"
      : action === "CREATE"
        ? "pill-success"
        : "pill-warning";

  return <span className={`pill ${tone}`}>{action}</span>;
}
