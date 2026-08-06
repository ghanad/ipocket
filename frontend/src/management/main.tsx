import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { ManagementPage } from "./ManagementPage";

const rootElement = document.getElementById("management-root");

if (rootElement) {
  const endpoint =
    rootElement.dataset.endpoint ?? "/api/management/overview";

  createRoot(rootElement).render(
    <StrictMode>
      <ManagementPage endpoint={endpoint} />
    </StrictMode>,
  );
}
