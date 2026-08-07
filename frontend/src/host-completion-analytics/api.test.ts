import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchHostCompletionAnalytics } from "./api";

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("fetchHostCompletionAnalytics", () => {
  it("requests the configured reconciliation summary endpoint as same-origin JSON", async () => {
    const payload = { active_assets: 12, rules: [] };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(payload)));
    vi.stubGlobal("fetch", fetchMock);
    await expect(fetchHostCompletionAnalytics("/api/host-completion/summary")).resolves.toEqual(payload);
    expect(fetchMock).toHaveBeenCalledWith("/api/host-completion/summary", expect.objectContaining({ credentials: "same-origin" }));
  });

  it("propagates request errors", async () => {
    const offline = new TypeError("offline");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(offline));
    await expect(fetchHostCompletionAnalytics("/api/host-completion/summary")).rejects.toBe(offline);
  });
});
