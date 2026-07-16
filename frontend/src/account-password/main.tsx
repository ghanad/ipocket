import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { AccountPasswordPage } from "./AccountPasswordPage";

interface AccountPasswordBootstrap {
  errors?: string[];
}

const rootElement = document.getElementById("account-password-root");
const bootstrapElement = document.getElementById("account-password-bootstrap");

function parseBootstrap(): AccountPasswordBootstrap {
  if (!bootstrapElement?.textContent) return {};
  try {
    return JSON.parse(bootstrapElement.textContent) as AccountPasswordBootstrap;
  } catch {
    return {};
  }
}

if (rootElement) {
  createRoot(rootElement).render(
    <StrictMode>
      <AccountPasswordPage
        endpoint={
          rootElement.dataset.endpoint ?? "/api/ui/account/password"
        }
        initialErrors={parseBootstrap().errors}
      />
    </StrictMode>,
  );
}
