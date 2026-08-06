import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { LoginPage } from "./LoginPage";

interface LoginBootstrap {
  return_to?: string;
  error_message?: string;
  username?: string;
}

const rootElement = document.getElementById("login-root");
const bootstrapElement = document.getElementById("login-bootstrap");

function parseBootstrap(): LoginBootstrap {
  if (!bootstrapElement?.textContent) return {};
  try {
    return JSON.parse(bootstrapElement.textContent) as LoginBootstrap;
  } catch {
    return {};
  }
}

if (rootElement) {
  const bootstrap = parseBootstrap();
  createRoot(rootElement).render(
    <StrictMode>
      <LoginPage
        endpoint={rootElement.dataset.endpoint ?? "/api/ui/login"}
        returnTo={bootstrap.return_to}
        initialError={bootstrap.error_message}
        initialUsername={bootstrap.username}
      />
    </StrictMode>,
  );
}
