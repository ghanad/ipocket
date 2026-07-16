import type { LibraryResponse } from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly messages: string[],
  ) {
    super(message);
  }
}

async function readErrorMessages(response: Response): Promise<string[]> {
  try {
    const payload = (await response.json()) as {
      detail?: string | Array<{ msg?: string }>;
    };
    if (typeof payload.detail === "string") {
      return [payload.detail];
    }
    if (Array.isArray(payload.detail)) {
      return payload.detail
        .map((item) => item.msg?.replace(/^Value error,\s*/, "") ?? "")
        .filter(Boolean);
    }
  } catch {
    // Use the stable fallback below.
  }
  return [`Library request failed (${response.status})`];
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

  if (response.redirected && response.url.includes("/ui/login")) {
    const returnTo = `${window.location.pathname}${window.location.search}`;
    window.location.assign(
      `/ui/login?return_to=${encodeURIComponent(returnTo)}`,
    );
    throw new ApiError("Authentication required.", ["Authentication required."]);
  }

  if (!response.ok) {
    const messages = await readErrorMessages(response);
    throw new ApiError(messages[0] ?? "Library request failed.", messages);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export function fetchLibraryItems<T>(
  endpoint: string,
  entity: string,
): Promise<LibraryResponse<T>> {
  return request<LibraryResponse<T>>(`${endpoint}/${entity}`);
}

export function createLibraryItem<T, V extends object = object>(
  endpoint: string,
  entity: string,
  values: V,
): Promise<T> {
  return request<T>(`${endpoint}/${entity}`, {
    method: "POST",
    body: JSON.stringify(values),
  });
}

export function updateLibraryItem<T, V extends object = object>(
  endpoint: string,
  entity: string,
  entityId: number,
  values: V,
): Promise<T> {
  return request<T>(`${endpoint}/${entity}/${entityId}`, {
    method: "PATCH",
    body: JSON.stringify(values),
  });
}

export function deleteLibraryItem(
  endpoint: string,
  entity: string,
  entityId: number,
  confirmName: string,
): Promise<void> {
  return request<void>(`${endpoint}/${entity}/${entityId}`, {
    method: "DELETE",
    body: JSON.stringify({ confirm_name: confirmName }),
  });
}
