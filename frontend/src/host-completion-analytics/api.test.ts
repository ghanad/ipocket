import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchHostCompletionAnalytics } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("fetchHostCompletionAnalytics", () => {
  it("requests the configured endpoint", async () => {
    const payload = { total_hosts: 12, patterns: [] };
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify(payload)));
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchHostCompletionAnalytics("/custom/analytics")).resolves.toEqual(
      payload,
    );
    expect(fetchMock.mock.calls[0][0]).toBe("/custom/analytics");
  });

  it("propagates request errors", async () => {
    const offline = new TypeError("offline");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(offline));

    await expect(
      fetchHostCompletionAnalytics("/api/host-completion/analytics"),
    ).rejects.toBe(offline);
  });
});
