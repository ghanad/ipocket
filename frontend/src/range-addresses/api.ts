import type {
  AddressFormValues,
  RangeAddressesResponse,
} from "./types";

export class RangeAddressesApiError extends Error {
  constructor(public messages: string[]) {
    super(messages[0] ?? "Range address request failed.");
  }
}

async function messages(response: Response): Promise<string[]> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return [body.detail];
    if (Array.isArray(body.detail)) {
      return body.detail
        .map((item: unknown) =>
          typeof item === "string"
            ? item
            : String((item as { msg?: string }).msg ?? "").replace(
                /^Value error,\s*/,
                "",
              ),
        )
        .filter(Boolean);
    }
  } catch {
    // Fall through to the generic message.
  }
  return [`Range address request failed (${response.status}).`];
}

async function request<T>(
  url: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(url, {
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
    ...options,
  });
  if (!response.ok) throw new RangeAddressesApiError(await messages(response));
  return response.json() as Promise<T>;
}

export function fetchRangeAddresses(url: string, signal?: AbortSignal) {
  return request<RangeAddressesResponse>(url, { signal });
}

function body(values: AddressFormValues) {
  return {
    ip_address: values.ip_address,
    type: values.type,
    project_id: values.project_id ? Number(values.project_id) : null,
    tags: values.tags,
    notes: values.notes,
  };
}

export function createRangeAddress(
  endpoint: string,
  values: AddressFormValues,
) {
  return request<{ asset_id: number; ip_address: string }>(endpoint, {
    method: "POST",
    body: JSON.stringify(body(values)),
  });
}

export function updateRangeAddress(
  endpoint: string,
  assetId: number,
  values: AddressFormValues,
) {
  const { ip_address: _ipAddress, ...payload } = body(values);
  return request<{ asset_id: number; ip_address: string }>(
    `${endpoint}/${assetId}`,
    { method: "PATCH", body: JSON.stringify(payload) },
  );
}
