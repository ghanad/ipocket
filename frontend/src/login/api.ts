import { ApiError as SharedApiError, apiRequest } from "../shared/apiClient";

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

export async function login(
  endpoint: string,
  values: LoginValues,
): Promise<LoginResponse> {
  let response: Response;
  try {
    response = await apiRequest<Response>(endpoint, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      json: values,
      responseMode: "response",
      onAuthenticationRequired: () => {
        // Login is the authentication endpoint; it must never redirect itself.
      },
    });
  } catch (error) {
    if (error instanceof SharedApiError) {
      const detail =
        error.payload && typeof error.payload === "object"
          ? (error.payload as Record<string, unknown>).detail
          : undefined;
      throw new LoginApiError(
        typeof detail === "string" ? detail : GENERIC_REQUEST_ERROR,
        error.status,
      );
    }
    throw new LoginApiError(GENERIC_REQUEST_ERROR, 0);
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
