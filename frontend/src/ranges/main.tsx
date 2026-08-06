import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { RangesPage } from "./RangesPage";
import type { RangesBootstrap } from "./types";

const rootElement = document.getElementById("ranges-root");
const bootstrapElement = document.getElementById("ranges-bootstrap");

function parseOptionalId(value: string | undefined): number | undefined {
  if (!value) {
    return undefined;
  }
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function parseBootstrap(): RangesBootstrap | null {
  if (!bootstrapElement?.textContent) {
    return null;
  }
  try {
    return JSON.parse(bootstrapElement.textContent) as RangesBootstrap | null;
  } catch {
    return null;
  }
}

if (rootElement) {
  createRoot(rootElement).render(
    <StrictMode>
      <RangesPage
        endpoint={rootElement.dataset.endpoint ?? "/api/ui/ranges"}
        initialEditId={parseOptionalId(rootElement.dataset.initialEditId)}
        initialDeleteId={parseOptionalId(rootElement.dataset.initialDeleteId)}
        bootstrap={parseBootstrap()}
      />
    </StrictMode>,
  );
}
