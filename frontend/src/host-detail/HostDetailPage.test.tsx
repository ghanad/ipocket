import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HostDetailPage } from "./HostDetailPage";
import type { HostDetailResponse } from "./types";

const response: HostDetailResponse = {
  host: {
    id: 7,
    name: "compute-08",
    vendor: "Supermicro",
    notes: "rack 4",
  },
  summary: {
    linked_count: 3,
    os_count: 1,
    bmc_count: 1,
    other_count: 1,
  },
  groups: {
    os: [
      {
        id: 10,
        ip_address: "10.80.0.8",
        type: "OS",
        project: { name: "Compute", color: "#0f766e" },
        tags: [{ name: "prod", color: "#111827" }],
        notes: "primary",
      },
    ],
    bmc: [
      {
        id: 11,
        ip_address: "10.80.1.8",
        type: "BMC",
        project: null,
        tags: [],
        notes: "—",
      },
    ],
    other: [
      {
        id: 12,
        ip_address: "10.80.2.8",
        type: "VIP",
        project: { name: "Compute", color: "#0f766e" },
        tags: [{ name: "service", color: "#fef08a" }],
        notes: "frontend",
      },
    ],
  },
};

function jsonResponse(payload: HostDetailResponse, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  };
}

function loginRedirect() {
  return {
    ok: true,
    status: 200,
    redirected: true,
    url: "http://testserver/ui/login?return_to=/api/ui/hosts/7/detail",
    headers: new Headers(),
    json: async () => null,
  };
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("HostDetailPage", () => {
  it("returns authentication redirects to the login flow", async () => {
    const onAuthenticationRequired = vi.fn();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(loginRedirect()));
    window.history.replaceState({}, "", "/ui/hosts/7");

    render(
      <HostDetailPage
        endpoint="/api/ui/hosts/7/detail"
        onAuthenticationRequired={onAuthenticationRequired}
      />,
    );

    await waitFor(() =>
      expect(onAuthenticationRequired).toHaveBeenCalledWith(
        "/ui/login?return_to=%2Fui%2Fhosts%2F7",
      ),
    );
  });

  it("renders loading, header, details, all asset tables, links, colors, and fallbacks", async () => {
    let resolveRequest!: (value: ReturnType<typeof jsonResponse>) => void;
    const pending = new Promise<ReturnType<typeof jsonResponse>>((resolve) => {
      resolveRequest = resolve;
    });
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(pending));

    render(<HostDetailPage endpoint="/api/ui/hosts/7/detail" />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading host details");

    resolveRequest(jsonResponse(response));

    expect(await screen.findByRole("heading", { name: "compute-08" })).toBeVisible();
    expect(screen.getByText("Vendor: Supermicro")).toBeVisible();
    expect(screen.getByText("Status: 3 linked IPs")).toBeVisible();
    expect(screen.getByText("OS: 1")).toBeVisible();
    expect(screen.getByText("BMC: 1")).toBeVisible();
    expect(screen.getByRole("link", { name: "Back to hosts" })).toHaveAttribute(
      "href",
      "/ui/hosts",
    );

    const details = screen.getByRole("heading", { name: "Details" }).closest("section");
    expect(details).toHaveTextContent("compute-08");
    expect(details).toHaveTextContent("Supermicro");
    expect(details).toHaveTextContent("rack 4");
    expect(details).toHaveTextContent("3");
    expect(details).toHaveTextContent("1 / 1");

    const osTable = screen.getByRole("table", { name: "OS IPs" });
    expect(within(osTable).getByRole("link", { name: "10.80.0.8" })).toHaveAttribute(
      "href",
      "/ui/ip-assets/10",
    );
    const project = within(osTable).getByText("Compute");
    expect(project.style.getPropertyValue("--project-color")).toBe("#0f766e");
    const darkTag = within(osTable).getByText("prod");
    expect(darkTag.style.getPropertyValue("--tag-color")).toBe("#111827");
    expect(darkTag.style.getPropertyValue("--tag-color-text")).toBe("#f8fafc");

    const bmcTable = screen.getByRole("table", { name: "BMC IPs" });
    expect(within(bmcTable).getByRole("link", { name: "10.80.1.8" })).toHaveAttribute(
      "href",
      "/ui/ip-assets/11",
    );
    expect(within(bmcTable).getByText("Unassigned")).toBeVisible();
    expect(within(bmcTable).getByText("No tags")).toBeVisible();
    expect(within(bmcTable).getByText("—")).toBeVisible();

    const otherTable = screen.getByRole("table", { name: "Other linked IPs" });
    expect(within(otherTable).getByText("VIP")).toBeVisible();
    expect(within(otherTable).getByRole("link", { name: "10.80.2.8" })).toHaveAttribute(
      "href",
      "/ui/ip-assets/12",
    );
    const lightTag = within(otherTable).getByText("service");
    expect(lightTag.style.getPropertyValue("--tag-color-text")).toBe("#0f172a");
  });

  it("shows retryable errors, then empty groups and hides Other", async () => {
    const empty: HostDetailResponse = {
      host: { id: 8, name: "empty-host", vendor: "Unassigned", notes: "No notes" },
      summary: { linked_count: 0, os_count: 0, bmc_count: 0, other_count: 0 },
      groups: { os: [], bmc: [], other: [] },
    };
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(jsonResponse(empty));
    vi.stubGlobal("fetch", fetchMock);

    render(<HostDetailPage endpoint="/api/ui/hosts/8/detail" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Host details could not be loaded",
    );
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(await screen.findByText("Status: No linked IPs")).toBeVisible();
    expect(screen.getByText("No notes")).toBeVisible();
    expect(screen.getByText("No OS IPs linked.")).toBeVisible();
    expect(screen.getByText("No BMC IPs linked.")).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "Other linked IPs" }),
    ).not.toBeInTheDocument();
  });

  it("renders a dedicated not-found state for a 404", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 404, json: async () => ({}) }),
    );

    render(<HostDetailPage endpoint="/api/ui/hosts/999/detail" />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Host not found");
    expect(screen.getByRole("link", { name: "Back to hosts" })).toHaveAttribute(
      "href",
      "/ui/hosts",
    );
  });
});
