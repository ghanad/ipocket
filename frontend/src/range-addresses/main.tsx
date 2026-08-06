import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { RangeAddressesPage } from "./RangeAddressesPage";

const root = document.getElementById("range-addresses-root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <RangeAddressesPage
        endpoint={root.dataset.endpoint ?? "/api/ui/ranges/0/addresses"}
        initialQuery={root.dataset.initialQuery ?? ""}
      />
    </StrictMode>,
  );
}
