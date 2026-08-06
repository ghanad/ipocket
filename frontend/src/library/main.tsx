import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { LibraryPage } from "./LibraryPage";
import type { LibraryBootstrap, LibraryTab } from "./types";

const rootElement = document.getElementById("library-root");
const bootstrapElement = document.getElementById("library-bootstrap");

function parseOptionalId(value: string | undefined): number | undefined {
  if (!value) {
    return undefined;
  }
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function parseTab(value: string | undefined): LibraryTab {
  return value === "vendors" || value === "tags" ? value : "projects";
}

function parseBootstrap(): LibraryBootstrap | null {
  if (!bootstrapElement?.textContent) {
    return null;
  }
  try {
    return JSON.parse(bootstrapElement.textContent) as LibraryBootstrap | null;
  } catch {
    return null;
  }
}

if (rootElement) {
  const bootstrap = parseBootstrap();
  createRoot(rootElement).render(
    <StrictMode>
      <LibraryPage
        endpoint={rootElement.dataset.endpoint ?? "/api/ui/library"}
        initialTab={bootstrap?.tab ?? parseTab(rootElement.dataset.activeTab)}
        initialEditId={parseOptionalId(rootElement.dataset.initialEditId)}
        initialDeleteId={parseOptionalId(rootElement.dataset.initialDeleteId)}
        bootstrap={bootstrap}
      />
    </StrictMode>,
  );
}
