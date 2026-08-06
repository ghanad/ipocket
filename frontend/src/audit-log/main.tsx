import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { AuditLogPage } from "./AuditLogPage";

const root = document.getElementById("audit-log-root");

if (root) {
  createRoot(root).render(
    <StrictMode>
      <AuditLogPage
        endpoint={root.dataset.endpoint ?? "/api/ui/audit-log"}
        initialQuery={root.dataset.initialQuery ?? ""}
      />
    </StrictMode>,
  );
}
