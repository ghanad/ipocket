import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HostCompletionReviewPage } from "./HostCompletionReviewPage";

const askQueue = {
  item: {
    case_type: "HOST_MISSING_BMC",
    host_id: 7,
    os_asset: { address: "10.10.7.7", hostname: null },
    bmc_asset: null,
    would_create_host: false,
    mode: "ASK",
    candidate_ip: null,
    confidence: null,
    evidence: [],
    reason_text: "No active rule matches this host.",
  },
  remaining: 4,
};

const suggestQueue = {
  item: {
    case_type: "HOST_MISSING_BMC",
    host_id: 8,
    os_asset: { address: "10.10.8.8", hostname: null },
    bmc_asset: null,
    would_create_host: false,
    mode: "SUGGEST",
    candidate_ip: "10.30.8.8",
    confidence: 0.85,
    evidence: ["10.10.1.1 -> 10.30.1.1"],
    reason_text: "3 confirmed hosts use this mapping.",
  },
  remaining: 2,
};

function jsonResponse(payload: unknown, ok = true, status = 200) {
  return {
    ok,
    status,
    redirected: false,
    url: "",
    headers: new Headers(),
    text: async () => JSON.stringify(payload),
  };
}

function renderPage() {
  return render(
    <HostCompletionReviewPage
      queueEndpoint="/api/host-completion/review-queue"
      decisionsEndpoint="/api/host-completion/decisions"
    />,
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("HostCompletionReviewPage", () => {
  it("loads and renders one ASK card", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(askQueue)));

    renderPage();

    expect(screen.getByText("Loading Host Completion review…")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Host #7" })).toBeInTheDocument();
    expect(screen.getByText("10.10.7.7")).toBeInTheDocument();
    expect(screen.getByText("remaining: 4")).toBeInTheDocument();
    expect(screen.getByText("What is the BMC IP for this case?")).toBeInTheDocument();
    expect(screen.getAllByRole("article")).toHaveLength(1);
  });

  it("uses the opposite side for direction-aware BMC and OS labels", async () => {
    const osQueue = {
      item: { ...askQueue.item, case_type: "HOST_MISSING_OS", os_asset: null, bmc_asset: { address: "10.30.7.7", hostname: null } },
      remaining: 0,
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(osQueue)));
    renderPage();

    expect(await screen.findByText("What is the OS IP for this case?")).toBeInTheDocument();
    expect(screen.getByLabelText("OS IP address")).toBeInTheDocument();
  });

  it("saves an entered ASK address and refetches the queue", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(askQueue))
      .mockResolvedValueOnce(jsonResponse({ id: 2, decision: "CORRECTED", applied_ip: "10.40.7.7" }))
      .mockResolvedValueOnce(jsonResponse({ item: null, remaining: 0 }));
    vi.stubGlobal("fetch", fetchMock);
    renderPage();

    fireEvent.change(await screen.findByLabelText("BMC IP address"), {
      target: { value: "10.40.7.7" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("No more cases 🎉")).toBeInTheDocument();
    expect(screen.getByText("BMC IP saved.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/host-completion/decisions",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          case_type: "HOST_MISSING_BMC",
          mode: "ASK",
          host_id: 7,
          os_address: "10.10.7.7",
          decision: "CORRECTED",
          corrected_ip: "10.40.7.7",
        }),
      }),
    );
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("renders a suggestion and handles Yes", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(suggestQueue))
      .mockResolvedValueOnce(jsonResponse({ id: 3, decision: "ACCEPT", applied_ip: "10.30.8.8" }))
      .mockResolvedValueOnce(jsonResponse({ item: null, remaining: 0 }));
    vi.stubGlobal("fetch", fetchMock);
    renderPage();

    expect(await screen.findByText("10.30.8.8")).toBeInTheDocument();
    expect(screen.getByText("3 confirmed hosts use this mapping.")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Suggestion confidence" })).toHaveAttribute("aria-valuenow", "85");
    fireEvent.click(screen.getByRole("button", { name: "Yes" }));

    expect(await screen.findByText("Suggested BMC IP saved.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/host-completion/decisions",
      expect.objectContaining({
        body: JSON.stringify({
          case_type: "HOST_MISSING_BMC",
          mode: "SUGGEST",
          host_id: 8,
          os_address: "10.10.8.8",
          candidate_ip: "10.30.8.8",
          decision: "ACCEPT",
        }),
      }),
    );
  });

  it("reveals and submits the inline correction", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(suggestQueue))
      .mockResolvedValueOnce(jsonResponse({ id: 4, decision: "CORRECTED", applied_ip: "10.40.8.8" }))
      .mockResolvedValueOnce(jsonResponse({ item: null, remaining: 0 }));
    vi.stubGlobal("fetch", fetchMock);
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Correct" }));
    fireEvent.change(screen.getByLabelText("Correct BMC IP address"), {
      target: { value: "10.40.8.8" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save correction" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/host-completion/decisions",
      expect.objectContaining({
        body: JSON.stringify({
          case_type: "HOST_MISSING_BMC",
          mode: "SUGGEST",
          host_id: 8,
          os_address: "10.10.8.8",
          candidate_ip: "10.30.8.8",
          decision: "CORRECTED",
          corrected_ip: "10.40.8.8",
        }),
      }),
    );
  });

  it.each([
    ["No", "REJECT"],
    ["Later", "UNSURE"],
    ["No BMC", "NO_BMC"],
  ])("maps %s to %s", async (buttonName, decision) => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(suggestQueue))
      .mockResolvedValueOnce(jsonResponse({ id: 5, decision, applied_ip: null }))
      .mockResolvedValueOnce(jsonResponse({ item: null, remaining: 0 }));
    vi.stubGlobal("fetch", fetchMock);
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: buttonName }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toMatchObject({
      candidate_ip: "10.30.8.8",
      decision,
    });
  });

  it("shows load and decision errors with recovery controls", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "broken" }, false, 500))
      .mockResolvedValueOnce(jsonResponse(suggestQueue))
      .mockResolvedValueOnce(jsonResponse({ detail: "Candidate is no longer available." }, false, 409));
    vi.stubGlobal("fetch", fetchMock);
    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent("review queue could not be loaded");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    fireEvent.click(await screen.findByRole("button", { name: "Yes" }));

    expect(await screen.findByText("Candidate is no longer available.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Host #8" })).toBeInTheDocument();
  });

  it("prefills the configured host template from a known or entered BMC and preserves manual edits", async () => {
    const queue = {
      item: {
        ...askQueue.item,
        case_type: "UNLINKED_OS",
        host_id: null,
        would_create_host: true,
        host_name_template: "server_{bmc}",
        host_options: [],
      },
      remaining: 0,
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(queue)));
    renderPage();

    const name = await screen.findByLabelText("Host name");
    expect(name).toHaveValue("");
    fireEvent.change(screen.getByLabelText("BMC IP address"), { target: { value: "10.30.1.1" } });
    expect(name).toHaveValue("server_10.30.1.1");
    fireEvent.change(name, { target: { value: "manual-name" } });
    fireEvent.change(screen.getByLabelText("BMC IP address"), { target: { value: "10.30.1.2" } });
    expect(name).toHaveValue("manual-name");
  });

  it("uses an attach confirmation when an autocomplete host already has the missing side", async () => {
    const queue = {
      item: {
        ...askQueue.item,
        case_type: "UNLINKED_OS",
        host_id: null,
        would_create_host: true,
        host_name_template: "server_{bmc}",
        host_options: [{ id: 42, name: "server_10.30.1.1", has_os: true, has_bmc: true }],
      },
      remaining: 0,
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(queue))
      .mockResolvedValueOnce(jsonResponse({ id: 9, decision: "ATTACH_EXISTING", applied_ip: null, host_id: 42, message: "Assets attached." }))
      .mockResolvedValueOnce(jsonResponse({ item: null, remaining: 0 }));
    vi.stubGlobal("fetch", fetchMock);
    renderPage();

    fireEvent.change(await screen.findByLabelText("Host name"), { target: { value: "server_10.30.1.1" } });
    expect(screen.getByRole("heading", { name: "Attach this case to server_10.30.1.1?" })).toBeInTheDocument();
    expect(screen.queryByLabelText("BMC IP address")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Attach to host" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toMatchObject({ decision: "ATTACH_EXISTING", target_host_id: 42 });
  });
});
