import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createRangeAddress,
  fetchRangeAddresses,
  RangeAddressesApiError,
  updateRangeAddress,
} from "./api";
import type { AddressFormValues } from "./types";

const values: AddressFormValues = {
  ip_address: "10.0.0.2",
  type: "VM",
  project_id: "7",
  tags: ["prod", "linux"],
  notes: "keep exactly",
};

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.history.replaceState({}, "", "/");
});

function fetchCall(fetchMock: ReturnType<typeof vi.fn>) {
  return fetchMock.mock.calls[0] as [string, RequestInit];
}

describe("range addresses API", () => {
  it("fetches the exact URL with AbortSignal forwarding", async () => {
    const payload = { addresses: [] };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(payload)));
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();

    await expect(
      fetchRangeAddresses("/api/ui/ranges/7/addresses?q=edge&tag=prod", controller.signal),
    ).resolves.toEqual(payload);
    const [url, init] = fetchCall(fetchMock);
    expect(url).toBe("/api/ui/ranges/7/addresses?q=edge&tag=prod");
    expect(init.signal).toBe(controller.signal);
  });

  it("preserves AbortError", async () => {
    const aborted = new DOMException("Aborted", "AbortError");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(aborted));

    await expect(fetchRangeAddresses("/api/ui/ranges/7/addresses")).rejects.toBe(aborted);
  });

  it("creates with POST and the exact transformed JSON payload", async () => {
    const result = { asset_id: 9, ip_address: values.ip_address };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(result), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(createRangeAddress("/api/ui/ranges/7/addresses", values)).resolves.toEqual(result);
    const [url, init] = fetchCall(fetchMock);
    expect(url).toBe("/api/ui/ranges/7/addresses");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({
      ip_address: "10.0.0.2",
      type: "VM",
      project_id: 7,
      tags: ["prod", "linux"],
      notes: "keep exactly",
    }));
  });

  it("updates the asset URL with PATCH, omits the IP, and converts an empty project to null", async () => {
    const result = { asset_id: 9, ip_address: values.ip_address };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(result)));
    vi.stubGlobal("fetch", fetchMock);

    await updateRangeAddress("/api/ui/ranges/7/addresses", 9, {
      ...values,
      project_id: "",
    });
    const [url, init] = fetchCall(fetchMock);
    expect(url).toBe("/api/ui/ranges/7/addresses/9");
    expect(init.method).toBe("PATCH");
    expect(init.body).toBe(JSON.stringify({
      type: "VM",
      project_id: null,
      tags: ["prod", "linux"],
      notes: "keep exactly",
    }));
  });

  it("preserves FastAPI string-detail errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "IP address is already assigned." }), { status: 400 }),
    ));

    await expect(createRangeAddress("/api/ui/ranges/7/addresses", values)).rejects.toMatchObject({
      message: "IP address is already assigned.",
      messages: ["IP address is already assigned."],
    });
  });

  it("preserves multiple validation messages and removes Value error prefixes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        detail: [
          { loc: ["body", "ip_address"], msg: "Value error, Invalid IP address" },
          { loc: ["body", "project_id"], msg: "Value error, Project is missing" },
        ],
      }), { status: 422 }),
    ));

    const error = await createRangeAddress("/api/ui/ranges/7/addresses", values).catch(
      (caught: unknown) => caught,
    );
    expect(error).toBeInstanceOf(RangeAddressesApiError);
    expect(error).toMatchObject({
      message: "Invalid IP address",
      messages: ["Invalid IP address", "Project is missing"],
    });
  });

  it("uses the stable fallback for non-JSON errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response("Gateway unavailable", { status: 502 }),
    ));

    await expect(fetchRangeAddresses("/api/ui/ranges/7/addresses")).rejects.toMatchObject({
      message: "Range address request failed (502).",
      messages: ["Range address request failed (502)."],
    });
  });

  it("redirects authentication to the exact encoded current pathname and query", async () => {
    const assign = vi.fn();
    vi.stubGlobal("window", {
      location: {
        pathname: "/ui/ranges/7/addresses",
        search: "?status=used&tag=core network",
        assign,
      },
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      redirected: true,
      url: "http://testserver/ui/login?return_to=/api/ui/ranges/7/addresses",
      headers: new Headers(),
    } as Response));

    await expect(fetchRangeAddresses("/api/ui/ranges/7/addresses")).rejects.toMatchObject({
      message: "Authentication required.",
      messages: ["Authentication required."],
    });
    expect(assign).toHaveBeenCalledWith(
      "/ui/login?return_to=%2Fui%2Franges%2F7%2Faddresses%3Fstatus%3Dused%26tag%3Dcore%20network",
    );
  });

  it("propagates network errors unchanged", async () => {
    const offline = new TypeError("offline");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(offline));

    await expect(fetchRangeAddresses("/api/ui/ranges/7/addresses")).rejects.toBe(offline);
  });
});
