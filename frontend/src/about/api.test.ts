import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../shared/apiClient";
import { fetchAboutData } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("fetchAboutData", () => {
  it("requests the configured endpoint and maps the response", async () => {
    const payload = { application: { name: "ipocket" }, build: {}, links: {} };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(payload)));
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchAboutData("/custom/about")).resolves.toEqual(payload);
    expect(fetchMock.mock.calls[0][0]).toBe("/custom/about");
  });

  it("propagates typed HTTP errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Unavailable" }), { status: 503 }),
    ));
    const error = await fetchAboutData("/api/ui/about").catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 503, message: "Unavailable" });
  });
});
