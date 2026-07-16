import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { IPAssetsPage } from "./IPAssetsPage";

const root = document.getElementById("ip-assets-root");

if (root) {
  createRoot(root).render(
    <StrictMode>
      <IPAssetsPage
        endpoint={root.dataset.endpoint ?? "/api/ui/ip-assets"}
        initialQuery={root.dataset.initialQuery ?? ""}
      />
    </StrictMode>,
  );
}
