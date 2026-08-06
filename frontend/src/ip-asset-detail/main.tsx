import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { IPAssetDetailPage } from "./IPAssetDetailPage";

const root = document.getElementById("ip-asset-detail-root");

if (root) {
  createRoot(root).render(
    <StrictMode>
      <IPAssetDetailPage
        endpoint={root.dataset.endpoint ?? "/api/ui/ip-assets/0"}
      />
    </StrictMode>,
  );
}
