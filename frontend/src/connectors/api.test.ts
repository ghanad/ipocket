import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ConnectorApiError,
  fetchConnectorJob,
  fetchConnectorsConfig,
  isConnectorName,
  jobUrl,
  runConnector,
} from "./api";
import type { ConnectorJob, ConnectorsConfig } from "./types";

function reply(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function config(): ConnectorsConfig {
  return {
    connectors: [{
      name: "vcenter",
      display_name: "vCenter",
      description: "Import vCenter inventory.",
      kind: "Manual CLI export",
      help: "See /docs/vcenter-connector.md.",
      command: "python -m app.connectors.vcenter",
      fields: [
        {
          name: "server",
          label: "vCenter server",
          type: "text",
          required: true,
          default: "",
          placeholder: "vc.example.local",
          span: true,
          secret: false,
        },
        {
          name: "password",
          label: "Password",
          type: "password",
          required: true,
          default: "",
          placeholder: "",
          span: false,
          secret: true,
        },
        {
          name: "insecure",
          label: "Skip TLS verification",
          type: "checkbox",
          required: false,
          default: false,
          placeholder: "",
          span: true,
          secret: false,
        },
      ],
      run_url: "/api/ui/connectors/vcenter/run",
    }],
    asset_types: ["OS", "BMC", "VM", "VIP", "OTHER"],
    policy: {
      can_dry_run: true,
      can_apply: false,
      apply_message: "Editor role is required to apply connector imports.",
    },
    jobs_url: "/api/ui/connectors/jobs/{job_id}",
    poll_interval_ms: 1000,
  };
}

function job(status: ConnectorJob["status"]): ConnectorJob {
  return {
    job_id: "job-1",
    connector: "vcenter",
    active_tab: "vcenter",
    status,
    form_state: { server: "vc.example", insecure: false, password: "" },
    logs: ["Safe job log."],
    toast_messages: [{ type: "success", message: "Done." }],
    polling: status === "queued" || status === "running",
  };
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.history.replaceState({}, "", "/");
});

describe("Connectors API adapter", () => {
  it("loads the exact configuration with its signal and same-origin JSON request settings", async () => {
    const payload = config();
    const controller = new AbortController();
    const fetchMock = vi.fn().mockResolvedValue(reply(payload));
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchConnectorsConfig("/api/ui/connectors?tab=vcenter", controller.signal)).resolves.toEqual(payload);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/ui/connectors?tab=vcenter");
    expect(init.credentials).toBe("same-origin");
    expect(init.signal).toBe(controller.signal);
    expect(init.body).toBeUndefined();
    expect(new Headers(init.headers).get("Accept")).toBe("application/json");
    expect(new Headers(init.headers).has("Content-Type")).toBe(false);
  });

  it("preserves config AbortError identity", async () => {
    const abortError = new DOMException("Aborted", "AbortError");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(abortError));

    await expect(fetchConnectorsConfig("/api/ui/connectors", new AbortController().signal)).rejects.toBe(abortError);
  });

  it("submits the schema-provided endpoint as JSON without coercing string or boolean fields", async () => {
    const fetchMock = vi.fn().mockResolvedValue(reply({
      job_id: "job-1",
      connector: "vcenter",
      status: "queued",
      poll_url: "/api/ui/connectors/jobs/job-1",
    }, 202));
    vi.stubGlobal("fetch", fetchMock);
    const values = {
      server: "vc.example",
      port: "443",
      password: "top-secret",
      insecure: true,
      mode: "apply",
    } as const;

    await expect(runConnector("/api/ui/connectors/vcenter/run", values)).resolves.toEqual({
      job_id: "job-1",
      connector: "vcenter",
      status: "queued",
      poll_url: "/api/ui/connectors/jobs/job-1",
    });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/ui/connectors/vcenter/run");
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("same-origin");
    expect(init.body).toBe(JSON.stringify(values));
    const headers = new Headers(init.headers);
    expect(headers.get("Accept")).toBe("application/json");
    expect(headers.get("Content-Type")).toBe("application/json");
  });

  it.each(["queued", "running", "completed", "failed"] as const)("loads %s jobs with the exact poll URL and signal", async (status) => {
    const controller = new AbortController();
    const payload = job(status);
    const fetchMock = vi.fn().mockResolvedValue(reply(payload));
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchConnectorJob("/api/ui/connectors/jobs/job-1", controller.signal)).resolves.toEqual(payload);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/ui/connectors/jobs/job-1");
    expect(init.signal).toBe(controller.signal);
    expect(init.body).toBeUndefined();
    expect(new Headers(init.headers).get("Accept")).toBe("application/json");
  });

  it("keeps a 404 status and its string detail available to page-owned expiry handling", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply({ detail: "Connector job was not found or has expired." }, 404)));

    await expect(fetchConnectorJob("/api/ui/connectors/jobs/gone")).rejects.toMatchObject({
      message: "Connector job was not found or has expired.",
      status: 404,
      loginUrl: null,
    });
  });

  it("uses string details and preserves legacy detail-array joining", async () => {
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(reply({ detail: "Invalid query." }, 400))
      .mockResolvedValueOnce(reply({ detail: ["first", { msg: "second" }, 7, null] }, 400)));

    await expect(runConnector("/api/ui/connectors/prometheus/run", { query: "up" })).rejects.toMatchObject({
      message: "Invalid query.",
      status: 400,
    });
    await expect(runConnector("/api/ui/connectors/prometheus/run", { query: "up" })).rejects.toMatchObject({
      message: "first [object Object] 7 null",
      status: 400,
    });
  });

  it.each([
    [reply({ message: "Unexpected payload." }, 502), "unknown JSON"],
    [new Response("Gateway unavailable", { status: 502 }), "non-JSON"],
  ])("uses the connector fallback for %s errors", async (result, _label) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(result));

    await expect(fetchConnectorsConfig("/api/ui/connectors")).rejects.toMatchObject({
      message: "Connector request failed (502).",
      status: 502,
    });
  });

  it("returns auth information without navigating and includes the current filtered connector URL", async () => {
    window.history.replaceState({}, "", "/ui/connectors?tab=kubernetes&job_id=job%2F1&filter=running");
    const redirectedResponse = {
      ok: true,
      status: 200,
      redirected: true,
      url: "http://testserver/ui/login?return_to=/api/ui/connectors",
      headers: new Headers(),
    } as Response;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(redirectedResponse));

    const error = await fetchConnectorJob("/api/ui/connectors/jobs/job-1").catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ConnectorApiError);
    expect(error).toMatchObject({
      message: "Authentication required.",
      status: 401,
      loginUrl: "/ui/login?return_to=%2Fui%2Fconnectors%3Ftab%3Dkubernetes%26job_id%3Djob%252F1%26filter%3Drunning",
    });
    expect(window.location.pathname).toBe("/ui/connectors");
  });

  it("preserves network failures and does not put submitted secrets in produced errors", async () => {
    const networkError = new TypeError("network unavailable");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValueOnce(networkError).mockResolvedValueOnce(reply({ detail: "Request was rejected." }, 400)));

    await expect(runConnector("/api/ui/connectors/vcenter/run", { password: "top-secret" })).rejects.toBe(networkError);
    const error = await runConnector("/api/ui/connectors/vcenter/run", { password: "top-secret" }).catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ConnectorApiError);
    expect((error as Error).message).not.toContain("top-secret");
  });

  it("encodes job IDs and only accepts supported connector names", () => {
    expect(jobUrl("/api/ui/connectors/jobs/{job_id}", "job/a b?x=1")).toBe("/api/ui/connectors/jobs/job%2Fa%20b%3Fx%3D1");
    for (const connector of ["vcenter", "prometheus", "elasticsearch", "cassandra", "ceph", "kubernetes"]) {
      expect(isConnectorName(connector)).toBe(true);
    }
    expect(isConnectorName("unknown")).toBe(false);
    expect(isConnectorName(null)).toBe(false);
  });
});
