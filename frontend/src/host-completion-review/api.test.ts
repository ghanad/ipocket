import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchHostCompletionReviewQueue, submitHostCompletionDecision } from "./api";

function jsonResponse(payload: unknown) {
  return { ok: true, status: 200, redirected: false, url: "", headers: new Headers(), text: async () => JSON.stringify(payload) };
}

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("host completion review API", () => {
  it("fetches the next reconciliation finding", async () => {
    const payload = { item: null, remaining: 0 };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(payload));
    vi.stubGlobal("fetch", fetchMock);
    await expect(fetchHostCompletionReviewQueue("/api/host-completion/findings/next")).resolves.toEqual(payload);
    expect(fetchMock).toHaveBeenCalledWith("/api/host-completion/findings/next", expect.objectContaining({ credentials: "same-origin" }));
  });

  it("posts the proposal identity with a deterministic Idempotency-Key", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ id: 12, decision: "ACCEPT" }));
    vi.stubGlobal("fetch", fetchMock);
    await submitHostCompletionDecision("/api/host-completion/findings/decisions", { proposal_id: "p-12", inventory_fingerprint: "f-12", decision: "ACCEPT" });

    const [, options] = fetchMock.mock.calls[0];
    expect(JSON.parse(options.body)).toEqual({ proposal_id: "p-12", inventory_fingerprint: "f-12", decision: "ACCEPT" });
    expect(options.headers).toBeInstanceOf(Headers);
    expect(options.headers.get("Idempotency-Key")).toBe("p-12:ACCEPT");
    expect(options.headers.get("Content-Type")).toBe("application/json");
  });
});
