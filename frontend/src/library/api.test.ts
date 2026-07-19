import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  createLibraryItem,
  deleteLibraryItem,
  fetchLibraryItems,
  updateLibraryItem,
} from "./api";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function fetchCall(fetchMock: ReturnType<typeof vi.fn>) {
  return fetchMock.mock.calls[0] as [string, RequestInit];
}

describe("library API", () => {
  it.each(["projects", "tags", "vendors"])(
    "fetches and maps the %s response from the exact endpoint",
    async (entity) => {
      const payload = { items: [{ id: 7, name: entity }], can_edit: true };
      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(payload)),
      );
      vi.stubGlobal("fetch", fetchMock);

      await expect(
        fetchLibraryItems<{ id: number; name: string }>("/api/ui/library", entity),
      ).resolves.toEqual(payload);
      const [url, init] = fetchCall(fetchMock);
      expect(url).toBe(`/api/ui/library/${entity}`);
      expect(init.credentials).toBe("same-origin");
    },
  );

  it("creates with POST and serializes the generic values without modification", async () => {
    const values = { name: "Core", description: null, color: "#123abc" };
    const result = { id: 7, ...values, usage_count: 0 };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(result), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      createLibraryItem<typeof result, typeof values>(
        "/api/ui/library",
        "projects",
        values,
      ),
    ).resolves.toEqual(result);
    const [url, init] = fetchCall(fetchMock);
    expect(url).toBe("/api/ui/library/projects");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify(values));
  });

  it("updates the entity URL with PATCH and the exact generic payload", async () => {
    const values = { name: "production", color: "#22c55e" };
    const result = { id: 4, ...values, usage_count: 3 };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(result)),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      updateLibraryItem<typeof result, typeof values>(
        "/api/ui/library",
        "tags",
        4,
        values,
      ),
    ).resolves.toEqual(result);
    const [url, init] = fetchCall(fetchMock);
    expect(url).toBe("/api/ui/library/tags/4");
    expect(init.method).toBe("PATCH");
    expect(init.body).toBe(JSON.stringify(values));
  });

  it("deletes with the exact confirmation payload and accepts 204", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      deleteLibraryItem("/api/ui/library", "vendors", 9, "Exact Vendor"),
    ).resolves.toBeUndefined();
    const [url, init] = fetchCall(fetchMock);
    expect(url).toBe("/api/ui/library/vendors/9");
    expect(init.method).toBe("DELETE");
    expect(init.body).toBe(JSON.stringify({ confirm_name: "Exact Vendor" }));
  });

  it("preserves FastAPI string-detail errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Project already exists." }), { status: 409 }),
    ));

    await expect(fetchLibraryItems("/api/ui/library", "projects")).rejects.toMatchObject({
      message: "Project already exists.",
      messages: ["Project already exists."],
    });
  });

  it("preserves every validation message and removes Value error prefixes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        detail: [
          { loc: ["body", "name"], msg: "Value error, Name is reserved" },
          { loc: ["body", "color"], msg: "Value error, Color is invalid" },
        ],
      }), { status: 422 }),
    ));

    const error = await fetchLibraryItems("/api/ui/library", "tags").catch(
      (caught: unknown) => caught,
    );
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      message: "Name is reserved",
      messages: ["Name is reserved", "Color is invalid"],
    });
  });

  it.each([
    ["JSON without detail", JSON.stringify({ error: "bad gateway" })],
    ["a non-JSON response", "Gateway unavailable"],
  ])("uses the stable fallback for %s", async (_label, body) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(body, { status: 502 }),
    ));

    await expect(fetchLibraryItems("/api/ui/library", "vendors")).rejects.toMatchObject({
      message: "Library request failed (502)",
      messages: ["Library request failed (502)"],
    });
  });

  it("redirects authentication with the exact encoded pathname and query", async () => {
    const assign = vi.fn();
    vi.stubGlobal("window", {
      location: { pathname: "/ui/projects", search: "?tab=tags", assign },
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      redirected: true,
      url: "http://testserver/ui/login?return_to=/api/ui/library/tags",
      headers: new Headers(),
    } as Response));

    await expect(fetchLibraryItems("/api/ui/library", "tags")).rejects.toMatchObject({
      message: "Authentication required.",
      messages: ["Authentication required."],
    });
    expect(assign).toHaveBeenCalledWith(
      "/ui/login?return_to=%2Fui%2Fprojects%3Ftab%3Dtags",
    );
  });

  it("propagates network errors unchanged", async () => {
    const offline = new TypeError("offline");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(offline));

    await expect(fetchLibraryItems("/api/ui/library", "projects")).rejects.toBe(offline);
  });
});
