import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LoginPage } from "./LoginPage";

function response(
  payload: unknown,
  options: { ok?: boolean; status?: number } = {},
) {
  return {
    ok: options.ok ?? true,
    status: options.status ?? 200,
    json: async () => payload,
  };
}

function fillCredentials(username = "viewer", password = "viewer-pass") {
  fireEvent.change(screen.getByLabelText("Username"), {
    target: { value: username },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: password },
  });
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("LoginPage", () => {
  it("renders the existing login content and focuses username initially", () => {
    render(<LoginPage endpoint="/api/ui/login" />);

    expect(
      screen.getByRole("heading", { name: "ipocket" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Internal IP asset management"),
    ).toBeInTheDocument();
    expect(screen.getByText("Authorized personnel only")).toBeInTheDocument();
    expect(screen.getByLabelText("Username")).toHaveFocus();
  });

  it("uses the appropriate credential autocomplete attributes", () => {
    render(<LoginPage endpoint="/api/ui/login" />);

    expect(screen.getByLabelText("Username")).toHaveAttribute(
      "autocomplete",
      "username",
    );
    expect(screen.getByLabelText("Password")).toHaveAttribute(
      "autocomplete",
      "current-password",
    );
  });

  it("keeps submit disabled until both credentials contain values", () => {
    render(<LoginPage endpoint="/api/ui/login" />);
    const submit = screen.getByRole("button", { name: "Login" });

    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "viewer" },
    });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "viewer-pass" },
    });
    expect(submit).toBeEnabled();
  });

  it("navigates to the successful server-approved return target", async () => {
    const onNavigate = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(response({ redirect_to: "/ui/audit-log" })),
    );
    render(
      <LoginPage
        endpoint="/api/ui/login"
        returnTo="/ui/audit-log"
        onNavigate={onNavigate}
      />,
    );
    fillCredentials();

    fireEvent.click(screen.getByRole("button", { name: "Login" }));

    await waitFor(() =>
      expect(onNavigate).toHaveBeenCalledWith("/ui/audit-log"),
    );
    expect(fetch).toHaveBeenCalledWith(
      "/api/ui/login",
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
        body: JSON.stringify({
          username: "viewer",
          password: "viewer-pass",
          return_to: "/ui/audit-log",
        }),
      }),
    );
  });

  it("uses the default IP assets target returned by the server", async () => {
    const onNavigate = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(response({ redirect_to: "/ui/ip-assets" })),
    );
    render(
      <LoginPage endpoint="/api/ui/login" onNavigate={onNavigate} />,
    );
    fillCredentials();

    fireEvent.click(screen.getByRole("button", { name: "Login" }));

    await waitFor(() =>
      expect(onNavigate).toHaveBeenCalledWith("/ui/ip-assets"),
    );
  });

  it("shows the generic invalid-credential error and preserves username", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        response(
          { detail: "Invalid username or password." },
          { ok: false, status: 401 },
        ),
      ),
    );
    render(<LoginPage endpoint="/api/ui/login" />);
    fillCredentials();

    fireEvent.click(screen.getByRole("button", { name: "Login" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invalid username or password.",
    );
    expect(screen.getByLabelText("Username")).toHaveValue("viewer");
  });

  it("shows the identical generic error for an inactive-user response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        response(
          { detail: "Invalid username or password." },
          { ok: false, status: 401 },
        ),
      ),
    );
    render(<LoginPage endpoint="/api/ui/login" />);
    fillCredentials("inactive", "correct-pass");

    fireEvent.click(screen.getByRole("button", { name: "Login" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invalid username or password.",
    );
  });

  it("clears and focuses password after a failed request", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        response(
          { detail: "Invalid username or password." },
          { ok: false, status: 401 },
        ),
      ),
    );
    render(<LoginPage endpoint="/api/ui/login" />);
    fillCredentials();

    fireEvent.click(screen.getByRole("button", { name: "Login" }));

    await screen.findByRole("alert");
    expect(screen.getByLabelText("Password")).toHaveValue("");
    expect(screen.getByLabelText("Password")).toHaveFocus();
  });

  it("prevents duplicate submissions while login is pending", async () => {
    let resolveRequest!: (value: ReturnType<typeof response>) => void;
    const pending = new Promise<ReturnType<typeof response>>((resolve) => {
      resolveRequest = resolve;
    });
    const fetchMock = vi.fn().mockReturnValue(pending);
    vi.stubGlobal("fetch", fetchMock);
    render(<LoginPage endpoint="/api/ui/login" onNavigate={vi.fn()} />);
    fillCredentials();
    const submit = screen.getByRole("button", { name: "Login" });

    fireEvent.click(submit);
    fireEvent.click(submit);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Logging in…" })).toBeDisabled();
    expect(submit.closest("form")).toHaveAttribute("aria-busy", "true");
    expect(screen.getByRole("status")).toHaveTextContent("Logging in");
    resolveRequest(response({ redirect_to: "/ui/ip-assets" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
  });

  it("handles network and unexpected API responses with a generic error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    render(<LoginPage endpoint="/api/ui/login" />);
    fillCredentials();

    fireEvent.click(screen.getByRole("button", { name: "Login" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Login could not be completed. Please try again.",
    );
    expect(screen.queryByText("offline")).not.toBeInTheDocument();
  });

  it("clears both credentials after successful submission", async () => {
    const onNavigate = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(response({ redirect_to: "/ui/ip-assets" })),
    );
    render(
      <LoginPage endpoint="/api/ui/login" onNavigate={onNavigate} />,
    );
    fillCredentials();

    fireEvent.click(screen.getByRole("button", { name: "Login" }));

    await waitFor(() => expect(onNavigate).toHaveBeenCalled());
    expect(screen.getByLabelText("Username")).toHaveValue("");
    expect(screen.getByLabelText("Password")).toHaveValue("");
  });
});
