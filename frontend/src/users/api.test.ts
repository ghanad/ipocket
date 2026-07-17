import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, createUser, deleteUser, fetchUsers, updateUser } from "./api";

const policy = {
  can_edit_role: true,
  can_deactivate: true,
  can_delete: true,
  delete_disabled_reason: null,
};
const user = {
  id: 7,
  username: "operator",
  role: "Editor" as const,
  role_label: "Editor" as const,
  is_active: true,
  policy,
};

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function fetchCall(fetchMock: ReturnType<typeof vi.fn>) {
  return fetchMock.mock.calls[0] as [string, RequestInit];
}

describe("users API", () => {
  it("fetches the configured endpoint and maps the response", async () => {
    const payload = {
      actor: { id: 1, username: "admin", role: "Admin" as const },
      users: [user],
    };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(payload)));
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchUsers("/custom/users")).resolves.toEqual(payload);
    expect(fetchCall(fetchMock)[0]).toBe("/custom/users");
  });

  it("creates with POST and the exact boolean-preserving payload", async () => {
    const values = {
      username: "new-user",
      password: "create-value",
      can_edit: false,
      is_active: true,
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(user), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(createUser("/api/ui/users", values)).resolves.toEqual(user);
    const [url, init] = fetchCall(fetchMock);
    expect(url).toBe("/api/ui/users");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify(values));
  });

  it("updates the user URL with PATCH and preserves an empty password and booleans", async () => {
    const values = { password: "", can_edit: true, is_active: false };
    const payload = { user: { ...user, is_active: false }, changed: true };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(payload)));
    vi.stubGlobal("fetch", fetchMock);

    await expect(updateUser("/api/ui/users", 7, values)).resolves.toEqual(payload);
    const [url, init] = fetchCall(fetchMock);
    expect(url).toBe("/api/ui/users/7");
    expect(init.method).toBe("PATCH");
    expect(init.body).toBe(JSON.stringify(values));
  });

  it("deletes with the exact confirmation payload and handles 204", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(deleteUser("/api/ui/users", 7, "operator")).resolves.toBeUndefined();
    const [url, init] = fetchCall(fetchMock);
    expect(url).toBe("/api/ui/users/7");
    expect(init.method).toBe("DELETE");
    expect(init.body).toBe(JSON.stringify({ confirm_username: "operator" }));
  });

  it("preserves FastAPI string-detail errors and status", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Username already exists." }), { status: 409 }),
    ));

    await expect(fetchUsers("/api/ui/users")).rejects.toMatchObject({
      message: "Username already exists.",
      messages: ["Username already exists."],
      status: 409,
    });
  });

  it("preserves multiple validation messages and removes Value error prefixes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        detail: [
          { loc: ["body", "username"], msg: "Value error, Username is reserved." },
          { loc: ["body", "password"], msg: "Password is invalid." },
        ],
      }), { status: 422 }),
    ));

    const error = await fetchUsers("/api/ui/users").catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      message: "Username is reserved.",
      messages: ["Username is reserved.", "Password is invalid."],
      status: 422,
    });
  });

  it("uses the stable generic fallback for non-JSON errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response("Gateway unavailable", { status: 503 }),
    ));

    await expect(fetchUsers("/api/ui/users")).rejects.toMatchObject({
      message: "User request failed (503).",
      messages: ["User request failed (503)."],
      status: 503,
    });
  });

  it("navigates authentication to the fixed Users return target", async () => {
    const assign = vi.fn();
    vi.stubGlobal("window", {
      location: { pathname: "/ui/users", search: "?view=active", assign },
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      redirected: true,
      url: "http://testserver/ui/login?return_to=/api/ui/users",
      headers: new Headers(),
    } as Response));

    await expect(fetchUsers("/api/ui/users")).rejects.toMatchObject({
      message: "Authentication required.",
      messages: ["Authentication required."],
      status: 401,
    });
    expect(assign).toHaveBeenCalledWith("/ui/login?return_to=/ui/users");
  });

  it("propagates network errors unchanged", async () => {
    const offline = new TypeError("offline");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(offline));

    await expect(fetchUsers("/api/ui/users")).rejects.toBe(offline);
  });
});
