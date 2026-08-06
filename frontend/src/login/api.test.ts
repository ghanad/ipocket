import { afterEach, describe, expect, it, vi } from "vitest";

import { LoginApiError, login } from "./api";

const GENERIC_REQUEST_ERROR = "Login could not be completed. Please try again.";
const endpoint = "/api/ui/login";
const values = {
  username: "viewer",
  password: "viewer-pass",
  return_to: "/ui/ip-assets",
};

function response(body: BodyInit | null, init: ResponseInit = {}): Response {
  return new Response(body, { status: 200, ...init });
}

function jsonResponse(payload: unknown, status = 200): Response {
  return response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.history.replaceState({}, "", "/");
});

describe("login", () => {
  it("uses the exact same-origin JSON login request contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ redirect_to: "/ui/ip-assets" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(login(endpoint, values)).resolves.toEqual({
      redirect_to: "/ui/ip-assets",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      endpoint,
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
        body: JSON.stringify(values),
      }),
    );
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = new Headers(init.headers);
    expect(headers.get("Accept")).toBe("application/json");
    expect(headers.get("Content-Type")).toBe("application/json");
  });

  it.each([
    "/ui/audit-log",
    "/ui/audit-log?scope=recent#top",
  ])("maps a safe server-approved redirect: %s", async (redirect_to) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ redirect_to })));

    await expect(login(endpoint, values)).resolves.toEqual({ redirect_to });
  });

  it.each([
    "//external.example/path",
    "https://external.example/path",
    "/\\external.example/path",
    "/ui/ip-assets\u0000",
    "/ui/ip-assets\u0085",
  ])("rejects an unsafe redirect_to %s", async (redirect_to) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ redirect_to }, 207)));

    await expect(login(endpoint, values)).rejects.toMatchObject({
      name: "Error",
      message: GENERIC_REQUEST_ERROR,
      status: 207,
    });
  });

  it.each([
    ["empty", response(null, { status: 204 })],
    ["malformed", response("{not-json", { status: 201 })],
    ["unknown", jsonResponse({ destination: "/ui/ip-assets" }, 202)],
  ])("uses the generic error for an %s successful response", async (_label, result) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(result));

    await expect(login(endpoint, values)).rejects.toMatchObject({
      message: GENERIC_REQUEST_ERROR,
      status: result.status,
    });
  });

  it("preserves an exact string detail and status for non-2xx JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({ detail: "Invalid username or password." }, 401),
      ),
    );

    await expect(login(endpoint, values)).rejects.toMatchObject({
      message: "Invalid username or password.",
      status: 401,
    });
  });

  it("sanitizes unknown JSON non-2xx payloads", async () => {
    const body = JSON.stringify({ internal: "database password", values });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(body, { status: 400 })));

    const error = await login(endpoint, values).catch((caught: unknown) => caught);
    expect(error).toMatchObject({
      message: GENERIC_REQUEST_ERROR,
      status: 400,
    });
    expect(error).toBeInstanceOf(LoginApiError);
    expect(String(error)).not.toContain(body);
    expect(String(error)).not.toContain(values.username);
    expect(String(error)).not.toContain(values.password);
  });

  it.each([
    ["malformed", "{not-json"],
    ["HTML", "<html>upstream failure</html>"],
    ["plain text", "upstream failure"],
    ["empty", ""],
  ])("sanitizes %s non-2xx responses", async (_label, body) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(body, { status: 502 })));

    const error = await login(endpoint, values).catch((caught: unknown) => caught);
    expect(error).toMatchObject({
      message: GENERIC_REQUEST_ERROR,
      status: 502,
    });
    if (body) expect(String(error)).not.toContain(body);
  });

  it("sanitizes network failures and does not expose submitted credentials", async () => {
    const rawError = `offline ${values.username} ${values.password} ${values.return_to}`;
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error(rawError)));

    const error = await login(endpoint, values).catch((caught: unknown) => caught);
    expect(error).toMatchObject({
      message: GENERIC_REQUEST_ERROR,
      status: 0,
    });
    expect(String(error)).not.toContain(rawError);
    expect(String(error)).not.toContain(values.username);
    expect(String(error)).not.toContain(values.password);
    expect(String(error)).not.toContain(values.return_to);
  });

  it("does not navigate when the shared client detects a login redirect", async () => {
    const originalWindow = window;
    const navigate = vi.fn();
    vi.stubGlobal("window", {
      ...originalWindow,
      location: {
        ...originalWindow.location,
        assign: navigate,
      },
      history: originalWindow.history,
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        redirected: true,
        url: "http://localhost/ui/login?return_to=/api/ui/login",
        headers: new Headers(),
      } as Response),
    );

    await expect(login(endpoint, values)).rejects.toMatchObject({
      message: GENERIC_REQUEST_ERROR,
      status: 401,
    });
    expect(navigate).not.toHaveBeenCalled();
  });

  it("exposes LoginApiError as the public error type", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

    const error = await login(endpoint, values).catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(LoginApiError);
    expect(error).toMatchObject({
      message: GENERIC_REQUEST_ERROR,
      status: 0,
    });
  });
});
