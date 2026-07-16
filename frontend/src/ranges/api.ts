import type {
  RangeFormValues,
  RangeRow,
  RangesResponse,
} from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly messages: string[],
  ) {
    super(message);
  }
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

  if (response.redirected && response.url.includes("/ui/login")) {
    window.location.assign("/ui/login?return_to=/ui/ranges");
    throw new ApiError("Authentication required.", ["Authentication required."]);
  }

  if (!response.ok) {
    const messages = await readErrorMessages(response);
    throw new ApiError(
      messages[0] ?? `Range request failed (${response.status})`,
      messages,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
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
    // Fall through to the stable generic message below.
  }
  return [`Range request failed (${response.status})`];
}

export async function fetchRanges(endpoint: string): Promise<RangesResponse> {
  return request<RangesResponse>(endpoint);
}

export async function createRange(
  endpoint: string,
  values: RangeFormValues,
): Promise<RangeRow> {
  return request<RangeRow>(endpoint, {
    method: "POST",
    body: JSON.stringify(values),
  });
}

export async function updateRange(
  endpoint: string,
  rangeId: number,
  values: RangeFormValues,
): Promise<RangeRow> {
  return request<RangeRow>(`${endpoint}/${rangeId}`, {
    method: "PATCH",
    body: JSON.stringify(values),
  });
}

export async function deleteRange(
  endpoint: string,
  rangeId: number,
  confirmName: string,
): Promise<void> {
  return request<void>(`${endpoint}/${rangeId}`, {
    method: "DELETE",
    body: JSON.stringify({ confirm_name: confirmName }),
  });
}
