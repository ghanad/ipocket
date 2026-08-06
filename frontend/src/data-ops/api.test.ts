import { afterEach, describe, expect, it, vi } from "vitest";

import {
  DataOpsApiError,
  fetchDataOpsConfig,
  runDataImport,
} from "./api";
import type { DataOpsConfig, ImportResult, NmapResult } from "./types";

const config: DataOpsConfig = {
  policy: { can_apply: true },
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

const importResult: ImportResult = {
  summary: {
    vendors: { would_create: 1, would_update: 2, would_skip: 3 },
    projects: { would_create: 4, would_update: 5, would_skip: 6 },
    hosts: { would_create: 7, would_update: 8, would_skip: 9 },
    ip_assets: { would_create: 10, would_update: 11, would_skip: 12 },
    total: { would_create: 22, would_update: 26, would_skip: 30 },
  },
  errors: [{ location: "ip_assets[1]", message: "Invalid IP" }],
  warnings: [{ location: "hosts[2]", message: "Unknown vendor" }],
};

const nmapResult: NmapResult = {
  discovered_up_hosts: 3,
  new_ips_created: 2,
  existing_ips_seen: 1,
  errors: ["One host was skipped"],
  new_assets: [{ id: 17, ip_address: "10.0.0.17" }],
};

function response(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function fetchCall(fetchMock: ReturnType<typeof vi.fn>) {
  return fetchMock.mock.calls[0] as [string, RequestInit];
}

function uploadForm(entries: Array<[string, File]>): FormData {
  const form = new FormData();
  for (const [field, file] of entries) form.append(field, file);
  return form;
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.history.replaceState({}, "", "/ui/import");
});

describe("Data Operations API", () => {
  it("fetches and maps config from the exact configured endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(config));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      fetchDataOpsConfig("/custom/data-ops?source=ui"),
    ).resolves.toEqual(config);
    const [url, init] = fetchCall(fetchMock);
    expect(url).toBe("/custom/data-ops?source=ui");
    expect(init.credentials).toBe("same-origin");
    expect(new Headers(init.headers).get("Accept")).toBe("application/json");
  });

  it.each([
    [
      "bundle dry-run",
      "/api/ui/import/bundle",
      "dry-run",
      "file",
      "bundle.json",
      importResult,
      "/api/ui/import/bundle?dry_run=1",
    ],
    [
      "bundle apply",
      "/api/ui/import/bundle",
      "apply",
      "file",
      "bundle.json",
      importResult,
      "/api/ui/import/bundle?dry_run=0",
    ],
    [
      "Nmap upload",
      "/api/ui/import/nmap",
      "dry-run",
      "file",
      "scan.xml",
      nmapResult,
      "/api/ui/import/nmap?dry_run=1",
    ],
  ] as const)(
    "preserves the %s multipart request and response mapping",
    async (_label, endpoint, mode, field, filename, result, expectedUrl) => {
      const file = new File(["payload"], filename);
      const form = uploadForm([[field, file]]);
      const fetchMock = vi.fn().mockResolvedValue(response(result));
      vi.stubGlobal("fetch", fetchMock);

      await expect(runDataImport(endpoint, mode, form)).resolves.toEqual(result);
      const [url, init] = fetchCall(fetchMock);
      const headers = new Headers(init.headers);
      expect(url).toBe(expectedUrl);
      expect(init.method).toBe("POST");
      expect(init.body).toBe(form);
      expect((init.body as FormData).get(field)).toBe(file);
      expect(headers.has("Content-Type")).toBe(false);
      expect(headers.get("Accept")).toBe("application/json");
      expect(init.credentials).toBe("same-origin");
    },
  );

  it.each([
    ["hosts only", [["hosts", "hosts.csv"]]],
    ["IP assets only", [["ip_assets", "ip-assets.csv"]]],
    [
      "both files",
      [["hosts", "hosts.csv"], ["ip_assets", "ip-assets.csv"]],
    ],
  ] as const)("preserves CSV %s fields", async (_label, fields) => {
    const entries = fields.map(
      ([field, filename]) =>
        [field, new File([field], filename)] as [string, File],
    );
    const form = uploadForm(entries);
    const fetchMock = vi.fn().mockResolvedValue(response(importResult));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      runDataImport("/api/ui/import/csv", "dry-run", form),
    ).resolves.toEqual(importResult);
    const [url, init] = fetchCall(fetchMock);
    expect(url).toBe("/api/ui/import/csv?dry_run=1");
    expect(init.body).toBe(form);
    expect([...(init.body as FormData).keys()]).toEqual(
      fields.map(([field]) => field),
    );
    for (const [index, [field]] of fields.entries()) {
      expect((init.body as FormData).get(field)).toBe(entries[index][1]);
    }
    expect(new Headers(init.headers).has("Content-Type")).toBe(false);
  });

  it.each([
    [
      "an existing query",
      "/api/ui/import/bundle?source=react",
      "/api/ui/import/bundle?source=react&dry_run=1",
    ],
    [
      "a trailing query marker",
      "/api/ui/import/bundle?",
      "/api/ui/import/bundle?dry_run=1",
    ],
    [
      "a fragment",
      "/api/ui/import/bundle?source=react#upload",
      "/api/ui/import/bundle?source=react&dry_run=1#upload",
    ],
  ])("adds dry-run after %s without malformed URLs", async (_label, endpoint, expected) => {
    const fetchMock = vi.fn().mockResolvedValue(response(importResult));
    vi.stubGlobal("fetch", fetchMock);

    await runDataImport(endpoint, "dry-run", new FormData());
    expect(fetchCall(fetchMock)[0]).toBe(expected);
  });

  it.each([
    ["string detail", { detail: "Invalid bundle." }, "Invalid bundle."],
    [
      "string-array detail",
      { detail: ["First issue", "Second issue"] },
      "First issue, Second issue",
    ],
    [
      "validation-object detail",
      { detail: [{ msg: "Value error, Invalid host" }, { msg: "Bad asset" }] },
      "Invalid host, Bad asset",
    ],
  ])("preserves %s as one page-facing message", async (_label, payload, message) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(payload, 422)));

    const error = await fetchDataOpsConfig("/api/ui/data-ops").catch(
      (caught: unknown) => caught,
    );
    expect(error).toBeInstanceOf(DataOpsApiError);
    expect(error).toMatchObject({ message });
    expect(error).not.toHaveProperty("messages");
  });

  it.each([
    ["JSON without usable detail", JSON.stringify({ error: "gateway" })],
    ["a non-JSON response", "Gateway unavailable"],
  ])("uses the exact status fallback for %s", async (_label, body) => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(body, { status: 502 })),
    );

    await expect(fetchDataOpsConfig("/api/ui/data-ops")).rejects.toMatchObject({
      message: "Data operation failed (502).",
    });
  });

  it("preserves the existing empty detail-array message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ detail: [] }, 422)));

    await expect(fetchDataOpsConfig("/api/ui/data-ops")).rejects.toMatchObject({
      message: "",
    });
  });

  it("redirects authentication to the encoded current Data Operations location", async () => {
    const assign = vi.fn();
    vi.stubGlobal("window", {
      location: { pathname: "/ui/import", search: "?tab=export", assign },
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      redirected: true,
      url: "http://testserver/ui/login?return_to=/api/ui/data-ops",
      headers: new Headers(),
    } as Response));

    await expect(fetchDataOpsConfig("/api/ui/data-ops")).rejects.toMatchObject({
      message: "Authentication required.",
    });
    expect(assign).toHaveBeenCalledWith(
      "/ui/login?return_to=%2Fui%2Fimport%3Ftab%3Dexport",
    );
  });

  it("propagates network errors unchanged", async () => {
    const offline = new TypeError("offline");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(offline));

    await expect(fetchDataOpsConfig("/api/ui/data-ops")).rejects.toBe(offline);
  });
});
