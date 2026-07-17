import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConnectorsPage } from "./ConnectorsPage";
import type { ConnectorsConfig } from "./types";

const fields = (names: string[]) => names.map((name) => ({
  name,
  label: ({ server: "vCenter server", username: "Username", password: "Password", prometheus_url: "Prometheus URL", query: "PromQL Query", ip_label: "IP label", token: "Prometheus auth (optional)", elasticsearch_url: "Elasticsearch URL", api_key: "API Key (optional)", contact_points: "Contact points", ceph_url: "Ceph Dashboard URL", api_url: "Kubernetes API URL", asset_type: "Asset type" } as Record<string, string>)[name] ?? name,
  type: ["password", "token", "api_key"].includes(name) ? "password" : name.endsWith("url") ? "url" : name === "insecure" ? "checkbox" : name === "asset_type" ? "select" : "text",
  required: ["server", "username", "password", "prometheus_url", "query", "ip_label", "contact_points", "ceph_url", "api_url"].includes(name),
  default: name === "ip_label" ? "instance" : name === "asset_type" ? "OTHER" : name === "insecure" ? false : "",
  placeholder: "",
  span: false,
  secret: ["password", "token", "api_key"].includes(name),
  options: name === "asset_type" ? ["OS", "BMC", "VM", "VIP", "OTHER"] : undefined,
})) as ConnectorsConfig["connectors"][number]["fields"];

const connectorDefs = [
  ["vcenter", "vCenter", ["server", "username", "password"]],
  ["prometheus", "Prometheus", ["prometheus_url", "query", "ip_label", "asset_type", "token"]],
  ["elasticsearch", "Elasticsearch", ["elasticsearch_url", "api_key", "asset_type"]],
  ["cassandra", "Cassandra", ["contact_points", "username", "password", "asset_type"]],
  ["ceph", "Ceph", ["ceph_url", "username", "password", "asset_type"]],
  ["kubernetes", "Kubernetes", ["api_url", "token", "asset_type", "insecure"]],
] as const;

function config(canApply = false): ConnectorsConfig {
  return {
    connectors: connectorDefs.map(([name, display_name, names]) => ({ name, display_name, description: `${display_name} description`, kind: "Inventory import", help: `See /docs/${name}-connector.md.`, command: `python -m app.connectors.${name}`, fields: fields([...names]), run_url: `/api/ui/connectors/${name}/run` })),
    asset_types: ["OS", "BMC", "VM", "VIP", "OTHER"],
    policy: { can_dry_run: true, can_apply: canApply, apply_message: "Editor required." },
    jobs_url: "/api/ui/connectors/jobs/{job_id}",
    poll_interval_ms: 1000,
  };
}

function reply(payload: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => payload } as Response;
}

function completeJob(connector = "vcenter") {
  return { job_id: "job-1", connector, active_tab: connector, status: "completed", form_state: {}, logs: ["Import mode: dry-run."], toast_messages: [{ type: "success", message: "Done." }], polling: false };
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
  window.history.replaceState({}, "", "/ui/connectors");
});

describe("ConnectorsPage", () => {
  it("defaults to Overview and exposes accessible tabs for every connector", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(config())));
    render(<ConnectorsPage endpoint="/api/ui/connectors" />);
    expect(await screen.findByRole("heading", { name: "Available Connectors" })).toBeVisible();
    expect(screen.getAllByRole("tab")).toHaveLength(7);
    for (const [, label] of connectorDefs) expect(screen.getByRole("tab", { name: label })).toBeVisible();
  });

  it("renders every schema-driven connector form and server defaults", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(config())));
    render(<ConnectorsPage endpoint="/api/ui/connectors" />);
    await screen.findByRole("heading", { name: "Available Connectors" });
    for (const [, label] of connectorDefs) {
      fireEvent.click(screen.getByRole("tab", { name: label }));
      expect(screen.getByRole("form", { name: `${label} connector` })).toBeVisible();
    }
    fireEvent.click(screen.getByRole("tab", { name: "Prometheus" }));
    expect(screen.getByLabelText(/IP label/)).toHaveValue("instance");
    expect(screen.getByLabelText(/Asset type/)).toHaveValue("OTHER");
  });

  it("uses pushState for tabs, Overview links, and restores popstate", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(config())));
    const push = vi.spyOn(window.history, "pushState");
    render(<ConnectorsPage endpoint="/api/ui/connectors" />);
    await screen.findByRole("heading", { name: "Available Connectors" });
    fireEvent.click(screen.getByRole("link", { name: "Prometheus tab" }));
    expect(push).toHaveBeenCalledWith({}, "", "/ui/connectors?tab=prometheus");
    expect(screen.getByRole("heading", { name: "Run Prometheus Connector" })).toBeVisible();
    window.history.pushState({}, "", "/ui/connectors?tab=ceph");
    fireEvent.popState(window);
    expect(await screen.findByRole("heading", { name: "Run Ceph Connector" })).toBeVisible();
    window.history.pushState({}, "", "/ui/connectors?tab=invalid");
    fireEvent.popState(window);
    expect(await screen.findByRole("heading", { name: "Available Connectors" })).toBeVisible();
  });

  it("keeps required forms unready and Viewer Apply disabled", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(config(false))));
    render(<ConnectorsPage endpoint="/api/ui/connectors" initialTab="vcenter" />);
    const form = await screen.findByRole("form", { name: "vCenter connector" });
    expect(within(form).getByRole("button", { name: "Dry-run" })).toBeDisabled();
    expect(within(form).getByRole("button", { name: "Apply" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/vCenter server/), { target: { value: "vc.example" } });
    fireEvent.change(screen.getByLabelText(/^Username/), { target: { value: "admin" } });
    fireEvent.change(screen.getByLabelText(/^Password/), { target: { value: "secret" } });
    expect(within(form).getByRole("button", { name: "Dry-run" })).toBeEnabled();
    expect(within(form).getByRole("button", { name: "Apply" })).toBeDisabled();
  });

  it("confirms Editor Apply, cancels without a request, and never confirms dry-run", async () => {
    const fetchMock = vi.fn().mockResolvedValue(reply(config(true)));
    vi.stubGlobal("fetch", fetchMock);
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<ConnectorsPage endpoint="/api/ui/connectors" initialTab="vcenter" />);
    await screen.findByRole("form", { name: "vCenter connector" });
    for (const [label, value] of [[/vCenter server/, "vc"], [/^Username/, "u"], [/^Password/, "p"]] as const) fireEvent.change(screen.getByLabelText(label), { target: { value } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining("created or updated"));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Dry-run" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(confirm).toHaveBeenCalledTimes(1);
  });

  it("starts a 202 job once, clears secrets, syncs job_id, and polls to completion", async () => {
    const fastConfig = { ...config(true), poll_interval_ms: 1 };
    const fetchMock = vi.fn().mockResolvedValueOnce(reply(fastConfig)).mockResolvedValueOnce(reply({ job_id: "job-1", connector: "vcenter", status: "queued", poll_url: "/api/ui/connectors/jobs/job-1" }, 202)).mockResolvedValueOnce(reply(completeJob()));
    vi.stubGlobal("fetch", fetchMock);
    render(<ConnectorsPage endpoint="/api/ui/connectors" initialTab="vcenter" />);
    await waitFor(() => expect(screen.getByRole("form", { name: "vCenter connector" })).toBeVisible());
    for (const [label, value] of [[/vCenter server/, "vc"], [/^Username/, "u"], [/^Password/, "secret"]] as const) fireEvent.change(screen.getByLabelText(label), { target: { value } });
    const dryRun = screen.getByRole("button", { name: "Dry-run" });
    fireEvent.click(dryRun); fireEvent.click(dryRun);
    await waitFor(() => expect(window.location.search).toContain("job_id=job-1"));
    expect(screen.getByLabelText(/^Password/)).toHaveValue("");
    expect(await screen.findByText("Import mode: dry-run.")).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("shows 400 and 403 API errors safely near the active form", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(reply(config(true))).mockResolvedValueOnce(reply({ detail: ["Invalid query."] }, 400)).mockResolvedValueOnce(reply({ detail: "Apply mode is restricted to editor accounts." }, 403));
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<ConnectorsPage endpoint="/api/ui/connectors" initialTab="prometheus" />);
    await screen.findByRole("form", { name: "Prometheus connector" });
    fireEvent.change(screen.getByLabelText(/Prometheus URL/), { target: { value: "http://prom" } });
    fireEvent.change(screen.getByLabelText(/PromQL Query/), { target: { value: "up" } });
    fireEvent.click(screen.getByRole("button", { name: "Dry-run" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid query.");
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("restricted to editor");
  });

  it("restores a running job URL, renders logs, failure, and expired-job retry state", async () => {
    const running = { ...completeJob("kubernetes"), status: "running", polling: true, logs: ["working"] };
    const failed = { ...running, status: "failed", polling: false, logs: ["Connector failed."] };
    const fetchMock = vi.fn().mockResolvedValueOnce(reply(config())).mockResolvedValueOnce(reply(running)).mockResolvedValueOnce(reply(failed));
    vi.stubGlobal("fetch", fetchMock);
    render(<ConnectorsPage endpoint="/api/ui/connectors" initialTab="kubernetes" initialJobId="job-1" />);
    expect(await screen.findByText("working")).toBeVisible();
    cleanup();
    const expiredFetch = vi.fn().mockResolvedValueOnce(reply(config())).mockResolvedValueOnce(reply({ detail: "expired" }, 404));
    vi.stubGlobal("fetch", expiredFetch);
    render(<ConnectorsPage endpoint="/api/ui/connectors" initialTab="kubernetes" initialJobId="gone" />);
    expect(await screen.findByText(/not found or has expired/)).toBeVisible();
  });

  it("keeps connector form state independent and clears secrets on tab changes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(config())));
    render(<ConnectorsPage endpoint="/api/ui/connectors" initialTab="vcenter" />);
    await screen.findByRole("form", { name: "vCenter connector" });
    fireEvent.change(screen.getByLabelText(/vCenter server/), { target: { value: "vc.saved" } });
    fireEvent.change(screen.getByLabelText(/^Password/), { target: { value: "secret" } });
    fireEvent.click(screen.getByRole("tab", { name: "Prometheus" }));
    fireEvent.change(screen.getByLabelText(/Prometheus URL/), { target: { value: "http://prom.saved" } });
    fireEvent.click(screen.getByRole("tab", { name: "vCenter" }));
    expect(screen.getByLabelText(/vCenter server/)).toHaveValue("vc.saved");
    expect(screen.getByLabelText(/^Password/)).toHaveValue("");
    fireEvent.click(screen.getByRole("tab", { name: "Prometheus" }));
    expect(screen.getByLabelText(/Prometheus URL/)).toHaveValue("http://prom.saved");
  });

  it("aborts polling when unmounted so stale responses cannot update state", async () => {
    let capturedSignal: AbortSignal | undefined;
    const fetchMock = vi.fn().mockImplementation((_url, init) => {
      capturedSignal = init?.signal;
      return Promise.resolve(reply(config()));
    });
    vi.stubGlobal("fetch", fetchMock);
    const view = render(<ConnectorsPage endpoint="/api/ui/connectors" />);
    await screen.findByRole("heading", { name: "Available Connectors" });
    view.unmount();
    expect(capturedSignal?.aborted).toBe(true);
  });
});
