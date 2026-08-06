import { afterEach, describe, expect, it, vi } from "vitest";

import {
  IPAssetApiError,
  autoHostIPAsset,
  deleteIPAsset,
  fetchIPAssetDetail,
  updateIPAsset,
} from "./api";
import type { DetailResponse, EditValues } from "./types";

const detail = {
  asset: { id: 7, ip_address: "10.0.0.7" },
  audit_logs: [],
  metadata: { projects: [], hosts: [], tags: [], types: [] },
  can_edit: true,
  delete_requires_exact_ip: true,
  auto_host_enabled: true,
  can_auto_host: false,
} as unknown as DetailResponse;

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function fetchCall(fetchMock: ReturnType<typeof vi.fn>) {
  return fetchMock.mock.calls[0] as [string, RequestInit];
}

describe("IP asset detail API", () => {
  it("fetches and maps detail from the exact detail endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(detail)));
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchIPAssetDetail("/api/ui/ip-assets/7")).resolves.toEqual(detail);
    expect(fetchCall(fetchMock)[0]).toBe("/api/ui/ip-assets/7/detail");
  });

  it("forwards AbortSignal and preserves AbortError identity", async () => {
    const aborted = new DOMException("Aborted", "AbortError");
    const fetchMock = vi.fn().mockRejectedValue(aborted);
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();

    await expect(
      fetchIPAssetDetail("/api/ui/ip-assets/7", controller.signal),
    ).rejects.toBe(aborted);
    expect(fetchCall(fetchMock)[1].signal).toBe(controller.signal);
  });

  it.each([
    ["numeric assignments", "2", "3", 2, 3],
    ["empty assignments", "", "", null, null],
  ])(
    "updates with PATCH and the exact transformed payload for %s",
    async (_label, projectId, hostId, expectedProject, expectedHost) => {
      const values: EditValues = {
        type: "BMC",
        project_id: projectId,
        host_id: hostId,
        tags: ["prod", "edge"],
        notes: "rack a",
      };
      const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
      vi.stubGlobal("fetch", fetchMock);

      await expect(updateIPAsset("/api/ui/ip-assets/7", values)).resolves.toBeUndefined();
      const [url, init] = fetchCall(fetchMock);
      expect(url).toBe("/api/ui/ip-assets/7");
      expect(init.method).toBe("PATCH");
      expect(JSON.parse(String(init.body))).toEqual({
        type: "BMC",
        project_id: expectedProject,
        host_id: expectedHost,
        tags: ["prod", "edge"],
        notes: "rack a",
      });
      expect(String(init.body)).not.toContain("ip_address");
    },
  );

  it("auto-hosts with POST, no request body, and maps the response", async () => {
    const result = { host_id: 11, host_name: "10-0-0-7" };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(result)));
    vi.stubGlobal("fetch", fetchMock);

    await expect(autoHostIPAsset("/api/ui/ip-assets/7")).resolves.toEqual(result);
    const [url, init] = fetchCall(fetchMock);
    expect(url).toBe("/api/ui/ip-assets/7/auto-host");
    expect(init.method).toBe("POST");
    expect(init.body).toBeUndefined();
  });

  it("deletes with the exact safeguard payload and accepts 204", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      deleteIPAsset("/api/ui/ip-assets/7", true, "10.0.0.7"),
    ).resolves.toBeUndefined();
    const [url, init] = fetchCall(fetchMock);
    expect(url).toBe("/api/ui/ip-assets/7");
    expect(init.method).toBe("DELETE");
    expect(init.body).toBe(JSON.stringify({
      acknowledged: true,
      confirm_ip: "10.0.0.7",
    }));
  });

  it("preserves FastAPI string-detail errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Asset not found." }), { status: 404 }),
    ));

    await expect(fetchIPAssetDetail("/api/ui/ip-assets/7")).rejects.toMatchObject({
      message: "Asset not found.",
      messages: ["Asset not found."],
      status: 404,
    });
  });

  it("preserves FastAPI string-array errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: ["First failure", "Second failure"] }), {
        status: 422,
      }),
    ));

    await expect(updateIPAsset("/api/ui/ip-assets/7", {
      type: "OS", project_id: "", host_id: "", tags: [], notes: "",
    })).rejects.toMatchObject({
      message: "First failure",
      messages: ["First failure", "Second failure"],
      status: 422,
    });
  });

  it("preserves multiple validation messages and removes Value error prefixes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        detail: [
          { loc: ["body", "project_id"], msg: "Value error, Project is invalid" },
          { loc: ["body", "host_id"], msg: "Value error, Host is invalid" },
        ],
      }), { status: 422 }),
    ));

    const error = await fetchIPAssetDetail("/api/ui/ip-assets/7").catch(
      (caught: unknown) => caught,
    );
    expect(error).toBeInstanceOf(IPAssetApiError);
    expect(error).toMatchObject({
      message: "Project is invalid",
      messages: ["Project is invalid", "Host is invalid"],
      status: 422,
    });
  });

  it("uses the stable generic fallback for non-JSON errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response("Gateway unavailable", { status: 502 }),
    ));

    await expect(fetchIPAssetDetail("/api/ui/ip-assets/7")).rejects.toMatchObject({
      message: "IP asset request failed (502).",
      messages: ["IP asset request failed (502)."],
      status: 502,
    });
  });

  it("uses the exact pathname-only authentication redirect and status 303", async () => {
    const assign = vi.fn();
    vi.stubGlobal("window", {
      location: { pathname: "/ui/ip-assets/7", search: "?tab=audit", assign },
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      redirected: true,
      url: "http://testserver/ui/login?return_to=/api/ui/ip-assets/7/detail",
      headers: new Headers(),
    } as Response));

    await expect(fetchIPAssetDetail("/api/ui/ip-assets/7")).rejects.toMatchObject({
      message: "Authentication required.",
      messages: ["Authentication required."],
      status: 303,
    });
    expect(assign).toHaveBeenCalledWith(
      "/ui/login?return_to=/ui/ip-assets/7",
    );
  });

  it("propagates network errors unchanged", async () => {
    const offline = new TypeError("offline");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(offline));

    await expect(fetchIPAssetDetail("/api/ui/ip-assets/7")).rejects.toBe(offline);
  });
});
