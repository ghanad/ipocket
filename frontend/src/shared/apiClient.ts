export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly payload?: unknown,
    public readonly messages: string[] = [message],
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function normalizedValidationMessages(detail: unknown[]): string[] {
  return detail.flatMap((item) => {
    if (typeof item === "string") return [item];
    if (!item || typeof item !== "object") return [];

    const message = (item as Record<string, unknown>).msg;
    return typeof message === "string"
      ? [message.replace(/^Value error,\s*/, "")]
      : [];
  });
}

type ResponseMode = "json" | "blob" | "response";

export interface ApiRequestOptions extends Omit<RequestInit, "body"> {
  body?: BodyInit | null;
  json?: unknown;
  responseMode?: ResponseMode;
  onAuthenticationRequired?: (loginUrl: string) => void;
}

function isLoginRedirect(response: Response): boolean {
  const location = response.headers.get("location") ?? "";
  return (
    response.redirected &&
    (response.url.includes("/ui/login") || location.includes("/ui/login"))
  );
}

function currentLoginUrl(): string {
  const returnTo = `${window.location.pathname}${window.location.search}`;
  return `/ui/login?return_to=${encodeURIComponent(returnTo)}`;
}

function describeValidationDetail(detail: unknown[]): string | null {
  const messages = detail.flatMap((item) => {
    if (typeof item === "string") return [item];
    if (!item || typeof item !== "object") return [];

    const record = item as Record<string, unknown>;
    if (typeof record.msg !== "string") return [];
    const location = Array.isArray(record.loc)
      ? record.loc.filter((part) => typeof part === "string" || typeof part === "number").join(".")
      : "";
    return [location ? `${location}: ${record.msg}` : record.msg];
  });
  return messages.length ? messages.join("; ") : null;
}

function errorMessage(status: number, payload: unknown, fallbackText: string): string {
  if (payload && typeof payload === "object") {
    const record = payload as Record<string, unknown>;
    if (typeof record.detail === "string") return record.detail;
    if (Array.isArray(record.detail)) {
      const validationMessage = describeValidationDetail(record.detail);
      if (validationMessage) return validationMessage;
    }
    if (typeof record.message === "string") return record.message;
  }
  if (fallbackText.trim()) return fallbackText.trim();
  return `Request failed (${status}).`;
}

function errorMessages(payload: unknown, message: string): string[] {
  if (payload && typeof payload === "object") {
    const detail = (payload as Record<string, unknown>).detail;
    if (typeof detail === "string") return [detail];
    if (Array.isArray(detail)) {
      return normalizedValidationMessages(detail);
    }
  }
  return [message];
}

async function readText(response: Response): Promise<string> {
  return response.text();
}

function parseJson(text: string): unknown {
  if (!text.trim()) return undefined;
  return JSON.parse(text) as unknown;
}

export async function apiRequest<T = unknown>(
  url: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const {
    json,
    responseMode = "json",
    onAuthenticationRequired = (loginUrl) => window.location.assign(loginUrl),
    headers: suppliedHeaders,
    ...init
  } = options;
  const headers = new Headers(suppliedHeaders);
  let body = init.body;

  if (json !== undefined) {
    if (body !== undefined && body !== null) {
      throw new TypeError("Use either json or body, not both.");
    }
    body = JSON.stringify(json);
    if (!headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
  }
  if (responseMode === "json" && !headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  const requestInit: RequestInit = {
    ...init,
    credentials: init.credentials ?? "same-origin",
    headers,
  };
  if (body !== undefined && body !== null) requestInit.body = body;

  const response = await fetch(url, requestInit);

  if (isLoginRedirect(response)) {
    const loginUrl = currentLoginUrl();
    onAuthenticationRequired(loginUrl);
    throw new ApiError(401, "Authentication required.");
  }

  if (!response.ok) {
    const text = await readText(response);
    let payload: unknown;
    try {
      payload = parseJson(text);
    } catch {
      payload = undefined;
    }
    const message = errorMessage(response.status, payload, text);
    throw new ApiError(response.status, message, payload, errorMessages(payload, message));
  }

  if (responseMode === "response") return response as T;
  if (responseMode === "blob") return (await response.blob()) as T;
  if (response.status === 204) return undefined as T;

  return parseJson(await readText(response)) as T;
}
