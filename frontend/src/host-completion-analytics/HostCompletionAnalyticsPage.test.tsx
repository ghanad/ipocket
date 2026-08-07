import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HostCompletionAnalyticsPage } from "./HostCompletionAnalyticsPage";

const analytics = {
  active_os_assets: 140,
  active_bmc_assets: 130,
  os_attached_to_hosts: 110,
  bmc_attached_to_hosts: 108,
  unresolved_os_assets: 12,
  unresolved_bmc_assets: 8,
  proposed_host_creations: 7,
  incomplete_hosts: 9,
  conflicts: 3,
  explicit_exceptions: 5,
  discovered_rules: 2,
  rule_support: 32,
  rule_contradictions: 4,
  reconciliation_coverage: 91.5,
  unexplained_active_assets: 20,
  active_assets: 270,
  states: { RESOLVED: 230, PROPOSED: 15, UNMATCHED: 12, CONFLICT: 8, EXCEPTION: 5 },
  rules: [{
    id: "rule-1", direction: "OS_TO_BMC", transformation: "replace second octet 10 → 30",
    source_pattern: "10.10.0.0/16", target_pattern: "10.30.0.0/16", strength: "STRONG",
    active: true, support: 28, contradictions: 3, examples: ["10.10.1.7 → 10.30.1.7", "10.10.2.8 → 10.30.2.8"],
  }],
};

function jsonResponse(payload: unknown = analytics, ok = true, status = 200) {
  return { ok, status, redirected: false, url: "", headers: new Headers(), text: async () => JSON.stringify(payload) };
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("HostCompletionAnalyticsPage", () => {
  it("renders reconciliation KPIs, every operational state, and deterministic rule evidence", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse()));
    render(<HostCompletionAnalyticsPage endpoint="/api/host-completion/summary" />);

    expect(screen.getByText("Loading reconciliation summary…")).toBeInTheDocument();
    expect(await screen.findByText("Unexplained")).toBeInTheDocument();
    expect(screen.getByText("20")).toBeInTheDocument();
    expect(screen.getByText("91.5%")).toBeInTheDocument();
    expect(screen.getByText("Host creations")).toBeInTheDocument();
    expect(screen.getByText("Conflicts")).toBeInTheDocument();
    expect(screen.getByText("270 active assets")).toBeInTheDocument();
    for (const state of ["resolved", "proposed", "unmatched", "conflict", "exception"]) expect(screen.getByText(state)).toBeInTheDocument();
    expect(screen.getByText("OS attached")).toHaveTextContent("110 / 140");
    expect(screen.getByText("BMC attached")).toHaveTextContent("108 / 130");
    expect(screen.getByText("Explicit exceptions")).toHaveTextContent("5");
    const rulesTable = screen.getByRole("table", { name: "Discovered reconciliation rules" });
    expect(rulesTable).toBeInTheDocument();
    expect(screen.getByText("strong")).toBeInTheDocument();
    expect(rulesTable).toHaveTextContent("28");
    expect(rulesTable).toHaveTextContent("3");
    expect(screen.getByText("10.10.1.7 → 10.30.1.7 · 10.10.2.8 → 10.30.2.8")).toBeInTheDocument();
    expect(screen.queryByText(/confidence/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("shows the empty deterministic-rule state", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ ...analytics, rules: [] })));
    render(<HostCompletionAnalyticsPage endpoint="/api/host-completion/summary" />);
    expect(await screen.findByText("No rule has enough confirmed evidence yet.")).toBeInTheDocument();
  });

  it("shows an error and retries the summary request", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "Unavailable" }, false, 500))
      .mockResolvedValueOnce(jsonResponse());
    vi.stubGlobal("fetch", fetchMock);
    render(<HostCompletionAnalyticsPage endpoint="/api/host-completion/summary" />);

    expect(await screen.findByRole("alert")).toHaveTextContent("reconciliation summary could not be loaded");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("270 active assets")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
