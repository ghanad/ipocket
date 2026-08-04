import { afterEach, describe, expect, it, vi } from "vitest";

import {
  IPAssetsApiError,
  autoHostAsset,
  bulkUpdateAssets,
  createAsset,
  deleteAsset,
  fetchAssets,
  updateAsset,
} from "./api";
import type { AssetFormValues, AssetsResponse, BulkValues } from "./types";

const endpoint = "/api/ui/ip-assets";
const assetsResponse = {
  assets: [],
  filters: {
    projects: [],
    hosts: [],
    tags: [],
    types: ["OS", "BMC", "VM", "VIP", "OTHER"],
    normalized: {},
  },
  pagination: { page: 1, per_page: 20, total: 0, total_pages: 1 },
  can_edit: true,
} as unknown as AssetsResponse;
const values: AssetFormValues = {
  ip_address: " 10.0.0.7 ",
  type: "BMC",
  project_id: "3",
  host_id: "9",
  tags: ["prod", "edge"],
  notes: " rack a ",
};

function response(body: unknown, status = 200): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), { status });
}

function fetchCall(fetchMock: ReturnType<typeof vi.fn>) {
  return fetchMock.mock.calls[0] as [string, RequestInit];
}

function requestBody(fetchMock: ReturnType<typeof vi.fn>) {
  return JSON.parse(String(fetchCall(fetchMock)[1].body)) as unknown;
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.history.replaceState({}, "", "/ui/ip-assets");
});

describe("IP Assets API", () => {
  it("fetches and maps the exact prebuilt list URL with its AbortSignal", async () => {
    const url = `${endpoint}?q=core&project_id=unassigned&tag_any=prod&tag_any=edge&page=2`;
    const controller = new AbortController();
    const fetchMock = vi.fn().mockResolvedValue(response(assetsResponse));
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchAssets(url, controller.signal)).resolves.toEqual(assetsResponse);
    const [calledUrl, init] = fetchCall(fetchMock);
    expect(calledUrl).toBe(url);
    expect(init.signal).toBe(controller.signal);
    expect(init.credentials).toBe("same-origin");
  });

  it("preserves AbortError identity", async () => {
    const aborted = new DOMException("Aborted", "AbortError");
    const fetchMock = vi.fn().mockRejectedValue(aborted);
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchAssets(endpoint, new AbortController().signal)).rejects.toBe(aborted);
  });

  it.each([
    ["numeric assignments", values, 3, 9],
    [
      "empty assignments",
      { ...values, project_id: "", host_id: "" },
      null,
      null,
    ],
  ])(
    "creates with POST, the exact transformation, and maps success for %s",
    async (_label, submitted, expectedProject, expectedHost) => {
      const fetchMock = vi.fn().mockResolvedValue(response({ asset_id: 17 }, 201));
      vi.stubGlobal("fetch", fetchMock);

      await expect(createAsset(endpoint, submitted)).resolves.toEqual({ asset_id: 17 });
      const [url, init] = fetchCall(fetchMock);
      expect(url).toBe(endpoint);
      expect(init.method).toBe("POST");
      expect(requestBody(fetchMock)).toEqual({
        ip_address: "10.0.0.7",
        type: "BMC",
        project_id: expectedProject,
        host_id: expectedHost,
        tags: ["prod", "edge"],
        notes: " rack a ",
      });
    },
  );

  it.each([
    ["numeric assignments", values, 3, 9],
    [
      "empty assignments",
      { ...values, project_id: "", host_id: "" },
      null,
      null,
    ],
  ])(
    "updates the exact asset URL with PATCH and omits immutable fields for %s",
    async (_label, submitted, expectedProject, expectedHost) => {
      const fetchMock = vi.fn().mockResolvedValue(response({ message: "updated" }));
      vi.stubGlobal("fetch", fetchMock);

      await expect(updateAsset(endpoint, 7, submitted)).resolves.toEqual({ message: "updated" });
      const [url, init] = fetchCall(fetchMock);
      expect(url).toBe(`${endpoint}/7`);
      expect(init.method).toBe("PATCH");
      const body = requestBody(fetchMock);
      expect(body).toEqual({
        type: "BMC",
        project_id: expectedProject,
        host_id: expectedHost,
        tags: ["prod", "edge"],
        notes: " rack a ",
      });
      expect(body).not.toHaveProperty("ip_address");
    },
  );

  it("auto-hosts with POST, no body, and maps the response", async () => {
    const result = { host_id: 11, host_name: "server_10.0.0.7" };
    const fetchMock = vi.fn().mockResolvedValue(response(result));
    vi.stubGlobal("fetch", fetchMock);

    await expect(autoHostAsset(endpoint, 7)).resolves.toEqual(result);
    const [url, init] = fetchCall(fetchMock);
    expect(url).toBe(`${endpoint}/7/auto-host`);
    expect(init.method).toBe("POST");
    expect(init.body).toBeUndefined();
  });

  it("permanently deletes with the exact safeguards and accepts 204", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(undefined, 204));
    vi.stubGlobal("fetch", fetchMock);

    await expect(deleteAsset(endpoint, 7, true, "10.0.0.7")).resolves.toBeUndefined();
    const [url, init] = fetchCall(fetchMock);
    expect(url).toBe(`${endpoint}/7`);
    expect(init.method).toBe("DELETE");
    expect(requestBody(fetchMock)).toEqual({
      acknowledged: true,
      confirm_ip: "10.0.0.7",
    });
  });

  it.each([
    [
      "assigns a project with type, tags, and set notes",
      {
        type: "VM",
        projectMode: "assign",
        project_id: "4",
        tags_to_add: ["prod"],
        tags_to_remove: ["old"],
        notes_mode: "set",
        notes: "new note",
      } satisfies BulkValues,
      {
        asset_ids: [7, 8],
        type: "VM",
        set_project: true,
        project_id: 4,
        tags_to_add: ["prod"],
        tags_to_remove: ["old"],
        notes_mode: "set",
        notes: "new note",
      },
    ],
    [
      "unassigns a project and clears notes",
      {
        type: "",
        projectMode: "unassign",
        project_id: "4",
        tags_to_add: [],
        tags_to_remove: ["old"],
        notes_mode: "clear",
        notes: "ignored by the server contract",
      } satisfies BulkValues,
      {
        asset_ids: [7, 8],
        type: null,
        set_project: true,
        project_id: null,
        tags_to_add: [],
        tags_to_remove: ["old"],
        notes_mode: "clear",
        notes: "ignored by the server contract",
      },
    ],
    [
      "keeps project, type, and notes in the no-op-relevant shape",
      {
        type: "",
        projectMode: "",
        project_id: "",
        tags_to_add: [],
        tags_to_remove: [],
        notes_mode: "",
        notes: "",
      } satisfies BulkValues,
      {
        asset_ids: [7, 8],
        type: null,
        set_project: false,
        project_id: null,
        tags_to_add: [],
        tags_to_remove: [],
        notes_mode: null,
        notes: "",
      },
    ],
  ])("bulk-updates and maps updated_count when it %s", async (_label, bulk, expected) => {
    const fetchMock = vi.fn().mockResolvedValue(response({ updated_count: 2 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(bulkUpdateAssets(endpoint, [7, 8], bulk)).resolves.toEqual({
      updated_count: 2,
    });
    const [url, init] = fetchCall(fetchMock);
    expect(url).toBe(`${endpoint}/bulk`);
    expect(init.method).toBe("POST");
    expect(requestBody(fetchMock)).toEqual(expected);
  });

  it.each([
    ["FastAPI string detail", { detail: "Asset not found." }, ["Asset not found."]],
    [
      "FastAPI string-array detail",
      { detail: ["First failure", "Second failure"] },
      ["First failure", "Second failure"],
    ],
    [
      "multi-validation detail",
      {
        detail: [
          { loc: ["body", "project_id"], msg: "Value error, Project is invalid" },
          { loc: ["body", "host_id"], msg: "Value error, Host is invalid" },
        ],
      },
      ["Project is invalid", "Host is invalid"],
    ],
  ])("preserves %s as page-domain messages", async (_label, payload, messages) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(payload, 422)));

    const error = await fetchAssets(endpoint).catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(IPAssetsApiError);
    expect(error).toMatchObject({ message: messages[0], messages });
  });

  it("preserves an empty FastAPI detail array and the domain error default message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ detail: [] }, 422)));

    await expect(fetchAssets(endpoint)).rejects.toMatchObject({
      message: "IP asset request failed.",
      messages: [],
    });
  });

  it("uses the exact stable fallback for non-JSON errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response("Gateway unavailable", { status: 502 }),
    ));

    await expect(fetchAssets(endpoint)).rejects.toMatchObject({
      message: "IP asset request failed (502).",
      messages: ["IP asset request failed (502)."],
    });
  });

  it("redirects authentication with the encoded pathname and query while preserving the domain error", async () => {
    const assign = vi.fn();
    vi.stubGlobal("window", {
      location: { pathname: "/ui/ip-assets", search: "?q=core&page=2", assign },
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      redirected: true,
      url: "http://testserver/ui/login?return_to=/api/ui/ip-assets",
      headers: new Headers(),
    } as Response));

    const error = await fetchAssets(endpoint).catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(IPAssetsApiError);
    expect(error).toMatchObject({
      message: "Authentication required.",
      messages: ["Authentication required."],
    });
    expect(error).not.toHaveProperty("status");
    expect(assign).toHaveBeenCalledWith(
      "/ui/login?return_to=%2Fui%2Fip-assets%3Fq%3Dcore%26page%3D2",
    );
  });

  it("propagates network errors unchanged", async () => {
    const offline = new TypeError("offline");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(offline));

    await expect(fetchAssets(endpoint)).rejects.toBe(offline);
  });
});
