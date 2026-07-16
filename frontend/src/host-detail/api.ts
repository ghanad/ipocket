import type { HostDetailResponse } from "./types";

export class HostDetailApiError extends Error {
  constructor(
    message: string,
    public readonly status: number | null = null,
  ) {
    super(message);
  }
}

export async function fetchHostDetail(
  endpoint: string,
  signal?: AbortSignal,
): Promise<HostDetailResponse> {
  let response: Response;
  try {
    response = await fetch(endpoint, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new HostDetailApiError("Host details could not be loaded.");
  }
  if (response.status === 404) {
    throw new HostDetailApiError("Host not found.", 404);
  }
  if (!response.ok) {
    throw new HostDetailApiError("Host details could not be loaded.", response.status);
  }
  return response.json() as Promise<HostDetailResponse>;
}
