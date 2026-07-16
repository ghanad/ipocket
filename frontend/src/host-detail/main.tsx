import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { HostDetailPage } from "./HostDetailPage";

const root = document.getElementById("host-detail-root");

if (root) {
  createRoot(root).render(
    <StrictMode>
      <HostDetailPage
        endpoint={root.dataset.endpoint ?? "/api/ui/hosts/0/detail"}
      />
    </StrictMode>,
  );
}
