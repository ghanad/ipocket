import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  filtersFromSearch,
  RangeAddressesPage,
  searchFromFilters,
} from "./RangeAddressesPage";
import type { RangeAddressesResponse } from "./types";

const response: RangeAddressesResponse = {
  range: {
    id: 7,
    name: "Lab Range",
    cidr: "10.0.0.0/29",
    total_usable: 6,
    used: 1,
    free: 5,
  },
  filters: {
    projects: [{ id: 3, name: "Core", color: "#2563eb" }],
    tags: [
      { id: 1, name: "alpha", color: "#ef4444" },
      { id: 2, name: "beta", color: "#f59e0b" },
      { id: 3, name: "gamma", color: "#22c55e" },
      { id: 4, name: "delta", color: "#0ea5e9" },
    ],
    types: ["OS", "BMC", "VM", "VIP", "OTHER"],
    policy: { can_write: true },
  },
  addresses: [
    {
      ip_address: "10.0.0.1",
      status: "free",
      asset_id: null,
      project_id: null,
      project_name: null,
      project_color: "#94a3b8",
      project_unassigned: true,
      asset_type: null,
      host_pair: "",
      tags: [],
      notes: "",
      policy: { can_add: true, can_edit: false },
    },
    {
      ip_address: "10.0.0.2",
      status: "used",
      asset_id: 9,
      project_id: 3,
      project_name: "Core",
      project_color: "#2563eb",
      project_unassigned: false,
      asset_type: "BMC",
      host_pair: "10.0.0.3",
      tags: [
        { id: 1, name: "alpha", color: "#ef4444" },
        { id: 2, name: "beta", color: "#f59e0b" },
        { id: 3, name: "gamma", color: "#22c55e" },
        { id: 4, name: "delta", color: "#0ea5e9" },
      ],
      notes: "management",
      policy: { can_add: false, can_edit: true },
    },
  ],
  query: {
    q: "",
    project_id: "",
    type: "",
    tags: [],
    status: "all",
    page: 1,
    per_page: 20,
  },
  pagination: {
    page: 1,
    per_page: 20,
    total: 2,
    total_pages: 1,
    has_prev: false,
    has_next: false,
    start_index: 1,
    end_index: 2,
  },
};

function reply(payload: unknown = response, status = 200) {
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
  window.history.replaceState({}, "", "/ui/ranges/7/addresses");
});

describe("RangeAddressesPage", () => {
  it("renders metadata, used/free rows, pagination, and tag overflow", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply()));
    render(<RangeAddressesPage endpoint="/api/ui/ranges/7/addresses" />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading range addresses");
    expect(await screen.findByText("CIDR 10.0.0.0/29 • 1 used • 5 free")).toBeVisible();
    expect(screen.getByText("Usable total: 6", { exact: false })).toBeVisible();
    expect(screen.getByRole("link", { name: "10.0.0.2" })).toHaveAttribute(
      "href",
      "/ui/ip-assets/9",
    );
    expect(screen.getByText("10.0.0.3")).toBeVisible();
    expect(screen.getByText("Showing 1-2 of 2")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "+1 more" }));
    expect(screen.getByRole("dialog", { name: "Tags for 10.0.0.2" })).toBeVisible();
    fireEvent.change(screen.getByLabelText("Filter tags"), {
      target: { value: "delta" },
    });
    expect(screen.getByRole("button", { name: "delta" })).toBeVisible();
  });

  it("renders empty, error, and retry states", async () => {
    const empty = {
      ...response,
      addresses: [],
      pagination: { ...response.pagination, total: 0, start_index: 0, end_index: 0 },
    };
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(reply(empty));
    vi.stubGlobal("fetch", fetchMock);
    render(<RangeAddressesPage endpoint="/api/ui/ranges/7/addresses" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Range addresses could not be loaded",
    );
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("No addresses in this range.")).toBeVisible();
  });

  it("debounces trimmed search, ignores stale responses, syncs URL, and handles popstate", async () => {
    let resolveOld!: (value: ReturnType<typeof reply>) => void;
    const old = new Promise<ReturnType<typeof reply>>((resolve) => {
      resolveOld = resolve;
    });
    const fresh = {
      ...response,
      addresses: [{ ...response.addresses[1], ip_address: "10.0.0.8" }],
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(reply())
      .mockReturnValueOnce(old)
      .mockResolvedValueOnce(reply(fresh))
      .mockResolvedValue(reply());
    vi.stubGlobal("fetch", fetchMock);
    render(<RangeAddressesPage endpoint="/api/ui/ranges/7/addresses" />);
    await screen.findByText("10.0.0.2");

    fireEvent.change(screen.getByRole("searchbox"), {
      target: { value: " old " },
    });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2), { timeout: 1200 });
    fireEvent.change(screen.getByRole("searchbox"), {
      target: { value: " fresh " },
    });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3), { timeout: 1200 });
    expect(window.location.search).toContain("q=fresh");
    expect(await screen.findByText("10.0.0.8")).toBeVisible();
    resolveOld(reply({ ...response, addresses: [{ ...response.addresses[1], ip_address: "stale" }] }));
    await Promise.resolve();
    expect(screen.queryByText("stale")).not.toBeInTheDocument();

    window.history.pushState({}, "", "/ui/ranges/7/addresses?status=free&per-page=10");
    fireEvent.popState(window);
    await waitFor(() => expect(screen.getByLabelText("Status")).toHaveValue("free"));
    expect(filtersFromSearch(window.location.search).per_page).toBe(10);
  });

  it("supports all filters, quick tag filtering, hashes, and page reset", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply()));
    render(<RangeAddressesPage endpoint="/api/ui/ranges/7/addresses" />);
    await screen.findByText("10.0.0.2");

    fireEvent.click(screen.getByRole("button", { name: "alpha" }));
    await waitFor(() => expect(window.location.search).toContain("tag=alpha"));
    fireEvent.change(screen.getAllByLabelText("Project")[0], { target: { value: "3" } });
    fireEvent.change(screen.getByLabelText("Type filter"), { target: { value: "BMC" } });
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "used" } });
    expect(filtersFromSearch("", "#used").status).toBe("used");
    expect(filtersFromSearch("", "#free").status).toBe("free");
    expect(filtersFromSearch("?status=all", "#used").status).toBe("all");
    const combined = searchFromFilters({
      ...response.query,
      project_id: "3",
      type: "BMC",
      tags: ["alpha", "beta"],
      status: "used",
      page: 1,
      per_page: 10,
    });
    expect(combined).toContain("project_id=3");
    expect(combined).toContain("type=BMC");
    expect(combined).toContain("tag=alpha&tag=beta");
    expect(combined).toContain("status=used");
    expect(combined).toContain("per-page=10");
    expect(combined).not.toMatch(/(^|&)page=/);
  });

  it("canonicalizes legacy used and free hashes into status query parameters", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply()));
    window.history.replaceState({}, "", "/ui/ranges/7/addresses#used");

    const { unmount } = render(
      <RangeAddressesPage endpoint="/api/ui/ranges/7/addresses" />,
    );

    await waitFor(() => {
      expect(window.location.search).toBe("?status=used");
      expect(window.location.hash).toBe("");
    });
    unmount();

    window.history.replaceState({}, "", "/ui/ranges/7/addresses#free");
    render(<RangeAddressesPage endpoint="/api/ui/ranges/7/addresses" />);
    await waitFor(() => {
      expect(window.location.search).toBe("?status=free");
      expect(window.location.hash).toBe("");
    });
  });

  it("hides mutation controls for read-only policy", async () => {
    const readOnly = {
      ...response,
      filters: { ...response.filters, policy: { can_write: false } },
      addresses: response.addresses.map((row) => ({
        ...row,
        policy: { can_add: false, can_edit: false },
      })),
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(readOnly)));
    render(<RangeAddressesPage endpoint="/api/ui/ranges/7/addresses" />);
    await screen.findByText("10.0.0.2");
    expect(screen.queryByRole("button", { name: "Add…" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
  });

  it("handles add/edit success, validation, dirty close, and duplicate submits", async () => {
    Element.prototype.scrollIntoView = vi.fn();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(reply())
      .mockResolvedValueOnce(reply({ detail: ["IP address is already assigned."] }, 400))
      .mockResolvedValueOnce(reply({ asset_id: 10, ip_address: "10.0.0.1" }, 201))
      .mockResolvedValueOnce(reply())
      .mockResolvedValueOnce(reply({ detail: ["Selected project does not exist."] }, 400))
      .mockResolvedValueOnce(reply({ asset_id: 9, ip_address: "10.0.0.2" }))
      .mockResolvedValueOnce(reply());
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    render(<RangeAddressesPage endpoint="/api/ui/ranges/7/addresses" />);
    await screen.findByText("10.0.0.2");

    fireEvent.click(screen.getByRole("button", { name: "Add…" }));
    let dialog = screen.getByRole("dialog", { name: "Add IP asset" });
    fireEvent.change(within(dialog).getByLabelText("Type"), { target: { value: "VIP" } });
    const allocate = within(dialog).getByRole("button", { name: "Allocate" });
    fireEvent.click(allocate);
    fireEvent.click(allocate);
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "IP address is already assigned.",
    );
    expect(fetchMock).toHaveBeenCalledTimes(2);
    fireEvent.change(within(dialog).getByLabelText("Notes"), { target: { value: "allocate now" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Allocate" }));
    expect(await screen.findByText("IP asset created.")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    dialog = screen.getByRole("dialog", { name: "Edit IP asset" });
    fireEvent.change(within(dialog).getByLabelText("Project"), { target: { value: "" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(window.confirm).toHaveBeenCalledWith("Discard changes?");
    expect(dialog).toHaveClass("is-open");
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(dialog).not.toHaveClass("is-open");

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    dialog = screen.getByRole("dialog", { name: "Edit IP asset" });
    fireEvent.change(within(dialog).getByLabelText("Project"), { target: { value: "" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save changes" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "Selected project does not exist.",
    );
    fireEvent.change(within(dialog).getByLabelText("Notes"), { target: { value: "updated" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save changes" }));
    expect(await screen.findByText("IP asset updated.")).toBeVisible();
  });
});
