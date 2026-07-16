import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { HostsPage } from "./HostsPage";

const root = document.getElementById("hosts-root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <HostsPage
        endpoint={root.dataset.endpoint ?? "/api/ui/hosts"}
        initialQuery={root.dataset.initialQuery ?? ""}
      />
    </StrictMode>,
  );
}
