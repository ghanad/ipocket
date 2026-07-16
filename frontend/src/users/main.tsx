import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import type { UsersBootstrap } from "./types";
import { UsersPage } from "./UsersPage";

const rootElement = document.getElementById("users-root");
const bootstrapElement = document.getElementById("users-bootstrap");

function parseBootstrap(): UsersBootstrap | null {
  if (!bootstrapElement?.textContent) return null;
  try {
    return JSON.parse(bootstrapElement.textContent) as UsersBootstrap | null;
  } catch {
    return null;
  }
}

if (rootElement) {
  createRoot(rootElement).render(
    <StrictMode>
      <UsersPage
        endpoint={rootElement.dataset.endpoint ?? "/api/ui/users"}
        bootstrap={parseBootstrap()}
      />
    </StrictMode>,
  );
}
