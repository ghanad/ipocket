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
  imports: {
    bundle: "/api/ui/import/bundle",
    csv: "/api/ui/import/csv",
    nmap: "/api/ui/import/nmap",
  },
  exports: {
    bundle_json: "/export/bundle.json",
    bundle_zip: "/export/bundle.zip",
    ip_assets_csv: "/export/ip-assets.csv",
    ip_assets_json: "/export/ip-assets.json",
    hosts_csv: "/export/hosts.csv",
    hosts_json: "/export/hosts.json",
    vendors_csv: "/export/vendors.csv",
    vendors_json: "/export/vendors.json",
    projects_csv: "/export/projects.csv",
    projects_json: "/export/projects.json",
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

function selectFile(card: HTMLElement, label: string, file: File) {
  fireEvent.change(within(card).getByLabelText(label), { target: { files: [file] } });
}

function bundleFile() {
  return new File(["{}"], "bundle.json", { type: "application/json" });
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.history.replaceState({}, "", "/ui/import");
});

describe("DataOpsPage", () => {
  it("disables each card until its required files are selected or cleared", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply({ ...config, policy: { can_apply: true } })));
    render(<DataOpsPage endpoint="/api/ui/data-ops" />);

    const bundle = (await screen.findByRole("heading", { name: "Import Bundle (JSON)" })).closest("section")!;
    const csv = screen.getByRole("heading", { name: "Import CSV" }).closest("section")!;
    const nmap = screen.getByRole("heading", { name: "Upload Nmap XML" }).closest("section")!;
    for (const card of [bundle, csv, nmap]) {
      expect(within(card).getByRole("button", { name: "Dry-run" })).toBeDisabled();
      expect(within(card).getByRole("button", { name: "Apply" })).toBeDisabled();
    }

    const bundleInput = within(bundle).getByLabelText("bundle.json");
    fireEvent.change(bundleInput, { target: { files: [bundleFile()] } });
    expect(within(bundle).getByRole("button", { name: "Dry-run" })).toBeEnabled();
    expect(within(bundle).getByRole("button", { name: "Apply" })).toBeEnabled();
    fireEvent.change(bundleInput, { target: { files: [] } });
    expect(within(bundle).getByRole("button", { name: "Dry-run" })).toBeDisabled();

    selectFile(csv, "hosts.csv", new File(["name\nnode"], "hosts.csv", { type: "text/csv" }));
    expect(within(csv).getByRole("button", { name: "Dry-run" })).toBeEnabled();
    selectFile(nmap, "Nmap XML file", new File(["<nmaprun/>"], "scan.xml", { type: "application/xml" }));
    expect(within(nmap).getByRole("button", { name: "Apply" })).toBeEnabled();
  });

  it("keeps viewer Apply disabled after file selection", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(config)));
    render(<DataOpsPage endpoint="/api/ui/data-ops" />);
    const card = (await screen.findByRole("heading", { name: "Import Bundle (JSON)" })).closest("section")!;
    selectFile(card, "bundle.json", bundleFile());
    expect(within(card).getByRole("button", { name: "Dry-run" })).toBeEnabled();
    expect(within(card).getByRole("button", { name: "Apply" })).toBeDisabled();
  });

  it("confirms and submits bundle Apply", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(reply({ ...config, policy: { can_apply: true } })).mockResolvedValueOnce(reply(importResult));
    vi.stubGlobal("fetch", fetchMock);
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<DataOpsPage endpoint="/api/ui/data-ops" />);
    const card = (await screen.findByRole("heading", { name: "Import Bundle (JSON)" })).closest("section")!;
    selectFile(card, "bundle.json", bundleFile());
    fireEvent.click(within(card).getByRole("button", { name: "Apply" }));

    expect(confirm).toHaveBeenCalledOnce();
    expect(confirm.mock.calls[0][0]).toContain("Inventory data may be created or updated");
    await waitFor(() => expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/ui/import/bundle?dry_run=0",
      expect.objectContaining({ method: "POST", body: expect.any(FormData) }),
    ));
    expect(await screen.findByText("Bundle import applied.")).toBeVisible();
  });

  it("requires confirmation for CSV and Nmap Apply", async () => {
    const nmapResult = { discovered_up_hosts: 0, new_ips_created: 0, existing_ips_seen: 0, errors: [], new_assets: [] };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(reply({ ...config, policy: { can_apply: true } }))
      .mockResolvedValueOnce(reply(importResult))
      .mockResolvedValueOnce(reply(nmapResult));
    vi.stubGlobal("fetch", fetchMock);
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<DataOpsPage endpoint="/api/ui/data-ops" />);
    const csv = (await screen.findByRole("heading", { name: "Import CSV" })).closest("section")!;
    const nmap = screen.getByRole("heading", { name: "Upload Nmap XML" }).closest("section")!;

    selectFile(csv, "hosts.csv", new File(["name\nnode"], "hosts.csv", { type: "text/csv" }));
    fireEvent.click(within(csv).getByRole("button", { name: "Apply" }));
    expect(await screen.findByText("CSV import applied.")).toBeVisible();
    selectFile(nmap, "Nmap XML file", new File(["<nmaprun/>"], "scan.xml", { type: "application/xml" }));
    fireEvent.click(within(nmap).getByRole("button", { name: "Apply" }));
    expect(await screen.findByText("Nmap import applied.")).toBeVisible();

    expect(confirm).toHaveBeenCalledTimes(2);
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/ui/import/csv?dry_run=0", expect.anything());
    expect(fetchMock).toHaveBeenNthCalledWith(3, "/api/ui/import/nmap?dry_run=0", expect.anything());
  });

  it("cancels Apply without changing files, results, or sending a request", async () => {
    const fetchMock = vi.fn().mockResolvedValue(reply({ ...config, policy: { can_apply: true } }));
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<DataOpsPage endpoint="/api/ui/data-ops" />);
    const card = (await screen.findByRole("heading", { name: "Import CSV" })).closest("section")!;
    const input = within(card).getByLabelText("ip-assets.csv") as HTMLInputElement;
    const file = new File(["ip_address\n10.0.0.1"], "ip-assets.csv", { type: "text/csv" });
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(within(card).getByRole("button", { name: "Apply" }));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(input.files?.[0]).toBe(file);
    expect(within(card).queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText(/import applied/i)).not.toBeInTheDocument();
  });

  it("runs Nmap dry-run without confirmation", async () => {
    const nmapResult = { discovered_up_hosts: 0, new_ips_created: 0, existing_ips_seen: 0, errors: [], new_assets: [] };
    const fetchMock = vi.fn().mockResolvedValueOnce(reply(config)).mockResolvedValueOnce(reply(nmapResult));
    vi.stubGlobal("fetch", fetchMock);
    const confirm = vi.spyOn(window, "confirm");
    render(<DataOpsPage endpoint="/api/ui/data-ops" />);
    const card = (await screen.findByRole("heading", { name: "Upload Nmap XML" })).closest("section")!;
    selectFile(card, "Nmap XML file", new File(["<nmaprun/>"], "scan.xml", { type: "application/xml" }));
    fireEvent.click(within(card).getByRole("button", { name: "Dry-run" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(confirm).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenLastCalledWith("/api/ui/import/nmap?dry_run=1", expect.anything());
  });

  it("prevents duplicate confirmation and submission", async () => {
    let resolveImport!: (value: Response) => void;
    const pending = new Promise<Response>((resolve) => { resolveImport = resolve; });
    const fetchMock = vi.fn().mockResolvedValueOnce(reply({ ...config, policy: { can_apply: true } })).mockReturnValueOnce(pending);
    vi.stubGlobal("fetch", fetchMock);
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<DataOpsPage endpoint="/api/ui/data-ops" />);
    const card = (await screen.findByRole("heading", { name: "Import Bundle (JSON)" })).closest("section")!;
    selectFile(card, "bundle.json", bundleFile());
    const csv = screen.getByRole("heading", { name: "Import CSV" }).closest("section")!;
    selectFile(csv, "hosts.csv", new File(["name\nnode"], "hosts.csv", { type: "text/csv" }));
    const apply = within(card).getByRole("button", { name: "Apply" });
    fireEvent.click(apply);
    fireEvent.click(apply);

    expect(confirm).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(within(csv).getByRole("button", { name: "Dry-run" })).toBeDisabled();
    resolveImport(reply(importResult));
    expect(await screen.findByText("Bundle import applied.")).toBeVisible();
    expect(within(csv).getByRole("button", { name: "Dry-run" })).toBeEnabled();
  });

  it("uses pushState for interactive tab changes and canonical URLs", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(config)));
    const pushState = vi.spyOn(window.history, "pushState");
    render(<DataOpsPage endpoint="/api/ui/data-ops" />);
    await screen.findByRole("heading", { name: "Import Bundle (JSON)" });
    fireEvent.click(screen.getByRole("tab", { name: "Export" }));
    expect(pushState).toHaveBeenCalledWith({}, "", "/ui/import?tab=export");
    expect(window.location.pathname + window.location.search).toBe("/ui/import?tab=export");
    expect(await screen.findByRole("heading", { name: "Export All Data" })).toBeVisible();
  });

  it("restores Import and Export on popstate like Back and Forward", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(config)));
    render(<DataOpsPage endpoint="/api/ui/data-ops" />);
    await screen.findByRole("heading", { name: "Import Bundle (JSON)" });
    window.history.pushState({}, "", "/ui/import?tab=export");
    fireEvent.popState(window);
    expect(await screen.findByRole("heading", { name: "Export All Data" })).toBeVisible();
    window.history.pushState({}, "", "/ui/import?tab=import");
    fireEvent.popState(window);
    expect(await screen.findByRole("heading", { name: "Import CSV" })).toBeVisible();
    window.history.pushState({}, "", "/ui/import?tab=invalid");
    fireEvent.popState(window);
    expect(await screen.findByRole("heading", { name: "Import Bundle (JSON)" })).toBeVisible();
  });

  it("opens /ui/export on Export for backward compatibility", async () => {
    window.history.replaceState({}, "", "/ui/export");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(config)));
    render(<DataOpsPage endpoint="/api/ui/data-ops" initialTab="export" />);
    expect(await screen.findByRole("heading", { name: "Export All Data" })).toBeVisible();
  });

  it("shows every server-provided export URL and notifies without preventing navigation", async () => {
    window.history.replaceState({}, "", "/ui/import?tab=export");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(config)));
    render(<DataOpsPage endpoint="/api/ui/data-ops" initialTab="export" />);
    await screen.findByRole("heading", { name: "Export All Data" });
    for (const href of Object.values(config.exports)) {
      expect(document.querySelector(`a[href="${href}"]`)).not.toBeNull();
    }
    const link = document.querySelector(`a[href="${config.exports.bundle_json}"]`)!;
    const click = new MouseEvent("click", { bubbles: true, cancelable: true });
    let componentPreventedNavigation = true;
    const stopJSDOMNavigation = (event: MouseEvent) => {
      componentPreventedNavigation = event.defaultPrevented;
      event.preventDefault();
    };
    document.addEventListener("click", stopJSDOMNavigation);
    link.dispatchEvent(click);
    document.removeEventListener("click", stopJSDOMNavigation);
    expect(componentPreventedNavigation).toBe(false);
    expect(await screen.findByText("Export started.")).toBeVisible();
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("keeps results and errors scoped to their import cards", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(reply({ ...config, policy: { can_apply: true } }))
      .mockResolvedValueOnce(reply(importResult))
      .mockResolvedValueOnce(reply({ detail: "Invalid CSV." }, 400));
    vi.stubGlobal("fetch", fetchMock);
    render(<DataOpsPage endpoint="/api/ui/data-ops" />);
    const bundle = (await screen.findByRole("heading", { name: "Import Bundle (JSON)" })).closest("section")!;
    const csv = screen.getByRole("heading", { name: "Import CSV" }).closest("section")!;
    selectFile(bundle, "bundle.json", bundleFile());
    fireEvent.click(within(bundle).getByRole("button", { name: "Dry-run" }));
    expect(await within(bundle).findByText("Total: 1 create, 0 update, 0 skip")).toBeVisible();
    selectFile(csv, "hosts.csv", new File(["bad"], "hosts.csv", { type: "text/csv" }));
    fireEvent.click(within(csv).getByRole("button", { name: "Dry-run" }));
    expect(await within(csv).findByRole("alert")).toHaveTextContent("Invalid CSV.");
    expect(within(bundle).getByText("Total: 1 create, 0 update, 0 skip")).toBeVisible();
    expect(within(bundle).queryByRole("alert")).not.toBeInTheDocument();
  });
});
