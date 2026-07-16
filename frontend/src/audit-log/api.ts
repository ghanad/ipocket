import type { AuditLogResponse } from "./types";

export async function fetchAuditLogs(
  url: string,
  signal?: AbortSignal,
): Promise<AuditLogResponse> {
  const response = await fetch(url, {
    credentials: "same-origin",
    headers: { Accept: "application/json" },
    signal,
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
    throw new Error("Authentication required.");
  }
  if (!response.ok) {
    throw new Error(`Audit history request failed (${response.status}).`);
  }
  return response.json() as Promise<AuditLogResponse>;
}
