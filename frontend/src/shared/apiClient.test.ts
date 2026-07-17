import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest } from "./apiClient";

function response(body: BodyInit | null, init: ResponseInit = {}): Response {
  return new Response(body, { status: 200, ...init });
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.history.replaceState({}, "", "/");
});

describe("apiRequest", () => {
  it("parses successful JSON with same-origin cookies", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      response(JSON.stringify({ value: 7 }), {
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiRequest<{ value: number }>("/api/value")).resolves.toEqual({ value: 7 });
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.credentials).toBe("same-origin");
    expect(new Headers(init.headers).get("Accept")).toBe("application/json");
  });

  it.each([
    ["204 response", response(null, { status: 204 })],
    ["empty response", response("")],
  ])("returns undefined for an %s", async (_label, result) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(result));
    await expect(apiRequest<void>("/api/empty")).resolves.toBeUndefined();
  });

  it("serializes JSON request bodies and preserves custom headers", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(JSON.stringify({ ok: true })));
    vi.stubGlobal("fetch", fetchMock);

    await apiRequest("/api/items", {
      method: "POST",
      json: { name: "router" },
      headers: { "X-Request-ID": "test" },
    });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = new Headers(init.headers);
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(headers.get("X-Request-ID")).toBe("test");
    expect(init.body).toBe(JSON.stringify({ name: "router" }));
  });

  it("leaves FormData Content-Type assignment to the browser", async () => {
    const form = new FormData();
    form.append("file", new Blob(["data"]), "input.txt");
    const fetchMock = vi.fn().mockResolvedValue(response(JSON.stringify({ ok: true })));
    vi.stubGlobal("fetch", fetchMock);

    await apiRequest("/api/upload", { method: "POST", body: form });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.body).toBe(form);
    expect(new Headers(init.headers).has("Content-Type")).toBe(false);
  });

  it("uses a FastAPI string detail in typed errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      response(JSON.stringify({ detail: "Record not found" }), { status: 404 }),
    ));

    await expect(apiRequest("/api/missing")).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
      message: "Record not found",
      payload: { detail: "Record not found" },
    });
  });

  it("formats FastAPI validation detail arrays", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      response(
        JSON.stringify({
          detail: [{ loc: ["body", "ip_address"], msg: "Field required", type: "missing" }],
        }),
        { status: 422 },
      ),
    ));

    await expect(apiRequest("/api/items")).rejects.toMatchObject({
      status: 422,
      message: "body.ip_address: Field required",
    });
  });

  it("retains unknown JSON error payloads and supplies a useful message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      response(JSON.stringify({ errors: { ip: ["invalid"] } }), { status: 400 }),
    ));

    const error = await apiRequest("/api/items").catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 400,
      message: JSON.stringify({ errors: { ip: ["invalid"] } }),
      payload: { errors: { ip: ["invalid"] } },
    });
  });

  it("uses a non-JSON error response as the error message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response("Gateway unavailable", { status: 502 })));
    await expect(apiRequest("/api/items")).rejects.toMatchObject({
      status: 502,
      message: "Gateway unavailable",
    });
  });

  it("navigates authentication redirects to login with the current UI return target", async () => {
    window.history.replaceState({}, "", "/ui/audit-log?page=2&per-page=10");
    const redirectedResponse = {
      ok: true,
      status: 200,
      redirected: true,
      url: "http://testserver/ui/login?return_to=/api/ui/audit-log",
      headers: new Headers(),
    } as Response;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(redirectedResponse));
    const navigate = vi.fn();

    await expect(
      apiRequest("/api/ui/audit-log", { onAuthenticationRequired: navigate }),
    ).rejects.toMatchObject({ status: 401, message: "Authentication required." });
    expect(navigate).toHaveBeenCalledWith(
      "/ui/login?return_to=%2Fui%2Faudit-log%3Fpage%3D2%26per-page%3D10",
    );
  });

  it("forwards AbortSignal and preserves AbortError", async () => {
    const abortError = new DOMException("Aborted", "AbortError");
    const fetchMock = vi.fn().mockRejectedValue(abortError);
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();

    await expect(apiRequest("/api/items", { signal: controller.signal })).rejects.toBe(abortError);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/items",
      expect.objectContaining({ signal: controller.signal }),
    );
  });

  it("supports native Blob responses without JSON parsing", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      response("inventory", { headers: { "Content-Type": "text/csv" } }),
    ));

    const downloaded = await apiRequest<Blob>("/export/ip-assets.csv", {
      responseMode: "blob",
    });
    expect(await downloaded.text()).toBe("inventory");
  });
});
