export interface LoginValues {
  username: string;
  password: string;
  return_to: string;
}

export interface LoginResponse {
  redirect_to: string;
}

export class LoginApiError extends Error {
  constructor(
    public readonly message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

const GENERIC_REQUEST_ERROR = "Login could not be completed. Please try again.";
const CONTROL_CHARACTER = /[\u0000-\u001f\u007f-\u009f]/u;

function isApprovedRedirect(target: string): boolean {
  if (
    !target.startsWith("/") ||
    target.startsWith("//") ||
    target.includes("\\") ||
    CONTROL_CHARACTER.test(target)
  ) {
    return false;
  }

  try {
    const resolved = new URL(target, window.location.href);
    return (
      resolved.origin === window.location.origin &&
      resolved.pathname.startsWith("/") &&
      !resolved.pathname.startsWith("//")
    );
  } catch {
    return false;
  }
}

async function readError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string") return payload.detail;
  } catch {
    // Use the stable fallback below.
  }
  return GENERIC_REQUEST_ERROR;
}

export async function login(
  endpoint: string,
  values: LoginValues,
): Promise<LoginResponse> {
  let response: Response;
  try {
    response = await fetch(endpoint, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(values),
    });
  } catch {
    throw new LoginApiError(GENERIC_REQUEST_ERROR, 0);
  }

  if (!response.ok) {
    throw new LoginApiError(await readError(response), response.status);
  }

  try {
    const payload = (await response.json()) as { redirect_to?: unknown };
    if (
      typeof payload.redirect_to !== "string" ||
      !isApprovedRedirect(payload.redirect_to)
    ) {
      throw new Error("Invalid redirect response.");
    }
    return { redirect_to: payload.redirect_to };
  } catch {
    throw new LoginApiError(GENERIC_REQUEST_ERROR, response.status);
  }
}
