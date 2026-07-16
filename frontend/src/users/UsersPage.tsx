import {
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  ApiError,
  createUser,
  deleteUser,
  fetchUsers,
  updateUser,
} from "./api";
import type {
  CreateUserValues,
  CurrentActor,
  EditUserValues,
  UserRow,
  UsersBootstrap,
} from "./types";
import { UserDrawer } from "./UserDrawer";

interface UsersPageProps {
  endpoint: string;
  bootstrap?: UsersBootstrap | null;
}

type DrawerMode = "create" | "edit" | "delete" | null;

const emptyCreate: CreateUserValues = {
  username: "",
  password: "",
  can_edit: true,
  is_active: true,
};

const emptyEdit: EditUserValues = {
  password: "",
  can_edit: false,
  is_active: true,
};

function editValuesFor(user: UserRow): EditUserValues {
  return {
    password: "",
    can_edit: user.role === "Editor" || user.role === "Admin",
    is_active: user.is_active,
  };
}

function errorMessages(error: unknown, fallback: string): string[] {
  return error instanceof ApiError ? error.messages : [fallback];
}

export function UsersPage({ endpoint, bootstrap }: UsersPageProps) {
  const [users, setUsers] = useState<UserRow[]>([]);
  const [actor, setActor] = useState<CurrentActor | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [drawerMode, setDrawerMode] = useState<DrawerMode>(
    bootstrap?.mode === "create" ? "create" : null,
  );
  const [activeUser, setActiveUser] = useState<UserRow | null>(null);
  const [createValues, setCreateValues] = useState<CreateUserValues>(() => ({
    ...emptyCreate,
    username: bootstrap?.mode === "create" ? bootstrap.form.username ?? "" : "",
    can_edit:
      bootstrap?.mode === "create"
        ? bootstrap.form.can_edit === "1"
        : emptyCreate.can_edit,
    is_active:
      bootstrap?.mode === "create"
        ? bootstrap.form.is_active === "1"
        : emptyCreate.is_active,
  }));
  const [editValues, setEditValues] = useState<EditUserValues>(emptyEdit);
  const [initialEditValues, setInitialEditValues] =
    useState<EditUserValues>(emptyEdit);
  const [errors, setErrors] = useState<string[]>(bootstrap?.errors ?? []);
  const [acknowledged, setAcknowledged] = useState(false);
  const [confirmUsername, setConfirmUsername] = useState(
    bootstrap?.mode === "delete" ? bootstrap.form.confirm_username ?? "" : "",
  );
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [legacyApplied, setLegacyApplied] = useState(
    !bootstrap || bootstrap.mode === "create",
  );

  const loadUsers = useCallback(
    async (showLoading = true) => {
      if (showLoading) setLoading(true);
      setLoadError(null);
      try {
        const response = await fetchUsers(endpoint);
        setUsers(response.users);
        setActor(response.actor);
      } catch {
        setLoadError("Users could not be loaded. Please try again.");
      } finally {
        if (showLoading) setLoading(false);
      }
    },
    [endpoint],
  );

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

  useEffect(() => {
    if (legacyApplied || loading || !bootstrap) return;
    const id = Number.parseInt(bootstrap.form.id ?? "", 10);
    const target = users.find((user) => user.id === id);
    if (target && bootstrap.mode === "edit") {
      const next = {
        ...editValuesFor(target),
        can_edit: bootstrap.form.can_edit === "1",
        is_active: bootstrap.form.is_active === "1",
      };
      setActiveUser(target);
      setEditValues(next);
      setInitialEditValues(editValuesFor(target));
      setDrawerMode("edit");
    } else if (target && bootstrap.mode === "delete") {
      setActiveUser(target);
      setAcknowledged(false);
      setDrawerMode("delete");
    }
    setLegacyApplied(true);
  }, [bootstrap, legacyApplied, loading, users]);

  useEffect(() => {
    if (!activeUser) return;
    const fresh = users.find((user) => user.id === activeUser.id);
    if (fresh) setActiveUser(fresh);
  }, [activeUser?.id, users]);

  const createDirty = useMemo(
    () =>
      createValues.username !== emptyCreate.username ||
      createValues.password !== emptyCreate.password ||
      createValues.can_edit !== emptyCreate.can_edit ||
      createValues.is_active !== emptyCreate.is_active,
    [createValues],
  );
  const editDirty = useMemo(
    () =>
      editValues.can_edit !== initialEditValues.can_edit ||
      editValues.is_active !== initialEditValues.is_active ||
      editValues.password !== "",
    [editValues, initialEditValues],
  );
  const createValid = Boolean(
    createValues.username.trim() && createValues.password,
  );
  const deleteValid = Boolean(
    activeUser &&
      acknowledged &&
      confirmUsername.trim() === activeUser.username,
  );

  function openCreate() {
    setDrawerMode("create");
    setActiveUser(null);
    setCreateValues(emptyCreate);
    setErrors([]);
  }

  function openEdit(user: UserRow) {
    const next = editValuesFor(user);
    setDrawerMode("edit");
    setActiveUser(user);
    setEditValues(next);
    setInitialEditValues(next);
    setErrors([]);
  }

  function openDelete(user: UserRow) {
    if (!user.policy.can_delete) return;
    setDrawerMode("delete");
    setActiveUser(user);
    setAcknowledged(false);
    setConfirmUsername("");
    setErrors([]);
  }

  const closeDrawer = useCallback(() => {
    const dirty =
      drawerMode === "create" ? createDirty : drawerMode === "edit" && editDirty;
    if (dirty && !window.confirm("Discard changes?")) return;
    setDrawerMode(null);
    setActiveUser(null);
    setCreateValues(emptyCreate);
    setEditValues(emptyEdit);
    setInitialEditValues(emptyEdit);
    setConfirmUsername("");
    setAcknowledged(false);
    setErrors([]);
  }, [createDirty, drawerMode, editDirty]);

  async function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!createValid || saving) return;
    setSaving(true);
    setErrors([]);
    try {
      await createUser(endpoint, createValues);
      setCreateValues(emptyCreate);
      setDrawerMode(null);
      setToast("User created.");
      await loadUsers(false);
    } catch (error) {
      setCreateValues((current) => ({ ...current, password: "" }));
      setErrors(errorMessages(error, "User could not be created."));
    } finally {
      setSaving(false);
    }
  }

  async function submitEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeUser || !editDirty || saving) return;
    setSaving(true);
    setErrors([]);
    try {
      await updateUser(endpoint, activeUser.id, editValues);
      setEditValues(emptyEdit);
      setDrawerMode(null);
      setActiveUser(null);
      setToast("User updated.");
      await loadUsers(false);
    } catch (error) {
      setEditValues((current) => ({ ...current, password: "" }));
      setErrors(errorMessages(error, "User could not be updated."));
    } finally {
      setSaving(false);
    }
  }

  async function submitDelete(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeUser || !deleteValid || saving) return;
    setSaving(true);
    setErrors([]);
    try {
      await deleteUser(endpoint, activeUser.id, confirmUsername);
      setDrawerMode(null);
      setActiveUser(null);
      setConfirmUsername("");
      setAcknowledged(false);
      setToast("User deleted.");
      await loadUsers(false);
    } catch (error) {
      setErrors(errorMessages(error, "User could not be deleted."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      {toast && (
        <div className="toast-container" role="status">
          <div className="toast toast-success">
            <span className="toast-message">{toast}</span>
            <button
              className="toast-close"
              type="button"
              aria-label="Dismiss notification"
              onClick={() => setToast(null)}
            >
              ×
            </button>
          </div>
        </div>
      )}

      <section className="page-header">
        <div>
          <p className="eyebrow">Access</p>
          <h1>User Management</h1>
          <p className="subtitle">
            Create users and manage editor access. This page is restricted to
            superusers.
          </p>
        </div>
        <div className="page-header-actions">
          <button className="btn btn-primary" type="button" onClick={openCreate}>
            New User
          </button>
        </div>
      </section>

      <section className="card table-card">
        <div className="table-wrapper">
          <table className="table table-compact">
            <thead>
              <tr>
                <th>Username</th>
                <th>Role</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={4} className="empty-state" role="status">
                    Loading users…
                  </td>
                </tr>
              ) : loadError ? (
                <tr>
                  <td colSpan={4} className="empty-state" role="alert">
                    {loadError}{" "}
                    <button
                      className="btn btn-secondary btn-small"
                      type="button"
                      onClick={() => void loadUsers()}
                    >
                      Try again
                    </button>
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={4} className="empty-state">
                    No users found.
                  </td>
                </tr>
              ) : (
                users.map((user) => (
                  <tr key={user.id}>
                    <td>{user.username}</td>
                    <td>
                      <span
                        className={
                          user.role === "Admin"
                            ? "pill pill-danger"
                            : user.role === "Editor"
                              ? "pill pill-success"
                              : "pill"
                        }
                      >
                        {user.role_label}
                      </span>
                    </td>
                    <td>
                      <span
                        className={
                          user.is_active
                            ? "pill pill-success"
                            : "pill pill-warning"
                        }
                      >
                        {user.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="asset-actions-cell">
                      <div className="table-actions">
                        <button
                          className="btn btn-secondary btn-small"
                          type="button"
                          onClick={() => openEdit(user)}
                        >
                          Edit
                        </button>
                        <button
                          className="btn btn-danger btn-small"
                          type="button"
                          disabled={!user.policy.can_delete}
                          title={user.policy.delete_disabled_reason ?? undefined}
                          aria-label={
                            user.id === actor?.id
                              ? `Delete ${user.username} (current user protected)`
                              : `Delete ${user.username}`
                          }
                          onClick={() => openDelete(user)}
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <UserDrawer
        open={drawerMode === "create"}
        formId="user-create-form"
        label="Create user"
        title="Create User"
        subtitle="Add a new account for UI/API login."
        errors={drawerMode === "create" ? errors : []}
        footerStatus={createDirty ? "Ready to create" : "Enter details"}
        primaryLabel={saving ? "Creating…" : "Create user"}
        primaryDisabled={!createValid || saving}
        onClose={closeDrawer}
        onSubmit={submitCreate}
      >
        <section className="ip-drawer-section">
          <h3>User details</h3>
          <label className="field">
            <span>Username</span>
            <input
              className="input"
              type="text"
              required
              autoComplete="username"
              value={createValues.username}
              onChange={(event) => {
                setCreateValues((current) => ({
                  ...current,
                  username: event.target.value,
                }));
                setErrors([]);
              }}
            />
          </label>
          <label className="field">
            <span>Password</span>
            <input
              className="input"
              type="password"
              required
              autoComplete="new-password"
              value={createValues.password}
              onChange={(event) => {
                setCreateValues((current) => ({
                  ...current,
                  password: event.target.value,
                }));
                setErrors([]);
              }}
            />
          </label>
          <UserCheckbox
            label="Can edit data"
            checked={createValues.can_edit}
            onChange={(value) =>
              setCreateValues((current) => ({ ...current, can_edit: value }))
            }
          />
          <UserCheckbox
            label="Active"
            checked={createValues.is_active}
            onChange={(value) =>
              setCreateValues((current) => ({ ...current, is_active: value }))
            }
          />
        </section>
      </UserDrawer>

      <UserDrawer
        open={drawerMode === "edit"}
        formId="user-edit-form"
        label="Edit user"
        title="Edit User"
        subtitle={activeUser?.username ?? "Select a user"}
        errors={drawerMode === "edit" ? errors : []}
        footerStatus={editDirty ? "Ready to save" : "No changes yet"}
        primaryLabel={saving ? "Saving…" : "Save changes"}
        primaryDisabled={!activeUser || !editDirty || saving}
        onClose={closeDrawer}
        onSubmit={submitEdit}
      >
        <section className="ip-drawer-section">
          <h3>Access controls</h3>
          <label className="field">
            <span>Username</span>
            <input
              className="input"
              type="text"
              value={activeUser?.username ?? ""}
              readOnly
            />
          </label>
          <UserCheckbox
            label="Can edit data"
            checked={editValues.can_edit}
            disabled={!activeUser?.policy.can_edit_role}
            onChange={(value) => {
              setEditValues((current) => ({ ...current, can_edit: value }));
              setErrors([]);
            }}
          />
          <UserCheckbox
            label="Active"
            checked={editValues.is_active}
            disabled={
              Boolean(activeUser?.is_active) &&
              !activeUser?.policy.can_deactivate
            }
            onChange={(value) => {
              setEditValues((current) => ({ ...current, is_active: value }));
              setErrors([]);
            }}
          />
          <label className="field">
            <span>New password (optional)</span>
            <input
              className="input"
              type="password"
              autoComplete="new-password"
              placeholder="Leave empty to keep current password"
              value={editValues.password}
              onChange={(event) => {
                setEditValues((current) => ({
                  ...current,
                  password: event.target.value,
                }));
                setErrors([]);
              }}
            />
          </label>
        </section>
      </UserDrawer>

      <UserDrawer
        open={drawerMode === "delete"}
        formId="user-delete-form"
        label="Delete user"
        title="Delete User"
        subtitle={activeUser?.username ?? "Permanent removal"}
        errors={drawerMode === "delete" ? errors : []}
        footerStatus={
          !acknowledged
            ? "Acknowledge delete"
            : deleteValid
              ? "Ready to delete"
              : "Type exact username"
        }
        primaryLabel={saving ? "Deleting…" : "Delete permanently"}
        primaryClassName="btn btn-danger"
        primaryDisabled={!deleteValid || saving}
        initialFocus="confirm"
        onClose={closeDrawer}
        onSubmit={submitDelete}
      >
        <section className="ip-drawer-section">
          <h3 className="ip-drawer-delete-heading">Delete this user?</h3>
          <p className="ip-drawer-delete-warning">
            This action cannot be undone.
          </p>
          <dl className="ip-drawer-delete-details">
            <div>
              <dt>Username</dt>
              <dd>{activeUser?.username ?? "—"}</dd>
            </div>
          </dl>
          <UserCheckbox
            label="I understand this cannot be undone"
            checked={acknowledged}
            onChange={setAcknowledged}
          />
          <label className="field">
            <span>
              Type username to confirm:{" "}
              <strong>{activeUser?.username ?? "—"}</strong>
            </span>
            <input
              className="input"
              type="text"
              autoComplete="off"
              data-user-confirm
              value={confirmUsername}
              onChange={(event) => {
                setConfirmUsername(event.target.value);
                setErrors([]);
              }}
            />
          </label>
        </section>
      </UserDrawer>
    </>
  );
}

function UserCheckbox({
  label,
  checked,
  disabled = false,
  onChange,
}: {
  label: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="checkbox-field">
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
      />
      {label}
    </label>
  );
}
