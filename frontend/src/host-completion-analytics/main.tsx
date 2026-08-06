import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { HostCompletionAnalyticsPage } from "./HostCompletionAnalyticsPage";

const rootElement = document.getElementById("host-completion-analytics-root");

if (rootElement) {
  const endpoint =
    rootElement.dataset.endpoint ?? "/api/host-completion/analytics";

  createRoot(rootElement).render(
    <StrictMode>
      <HostCompletionAnalyticsPage endpoint={endpoint} />
    </StrictMode>,
  );
}
