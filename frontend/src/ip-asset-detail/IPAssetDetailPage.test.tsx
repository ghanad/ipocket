import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { IPAssetDetailPage } from "./IPAssetDetailPage";
import type { DetailResponse } from "./types";

const response: DetailResponse = {
  asset: {
    id: 7,
    ip_address: "10.0.0.7",
    type: "OS",
    project_id: 2,
    project_name: "Core",
    project_color: "#ffffff",
    project_unassigned: false,
    host_id: 3,
    host_name: "node-1",
    tags: [{ name: "prod", color: "#ffffff" }],
    notes: "Primary address",
    unassigned: false,
    host_pair_assets: [{ id: 8, ip_address: "10.0.0.8" }],
  },
  audit_logs: [
    {
      created_at: "2026-07-16 10:00:00",
      user: "System",
      action: "CREATE",
      changes: {
        summary: "Type: OS; Project ID: 2",
        raw: "Created IP asset (type=OS, project_id=2)",
      },
    },
  ],
  metadata: {
    projects: [
      { id: 2, name: "Core", color: "#ffffff" },
      { id: 4, name: "Edge", color: "#000000" },
    ],
    hosts: [
      { id: 3, name: "node-1" },
      { id: 5, name: "edge-node" },
    ],
    tags: [
      { id: 1, name: "prod", color: "#ffffff" },
      { id: 2, name: "edge", color: "#000000" },
    ],
    types: ["OS", "BMC", "VM", "VIP", "OTHER"],
  },
  can_edit: true,
  delete_requires_exact_ip: true,
  auto_host_enabled: true,
  can_auto_host: false,
};

function ok(payload: DetailResponse = response) {
  return {
    ok: true,
    status: 200,
    redirected: false,
    headers: new Headers(),
    text: async () => JSON.stringify(payload),
    json: async () => payload,
  };
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("IPAssetDetailPage", () => {
  it("renders loading, header metadata, details, colors, pair links, and audit raw details", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(ok()));
    render(<IPAssetDetailPage endpoint="/api/ui/ip-assets/7" />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading IP asset details");
    expect(await screen.findByRole("heading", { name: "10.0.0.7" })).toBeInTheDocument();
    expect(screen.getByText("Project: Core")).toHaveStyle(
      "--tag-color: #ffffff; --tag-color-text: #0f172a",
    );
    expect(screen.getAllByText("prod")[0]).toHaveStyle(
      "--tag-color: #ffffff; --tag-color-text: #0f172a",
    );
    expect(screen.getByRole("link", { name: "node-1" })).toHaveAttribute(
      "href",
      "/ui/hosts/3",
    );
    expect(screen.getByRole("link", { name: "10.0.0.8" })).toHaveAttribute(
      "href",
      "/ui/ip-assets/8",
    );
    expect(screen.getByText("System")).toBeInTheDocument();
    fireEvent.click(screen.getByText("View details"));
    expect(
      screen.getByText("Created IP asset (type=OS, project_id=2)"),
    ).toBeInTheDocument();
  });

  it("renders viewer mode and empty fallbacks without mutation actions", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        ok({
          ...response,
          can_edit: false,
          asset: {
            ...response.asset,
            type: "VM",
            project_id: "",
            project_name: "",
            project_color: null,
            project_unassigned: true,
            host_id: "",
            host_name: "",
            tags: [],
            notes: "",
            unassigned: true,
            host_pair_assets: [],
          },
          audit_logs: [],
        }),
      ),
    );
    render(<IPAssetDetailPage endpoint="/api/ui/ip-assets/7" />);

    await screen.findByText("Project: Unassigned");
    expect(screen.getAllByText("No tags")).toHaveLength(1);
    expect(screen.getByText("No notes")).toBeInTheDocument();
    expect(screen.getByText("No audit history yet.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByText("BMC address")).not.toBeInTheDocument();
  });

  it("edits with searchable hosts, clears assignment, and supports tag keyboard controls", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(ok())
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        redirected: false,
        headers: new Headers(),
        text: async () => JSON.stringify({ message: "updated" }),
        json: async () => ({ message: "updated" }),
      })
      .mockResolvedValueOnce(
        ok({
          ...response,
          asset: {
            ...response.asset,
            type: "VM",
            project_id: "",
            project_name: "",
            project_unassigned: true,
            host_id: "",
            host_name: "",
            tags: [{ name: "edge", color: "#000000" }],
          },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<IPAssetDetailPage endpoint="/api/ui/ip-assets/7" />);

    await screen.findByRole("button", { name: "Edit" });
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    const dialog = screen.getByRole("dialog", { name: "Edit IP asset" });
    fireEvent.change(within(dialog).getByLabelText("Search hosts"), {
      target: { value: "edge" },
    });
    expect(within(dialog).getByRole("option", { name: "edge-node" })).toBeInTheDocument();
    fireEvent.change(within(dialog).getByLabelText("Project"), {
      target: { value: "" },
    });
    fireEvent.change(within(dialog).getByLabelText("Type"), {
      target: { value: "VM" },
    });
    expect(within(dialog).queryByLabelText("Host")).not.toBeInTheDocument();
    const tagSearch = within(dialog).getByLabelText("Search tags");
    fireEvent.change(tagSearch, { target: { value: "edge" } });
    fireEvent.keyDown(tagSearch, { key: "Enter" });
    expect(within(dialog).getByRole("button", { name: "Remove edge" })).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/ui/ip-assets/7",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({
          type: "VM",
          project_id: null,
          host_id: null,
          tags: ["prod", "edge"],
          notes: "Primary address",
        }),
      }),
    );
  });

  it("confirms dirty close and exposes auto-host only for an unassigned BMC", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        ok({
          ...response,
          asset: {
            ...response.asset,
            type: "BMC",
            host_id: "",
            host_name: "",
          },
          can_auto_host: true,
        }),
      ),
    );
    render(<IPAssetDetailPage endpoint="/api/ui/ip-assets/7" />);

    await screen.findByRole("button", { name: "Edit" });
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    const dialog = screen.getByRole("dialog", { name: "Edit IP asset" });
    expect(within(dialog).getByRole("button", { name: "Create host" })).toBeInTheDocument();
    fireEvent.change(within(dialog).getByLabelText("Project"), {
      target: { value: "4" },
    });
    fireEvent.keyDown(document, { key: "Escape" });
    expect(confirm).toHaveBeenCalledWith("Discard changes?");
    expect(screen.getByRole("dialog", { name: "Edit IP asset" })).toBeInTheDocument();
  });

  it("shows retryable load errors and delete high-risk confirmation", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        redirected: false,
        headers: new Headers(),
        text: async () => JSON.stringify({ detail: "failed" }),
        json: async () => ({ detail: "failed" }),
      })
      .mockResolvedValueOnce(ok());
    vi.stubGlobal("fetch", fetchMock);
    render(<IPAssetDetailPage endpoint="/api/ui/ip-assets/7" />);

    expect(
      await screen.findByText("IP asset details could not be loaded. Please try again."),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByRole("button", { name: "Delete" });
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    const dialog = screen.getByRole("dialog", { name: "Delete IP asset" });
    const deleteButton = within(dialog).getByRole("button", {
      name: "Delete permanently",
    });
    expect(deleteButton).toBeDisabled();
    fireEvent.click(within(dialog).getByRole("checkbox"));
    fireEvent.change(within(dialog).getByRole("textbox"), {
      target: { value: "10.0.0.7" },
    });
    expect(deleteButton).toBeEnabled();
  });
});
