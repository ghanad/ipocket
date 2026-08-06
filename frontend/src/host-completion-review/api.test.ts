import { afterEach, describe, expect, it, vi } from "vitest";

import {
  fetchHostCompletionReviewQueue,
  submitHostCompletionDecision,
} from "./api";

function jsonResponse(payload: unknown) {
  return {
    ok: true,
    status: 200,
    redirected: false,
    url: "",
    headers: new Headers(),
    text: async () => JSON.stringify(payload),
  };
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("host completion review API", () => {
  it("fetches the next queue item", async () => {
    const payload = { item: null, remaining: 0 };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(payload));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      fetchHostCompletionReviewQueue("/api/host-completion/review-queue"),
    ).resolves.toEqual(payload);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/host-completion/review-queue",
      expect.objectContaining({ credentials: "same-origin" }),
    );
  });

  it("posts a decision as JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ id: 12, decision: "ACCEPT", applied_ip: "10.30.1.4" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await submitHostCompletionDecision("/api/host-completion/decisions", {
      host_id: 4,
      mode: "SUGGEST",
      decision: "ACCEPT",
      candidate_ip: "10.30.1.4",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/host-completion/decisions",
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
        body: JSON.stringify({
          host_id: 4,
          mode: "SUGGEST",
          decision: "ACCEPT",
          candidate_ip: "10.30.1.4",
        }),
      }),
    );
  });
});
