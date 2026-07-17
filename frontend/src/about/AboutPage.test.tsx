import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AboutPage } from "./AboutPage";
import type { AboutData } from "./types";

const aboutData: AboutData = {
  application: { name: "ipocket" },
  build: {
    version: "2.4.1",
    commit: "abc1234",
    build_time: "2026-07-17T12:34:56Z",
  },
  links: {
    health: "/health",
    metrics: "/metrics",
  },
};

function successfulResponse(data: AboutData = aboutData) {
  return {
    ok: true,
    status: 200,
    redirected: false,
    url: "",
    headers: new Headers(),
    text: async () => JSON.stringify(data),
  };
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("AboutPage", () => {
  it("announces the loading state", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => undefined)));

    render(<AboutPage endpoint="/api/ui/about" />);

    expect(screen.getByRole("heading", { name: "About ipocket", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Loading About information");
  });

  it("renders accessible build metadata and operational links", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(successfulResponse()));

    render(<AboutPage endpoint="/api/ui/about" />);

    expect(await screen.findByText("2.4.1")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "About ipocket", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Build information", level: 2 })).toBeInTheDocument();
    expect(screen.getByText("Version").tagName).toBe("DT");
    expect(screen.getByText("Commit").tagName).toBe("DT");
    expect(screen.getByText("Build time").tagName).toBe("DT");
    expect(screen.getByText("abc1234")).toBeInTheDocument();
    expect(screen.getByText("2026-07-17T12:34:56Z")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Health" })).toHaveAttribute("href", "/health");
    expect(screen.getByRole("link", { name: "Prometheus Metrics" })).toHaveAttribute("href", "/metrics");
  });

  it("shows an accessible error when the API request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 }));

    render(<AboutPage endpoint="/api/ui/about" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "About information could not be loaded",
    );
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("retries after a failed request", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 503 })
      .mockResolvedValueOnce(successfulResponse());
    vi.stubGlobal("fetch", fetchMock);

    render(<AboutPage endpoint="/api/ui/about" />);
    fireEvent.click(await screen.findByRole("button", { name: "Try again" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("2.4.1")).toBeInTheDocument();
  });

  it("uses a safe unknown label for empty build values", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        successfulResponse({
          ...aboutData,
          build: { version: "", commit: "   ", build_time: "unknown" },
        }),
      ),
    );

    render(<AboutPage endpoint="/api/ui/about" />);

    expect(await screen.findAllByText("unknown")).toHaveLength(3);
  });

  it("preserves long metadata values without changing their content", async () => {
    const longVersion = `release-${"v".repeat(180)}`;
    const longCommit = "a".repeat(160);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        successfulResponse({
          ...aboutData,
          build: { ...aboutData.build, version: longVersion, commit: longCommit },
        }),
      ),
    );

    render(<AboutPage endpoint="/api/ui/about" />);

    const version = await screen.findByText(longVersion);
    const commit = screen.getByText(longCommit);
    expect(version).toHaveTextContent(longVersion);
    expect(commit).toHaveTextContent(longCommit);
    expect(version).toHaveClass("about-metadata-value");
    expect(commit).toHaveClass("about-metadata-value");
  });

  it("requests only the configured About endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(successfulResponse());
    vi.stubGlobal("fetch", fetchMock);

    render(<AboutPage endpoint="/custom/about" />);
    await screen.findByText("2.4.1");

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/custom/about");
    expect(init.credentials).toBe("same-origin");
    expect(new Headers(init.headers).get("Accept")).toBe("application/json");
  });
});
