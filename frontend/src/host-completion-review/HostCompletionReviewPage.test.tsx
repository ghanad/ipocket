import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HostCompletionReviewPage } from "./HostCompletionReviewPage";

const createHost = {
  finding_type: "CREATE_HOST",
  state: "PROPOSED",
  proposal_id: "proposal-create-1",
  inventory_fingerprint: "inventory-create-1",
  host_id: null,
  proposed_host_name: "server_10.30.1.17",
  assets: [
    { id: 11, ip_address: "10.10.1.17", type: "OS", host_id: null },
    { id: 12, ip_address: "10.30.1.17", type: "BMC", host_id: null },
  ],
  candidate_ips: ["10.30.1.17"],
  match_strength: "STRONG",
  evidence: ["Rule r-17 maps the final octet."],
  reasons: ["Both unlinked assets match a confirmed rule."],
  rule_ids: ["r-17"],
} as const;

function jsonResponse(payload: unknown, ok = true, status = 200) {
  return { ok, status, redirected: false, url: "", headers: new Headers(), text: async () => JSON.stringify(payload) };
}

function renderPage() {
  return render(<HostCompletionReviewPage queueEndpoint="/api/host-completion/findings/next" decisionsEndpoint="/api/host-completion/findings/decisions" />);
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("HostCompletionReviewPage", () => {
  it("renders loading, error recovery, and the empty queue state", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "offline" }, false, 500))
      .mockResolvedValueOnce(jsonResponse({ item: null, remaining: 0 }));
    vi.stubGlobal("fetch", fetchMock);
    renderPage();

    expect(screen.getByText("Loading reconciliation findings…")).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("reconciliation queue could not be loaded");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("No unexplained findings")).toBeInTheDocument();
    expect(screen.getByText("Every active OS/BMC asset is resolved, proposed, or explicitly excepted.")).toBeInTheDocument();
  });

  it("shows CREATE_HOST inventory and deterministic evidence, then accepts with proposal identity", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ item: createHost, remaining: 3 }))
      .mockResolvedValueOnce(jsonResponse({ id: 9, decision: "ACCEPT", host_id: 42, proposal_id: createHost.proposal_id, idempotent_replay: false }))
      .mockResolvedValueOnce(jsonResponse({ item: null, remaining: 0 }));
    vi.stubGlobal("fetch", fetchMock);
    renderPage();

    expect(await screen.findByRole("heading", { name: "Create and connect this physical Host" })).toBeInTheDocument();
    expect(screen.getByText("Create server_10.30.1.17")).toBeInTheDocument();
    expect(screen.getByText("Attach both active assets in one transaction")).toBeInTheDocument();
    expect(screen.getByText("Both unlinked assets match a confirmed rule.")).toBeInTheDocument();
    expect(screen.getByText("Rule r-17 maps the final octet.")).toBeInTheDocument();
    expect(screen.getByText("strong match")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Create Host and attach assets" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({
      proposal_id: "proposal-create-1",
      inventory_fingerprint: "inventory-create-1",
      decision: "ACCEPT",
    });
    expect(screen.getByText("Proposal applied.")).toBeInTheDocument();
  });

  it("asks for a BMC address when the unmatched asset is an OS", async () => {
    const unmatched = { ...createHost, finding_type: "UNMATCHED_ASSET", state: "UNMATCHED", proposal_id: "proposal-unmatched", assets: [createHost.assets[0]], proposed_host_name: null, match_strength: null, evidence: [], reasons: ["No safe counterpart exists."], rule_ids: [] } as const;
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ item: unmatched, remaining: 1 }))
      .mockResolvedValueOnce(jsonResponse({ id: 10, decision: "CORRECT", host_id: 55, proposal_id: unmatched.proposal_id, idempotent_replay: false }))
      .mockResolvedValueOnce(jsonResponse({ item: null, remaining: 0 }));
    vi.stubGlobal("fetch", fetchMock);
    renderPage();

    expect(await screen.findByText("No safe counterpart was found")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /attach assets/i })).not.toBeInTheDocument();
    expect(screen.getByText("No deterministic rule supplied enough evidence for an automatic proposal.")).toBeInTheDocument();
    expect(screen.getByText("What is the BMC address for this OS?")).toBeInTheDocument();
    expect(screen.getByText("server_<bmc-ip>")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Mark exception" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Archive asset" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("BMC IP address"), { target: { value: "10.30.1.17" } });
    expect(screen.getByText("server_10.30.1.17")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Link BMC and update Host" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ proposal_id: "proposal-unmatched", inventory_fingerprint: "inventory-create-1", decision: "CORRECT", counterpart_ip: "10.30.1.17", counterpart_type: "BMC" });
  });

  it.each([
    ["Mark exception", "EXCEPTION"],
    ["Archive asset", "DEACTIVATE"],
  ])("records %s for an unmatched asset", async (buttonName, decision) => {
    const unmatched = { ...createHost, finding_type: "UNMATCHED_ASSET", state: "UNMATCHED", proposal_id: `proposal-${decision}`, assets: [createHost.assets[0]], proposed_host_name: null, match_strength: null, evidence: [], reasons: [], rule_ids: [] } as const;
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ item: unmatched, remaining: 1 }))
      .mockResolvedValueOnce(jsonResponse({ id: 11, decision, host_id: null, proposal_id: unmatched.proposal_id, idempotent_replay: false }))
      .mockResolvedValueOnce(jsonResponse({ item: null, remaining: 0 }));
    vi.stubGlobal("fetch", fetchMock);
    renderPage();

    await screen.findByText("No safe counterpart was found");
    fireEvent.click(screen.getByRole("button", { name: buttonName }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ proposal_id: unmatched.proposal_id, inventory_fingerprint: "inventory-create-1", decision });
  });

  it("never presents an automatic accept action for conflicts", async () => {
    const conflict = { ...createHost, finding_type: "CONFLICT", state: "CONFLICT", proposal_id: "proposal-conflict", proposed_host_name: null, match_strength: "WEAK", reasons: ["The candidate is attached elsewhere."] } as const;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ item: conflict, remaining: 1 })));
    renderPage();

    expect(await screen.findByText("Resolve this conflict manually")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /attach missing asset|create host/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Wrong pair" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Mark exception" })).toBeInTheDocument();
    expect(screen.getByLabelText("BMC IP address")).toBeInTheDocument();
  });

  it("asks for an OS address when the unmatched asset is a BMC", async () => {
    const unmatchedBmc = { ...createHost, finding_type: "UNMATCHED_ASSET", state: "UNMATCHED", proposal_id: "proposal-bmc", assets: [createHost.assets[1]], proposed_host_name: null, match_strength: null, evidence: [], reasons: [], rule_ids: [] } as const;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ item: unmatchedBmc, remaining: 0 })));
    renderPage();

    expect(await screen.findByText("What is the OS address for this BMC?")).toBeInTheDocument();
    expect(screen.getByLabelText("OS IP address")).toBeInTheDocument();
    expect(screen.getByText("server_10.30.1.17")).toBeInTheDocument();
  });
});
