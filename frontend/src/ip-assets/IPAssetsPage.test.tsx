import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { IPAssetsPage } from "./IPAssetsPage";
import type { AssetsResponse } from "./types";

const response: AssetsResponse = {
  assets: [
    {
      id: 7,
      ip_address: "10.0.0.7",
      type: "BMC",
      project_id: 3,
      project_name: "Core",
      project_color: "#2563eb",
      project_unassigned: false,
      host_id: "",
      host_name: "",
      tags: [
        { name: "alpha", color: "#ef4444" },
        { name: "beta", color: "#f59e0b" },
        { name: "gamma", color: "#22c55e" },
        { name: "delta", color: "#0ea5e9" },
      ],
      notes: "Primary management interface",
      unassigned: false,
      delete_requires_exact_ip: true,
      can_auto_host: true,
    },
  ],
  filters: {
    projects: [{ id: 3, name: "Core", color: "#2563eb" }],
    hosts: [{ id: 9, name: "node-01" }],
    tags: [
      { id: 1, name: "alpha", color: "#ef4444" },
      { id: 2, name: "beta", color: "#f59e0b" },
      { id: 3, name: "gamma", color: "#22c55e" },
      { id: 4, name: "delta", color: "#0ea5e9" },
    ],
    types: ["OS", "BMC", "VM", "VIP", "OTHER"],
    normalized: {
      q: "",
      project_id: "",
      type: "",
      unassigned_only: false,
      archived_only: false,
      tag_any: [],
      tag_all: [],
      tag_not: [],
      page: 1,
      per_page: 20,
    },
  },
  pagination: { page: 1, per_page: 20, total: 1, total_pages: 1 },
  can_edit: true,
};

function ok(payload: unknown = response, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    redirected: false,
    headers: new Headers(),
    json: async () => payload,
  };
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.history.replaceState({}, "", "/ui/ip-assets");
});

describe("IPAssetsPage", () => {
  it("renders loading, list content, links, notes, pagination, and viewer read-only state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        ok({ ...response, can_edit: false }),
      ),
    );
    render(<IPAssetsPage endpoint="/api/ui/ip-assets" />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading IP assets");
    expect(await screen.findByRole("link", { name: "10.0.0.7" })).toHaveAttribute(
      "href",
      "/ui/ip-assets/7",
    );
    expect(screen.getByTitle("Primary management interface")).toBeVisible();
    expect(screen.getByText("Showing 1-1 of 1")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Add IP" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Select 10.0.0.7")).not.toBeInTheDocument();
  });

  it("debounces trimmed search, ignores stale requests, syncs URL, and handles popstate", async () => {
    let resolveOld!: (value: ReturnType<typeof ok>) => void;
    const oldRequest = new Promise<ReturnType<typeof ok>>((resolve) => {
      resolveOld = resolve;
    });
    const fresh = {
      ...response,
      assets: [{ ...response.assets[0], ip_address: "10.0.0.8" }],
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(ok())
      .mockReturnValueOnce(oldRequest)
      .mockResolvedValueOnce(ok(fresh))
      .mockResolvedValue(ok(response));
    vi.stubGlobal("fetch", fetchMock);
    render(<IPAssetsPage endpoint="/api/ui/ip-assets" />);
    await screen.findByText("10.0.0.7");

    fireEvent.change(screen.getByRole("searchbox", { name: "Search" }), {
      target: { value: " old " },
    });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2), {
      timeout: 1200,
    });
    fireEvent.change(screen.getByRole("searchbox", { name: "Search" }), {
      target: { value: " fresh " },
    });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3), {
      timeout: 1200,
    });
    expect(window.location.search).toContain("q=fresh");
    expect(await screen.findByText("10.0.0.8")).toBeVisible();
    resolveOld(ok({ ...response, assets: [{ ...response.assets[0], ip_address: "stale" }] }));
    await Promise.resolve();
    expect(screen.queryByText("stale")).not.toBeInTheDocument();

    window.history.pushState({}, "", "/ui/ip-assets?type=VM&page=2");
    fireEvent.popState(window);
    await waitFor(() =>
      expect(screen.getByLabelText("Type filter")).toHaveValue("VM"),
    );
  });

  it("applies project, type, assignment, status, OR/AND/NOT tags, quick filters, and page size", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(ok()));
    render(<IPAssetsPage endpoint="/api/ui/ip-assets" />);
    await screen.findByText("10.0.0.7");

    fireEvent.change(screen.getAllByLabelText("Project")[0], { target: { value: "3" } });
    fireEvent.change(screen.getByLabelText("Type filter"), { target: { value: "BMC" } });
    fireEvent.change(screen.getByLabelText("Assignment"), { target: { value: "true" } });
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "true" } });
    await waitFor(() => {
      expect(window.location.search).toContain("project_id=3");
      expect(window.location.search).toContain("type=BMC");
      expect(window.location.search).toContain("unassigned-only=true");
      expect(window.location.search).toContain("archived-only=true");
    });

    const tagInput = screen.getByLabelText("Tag filter");
    fireEvent.change(tagInput, { target: { value: "alpha" } });
    fireEvent.submit(tagInput.closest("form")!);
    fireEvent.click(screen.getByRole("button", { name: "AND" }));
    fireEvent.change(tagInput, { target: { value: "beta" } });
    fireEvent.submit(tagInput.closest("form")!);
    fireEvent.click(screen.getByRole("button", { name: "NOT" }));
    fireEvent.change(tagInput, { target: { value: "gamma" } });
    fireEvent.submit(tagInput.closest("form")!);
    await waitFor(() => {
      expect(window.location.search).toContain("tag_any=alpha");
      expect(window.location.search).toContain("tag_all=beta");
      expect(window.location.search).toContain("tag_not=gamma");
    });

    fireEvent.click(screen.getByRole("button", { name: "Core" }));
    fireEvent.click(screen.getAllByRole("button", { name: "BMC" })[0]);
    fireEvent.change(screen.getByLabelText("Rows per page"), {
      target: { value: "50" },
    });
    await waitFor(() => expect(window.location.search).toContain("per-page=50"));
  });

  it("opens and searches the +N tag popover and applies its quick filter", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(ok()));
    render(<IPAssetsPage endpoint="/api/ui/ip-assets" />);
    await screen.findByText("10.0.0.7");

    fireEvent.click(screen.getByRole("button", { name: "+2 more" }));
    const popover = screen.getByRole("dialog", { name: "Tags for 10.0.0.7" });
    fireEvent.change(within(popover).getByLabelText("Filter tags"), {
      target: { value: "delta" },
    });
    expect(within(popover).getByRole("button", { name: "delta" })).toBeVisible();
    fireEvent.click(within(popover).getByRole("button", { name: "delta" }));
    await waitFor(() => expect(window.location.search).toContain("tag_any=delta"));
  });

  it("supports add and edit success/error flows plus auto-host", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(ok())
      .mockResolvedValueOnce(ok({ detail: ["IP address already exists."] }, 409))
      .mockResolvedValueOnce(ok({ asset_id: 8 }, 201))
      .mockResolvedValueOnce(ok())
      .mockResolvedValueOnce(ok())
      .mockResolvedValueOnce(ok())
      .mockResolvedValueOnce(ok({ host_id: 9, host_name: "node-01" }))
      .mockResolvedValueOnce(ok());
    vi.stubGlobal("fetch", fetchMock);
    render(<IPAssetsPage endpoint="/api/ui/ip-assets" />);
    await screen.findByText("10.0.0.7");

    fireEvent.click(screen.getByRole("button", { name: "Add IP" }));
    fireEvent.change(screen.getByLabelText("IP address"), {
      target: { value: "10.0.0.8" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "IP address already exists",
    );
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    expect(await screen.findByText("IP asset created.")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    const editDrawer = screen.getByRole("dialog", { name: "Edit IP asset" });
    fireEvent.change(within(editDrawer).getByLabelText("Project"), {
      target: { value: "" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByText("IP asset updated.")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    fireEvent.click(screen.getByRole("button", { name: "Create host" }));
    expect(await screen.findByText(/Created and assigned node-01/)).toBeVisible();
  });

  it("enforces high-risk delete confirmation and performs deletion", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce(ok())
        .mockResolvedValueOnce(ok(undefined, 204))
        .mockResolvedValueOnce(ok({ ...response, assets: [], pagination: { ...response.pagination, total: 0 } })),
    );
    render(<IPAssetsPage endpoint="/api/ui/ip-assets" />);
    await screen.findByText("10.0.0.7");
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    const drawer = screen.getByRole("dialog", { name: "Delete IP asset" });
    const deleteButton = within(drawer).getByRole("button", {
      name: "Delete permanently",
    });
    expect(deleteButton).toBeDisabled();
    fireEvent.click(within(drawer).getByText("I understand this cannot be undone"));
    fireEvent.change(within(drawer).getByLabelText(/High-risk asset/), {
      target: { value: "wrong" },
    });
    expect(deleteButton).toBeDisabled();
    fireEvent.change(within(drawer).getByLabelText(/High-risk asset/), {
      target: { value: "10.0.0.7" },
    });
    fireEvent.click(deleteButton);
    expect(await screen.findByText("IP asset deleted.")).toBeVisible();
  });

  it("selects the current page, computes common tags, validates bulk changes, and updates", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce(ok())
        .mockResolvedValueOnce(ok({ updated_count: 1 }))
        .mockResolvedValueOnce(ok()),
    );
    render(<IPAssetsPage endpoint="/api/ui/ip-assets" />);
    await screen.findByText("10.0.0.7");
    fireEvent.click(screen.getByLabelText("Select all IP assets"));
    expect(screen.getAllByText("1 selected").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Bulk update" }));
    const drawer = screen.getByRole("dialog", {
      name: "Bulk update IP assets",
    });
    expect(within(drawer).getByText("alpha")).toBeVisible();
    const submit = within(drawer).getByRole("button", {
      name: "Update selected",
    });
    expect(submit).toBeDisabled();
    fireEvent.change(within(drawer).getByLabelText("Bulk type"), {
      target: { value: "VM" },
    });
    fireEvent.click(submit);
    expect(await screen.findByText("Updated 1 IP assets.")).toBeVisible();
  });

  it("shows retryable API errors and the empty state", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(
        ok({
          ...response,
          assets: [],
          pagination: { ...response.pagination, total: 0 },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<IPAssetsPage endpoint="/api/ui/ip-assets" />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "IP assets could not be loaded",
    );
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("No IP assets found.")).toBeVisible();
  });
});
