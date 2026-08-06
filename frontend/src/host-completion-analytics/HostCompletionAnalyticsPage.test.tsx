import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HostCompletionAnalyticsPage } from "./HostCompletionAnalyticsPage";

const analytics = {
  total_hosts: 450,
  complete_hosts: 310,
  incomplete_hosts: 140,
  breakdown: { os_only: 120, bmc_only: 15, unlinked: 5 },
  confirmed_pairs: 310,
  patterns: [
    {
      source_prefix: "10.10.0.0/16",
      target_prefix: "10.30.0.0/16",
      support: 248,
      contradictions: 12,
      coverage_percent: 80,
    },
  ],
  ip_type_counts: { BMC: 310, OS: 380, VM: 85, unknown: 23 },
};

function jsonResponse(payload = analytics) {
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
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("HostCompletionAnalyticsPage", () => {
  it("shows loading before rendering all analytics sections", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse()));

    render(
      <HostCompletionAnalyticsPage endpoint="/api/host-completion/analytics" />,
    );

    expect(screen.getByText("Loading Host Completion analytics…")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Review hosts" })).toHaveAttribute(
      "href",
      "/host-completion/review",
    );
    expect(screen.queryByText("Auto-refreshes every 60 seconds")).not.toBeInTheDocument();
    expect(await screen.findByText("450 total hosts in inventory")).toBeInTheDocument();
    expect(
      screen.getByRole("img", {
        name: "310 complete hosts and 140 incomplete hosts",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", {
        name: "OS only 120, BMC only 15, unlinked 5",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("10.10.0.0/16")).toBeInTheDocument();
    expect(screen.getByText("10.30.0.0/16")).toBeInTheDocument();
    expect(screen.getByText("248")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(
      screen.getByRole("progressbar", {
        name: "10.10.0.0/16 to 10.30.0.0/16 confidence",
      }),
    ).toHaveAttribute("aria-valuenow", "80");
    expect(screen.getByRole("progressbar", { name: "OS addresses" })).toHaveAttribute(
      "aria-valuenow",
      "380",
    );
  });

  it("does not refresh analytics automatically", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse());
    vi.stubGlobal("fetch", fetchMock);

    render(
      <HostCompletionAnalyticsPage endpoint="/api/host-completion/analytics" />,
    );
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByText("450 total hosts in inventory")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("shows an empty pattern state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ ...analytics, patterns: [] })),
    );

    render(
      <HostCompletionAnalyticsPage endpoint="/api/host-completion/analytics" />,
    );

    expect(
      await screen.findByText(
        "No supported /16 replacement patterns have been discovered yet.",
      ),
    ).toBeInTheDocument();
  });

  it("shows an error and retries the request", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 500, text: async () => "" })
      .mockResolvedValueOnce(jsonResponse());
    vi.stubGlobal("fetch", fetchMock);

    render(
      <HostCompletionAnalyticsPage endpoint="/api/host-completion/analytics" />,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Host Completion analytics could not be loaded",
    );
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(await screen.findByText("450 total hosts in inventory")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
