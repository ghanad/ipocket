import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AccountPasswordPage } from "./AccountPasswordPage";

function response(
  payload: unknown,
  options: {
    ok?: boolean;
    status?: number;
    redirected?: boolean;
    url?: string;
  } = {},
) {
  return {
    ok: options.ok ?? true,
    status: options.status ?? 200,
    redirected: options.redirected ?? false,
    url: options.url ?? "http://testserver/api/ui/account/password",
    json: async () => payload,
    text: async () => payload == null ? "" : JSON.stringify(payload),
    headers: new Headers(),
  };
}

function fillPasswords(
  current = "current-pass",
  next = "next-pass",
  confirm = next,
) {
  fireEvent.change(screen.getByLabelText("Current password"), {
    target: { value: current },
  });
  fireEvent.change(screen.getByLabelText("New password"), {
    target: { value: next },
  });
  fireEvent.change(screen.getByLabelText("Confirm new password"), {
    target: { value: confirm },
  });
}

function expectPasswordFieldsCleared() {
  expect(screen.getByLabelText("Current password")).toHaveValue("");
  expect(screen.getByLabelText("New password")).toHaveValue("");
  expect(screen.getByLabelText("Confirm new password")).toHaveValue("");
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("AccountPasswordPage", () => {
  it("renders the existing page content and password autocomplete attributes", () => {
    render(<AccountPasswordPage endpoint="/api/ui/account/password" />);

    expect(
      screen.getByRole("heading", { name: "Change Password" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Update your account password for UI and API login."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Current password")).toHaveAttribute(
      "autocomplete",
      "current-password",
    );
    expect(screen.getByLabelText("New password")).toHaveAttribute(
      "autocomplete",
      "new-password",
    );
    expect(screen.getByLabelText("Confirm new password")).toHaveAttribute(
      "autocomplete",
      "new-password",
    );
  });

  it("keeps submit disabled until every required field contains a value", () => {
    render(<AccountPasswordPage endpoint="/api/ui/account/password" />);
    const submit = screen.getByRole("button", { name: "Change password" });

    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Current password"), {
      target: { value: "current-pass" },
    });
    fireEvent.change(screen.getByLabelText("New password"), {
      target: { value: "next-pass" },
    });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Confirm new password"), {
      target: { value: "next-pass" },
    });
    expect(submit).toBeEnabled();
  });

  it("rejects mismatched confirmation locally and clears every field", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<AccountPasswordPage endpoint="/api/ui/account/password" />);
    fillPasswords("current-pass", "next-pass", "different-pass");

    fireEvent.click(screen.getByRole("button", { name: "Change password" }));

    expect(screen.getByRole("alert")).toHaveTextContent(
      "New password and confirmation do not match.",
    );
    expectPasswordFieldsCleared();
    expect(screen.getByLabelText("Confirm new password")).toHaveFocus();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects reuse of the current password locally and clears every field", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<AccountPasswordPage endpoint="/api/ui/account/password" />);
    fillPasswords("same-pass", "same-pass", "same-pass");

    fireEvent.click(screen.getByRole("button", { name: "Change password" }));

    expect(screen.getByRole("alert")).toHaveTextContent(
      "New password must be different from current password.",
    );
    expectPasswordFieldsCleared();
    expect(screen.getByLabelText("New password")).toHaveFocus();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows an incorrect-current-password API error and clears every field", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        response(
          { detail: "Current password is incorrect." },
          { ok: false, status: 400 },
        ),
      ),
    );
    render(<AccountPasswordPage endpoint="/api/ui/account/password" />);
    fillPasswords();

    fireEvent.click(screen.getByRole("button", { name: "Change password" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Current password is incorrect.",
    );
    expectPasswordFieldsCleared();
    expect(screen.getByLabelText("Current password")).toHaveFocus();
  });

  it("clears every password field after any failed request", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        response(
          { detail: ["Request could not be validated."] },
          { ok: false, status: 422 },
        ),
      ),
    );
    render(<AccountPasswordPage endpoint="/api/ui/account/password" />);
    fillPasswords();

    fireEvent.click(screen.getByRole("button", { name: "Change password" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Request could not be validated.",
    );
    expectPasswordFieldsCleared();
  });

  it("submits successfully, clears every field, and shows the existing toast", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      response({ message: "Password changed successfully." }),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<AccountPasswordPage endpoint="/api/ui/account/password" />);
    fillPasswords();

    fireEvent.click(screen.getByRole("button", { name: "Change password" }));

    expect(
      await screen.findByText("Password changed successfully."),
    ).toBeInTheDocument();
    expectPasswordFieldsCleared();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/ui/account/password",
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
        body: JSON.stringify({
          current_password: "current-pass",
          new_password: "next-pass",
          confirm_new_password: "next-pass",
        }),
      }),
    );
  });

  it("prevents duplicate submissions while the request is pending", async () => {
    let resolveRequest!: (value: ReturnType<typeof response>) => void;
    const pending = new Promise<ReturnType<typeof response>>((resolve) => {
      resolveRequest = resolve;
    });
    const fetchMock = vi.fn().mockReturnValue(pending);
    vi.stubGlobal("fetch", fetchMock);
    render(<AccountPasswordPage endpoint="/api/ui/account/password" />);
    fillPasswords();
    const submit = screen.getByRole("button", { name: "Change password" });

    fireEvent.click(submit);
    fireEvent.click(submit);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const pendingSubmit = screen.getByRole("button", { name: "Changing…" });
    expect(pendingSubmit).toBeDisabled();
    expect(pendingSubmit.closest("form")).toHaveAttribute("aria-busy", "true");
    resolveRequest(response({ message: "Password changed successfully." }));
    expect(
      await screen.findByText("Password changed successfully."),
    ).toBeInTheDocument();
  });

  it("shows a stable generic error when the request cannot be completed", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    render(<AccountPasswordPage endpoint="/api/ui/account/password" />);
    fillPasswords();

    fireEvent.click(screen.getByRole("button", { name: "Change password" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Password could not be changed. Please try again.",
    );
    expectPasswordFieldsCleared();
  });

  it("hands authentication redirects back to the existing login flow", async () => {
    const onAuthenticationRequired = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        response(null, {
          redirected: true,
          url: "http://testserver/ui/login?return_to=/api/ui/account/password",
        }),
      ),
    );
    render(
      <AccountPasswordPage
        endpoint="/api/ui/account/password"
        onAuthenticationRequired={onAuthenticationRequired}
      />,
    );
    fillPasswords();

    fireEvent.click(screen.getByRole("button", { name: "Change password" }));

    await waitFor(() =>
      expect(onAuthenticationRequired).toHaveBeenCalledWith(
        "/ui/login?return_to=/ui/account/password",
      ),
    );
    expectPasswordFieldsCleared();
  });
});
