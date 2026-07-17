import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DataOpsPage } from "./DataOpsPage";

const config = {
  policy: { can_apply: false },
  upload: { max_bytes: 10_485_760, max_size: "10 MB" },
  samples: {
    hosts: "/static/samples/hosts.csv",
    ip_assets: "/static/samples/ip-assets.csv",
  },
};

const importResult = {
  summary: {
    vendors: { would_create: 0, would_update: 0, would_skip: 0 },
    projects: { would_create: 0, would_update: 0, would_skip: 0 },
    hosts: { would_create: 0, would_update: 0, would_skip: 0 },
    ip_assets: { would_create: 1, would_update: 0, would_skip: 0 },
    total: { would_create: 1, would_update: 0, would_skip: 0 },
  },
  errors: [],
  warnings: [],
};

function reply(payload: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  } as Response;
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.history.replaceState({}, "", "/ui/import");
});

describe("DataOpsPage", () => {
  it("loads viewer capabilities, runs bundle dry-runs, and disables apply", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(reply(config))
      .mockResolvedValueOnce(reply(importResult));
    vi.stubGlobal("fetch", fetchMock);
    render(<DataOpsPage endpoint="/api/ui/data-ops" importEndpoint="/api/ui/import" />);

    const bundleCard = (await screen.findByRole("heading", { name: "Import Bundle (JSON)" })).closest("section")!;
    const file = new File(["{}"], "bundle.json", { type: "application/json" });
    fireEvent.change(within(bundleCard).getByLabelText("bundle.json"), {
      target: { files: [file] },
    });
    expect(within(bundleCard).getByRole("button", { name: "Apply" })).toBeDisabled();
    fireEvent.click(within(bundleCard).getByRole("button", { name: "Dry-run" }));

    expect(await within(bundleCard).findByText("Total: 1 create, 0 update, 0 skip")).toBeVisible();
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/ui/import/bundle?dry_run=1",
      expect.objectContaining({ method: "POST", body: expect.any(FormData) }),
    );
    expect(screen.getByText("Bundle dry-run completed.")).toBeVisible();
  });

  it("switches to export downloads and keeps the canonical tab URL", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(config)));
    render(<DataOpsPage endpoint="/api/ui/data-ops" importEndpoint="/api/ui/import" initialTab="export" />);

    expect(await screen.findByRole("heading", { name: "Export All Data" })).toBeVisible();
    expect(screen.getByRole("link", { name: "bundle.json" })).toHaveAttribute("href", "/export/bundle.json");
    fireEvent.click(screen.getByRole("tab", { name: "Import" }));
    expect(window.location.search).toBe("?tab=import");
    expect(await screen.findByRole("heading", { name: "Import CSV" })).toBeVisible();
  });

  it("allows editors to apply Nmap XML and renders returned assets", async () => {
    const editorConfig = { ...config, policy: { can_apply: true } };
    const nmapResult = {
      discovered_up_hosts: 1,
      new_ips_created: 1,
      existing_ips_seen: 0,
      errors: [],
      new_assets: [{ id: 12, ip_address: "10.0.0.12" }],
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(reply(editorConfig))
      .mockResolvedValueOnce(reply(nmapResult));
    vi.stubGlobal("fetch", fetchMock);
    render(<DataOpsPage endpoint="/api/ui/data-ops" importEndpoint="/api/ui/import" />);

    const nmapCard = (await screen.findByRole("heading", { name: "Upload Nmap XML" })).closest("section")!;
    fireEvent.change(within(nmapCard).getByLabelText("Nmap XML file"), {
      target: { files: [new File(["<nmaprun/>"] , "scan.xml", { type: "application/xml" })] },
    });
    fireEvent.click(within(nmapCard).getByRole("button", { name: "Apply" }));

    expect(await within(nmapCard).findByRole("link", { name: "10.0.0.12" })).toHaveAttribute("href", "/ui/ip-assets/12");
    await waitFor(() => expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/ui/import/nmap?dry_run=0",
      expect.objectContaining({ method: "POST" }),
    ));
  });

  it("shows client and API validation errors", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(reply(config))
      .mockResolvedValueOnce(reply({ detail: "Invalid bundle." }, 400));
    vi.stubGlobal("fetch", fetchMock);
    render(<DataOpsPage endpoint="/api/ui/data-ops" importEndpoint="/api/ui/import" />);

    const csvCard = (await screen.findByRole("heading", { name: "Import CSV" })).closest("section")!;
    fireEvent.click(within(csvCard).getByRole("button", { name: "Dry-run" }));
    expect(within(csvCard).getByRole("alert")).toHaveTextContent("Select at least one CSV file.");

    const bundleCard = screen.getByRole("heading", { name: "Import Bundle (JSON)" }).closest("section")!;
    fireEvent.change(within(bundleCard).getByLabelText("bundle.json"), {
      target: { files: [new File(["bad"], "bundle.json")] },
    });
    fireEvent.click(within(bundleCard).getByRole("button", { name: "Dry-run" }));
    expect(await within(bundleCard).findByRole("alert")).toHaveTextContent("Invalid bundle.");
  });
});
