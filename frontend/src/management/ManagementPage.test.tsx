import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ManagementPage } from "./ManagementPage";

const overview = {
  summary: {
    active_ip_total: 12,
    archived_ip_total: 2,
    host_total: 4,
    vendor_total: 3,
    project_total: 5,
  },
  utilization: [
    {
      id: 7,
      name: "Corp LAN",
      cidr: "192.168.10.0/24",
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

describe("ManagementPage", () => {
  it("shows loading and then renders summary and utilization data", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => overview,
      }),
    );

    render(<ManagementPage endpoint="/api/management/overview" />);

    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading management data",
    );
    expect(await screen.findByText("12")).toBeInTheDocument();
    expect(screen.getByText("192.168.10.0/24")).toBeInTheDocument();
    expect(screen.getByText("0.8%")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "2" })).toHaveAttribute(
      "href",
      "/ui/ranges/7/addresses#used",
    );
  });

  it("renders the range empty state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ ...overview, utilization: [] }),
      }),
    );

    render(<ManagementPage endpoint="/api/management/overview" />);

    expect(
      await screen.findByText("No ranges yet. Add ranges to see utilization."),
    ).toBeInTheDocument();
  });

  it("shows an error and retries the request", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 500 })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => overview,
      });
    vi.stubGlobal("fetch", fetchMock);

    render(<ManagementPage endpoint="/api/management/overview" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Management data could not be loaded",
    );
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("192.168.10.0/24")).toBeInTheDocument();
  });
});
