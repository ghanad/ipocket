import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { HostsPage } from "./HostsPage";
import type { HostsBootstrap } from "./types";

const root = document.getElementById("hosts-root");
const bootstrapElement = document.getElementById("hosts-bootstrap");

function parseBootstrap(): HostsBootstrap | null {
  if (!bootstrapElement?.textContent) return null;
  try {
    return JSON.parse(bootstrapElement.textContent) as HostsBootstrap | null;
  } catch {
    return null;
  }
}

if (root) {
  createRoot(root).render(
    <StrictMode>
      <HostsPage
        endpoint={root.dataset.endpoint ?? "/api/ui/hosts"}
        initialQuery={root.dataset.initialQuery ?? ""}
        bootstrap={parseBootstrap()}
      />
    </StrictMode>,
  );
}
