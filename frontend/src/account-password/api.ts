import { ApiError as SharedApiError, apiRequest } from "../shared/apiClient";

export interface AccountPasswordValues {
  current_password: string;
  new_password: string;
  confirm_new_password: string;
}

export interface AccountPasswordResponse {
  message: string;
}

export class AccountPasswordApiError extends Error {
  constructor(
    public readonly messages: string[],
    public readonly status: number,
    public readonly loginUrl: string | null = null,
  ) {
    super(messages[0] ?? "Password change request failed.");
  }
}

export async function changePassword(
  endpoint: string,
  values: AccountPasswordValues,
): Promise<AccountPasswordResponse> {
  let authenticationRequired = false;
  try {
    return await apiRequest<AccountPasswordResponse>(endpoint, {
      method: "POST",
      json: values,
      onAuthenticationRequired: () => {
        authenticationRequired = true;
      },
    });
  } catch (error) {
    if (error instanceof SharedApiError) {
      if (authenticationRequired) {
        throw new AccountPasswordApiError(
          ["Authentication required."],
          401,
          "/ui/login?return_to=/ui/account/password",
        );
      }

      const detail = error.payload && typeof error.payload === "object"
        ? (error.payload as Record<string, unknown>).detail
        : undefined;
      const messages =
        (typeof detail === "string" || Array.isArray(detail)) &&
        error.messages.length
          ? error.messages
          : [`Password change request failed (${error.status}).`];
      throw new AccountPasswordApiError(messages, error.status);
    }
    throw new AccountPasswordApiError(
      ["Password could not be changed. Please try again."],
      0,
    );
  }
}
