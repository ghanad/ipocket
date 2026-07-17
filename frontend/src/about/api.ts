import type { AboutData } from "./types";

export async function fetchAboutData(endpoint: string): Promise<AboutData> {
  const response = await fetch(endpoint, {
    credentials: "same-origin",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`About request failed (${response.status})`);
  }

  return response.json() as Promise<AboutData>;
}
