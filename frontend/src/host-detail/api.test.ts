import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchHostDetail, HostDetailApiError } from "./api";
import type { HostDetailResponse } from "./types";

const payload: HostDetailResponse = {
  host: { id: 7, name: "compute-08", vendor: "Supermicro", notes: "rack 4" },
  summary: { linked_count: 0, os_count: 0, bmc_count: 0, other_count: 0 },
  groups: { os: [], bmc: [], other: [] },
};

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.history.replaceState({}, "", "/");
});

describe("fetchHostDetail", () => {
  it("requests the configured endpoint and maps a successful response", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(payload)));
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchHostDetail("/custom/hosts/7")).resolves.toEqual(payload);
    expect(fetchMock.mock.calls[0][0]).toBe("/custom/hosts/7");
  });

  it("forwards AbortSignal and preserves AbortError", async () => {
    const abortError = new DOMException("Aborted", "AbortError");
    const fetchMock = vi.fn().mockRejectedValue(abortError);
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();

    await expect(fetchHostDetail("/api/ui/hosts/7/detail", controller.signal)).rejects.toBe(
      abortError,
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/ui/hosts/7/detail",
      expect.objectContaining({ signal: controller.signal }),
    );
  });

  it("maps network failures to the stable page error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));

    await expect(fetchHostDetail("/api/ui/hosts/7/detail")).rejects.toEqual(
      expect.objectContaining({ message: "Host details could not be loaded.", status: null }),
    );
  });

  it("maps 404 responses to Host not found", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "missing" }), { status: 404 }),
    ));

    await expect(fetchHostDetail("/api/ui/hosts/999/detail")).rejects.toEqual(
      expect.objectContaining({ message: "Host not found.", status: 404 }),
    );
  });

  it("maps other HTTP errors to the stable page fallback", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "internal detail" }), { status: 503 }),
    ));

    const error = await fetchHostDetail("/api/ui/hosts/7/detail").catch(
      (caught: unknown) => caught,
    );
    expect(error).toBeInstanceOf(HostDetailApiError);
    expect(error).toMatchObject({
      message: "Host details could not be loaded.",
      status: 503,
      loginUrl: null,
    });
  });

  it("preserves the page login flow and pathname-only return target", async () => {
    window.history.replaceState({}, "", "/ui/hosts/7?tab=assets");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      redirected: true,
      url: "http://testserver/ui/login?return_to=/api/ui/hosts/7/detail",
      headers: new Headers(),
    } as Response));

    await expect(fetchHostDetail("/api/ui/hosts/7/detail")).rejects.toMatchObject({
      message: "Authentication required.",
      status: 401,
      loginUrl: "/ui/login?return_to=%2Fui%2Fhosts%2F7",
    });
  });
});
