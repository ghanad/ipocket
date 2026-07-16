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
import type { HostsResponse } from "./types";

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

function ok(payload: HostsResponse = response) {
  return {
    ok: true,
    status: 200,
    redirected: false,
    headers: new Headers(),
    json: async () => payload,
  };
}

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

  it("creates and edits in the drawer while preserving validation errors", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(ok({ ...response, hosts: [], pagination: { ...response.pagination, total: 0 } }))
      .mockResolvedValueOnce({
        ok: false,
        status: 422,
        redirected: false,
        headers: new Headers(),
        json: async () => ({ detail: "Invalid IP address (bad-ip)" }),
      })
      .mockResolvedValueOnce({ ok: true, status: 201, redirected: false, headers: new Headers(), json: async () => ({ id: 8, name: "node" }) })
      .mockResolvedValueOnce(ok())
      .mockResolvedValueOnce({ ok: true, status: 200, redirected: false, headers: new Headers(), json: async () => ({ id: 7, name: "edge-renamed" }) })
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

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
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
