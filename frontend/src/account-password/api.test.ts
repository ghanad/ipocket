import { afterEach, describe, expect, it, vi } from "vitest";

import { AccountPasswordApiError, changePassword } from "./api";

const values = {
  current_password: "current-value",
  new_password: "new-value",
  confirm_new_password: "new-value",
};

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function fetchCall(fetchMock: ReturnType<typeof vi.fn>) {
  return fetchMock.mock.calls[0] as [string, RequestInit];
}

describe("account password API", () => {
  it("posts the exact JSON payload to the configured endpoint", async () => {
    const payload = { message: "Password changed successfully." };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload)),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(changePassword("/custom/password", values)).resolves.toEqual(payload);
    const [url, init] = fetchCall(fetchMock);
    const headers = new Headers(init.headers);
    expect(url).toBe("/custom/password");
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("same-origin");
    expect(headers.get("Accept")).toBe("application/json");
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(init.body).toBe(JSON.stringify(values));
  });

  it("preserves FastAPI string-detail errors and status", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Current password is incorrect." }), {
        status: 400,
      }),
    ));

    await expect(changePassword("/api/ui/account/password", values)).rejects.toMatchObject({
      messages: ["Current password is incorrect."],
      status: 400,
      loginUrl: null,
    });
  });

  it("preserves FastAPI string-array detail", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: ["First issue.", "Second issue."] }), {
        status: 422,
      }),
    ));

    await expect(changePassword("/api/ui/account/password", values)).rejects.toMatchObject({
      messages: ["First issue.", "Second issue."],
      status: 422,
    });
  });

  it("preserves every validation-object message and removes Value error prefixes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        detail: [
          { loc: ["body", "new_password"], msg: "Value error, Too short." },
          { loc: ["body", "confirm_new_password"], msg: "Confirmation is invalid." },
        ],
      }), { status: 422 }),
    ));

    const error = await changePassword("/api/ui/account/password", values).catch(
      (caught: unknown) => caught,
    );
    expect(error).toBeInstanceOf(AccountPasswordApiError);
    expect(error).toMatchObject({
      message: "Too short.",
      messages: ["Too short.", "Confirmation is invalid."],
      status: 422,
    });
  });

  it("uses the stable generic fallback for non-JSON errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response("Gateway unavailable", { status: 502 }),
    ));

    await expect(changePassword("/api/ui/account/password", values)).rejects.toMatchObject({
      message: "Password change request failed (502).",
      messages: ["Password change request failed (502)."],
      status: 502,
    });
  });

  it("maps network failures to the existing message and status zero", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));

    await expect(changePassword("/api/ui/account/password", values)).rejects.toMatchObject({
      message: "Password could not be changed. Please try again.",
      messages: ["Password could not be changed. Please try again."],
      status: 0,
      loginUrl: null,
    });
  });

  it("returns the fixed login URL without navigating directly", async () => {
    const assign = vi.fn();
    const redirectedResponse = {
      ok: true,
      status: 200,
      redirected: true,
      url: "http://testserver/ui/login?return_to=/api/ui/account/password",
      headers: new Headers(),
    } as Response;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(redirectedResponse));
    vi.stubGlobal("window", {
      location: {
        pathname: "/ui/account/password",
        search: "",
        assign,
      },
    });

    await expect(changePassword("/api/ui/account/password", values)).rejects.toMatchObject({
      message: "Authentication required.",
      messages: ["Authentication required."],
      status: 401,
      loginUrl: "/ui/login?return_to=/ui/account/password",
    });
    expect(assign).not.toHaveBeenCalled();
  });
});
