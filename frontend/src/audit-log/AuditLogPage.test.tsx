import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuditLogPage } from "./AuditLogPage";
import type { AuditLogResponse } from "./types";

function response(
  page = 1,
  perPage = 20,
  total = 1,
  label = "10.0.0.1",
  username = "auditor",
): AuditLogResponse {
  return {
    audit_logs: total
      ? [
          {
            id: page,
            created_at: "2026-07-16 10:00:00",
            target_label: label,
            username,
            action: "CREATE",
            changes: "Type: VM",
          },
        ]
      : [],
    pagination: {
      page,
      per_page: perPage,
      total,
      total_pages: Math.max(1, Math.ceil(total / perPage)),
    },
    query: { page, per_page: perPage },
  };
}

function ok(payload: AuditLogResponse) {
  return {
    ok: true,
    status: 200,
    redirected: false,
    url: "",
    headers: new Headers(),
    json: async () => payload,
  };
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.history.replaceState({}, "", "/ui/audit-log");
});

describe("AuditLogPage", () => {
  it("renders loading and audit rows with the established action badge", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(ok(response())));

    render(<AuditLogPage endpoint="/api/ui/audit-log" />);

    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading audit history",
    );
    expect(await screen.findByText("10.0.0.1")).toBeVisible();
    expect(screen.getByText("auditor")).toBeVisible();
    expect(screen.getByText("Type: VM")).toBeVisible();
    expect(screen.getByText("CREATE")).toHaveClass("pill-success");
  });

  it("renders the System username fallback", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(ok(response(1, 20, 1, "system-task", ""))),
    );

    render(<AuditLogPage endpoint="/api/ui/audit-log" />);

    expect(await screen.findByText("System")).toBeVisible();
  });

  it("renders the empty state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(ok(response(1, 20, 0))),
    );

    render(<AuditLogPage endpoint="/api/ui/audit-log" />);

    expect(await screen.findByText("No audit history yet.")).toBeVisible();
    expect(
      screen.queryByRole("navigation", { name: "Audit log pagination" }),
    ).not.toBeInTheDocument();
  });

  it("shows an API error and retries", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(ok(response()));
    vi.stubGlobal("fetch", fetchMock);

    render(<AuditLogPage endpoint="/api/ui/audit-log" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Audit history could not be loaded",
    );
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("10.0.0.1")).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("navigates with Previous and Next and disables boundaries", async () => {
    const fetchMock = vi.fn((url: string) => {
      const page = Number(new URL(url, "http://test").searchParams.get("page") || 1);
      return Promise.resolve(ok(response(page, 10, 25, `page-${page}`)));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <AuditLogPage
        endpoint="/api/ui/audit-log"
        initialQuery="page=2&per-page=10"
      />,
    );

    expect(await screen.findByText("page-2")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Previous" }));
    expect(await screen.findByText("page-1")).toBeVisible();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByText("page-2")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByText("page-3")).toBeVisible();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  it("resets to page 1 when rows per page changes and synchronizes the URL", async () => {
    const fetchMock = vi.fn((url: string) => {
      const parsed = new URL(url, "http://test");
      const page = Number(parsed.searchParams.get("page") || 1);
      const perPage = Number(parsed.searchParams.get("per-page") || 20);
      return Promise.resolve(ok(response(page, perPage, 120)));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <AuditLogPage
        endpoint="/api/ui/audit-log"
        initialQuery="page=3"
      />,
    );
    await screen.findByText("Page 3 of 6");

    fireEvent.change(screen.getByLabelText("Rows per page"), {
      target: { value: "50" },
    });

    expect(await screen.findByText("Page 1 of 3")).toBeVisible();
    await waitFor(() => {
      expect(window.location.search).toBe("?per-page=50");
    });
  });

  it("restores pagination from popstate navigation", async () => {
    const fetchMock = vi.fn((url: string) => {
      const parsed = new URL(url, "http://test");
      const page = Number(parsed.searchParams.get("page") || 1);
      const perPage = Number(parsed.searchParams.get("per-page") || 20);
      return Promise.resolve(
        ok(response(page, perPage, 60, `history-${page}-${perPage}`)),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<AuditLogPage endpoint="/api/ui/audit-log" />);
    await screen.findByText("history-1-20");

    window.history.pushState(
      {},
      "",
      "/ui/audit-log?page=2&per-page=10",
    );
    fireEvent.popState(window);

    expect(await screen.findByText("history-2-10")).toBeVisible();
    expect(screen.getByLabelText("Rows per page")).toHaveValue("10");
    expect(screen.getByText("Page 2 of 6")).toBeVisible();
  });

  it("ignores stale responses after newer navigation", async () => {
    let resolveStale!: (value: ReturnType<typeof ok>) => void;
    const stale = new Promise<ReturnType<typeof ok>>((resolve) => {
      resolveStale = resolve;
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(ok(response(1, 20, 60, "initial")))
      .mockReturnValueOnce(stale)
      .mockResolvedValueOnce(ok(response(3, 20, 60, "fresh")));
    vi.stubGlobal("fetch", fetchMock);

    render(<AuditLogPage endpoint="/api/ui/audit-log" />);
    await screen.findByText("initial");

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    window.history.pushState({}, "", "/ui/audit-log?page=3");
    fireEvent.popState(window);

    expect(await screen.findByText("fresh")).toBeVisible();
    resolveStale(ok(response(2, 20, 60, "stale")));
    await Promise.resolve();
    expect(screen.queryByText("stale")).not.toBeInTheDocument();
    expect(screen.getByText("fresh")).toBeVisible();
  });
});
