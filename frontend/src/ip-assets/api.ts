import type {
  AssetFormValues,
  AssetsResponse,
  BulkValues,
} from "./types";

export class IPAssetsApiError extends Error {
  constructor(public readonly messages: string[]) {
    super(messages[0] ?? "IP asset request failed.");
  }
}

async function readErrors(response: Response): Promise<string[]> {
  try {
    const payload = (await response.json()) as {
      detail?: string | string[] | Array<{ msg?: string }>;
    };
    if (typeof payload.detail === "string") return [payload.detail];
    if (Array.isArray(payload.detail)) {
      return payload.detail
        .map((item) =>
          typeof item === "string"
            ? item
            : item.msg?.replace(/^Value error,\s*/, "") ?? "",
        )
        .filter(Boolean);
    }
  } catch {
    // Use the stable fallback below.
  }
  return [`IP asset request failed (${response.status}).`];
}

async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(url, {
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
    ...options,
  });
  if (
    response.redirected &&
    (response.url.includes("/ui/login") ||
      response.headers.get("location")?.includes("/ui/login"))
  ) {
    window.location.assign(
      `/ui/login?return_to=${encodeURIComponent(
        `${window.location.pathname}${window.location.search}`,
      )}`,
    );
    throw new IPAssetsApiError(["Authentication required."]);
  }
  if (!response.ok) throw new IPAssetsApiError(await readErrors(response));
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function assetPayload(values: AssetFormValues) {
  return {
    ip_address: values.ip_address.trim(),
    type: values.type,
    project_id: values.project_id ? Number(values.project_id) : null,
    host_id: values.host_id ? Number(values.host_id) : null,
    tags: values.tags,
    notes: values.notes,
  };
}

export function fetchAssets(url: string, signal?: AbortSignal) {
  return request<AssetsResponse>(url, { signal });
}

export function createAsset(endpoint: string, values: AssetFormValues) {
  return request<{ asset_id: number }>(endpoint, {
    method: "POST",
    body: JSON.stringify(assetPayload(values)),
  });
}

export function updateAsset(
  endpoint: string,
  assetId: number,
  values: AssetFormValues,
) {
  const { ip_address: _ipAddress, ...payload } = assetPayload(values);
  return request<void>(`${endpoint}/${assetId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function autoHostAsset(endpoint: string, assetId: number) {
  return request<{ host_id: number; host_name: string }>(
    `${endpoint}/${assetId}/auto-host`,
    { method: "POST" },
  );
}

export function deleteAsset(
  endpoint: string,
  assetId: number,
  acknowledged: boolean,
  confirmIp: string,
) {
  return request<void>(`${endpoint}/${assetId}`, {
    method: "DELETE",
    body: JSON.stringify({
      acknowledged,
      confirm_ip: confirmIp,
    }),
  });
}

export function bulkUpdateAssets(
  endpoint: string,
  assetIds: number[],
  values: BulkValues,
) {
  return request<{ updated_count: number }>(`${endpoint}/bulk`, {
    method: "POST",
    body: JSON.stringify({
      asset_ids: assetIds,
      type: values.type || null,
      set_project: Boolean(values.projectMode),
      project_id:
        values.projectMode === "assign" && values.project_id
          ? Number(values.project_id)
          : null,
      tags_to_add: values.tags_to_add,
      tags_to_remove: values.tags_to_remove,
      notes_mode: values.notes_mode || null,
      notes: values.notes,
    }),
  });
}
