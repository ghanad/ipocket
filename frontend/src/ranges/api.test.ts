import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  createRange,
  deleteRange,
  fetchRanges,
  updateRange,
} from "./api";
import type { RangeFormValues } from "./types";

const values: RangeFormValues = {
  name: "Corp LAN",
  cidr: "192.168.10.0/24",
  notes: "office",
};
const row = {
  id: 7,
  ...values,
  total_usable: 254,
  used: 2,
  free: 252,
  utilization_percent: 0.7874,
};

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function fetchCall(fetchMock: ReturnType<typeof vi.fn>) {
  return fetchMock.mock.calls[0] as [string, RequestInit];
}

describe("ranges API", () => {
  it("fetches ranges from the configured endpoint", async () => {
    const payload = { ranges: [row] };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(payload)));
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchRanges("/custom/ranges")).resolves.toEqual(payload);
    expect(fetchCall(fetchMock)[0]).toBe("/custom/ranges");
  });

  it("creates a range with POST and the exact JSON payload", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(row), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(createRange("/api/ui/ranges", values)).resolves.toEqual(row);
    const [url, init] = fetchCall(fetchMock);
    expect(url).toBe("/api/ui/ranges");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify(values));
  });

  it("updates the selected URL with PATCH and the exact JSON payload", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(row)));
    vi.stubGlobal("fetch", fetchMock);

    await expect(updateRange("/api/ui/ranges", 7, values)).resolves.toEqual(row);
    const [url, init] = fetchCall(fetchMock);
    expect(url).toBe("/api/ui/ranges/7");
    expect(init.method).toBe("PATCH");
    expect(init.body).toBe(JSON.stringify(values));
  });

  it("deletes with the confirmation payload and accepts a 204 response", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(deleteRange("/api/ui/ranges", 7, "Corp LAN")).resolves.toBeUndefined();
    const [url, init] = fetchCall(fetchMock);
    expect(url).toBe("/api/ui/ranges/7");
    expect(init.method).toBe("DELETE");
    expect(init.body).toBe(JSON.stringify({ confirm_name: "Corp LAN" }));
  });

  it("preserves FastAPI string-detail errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "CIDR already exists." }), { status: 409 }),
    ));

    await expect(createRange("/api/ui/ranges", values)).rejects.toMatchObject({
      message: "CIDR already exists.",
      messages: ["CIDR already exists."],
    });
  });

  it("preserves multiple FastAPI validation messages and removes Value error prefixes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        detail: [
          { loc: ["body", "name"], msg: "Value error, Name is required" },
          { loc: ["body", "cidr"], msg: "Value error, CIDR is invalid" },
        ],
      }), { status: 422 }),
    ));

    const error = await createRange("/api/ui/ranges", values).catch(
      (caught: unknown) => caught,
    );
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      message: "Name is required",
      messages: ["Name is required", "CIDR is invalid"],
    });
  });

  it("uses the stable fallback for a non-JSON response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response("Gateway unavailable", { status: 502 }),
    ));

    await expect(fetchRanges("/api/ui/ranges")).rejects.toMatchObject({
      message: "Range request failed (502)",
      messages: ["Range request failed (502)"],
    });
  });

  it("uses the stable fallback for JSON without FastAPI detail", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: "Gateway unavailable" }), { status: 502 }),
    ));

    await expect(fetchRanges("/api/ui/ranges")).rejects.toMatchObject({
      message: "Range request failed (502)",
      messages: ["Range request failed (502)"],
    });
  });

  it("redirects authentication responses to the fixed Ranges return target", async () => {
    const assign = vi.fn();
    vi.stubGlobal("window", {
      location: { pathname: "/ui/ranges", search: "", assign },
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      redirected: true,
      url: "http://testserver/ui/login?return_to=/api/ui/ranges",
      headers: new Headers(),
    } as Response));

    await expect(fetchRanges("/api/ui/ranges")).rejects.toMatchObject({
      message: "Authentication required.",
      messages: ["Authentication required."],
    });
    expect(assign).toHaveBeenCalledWith("/ui/login?return_to=/ui/ranges");
  });

  it("propagates network failures unchanged", async () => {
    const offline = new TypeError("offline");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(offline));

    await expect(fetchRanges("/api/ui/ranges")).rejects.toBe(offline);
  });
});
