import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ConnectorsPage } from "./ConnectorsPage";
import type { ConnectorTab } from "./types";

const root = document.getElementById("connectors-root");
if (root) createRoot(root).render(<StrictMode><ConnectorsPage endpoint={root.dataset.endpoint ?? "/api/ui/connectors"} initialTab={(root.dataset.initialTab as ConnectorTab) ?? "overview"} initialJobId={root.dataset.initialJobId ?? ""} /></StrictMode>);
