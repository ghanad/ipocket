import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BMCDiscoveryDrawer } from "./BMCDiscoveryDrawer";

const mockTargetsResponse = {
  targets: [
    {
      host_id: 1,
      host_name: "server-dell",
      vendor_name: null,
      bmc_assets: [{ id: 101, ip_address: "192.168.10.50" }],
    },
    {
      host_id: 2,
      host_name: "server-unknown",
      vendor_name: null,
      bmc_assets: [{ id: 102, ip_address: "192.168.10.51" }],
    },
  ],
  total: 2,
};

const mockScanResponse = {
  results: [
    {
      host_id: 1,
      host_name: "server-dell",
      bmc_ip: "192.168.10.50",
      detected_vendor: "Dell",
      confidence: "high" as const,
      fingerprint_summary: "CN=idrac-test, O=Dell Inc.",
      status: "matched" as const,
      error: null,
    },
    {
      host_id: 2,
      host_name: "server-unknown",
      bmc_ip: "192.168.10.51",
      detected_vendor: null,
      confidence: null,
      fingerprint_summary: "Timeout connecting to port 443",
      status: "timeout" as const,
      error: "Timeout",
    },
  ],
  total: 2,
  matched_count: 1,
};

const mockApplyResponse = {
  applied: [
    { host_id: 1, host_name: "server-dell", vendor_name: "Dell" },
  ],
  count: 1,
};

function jsonReply(payload: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    redirected: false,
    headers: new Headers({ "content-type": "application/json" }),
    text: async () => JSON.stringify(payload),
  } as Response;
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("BMCDiscoveryDrawer", () => {
  it("loads targets on open and handles scan and apply flow", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string, opts?: RequestInit) => {
      if (url.includes("/api/hosts/bmc-discovery/targets")) {
        return Promise.resolve(jsonReply(mockTargetsResponse));
      }
      if (url.includes("/api/hosts/bmc-discovery/scan")) {
        return Promise.resolve(jsonReply(mockScanResponse));
      }
      if (url.includes("/api/hosts/bmc-discovery/apply")) {
        return Promise.resolve(jsonReply(mockApplyResponse));
      }
      return Promise.reject(new Error(`Unhandled URL: ${url}`));
    });

    vi.stubGlobal("fetch", fetchMock);

    const onApplied = vi.fn();
    const onClose = vi.fn();

    render(
      <BMCDiscoveryDrawer
        open={true}
        onClose={onClose}
        onApplied={onApplied}
        vendors={[{ id: 1, name: "Dell" }]}
      />
    );

    // Initial targets load
    expect(await screen.findByText(/2 host\(s\) without vendor have linked BMC IPs/i)).toBeInTheDocument();

    // Trigger scan
    const scanButton = screen.getByRole("button", { name: /Run Discovery Scan/i });
    fireEvent.click(scanButton);

    // Verify scan results appear
    expect(await screen.findByText("server-dell")).toBeInTheDocument();
    expect(screen.getByText("server-unknown")).toBeInTheDocument();
    expect(screen.getByText("matched")).toBeInTheDocument();
    expect(screen.getByText("timeout")).toBeInTheDocument();

    // The matched row should be selected by default
    const applyButton = screen.getByRole("button", { name: /Apply to Selected \(1\)/i });
    expect(applyButton).toBeEnabled();

    // Trigger apply
    fireEvent.click(applyButton);

    // Verify apply API was called and success message displayed
    await waitFor(() => {
      expect(onApplied).toHaveBeenCalledTimes(1);
      expect(screen.getByText(/Successfully applied vendor to 1 host\(s\)/i)).toBeInTheDocument();
    });

    // Close drawer
    const closeButton = screen.getByRole("button", { name: /Close discovery drawer/i });
    fireEvent.click(closeButton);
    expect(onClose).toHaveBeenCalled();
  });
});
