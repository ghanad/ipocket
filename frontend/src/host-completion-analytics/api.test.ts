import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchHostCompletionAnalytics, saveManualRule } from "./api";

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

  it("creates and updates a managed rule with JSON input", async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response("{}")));
    vi.stubGlobal("fetch", fetchMock);
    const input = { source_prefix: "10.10.0.0/16", target_prefix: "10.30.0.0/16", active: true, notes: null };
    await saveManualRule(input);
    await saveManualRule({ ...input, active: false }, 7);
    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/host-completion/rules", expect.objectContaining({ method: "POST", body: JSON.stringify(input) }));
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/host-completion/rules/7", expect.objectContaining({ method: "PUT", body: JSON.stringify({ ...input, active: false }) }));
  });
});
