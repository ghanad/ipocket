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

async function readErrorMessages(response: Response): Promise<string[]> {
  try {
    const payload = (await response.json()) as {
      detail?: string | string[] | Array<{ msg?: string }>;
    };
    if (typeof payload.detail === "string") return [payload.detail];
    if (Array.isArray(payload.detail)) {
      return payload.detail
        .map((item) =>
          typeof item === "string"
            ? item
            : (item.msg?.replace(/^Value error,\s*/, "") ?? ""),
        )
        .filter(Boolean);
    }
  } catch {
    // Use the stable fallback below.
  }
  return [`Password change request failed (${response.status}).`];
}

export async function changePassword(
  endpoint: string,
  values: AccountPasswordValues,
): Promise<AccountPasswordResponse> {
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
    throw new AccountPasswordApiError(
      ["Password could not be changed. Please try again."],
      0,
    );
  }

  if (response.redirected && response.url.includes("/ui/login")) {
    throw new AccountPasswordApiError(
      ["Authentication required."],
      401,
      "/ui/login?return_to=/ui/account/password",
    );
  }
  if (!response.ok) {
    throw new AccountPasswordApiError(
      await readErrorMessages(response),
      response.status,
    );
  }
  return response.json() as Promise<AccountPasswordResponse>;
}
