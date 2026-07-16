import type { ManagementOverview } from "./types";

export async function fetchManagementOverview(
  endpoint: string,
): Promise<ManagementOverview> {
  const response = await fetch(endpoint, {
    credentials: "same-origin",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Management overview request failed (${response.status})`);
  }

  return response.json() as Promise<ManagementOverview>;
}
