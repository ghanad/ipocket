import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { UsersPage } from "./UsersPage";

const admin = {
  id: 1,
  username: "admin",
  role: "Admin" as const,
  role_label: "Superuser" as const,
  is_active: true,
  policy: {
    can_edit_role: false,
    can_deactivate: false,
    can_delete: false,
    delete_disabled_reason: "You cannot delete your own account.",
  },
};

const editor = {
  id: 2,
  username: "operator",
  role: "Editor" as const,
  role_label: "Editor" as const,
  is_active: true,
  policy: {
    can_edit_role: true,
    can_deactivate: true,
    can_delete: true,
    delete_disabled_reason: null,
  },
};

const viewer = {
  id: 3,
  username: "readonly",
  role: "Viewer" as const,
  role_label: "Viewer" as const,
  is_active: false,
  policy: {
    can_edit_role: true,
    can_deactivate: true,
    can_delete: true,
    delete_disabled_reason: null,
  },
};

const usersResponse = {
  actor: { id: 1, username: "admin", role: "Admin" as const },
  users: [admin, editor, viewer],
};

function response(
  payload: unknown,
  options: { ok?: boolean; status?: number } = {},
) {
  return {
    ok: options.ok ?? true,
    status: options.status ?? 200,
    redirected: false,
    json: async () => payload,
  };
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("UsersPage", () => {
  it("loads users and renders role and status badges", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(usersResponse)));

    render(<UsersPage endpoint="/api/ui/users" />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading users");
    expect(await screen.findByText("operator")).toBeInTheDocument();
    expect(screen.getByText("Superuser")).toHaveClass("pill-danger");
    expect(screen.getByText("Editor")).toHaveClass("pill-success");
    expect(screen.getByText("Viewer")).toHaveClass("pill");
    const table = screen.getByRole("table");
    expect(within(table).getAllByText("Active")).toHaveLength(2);
    expect(screen.getByText("Inactive")).toHaveClass("pill-warning");
  });

  it("renders the empty state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        response({ ...usersResponse, users: [] }),
      ),
    );

    render(<UsersPage endpoint="/api/ui/users" />);

    expect(await screen.findByText("No users found.")).toBeInTheDocument();
  });

  it("shows an API error and retries loading", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(response(usersResponse));
    vi.stubGlobal("fetch", fetchMock);

    render(<UsersPage endpoint="/api/ui/users" />);

    expect(
      await screen.findByText("Users could not be loaded. Please try again.", {
        exact: false,
      }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("operator")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("requires username and password before creating", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(usersResponse)));
    render(<UsersPage endpoint="/api/ui/users" />);
    await screen.findByText("operator");

    fireEvent.click(screen.getByRole("button", { name: "New User" }));
    const dialog = screen.getByRole("dialog", { name: "Create user" });
    const submit = within(dialog).getByRole("button", { name: "Create user" });
    expect(submit).toBeDisabled();

    fireEvent.change(within(dialog).getByLabelText("Username"), {
      target: { value: "new-user" },
    });
    expect(submit).toBeDisabled();
    fireEvent.change(within(dialog).getByLabelText("Password"), {
      target: { value: "secret" },
    });
    expect(submit).toBeEnabled();
  });

  it("creates a user, refreshes the list, and shows the existing toast language", async () => {
    const created = { ...viewer, id: 4, username: "new-user", is_active: true };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(usersResponse))
      .mockResolvedValueOnce(response(created, { status: 201 }))
      .mockResolvedValueOnce(
        response({ ...usersResponse, users: [...usersResponse.users, created] }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<UsersPage endpoint="/api/ui/users" />);
    await screen.findByText("operator");

    fireEvent.click(screen.getByRole("button", { name: "New User" }));
    const dialog = screen.getByRole("dialog", { name: "Create user" });
    fireEvent.change(within(dialog).getByLabelText("Username"), {
      target: { value: "new-user" },
    });
    fireEvent.change(within(dialog).getByLabelText("Password"), {
      target: { value: "secret" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Create user" }));

    expect(await screen.findByText("User created.")).toBeInTheDocument();
    expect(await screen.findByText("new-user")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/ui/users",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          username: "new-user",
          password: "secret",
          can_edit: true,
          is_active: true,
        }),
      }),
    );
  });

  it("shows duplicate errors and clears the create password", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(usersResponse))
      .mockResolvedValueOnce(
        response(
          { detail: "Username already exists." },
          { ok: false, status: 409 },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<UsersPage endpoint="/api/ui/users" />);
    await screen.findByText("operator");

    fireEvent.click(screen.getByRole("button", { name: "New User" }));
    const dialog = screen.getByRole("dialog", { name: "Create user" });
    fireEvent.change(within(dialog).getByLabelText("Username"), {
      target: { value: "operator" },
    });
    const password = within(dialog).getByLabelText("Password");
    fireEvent.change(password, { target: { value: "plaintext" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Create user" }));

    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "Username already exists.",
    );
    expect(password).toHaveValue("");
    expect(within(dialog).getByRole("button", { name: "Create user" })).toBeDisabled();
  });

  it("clears password state after closing the create drawer", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(usersResponse)));
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<UsersPage endpoint="/api/ui/users" />);
    await screen.findByText("operator");

    fireEvent.click(screen.getByRole("button", { name: "New User" }));
    let dialog = screen.getByRole("dialog", { name: "Create user" });
    fireEvent.change(within(dialog).getByLabelText("Password"), {
      target: { value: "temporary" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    fireEvent.click(screen.getByRole("button", { name: "New User" }));

    dialog = screen.getByRole("dialog", { name: "Create user" });
    expect(within(dialog).getByLabelText("Password")).toHaveValue("");
  });

  it("updates role and status with optional password rotation", async () => {
    const updated = { ...viewer, role: "Editor" as const, role_label: "Editor" as const };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(usersResponse))
      .mockResolvedValueOnce(response({ user: updated, changed: true }))
      .mockResolvedValueOnce(
        response({
          ...usersResponse,
          users: [admin, editor, updated],
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<UsersPage endpoint="/api/ui/users" />);
    await screen.findByText("readonly");

    const readonlyRow = screen.getByText("readonly").closest("tr")!;
    fireEvent.click(within(readonlyRow).getByRole("button", { name: "Edit" }));
    const dialog = screen.getByRole("dialog", { name: "Edit user" });
    fireEvent.click(within(dialog).getByLabelText("Can edit data"));
    fireEvent.click(within(dialog).getByLabelText("Active"));
    fireEvent.change(within(dialog).getByLabelText("New password (optional)"), {
      target: { value: "rotated" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(fetchMock.mock.calls[1][0]).toBe("/api/ui/users/3");
    expect(fetchMock.mock.calls[1][1]).toEqual(
      expect.objectContaining({ method: "PATCH" }),
    );
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toEqual({
      can_edit: true,
      is_active: true,
      password: "rotated",
    });
    expect(await screen.findByText("User updated.")).toBeInTheDocument();
  });

  it("keeps unchanged edit submission disabled and protects Superuser controls", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(usersResponse)));
    render(<UsersPage endpoint="/api/ui/users" />);
    await screen.findByText("admin");

    const adminRow = screen.getByText("admin").closest("tr")!;
    fireEvent.click(within(adminRow).getByRole("button", { name: "Edit" }));
    const dialog = screen.getByRole("dialog", { name: "Edit user" });
    expect(within(dialog).getByLabelText("Can edit data")).toBeDisabled();
    expect(within(dialog).getByLabelText("Active")).toBeDisabled();
    expect(within(dialog).getByRole("button", { name: "Save changes" })).toBeDisabled();
  });

  it("prevents the current user from opening delete", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(usersResponse)));
    render(<UsersPage endpoint="/api/ui/users" />);
    await screen.findByText("admin");

    const deleteButton = screen.getByRole("button", {
      name: "Delete admin (current user protected)",
    });
    expect(deleteButton).toBeDisabled();
    fireEvent.click(deleteButton);
    expect(screen.queryByRole("dialog", { name: "Delete user" })).not.toBeInTheDocument();
  });

  it("requires acknowledgement and exact username before successful deletion", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(usersResponse))
      .mockResolvedValueOnce(response(null, { status: 204 }))
      .mockResolvedValueOnce(
        response({ ...usersResponse, users: [admin, editor] }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<UsersPage endpoint="/api/ui/users" />);
    await screen.findByText("readonly");

    fireEvent.click(screen.getByRole("button", { name: "Delete readonly" }));
    const dialog = screen.getByRole("dialog", { name: "Delete user" });
    const submit = within(dialog).getByRole("button", {
      name: "Delete permanently",
    });
    expect(submit).toBeDisabled();
    fireEvent.click(
      within(dialog).getByLabelText("I understand this cannot be undone"),
    );
    fireEvent.change(within(dialog).getByLabelText(/Type username to confirm/), {
      target: { value: "Readonly" },
    });
    expect(submit).toBeDisabled();
    fireEvent.change(within(dialog).getByLabelText(/Type username to confirm/), {
      target: { value: "readonly" },
    });
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(await screen.findByText("User deleted.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/ui/users/3",
      expect.objectContaining({
        method: "DELETE",
        body: JSON.stringify({ confirm_username: "readonly" }),
      }),
    );
  });

  it("keeps the delete drawer open for last-active-Superuser policy errors", async () => {
    const protectedAdmin = {
      ...admin,
      id: 8,
      username: "other-admin",
      policy: { ...admin.policy, can_delete: true, delete_disabled_reason: null },
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        response({
          ...usersResponse,
          users: [admin, protectedAdmin],
        }),
      )
      .mockResolvedValueOnce(
        response(
          { detail: "Cannot delete the last active superuser." },
          { ok: false, status: 403 },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<UsersPage endpoint="/api/ui/users" />);
    await screen.findByText("other-admin");

    fireEvent.click(screen.getByRole("button", { name: "Delete other-admin" }));
    const dialog = screen.getByRole("dialog", { name: "Delete user" });
    fireEvent.click(
      within(dialog).getByLabelText("I understand this cannot be undone"),
    );
    fireEvent.change(within(dialog).getByLabelText(/Type username to confirm/), {
      target: { value: "other-admin" },
    });
    fireEvent.click(
      within(dialog).getByRole("button", { name: "Delete permanently" }),
    );

    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "Cannot delete the last active superuser.",
    );
    expect(dialog).toHaveClass("is-open");
  });

  it("asks before closing dirty drawers and preserves changes when declined", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(usersResponse)));
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<UsersPage endpoint="/api/ui/users" />);
    await screen.findByText("operator");

    fireEvent.click(screen.getByRole("button", { name: "New User" }));
    const dialog = screen.getByRole("dialog", { name: "Create user" });
    fireEvent.change(within(dialog).getByLabelText("Username"), {
      target: { value: "unsaved" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));

    expect(confirm).toHaveBeenCalledWith("Discard changes?");
    expect(dialog).toHaveClass("is-open");
    expect(within(dialog).getByLabelText("Username")).toHaveValue("unsaved");
  });

  it("prevents duplicate submissions while a mutation is pending", async () => {
    let resolveCreate!: (value: ReturnType<typeof response>) => void;
    const pending = new Promise<ReturnType<typeof response>>((resolve) => {
      resolveCreate = resolve;
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(usersResponse))
      .mockReturnValueOnce(pending)
      .mockResolvedValueOnce(response(usersResponse));
    vi.stubGlobal("fetch", fetchMock);
    render(<UsersPage endpoint="/api/ui/users" />);
    await screen.findByText("operator");

    fireEvent.click(screen.getByRole("button", { name: "New User" }));
    const dialog = screen.getByRole("dialog", { name: "Create user" });
    fireEvent.change(within(dialog).getByLabelText("Username"), {
      target: { value: "single-submit" },
    });
    fireEvent.change(within(dialog).getByLabelText("Password"), {
      target: { value: "secret" },
    });
    const submit = within(dialog).getByRole("button", { name: "Create user" });
    fireEvent.click(submit);
    fireEvent.click(submit);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(
      within(dialog).getByRole("button", { name: "Creating…" }),
    ).toBeDisabled();
    resolveCreate(response(viewer, { status: 201 }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  });
});
