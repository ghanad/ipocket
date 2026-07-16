import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RangesPage } from "./RangesPage";

const rangeResponse = {
  ranges: [
    {
      id: 7,
      name: "Corp LAN",
      cidr: "192.168.10.0/24",
      notes: "office",
      total_usable: 254,
      used: 2,
      free: 252,
      utilization_percent: 0.7874,
    },
  ],
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("RangesPage", () => {
  it("renders the existing table values, actions, and drill-down links", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        redirected: false,
        json: async () => rangeResponse,
      }),
    );

    render(<RangesPage endpoint="/api/ui/ranges" />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading IP ranges");
    expect(await screen.findByText("192.168.10.0/24")).toBeInTheDocument();
    const rangeRow = screen.getByText("192.168.10.0/24").closest("tr");
    expect(rangeRow).toHaveClass("row-with-actions");
    expect(rangeRow).toHaveAttribute("tabindex", "0");
    expect(screen.getByText("0.8%")).toBeInTheDocument();
    expect(screen.getAllByRole("columnheader")).toHaveLength(7);
    expect(screen.getByRole("columnheader", { name: "Used" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "2" })).toHaveAttribute(
      "href",
      "/ui/ranges/7/addresses?status=used#used",
    );
    expect(screen.getByRole("link", { name: "252" })).toHaveAttribute(
      "href",
      "/ui/ranges/7/addresses?status=free#free",
    );
  });

  it("creates a range through the drawer and refreshes the table", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        redirected: false,
        json: async () => ({ ranges: [] }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 201,
        redirected: false,
        json: async () => rangeResponse.ranges[0],
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        redirected: false,
        json: async () => rangeResponse,
      });
    vi.stubGlobal("fetch", fetchMock);

    render(<RangesPage endpoint="/api/ui/ranges" />);

    await screen.findByText("No ranges yet. Add ranges to see utilization.");
    fireEvent.click(screen.getByRole("button", { name: "New Range" }));

    const dialog = screen.getByRole("dialog", { name: "Add IP range" });
    const inputs = dialog.querySelectorAll("input");
    fireEvent.change(inputs[0], { target: { value: "Corp LAN" } });
    fireEvent.change(inputs[1], { target: { value: "192.168.10.17/24" } });

    const saveButton = screen.getByRole("button", { name: "Save range" });
    expect(saveButton).toBeEnabled();
    fireEvent.click(saveButton);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/ui/ranges",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          name: "Corp LAN",
          cidr: "192.168.10.17/24",
          notes: "",
        }),
      }),
    );
    expect(await screen.findByText("192.168.10.0/24")).toBeInTheDocument();
  });

  it("keeps edit validation errors in the drawer", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        redirected: false,
        json: async () => rangeResponse,
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 409,
        redirected: false,
        json: async () => ({ detail: "CIDR already exists." }),
      });
    vi.stubGlobal("fetch", fetchMock);

    render(<RangesPage endpoint="/api/ui/ranges" />);

    await screen.findByText("192.168.10.0/24");
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    const dialog = screen.getByRole("dialog", { name: "Edit IP range" });
    fireEvent.change(dialog.querySelector("input")!, {
      target: { value: "Corporate LAN" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "CIDR already exists.",
    );
    expect(dialog).toHaveClass("is-open");
  });

  it("requires acknowledgement and exact-name confirmation before delete", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        redirected: false,
        json: async () => rangeResponse,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 204,
        redirected: false,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        redirected: false,
        json: async () => ({ ranges: [] }),
      });
    vi.stubGlobal("fetch", fetchMock);

    render(<RangesPage endpoint="/api/ui/ranges" />);

    await screen.findByText("192.168.10.0/24");
    fireEvent.click(
      screen.getByRole("button", { name: "More actions for Corp LAN" }),
    );
    fireEvent.click(
      screen.getByRole("menuitem", { name: "Delete Corp LAN" }),
    );
    const deleteButton = screen.getByRole("button", {
      name: "Delete permanently",
    });
    expect(deleteButton).toBeDisabled();

    fireEvent.click(
      screen.getByRole("checkbox", {
        name: "I understand this cannot be undone",
      }),
    );
    fireEvent.change(screen.getByRole("textbox", { name: /Type the range name/ }), {
      target: { value: "Corp LAN" },
    });
    expect(deleteButton).toBeEnabled();
    fireEvent.click(deleteButton);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/ui/ranges/7",
      expect.objectContaining({
        method: "DELETE",
        body: JSON.stringify({ confirm_name: "Corp LAN" }),
      }),
    );
  });

  it("opens an edit drawer requested by the legacy query link", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        redirected: false,
        json: async () => rangeResponse,
      }),
    );

    render(
      <RangesPage endpoint="/api/ui/ranges" initialEditId={7} />,
    );

    const dialog = await screen.findByRole("dialog", { name: "Edit IP range" });
    await waitFor(() => expect(dialog).toHaveClass("is-open"));
    expect(
      screen.getByRole("textbox", { name: "Name" }),
    ).toHaveValue("Corp LAN");
  });
});
