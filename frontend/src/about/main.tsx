import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { AboutPage } from "./AboutPage";

const rootElement = document.getElementById("about-root");

if (rootElement) {
  createRoot(rootElement).render(
    <StrictMode>
      <AboutPage endpoint={rootElement.dataset.endpoint ?? "/api/ui/about"} />
    </StrictMode>,
  );
}
