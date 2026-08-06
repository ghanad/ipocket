import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchAuditLogs } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("fetchAuditLogs", () => {
  it("constructs the endpoint query string and maps the response", async () => {
    const payload = { audit_logs: [], pagination: {}, query: {} };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(payload)));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      fetchAuditLogs("/api/ui/audit-log", "page=2&per-page=50"),
    ).resolves.toEqual(payload);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/ui/audit-log?page=2&per-page=50");
  });

  it("does not add a question mark for an empty query", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({})));
    vi.stubGlobal("fetch", fetchMock);
    await fetchAuditLogs("/api/ui/audit-log");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/ui/audit-log");
  });

  it("propagates typed API errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Forbidden" }), { status: 403 }),
    ));
    await expect(fetchAuditLogs("/api/ui/audit-log")).rejects.toMatchObject({
      status: 403,
      message: "Forbidden",
    });
  });

  it("forwards cancellation and preserves AbortError", async () => {
    const abortError = new DOMException("Aborted", "AbortError");
    const fetchMock = vi.fn().mockRejectedValue(abortError);
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();

    await expect(
      fetchAuditLogs("/api/ui/audit-log", "page=2", controller.signal),
    ).rejects.toBe(abortError);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/ui/audit-log?page=2",
      expect.objectContaining({ signal: controller.signal }),
    );
  });
});
