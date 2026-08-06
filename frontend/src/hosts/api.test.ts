import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  createHost,
  deleteHost,
  fetchHosts,
  updateHost,
} from "./api";
import type { HostFormValues } from "./types";

const values: HostFormValues = {
  name: "edge-01",
  vendor_id: "4",
  project_id: "3",
  os_ips: " 10.0.0.10, ,10.0.0.11 ",
  bmc_ips: "10.0.0.20,  , 10.0.0.21",
  notes: "rack-a",
};

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function fetchCall(fetchMock: ReturnType<typeof vi.fn>) {
  return fetchMock.mock.calls[0] as [string, RequestInit];
}

describe("hosts API", () => {
  it("fetches the exact URL with AbortSignal forwarding", async () => {
    const payload = { hosts: [] };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(payload)));
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();

    await expect(fetchHosts("/api/ui/hosts?q=edge&per-page=10", controller.signal)).resolves.toEqual(payload);
    const [url, init] = fetchCall(fetchMock);
    expect(url).toBe("/api/ui/hosts?q=edge&per-page=10");
    expect(init.signal).toBe(controller.signal);
  });

  it("preserves AbortError", async () => {
    const aborted = new DOMException("Aborted", "AbortError");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(aborted));

    await expect(fetchHosts("/api/ui/hosts")).rejects.toBe(aborted);
  });

  it("creates with POST and the exact transformed payload", async () => {
    const result = { id: 7, name: values.name };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(result), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(createHost("/api/ui/hosts", values)).resolves.toEqual(result);
    const [url, init] = fetchCall(fetchMock);
    expect(url).toBe("/api/ui/hosts");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({
      name: "edge-01",
      notes: "rack-a",
      vendor_id: 4,
      os_ips: ["10.0.0.10", "10.0.0.11"],
      bmc_ips: ["10.0.0.20", "10.0.0.21"],
      project_id: 3,
    }));
  });

  it("updates the host URL with PATCH and omits a mixed project", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: 7, name: values.name })),
    );
    vi.stubGlobal("fetch", fetchMock);

    await updateHost("/api/ui/hosts", 7, { ...values, project_id: "mixed" });
    const [url, init] = fetchCall(fetchMock);
    expect(url).toBe("/api/ui/hosts/7");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(String(init.body))).toEqual({
      name: "edge-01",
      notes: "rack-a",
      vendor_id: 4,
      os_ips: ["10.0.0.10", "10.0.0.11"],
      bmc_ips: ["10.0.0.20", "10.0.0.21"],
    });
  });

  it("converts empty project and vendor values to null", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: 7, name: values.name })),
    );
    vi.stubGlobal("fetch", fetchMock);

    await updateHost("/api/ui/hosts", 7, {
      ...values,
      vendor_id: "",
      project_id: "",
      os_ips: " , ",
      bmc_ips: "",
    });
    expect(JSON.parse(String(fetchCall(fetchMock)[1].body))).toEqual({
      name: "edge-01",
      notes: "rack-a",
      vendor_id: null,
      os_ips: [],
      bmc_ips: [],
      project_id: null,
    });
  });

  it("deletes with the exact URL, method, confirmation payload, and 204 handling", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(deleteHost("/api/ui/hosts", 7, "edge-01")).resolves.toBeUndefined();
    const [url, init] = fetchCall(fetchMock);
    expect(url).toBe("/api/ui/hosts/7");
    expect(init.method).toBe("DELETE");
    expect(init.body).toBe(JSON.stringify({ confirm_name: "edge-01" }));
  });

  it("preserves FastAPI string-detail errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Host name already exists." }), { status: 409 }),
    ));

    await expect(createHost("/api/ui/hosts", values)).rejects.toMatchObject({
      message: "Host name already exists.",
      messages: ["Host name already exists."],
    });
  });

  it("preserves multiple validation messages and removes Value error prefixes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        detail: [
          { loc: ["body", "name"], msg: "Value error, Host name is required." },
          { loc: ["body", "os_ips"], msg: "Value error, Invalid IP address" },
        ],
      }), { status: 422 }),
    ));

    const error = await createHost("/api/ui/hosts", values).catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      message: "Host name is required.",
      messages: ["Host name is required.", "Invalid IP address"],
    });
  });

  it("uses the stable fallback for non-JSON errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response("Gateway unavailable", { status: 502 }),
    ));

    await expect(fetchHosts("/api/ui/hosts")).rejects.toMatchObject({
      message: "Host request failed (502).",
      messages: ["Host request failed (502)."],
    });
  });

  it("redirects authentication to the fixed Hosts return target", async () => {
    const assign = vi.fn();
    vi.stubGlobal("window", {
      location: { pathname: "/ui/hosts", search: "?q=edge", assign },
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      redirected: true,
      url: "http://testserver/ui/login?return_to=/api/ui/hosts",
      headers: new Headers(),
    } as Response));

    await expect(fetchHosts("/api/ui/hosts")).rejects.toMatchObject({
      message: "Authentication required.",
      messages: ["Authentication required."],
    });
    expect(assign).toHaveBeenCalledWith("/ui/login?return_to=/ui/hosts");
  });

  it("propagates network errors unchanged", async () => {
    const offline = new TypeError("offline");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(offline));

    await expect(fetchHosts("/api/ui/hosts")).rejects.toBe(offline);
  });
});
