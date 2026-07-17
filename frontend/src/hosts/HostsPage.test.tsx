import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HostsPage } from "./HostsPage";
import type { HostsBootstrap, HostsResponse } from "./types";

const response: HostsResponse = {
  hosts: [
    {
      id: 7,
      name: "edge-01",
      notes: "rack-a",
      vendor: "Dell",
      project_count: 1,
      project_id: 3,
      project_name: "Core",
      project_color: "#2563eb",
      ip_count: 2,
      os_ip_links: [{ id: 10, ip_address: "10.0.0.10" }],
      bmc_ip_links: [{ id: 11, ip_address: "10.0.0.11" }],
      ip_tags: [
        { name: "alpha", color: "#ef4444" },
        { name: "beta", color: "#f59e0b" },
        { name: "gamma", color: "#22c55e" },
      ],
    },
  ],
  filters: {
    projects: [{ id: 3, name: "Core", color: "#2563eb" }],
    vendors: [{ id: 4, name: "Dell" }],
    tags: [
      { id: 1, name: "alpha", color: "#ef4444" },
      { id: 2, name: "beta", color: "#f59e0b" },
      { id: 3, name: "gamma", color: "#22c55e" },
    ],
  },
  pagination: { page: 1, per_page: 20, total: 1, total_pages: 1 },
  can_edit: true,
};

function reply(payload: unknown = response, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    redirected: false,
    headers: new Headers(),
    text: async () => JSON.stringify(payload),
  } as Response;
}

const ok = (payload: HostsResponse = response) => reply(payload);

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
  window.history.replaceState({}, "", "/ui/hosts");
});

describe("HostsPage", () => {
  it("renders loading, the host table, links, project, IPs, and collapsed tags", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(ok()));
    render(<HostsPage endpoint="/api/ui/hosts" />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading hosts");
    expect(await screen.findByRole("link", { name: "edge-01" })).toHaveAttribute(
      "href",
      "/ui/hosts/7",
    );
    expect(screen.getAllByText("Core").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "10.0.0.10" })).toHaveAttribute(
      "href",
      "/ui/ip-assets/10",
    );
    expect(screen.getByRole("link", { name: "10.0.0.11" })).toHaveAttribute(
      "href",
      "/ui/ip-assets/11",
    );
    expect(screen.getByRole("button", { name: "+1 more" })).toBeInTheDocument();
    const tableCard = screen.getByRole("table").closest(".table-card");
    expect(tableCard).toHaveTextContent("Showing 1–1 of 1");
    expect(
      screen.getByRole("navigation", { name: "Hosts pagination" }),
    ).toHaveTextContent("1 / 1");
    expect(screen.getByLabelText("Rows per page")).toHaveValue("20");
  });

  it("keeps the public hosts list read-only when can_edit is false", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(ok({ ...response, can_edit: false })),
    );

    render(<HostsPage endpoint="/api/ui/hosts" />);

    expect(await screen.findByRole("link", { name: "edge-01" })).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "New Host" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Edit" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Delete" }),
    ).not.toBeInTheDocument();
  });

  it("shows retryable errors and empty state", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(ok({ ...response, hosts: [], pagination: { ...response.pagination, total: 0 } }));
    vi.stubGlobal("fetch", fetchMock);
    render(<HostsPage endpoint="/api/ui/hosts" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Hosts could not be loaded",
    );
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("No hosts found.")).toBeInTheDocument();
  });

  it("debounces search, updates query string, and ignores stale responses", async () => {
    let resolveOld!: (value: ReturnType<typeof ok>) => void;
    const oldRequest = new Promise<ReturnType<typeof ok>>((resolve) => {
      resolveOld = resolve;
    });
    const fresh = {
      ...response,
      hosts: [{ ...response.hosts[0], name: "fresh-host" }],
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(ok())
      .mockReturnValueOnce(oldRequest)
      .mockResolvedValueOnce(ok(fresh));
    vi.stubGlobal("fetch", fetchMock);
    render(<HostsPage endpoint="/api/ui/hosts" />);
    await screen.findByText("edge-01");

    fireEvent.change(screen.getByRole("searchbox"), {
      target: { value: "old" },
    });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2), {
      timeout: 1000,
    });
    fireEvent.change(screen.getByRole("searchbox"), {
      target: { value: "fresh" },
    });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3), {
      timeout: 1000,
    });
    expect(window.location.search).toContain("q=fresh");
    expect(await screen.findByText("fresh-host")).toBeInTheDocument();

    resolveOld(ok({ ...response, hosts: [{ ...response.hosts[0], name: "stale-host" }] }));
    await Promise.resolve();
    expect(screen.queryByText("stale-host")).not.toBeInTheDocument();
  });

  it("anchors the tag popover to +more, opens on hover, filters, and closes with Escape", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(ok()));
    render(<HostsPage endpoint="/api/ui/hosts" />);
    await screen.findByText("edge-01");

    fireEvent.click(screen.getByRole("button", { name: "alpha" }));
    await waitFor(() => expect(window.location.search).toContain("tag=alpha"));

    const moreButton = screen.getByRole("button", { name: "+1 more" });
    moreButton.getBoundingClientRect = () =>
      ({
        top: 100,
        bottom: 120,
        left: 400,
        right: 460,
        width: 60,
        height: 20,
        x: 400,
        y: 100,
        toJSON: () => ({}),
      }) as DOMRect;
    fireEvent.mouseEnter(moreButton);
    const popover = await screen.findByRole("dialog", {
      name: /IP tags for edge-01/,
    });
    expect(popover).toHaveStyle({
      position: "fixed",
      top: "126px",
      left: "400px",
    });
    fireEvent.change(screen.getByRole("searchbox", { name: "Filter tags" }), {
      target: { value: "gamma" },
    });
    expect(within(popover).getByRole("button", { name: "gamma" })).toBeInTheDocument();
    expect(
      within(popover).queryByRole("button", { name: "beta" }),
    ).not.toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: /IP tags/ })).not.toBeInTheDocument();
  });

  it("uses the catalog color and current contrast for selected tag filters", async () => {
    const darkTagResponse: HostsResponse = {
      ...response,
      filters: {
        ...response.filters,
        tags: [
          ...response.filters.tags,
          { id: 4, name: "dark", color: "#111827" },
        ],
      },
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(ok(darkTagResponse)));

    render(
      <HostsPage endpoint="/api/ui/hosts" initialQuery="tag=dark" />,
    );

    const chip = await screen.findByRole("button", { name: "dark ×" });
    expect(chip.style.getPropertyValue("--tag-color")).toBe("#111827");
    expect(chip.style.getPropertyValue("--tag-color-text")).toBe("#f8fafc");
  });

  it.each([
    ["edit", "Edit Host"],
    ["delete", "Delete Host"],
  ] as const)(
    "opens the %s legacy drawer from bootstrap when the host is off-page",
    async (mode, dialogName) => {
      const target = {
        ...response.hosts[0],
        id: 42,
        name: "off-page-host",
      };
      const bootstrap: HostsBootstrap = { mode, host: target };
      const pageWithoutTarget = {
        ...response,
        hosts: [{ ...response.hosts[0], id: 7, name: "visible-host" }],
      };
      const fetchMock = vi.fn().mockResolvedValue(ok(pageWithoutTarget));
      vi.stubGlobal("fetch", fetchMock);
      window.history.replaceState(
        {},
        "",
        `/ui/hosts?${mode}=${target.id}&q=visible`,
      );

      render(
        <HostsPage
          endpoint="/api/ui/hosts"
          initialQuery={`${mode}=${target.id}&q=visible`}
          bootstrap={bootstrap}
        />,
      );

      const dialog = await screen.findByRole("dialog", { name: dialogName });
      await waitFor(() => expect(dialog).toHaveClass("is-open"));
      expect(dialog).toHaveTextContent("off-page-host");
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/ui/hosts?q=visible",
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      );
    },
  );

  it("creates and edits in the drawer while preserving validation errors", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(ok({ ...response, hosts: [], pagination: { ...response.pagination, total: 0 } }))
      .mockResolvedValueOnce(reply({ detail: "Invalid IP address (bad-ip)" }, 422))
      .mockResolvedValueOnce(reply({ id: 8, name: "node" }, 201))
      .mockResolvedValueOnce(ok())
      .mockResolvedValueOnce(reply({ id: 7, name: "edge-renamed" }))
      .mockResolvedValueOnce(ok());
    vi.stubGlobal("fetch", fetchMock);
    render(<HostsPage endpoint="/api/ui/hosts" />);
    await screen.findByText("No hosts found.");

    fireEvent.click(screen.getByRole("button", { name: "New Host" }));
    const add = screen.getByRole("dialog", { name: "Add Host" });
    fireEvent.change(screen.getByRole("textbox", { name: "Name" }), {
      target: { value: "node" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "OS IP" }), {
      target: { value: "bad-ip" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create Host" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid IP");
    expect(add).toHaveClass("is-open");

    fireEvent.change(screen.getByRole("textbox", { name: "OS IP" }), {
      target: { value: "10.0.0.20" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create Host" }));
    await screen.findByText("edge-01");
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Name" }), {
      target: { value: "edge-renamed" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(6));
  });

  it("requires delete acknowledgement and exact name, and confirms dirty close", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(ok()));
    const confirm = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    render(<HostsPage endpoint="/api/ui/hosts" />);
    await screen.findByText("edge-01");

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Name" }), {
      target: { value: "changed" },
    });
    fireEvent.keyDown(document, { key: "Escape" });
    expect(confirm).toHaveBeenCalledWith("Discard changes?");
    expect(screen.getByRole("dialog", { name: "Edit Host" })).toHaveClass("is-open");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    fireEvent.click(
      screen.getByRole("button", { name: "More actions for edge-01" }),
    );
    fireEvent.click(
      screen.getByRole("menuitem", { name: "Delete edge-01" }),
    );
    const deleteButton = screen.getByRole("button", { name: "Delete permanently" });
    expect(deleteButton).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.change(screen.getByRole("textbox", { name: /Type the host name/ }), {
      target: { value: "edge-01" },
    });
    expect(deleteButton).toBeEnabled();
  });

  it("keeps focus in Notes while the controlled edit form updates", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(ok()));
    render(<HostsPage endpoint="/api/ui/hosts" />);
    await screen.findByText("edge-01");

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    const notes = screen.getByRole("textbox", { name: "Notes" });
    notes.focus();
    fireEvent.change(notes, { target: { value: "f" } });

    expect(notes).toHaveFocus();
    fireEvent.change(notes, { target: { value: "first note" } });
    expect(notes).toHaveFocus();
    expect(notes).toHaveValue("first note");
    expect(screen.getByRole("textbox", { name: "Name" })).not.toHaveFocus();
  });
});
