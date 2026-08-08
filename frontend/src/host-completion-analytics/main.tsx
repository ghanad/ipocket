import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { HostCompletionAnalyticsPage } from "./HostCompletionAnalyticsPage";

const rootElement = document.getElementById("host-completion-analytics-root");

if (rootElement) {
  const endpoint =
    rootElement.dataset.endpoint ?? "/api/host-completion/summary";
  const canManageRules = rootElement.dataset.canManageRules === "true";

  createRoot(rootElement).render(
    <StrictMode>
      <HostCompletionAnalyticsPage endpoint={endpoint} canManageRules={canManageRules} />
    </StrictMode>,
  );
}
