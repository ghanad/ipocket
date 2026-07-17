import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { DataOpsPage } from "./DataOpsPage";
import type { DataOpsTab } from "./types";

const root = document.getElementById("data-ops-root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <DataOpsPage
        endpoint={root.dataset.endpoint ?? "/api/ui/data-ops"}
        initialTab={(root.dataset.initialTab as DataOpsTab) ?? "import"}
      />
    </StrictMode>,
  );
}
