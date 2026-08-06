import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchManagementOverview } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("fetchManagementOverview", () => {
  it("requests the configured endpoint and maps the response", async () => {
    const payload = { summary: { active_ip_total: 3 }, utilization: [] };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(payload)));
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchManagementOverview("/custom/overview")).resolves.toEqual(payload);
    expect(fetchMock.mock.calls[0][0]).toBe("/custom/overview");
  });

  it("propagates request errors", async () => {
    const offline = new TypeError("offline");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(offline));
    await expect(fetchManagementOverview("/api/management/overview")).rejects.toBe(offline);
  });
});
