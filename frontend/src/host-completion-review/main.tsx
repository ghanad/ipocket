import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { HostCompletionReviewPage } from "./HostCompletionReviewPage";

const rootElement = document.getElementById("host-completion-review-root");

if (rootElement) {
  const queueEndpoint =
    rootElement.dataset.endpoint ?? "/api/host-completion/findings/next";
  const decisionsEndpoint =
    rootElement.dataset.decisionsEndpoint ??
    "/api/host-completion/findings/decisions";

  createRoot(rootElement).render(
    <StrictMode>
      <HostCompletionReviewPage
        queueEndpoint={queueEndpoint}
        decisionsEndpoint={decisionsEndpoint}
      />
    </StrictMode>,
  );
}
