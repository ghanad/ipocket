import {
  type CSSProperties,
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  ApiError,
  createLibraryItem,
  deleteLibraryItem,
  updateLibraryItem,
} from "./api";
import { DeleteFields } from "./DeleteFields";
import { LibraryDrawer } from "./LibraryDrawer";
import type { DrawerMode, LibraryBootstrap, TagRow } from "./types";
import { useLibraryData } from "./useLibraryData";

interface TagValues {
  name: string;
  color: string;
}

const defaultColor = "#e2e8f0";

function normalized(values: TagValues): TagValues {
  return {
    name: values.name.trim(),
    color: values.color.trim().toLowerCase(),
  };
}

export function TagsTab({
  endpoint,
  createRequest,
  initialEditId,
  initialDeleteId,
  onPermissionChange,
  onClearQuery,
  bootstrap,
}: {
  endpoint: string;
  createRequest: number;
  initialEditId?: number;
  initialDeleteId?: number;
  onPermissionChange: (canEdit: boolean) => void;
  onClearQuery: () => void;
  bootstrap?: LibraryBootstrap | null;
}) {
  const { items, metadata, loading, loadError, load } =
    useLibraryData<TagRow>(endpoint, "tags", onPermissionChange);
  const bootstrapValues = {
    name: bootstrap?.values?.name ?? "",
    color: bootstrap?.values?.color ?? defaultColor,
  };
  const [mode, setMode] = useState<DrawerMode>(bootstrap?.mode ?? null);
  const [active, setActive] = useState<TagRow | null>(null);
  const [values, setValues] = useState<TagValues>(bootstrapValues);
  const [initialValues, setInitialValues] =
    useState<TagValues>(bootstrapValues);
  const [errors, setErrors] = useState<string[]>(bootstrap?.errors ?? []);
  const [success, setSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [confirmName, setConfirmName] = useState(bootstrap?.confirm_name ?? "");
  const [acknowledged, setAcknowledged] = useState(false);
  const [queryApplied, setQueryApplied] = useState(false);
  const handledCreateRequest = useRef(0);

  const dirty = useMemo(
    () =>
      JSON.stringify(normalized(values)) !==
      JSON.stringify(normalized(initialValues)),
    [initialValues, values],
  );
  const deleteValid = Boolean(
    active && acknowledged && confirmName.trim() === active.name,
  );

  const openCreate = useCallback(() => {
    const next = {
      name: "",
      color: metadata?.suggested_color ?? defaultColor,
    };
    setMode("create");
    setActive(null);
    setValues(next);
    setInitialValues(next);
    setErrors([]);
    setSuccess(null);
  }, [metadata?.suggested_color]);

  const openEdit = useCallback((tag: TagRow) => {
    const next = { name: tag.name, color: tag.color };
    setMode("edit");
    setActive(tag);
    setValues(next);
    setInitialValues(next);
    setErrors([]);
    setSuccess(null);
  }, []);

  const openDelete = useCallback((tag: TagRow) => {
    setMode("delete");
    setActive(tag);
    setConfirmName("");
    setAcknowledged(false);
    setErrors([]);
    setSuccess(null);
  }, []);

  useEffect(() => {
    if (createRequest > handledCreateRequest.current) {
      handledCreateRequest.current = createRequest;
      openCreate();
    }
  }, [createRequest, openCreate]);

  useEffect(() => {
    if (loading || queryApplied) {
      return;
    }
    if (bootstrap?.mode === "create") {
      setQueryApplied(true);
      return;
    }
    const requestedId = bootstrap?.entity_id;
    const editTarget = (requestedId ?? initialEditId)
      ? items.find((item) => item.id === (requestedId ?? initialEditId))
      : undefined;
    const deleteTarget = (requestedId ?? initialDeleteId)
      ? items.find((item) => item.id === (requestedId ?? initialDeleteId))
      : undefined;
    if (editTarget && bootstrap?.mode === "edit") {
      setActive(editTarget);
      setInitialValues({ name: editTarget.name, color: editTarget.color });
    } else if (deleteTarget && bootstrap?.mode === "delete") {
      setActive(deleteTarget);
    } else if (editTarget) {
      openEdit(editTarget);
    } else if (deleteTarget) {
      openDelete(deleteTarget);
    }
    setQueryApplied(true);
  }, [
    initialDeleteId,
    initialEditId,
    bootstrap?.entity_id,
    bootstrap?.mode,
    items,
    loading,
    openDelete,
    openEdit,
    queryApplied,
  ]);

  const closeDrawer = useCallback(() => {
    if (
      (mode === "create" || mode === "edit") &&
      dirty &&
      !window.confirm("Discard changes?")
    ) {
      return;
    }
    setMode(null);
    setErrors([]);
    onClearQuery();
  }, [dirty, mode, onClearQuery]);

  function updateValue(field: keyof TagValues, value: string) {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors([]);
  }

  async function submit(
    event: FormEvent<HTMLFormElement>,
    operation: "create" | "edit",
  ) {
    event.preventDefault();
    if (
      !dirty ||
      !values.name.trim() ||
      saving ||
      (operation === "edit" && !active)
    ) {
      return;
    }
    setSaving(true);
    setErrors([]);
    try {
      if (operation === "create") {
        await createLibraryItem<TagRow>(endpoint, "tags", values);
        setSuccess("Tag created.");
      } else {
        await updateLibraryItem<TagRow>(
          endpoint,
          "tags",
          active!.id,
          values,
        );
        setSuccess("Tag updated.");
      }
      setMode(null);
      onClearQuery();
      await load(false);
    } catch (error) {
      setErrors(
        error instanceof ApiError
          ? error.messages
          : [`Tag could not be ${operation === "create" ? "created" : "updated"}.`],
      );
    } finally {
      setSaving(false);
    }
  }

  async function submitDelete(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!active || !deleteValid || saving) {
      return;
    }
    setSaving(true);
    setErrors([]);
    try {
      await deleteLibraryItem(endpoint, "tags", active.id, confirmName);
      setMode(null);
      setSuccess("Tag deleted.");
      onClearQuery();
      await load(false);
    } catch (error) {
      setErrors(
        error instanceof ApiError ? error.messages : ["Tag could not be deleted."],
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      {success && (
        <div className="toast toast-success library-success" role="status">
          <span className="toast-message">{success}</span>
        </div>
      )}
      <section className="card table-card tags-existing-card">
        <div className="card-header">
          <div>
            <h2>Existing tags</h2>
            <p className="subtitle">Edit, recolor, or remove tags as needed.</p>
          </div>
          {loadError && (
            <button
              className="btn btn-secondary btn-small"
              type="button"
              onClick={() => void load()}
            >
              Try again
            </button>
          )}
        </div>
        <div className="table-wrapper">
          <table className="table table-compact">
            <thead>
              <tr>
                <th>Name</th>
                <th>Color</th>
                <th>Preview</th>
                <th>IPs</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} className="empty-state" role="status">
                    Loading tags…
                  </td>
                </tr>
              ) : loadError ? (
                <tr>
                  <td colSpan={5} className="empty-state" role="alert">
                    {loadError}
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={5} className="empty-state">
                    No tags yet.
                  </td>
                </tr>
              ) : (
                items.map((tag) => (
                  <tr key={tag.id}>
                    <td>{tag.name}</td>
                    <td>
                      <input
                        className="input input-color"
                        type="color"
                        value={tag.color}
                        disabled
                        aria-label={`${tag.name} color`}
                      />
                    </td>
                    <td>
                      <span
                        className="tag tag-color"
                        style={{ "--tag-color": tag.color } as CSSProperties}
                      >
                        {tag.name}
                      </span>
                    </td>
                    <td>{tag.usage_count}</td>
                    <td className="asset-actions-cell">
                      {metadata?.can_edit ? (
                        <div className="table-actions">
                          <button
                            className="btn btn-secondary btn-small"
                            type="button"
                            onClick={() => openEdit(tag)}
                          >
                            Edit
                          </button>
                          <button
                            className="btn btn-danger btn-small"
                            type="button"
                            onClick={() => openDelete(tag)}
                          >
                            Delete
                          </button>
                        </div>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <LibraryDrawer
        open={mode === "create"}
        formId="tag-create-form"
        label="Create Tag"
        title="Create Tag"
        subtitle="Add reusable labels for IP assets."
        errors={mode === "create" ? errors : []}
        footerStatus={dirty ? "Ready to create" : "Enter details"}
        primaryLabel={saving ? "Creating…" : "Create tag"}
        primaryDisabled={!dirty || !values.name.trim() || saving}
        onClose={closeDrawer}
        onSubmit={(event) => void submit(event, "create")}
      >
        <TagFields values={values} onChange={updateValue} />
      </LibraryDrawer>

      <LibraryDrawer
        open={mode === "edit"}
        formId="tag-edit-form"
        label="Edit Tag"
        title="Edit Tag"
        subtitle="Update tag name and color."
        errors={mode === "edit" ? errors : []}
        footerStatus={dirty ? "Ready to save" : "No changes yet"}
        primaryLabel={saving ? "Saving…" : "Save changes"}
        primaryDisabled={!active || !dirty || !values.name.trim() || saving}
        onClose={closeDrawer}
        onSubmit={(event) => void submit(event, "edit")}
      >
        <TagFields values={values} onChange={updateValue} />
      </LibraryDrawer>

      <LibraryDrawer
        open={mode === "delete"}
        formId="tag-delete-form"
        label="Delete Tag"
        title="Delete Tag"
        subtitle={active?.name ?? "Permanent removal"}
        errors={mode === "delete" ? errors : []}
        footerStatus={
          !acknowledged
            ? "Acknowledge delete"
            : deleteValid
              ? "Ready to delete"
              : "Type exact tag name"
        }
        primaryLabel={saving ? "Deleting…" : "Delete permanently"}
        primaryClassName="btn btn-danger"
        primaryDisabled={!deleteValid || saving}
        initialFocus="confirm"
        onClose={closeDrawer}
        onSubmit={(event) => void submitDelete(event)}
      >
        <DeleteFields
          entityLabel="tag"
          name={active?.name ?? ""}
          usageCount={active?.usage_count ?? 0}
          acknowledged={acknowledged}
          confirmName={confirmName}
          onAcknowledge={setAcknowledged}
          onConfirmName={(value) => {
            setConfirmName(value);
            setErrors([]);
          }}
        />
      </LibraryDrawer>
    </>
  );
}

function TagFields({
  values,
  onChange,
}: {
  values: TagValues;
  onChange: (field: keyof TagValues, value: string) => void;
}) {
  return (
    <section className="ip-drawer-section">
      <h3>Tag details</h3>
      <label className="field">
        <span>Name</span>
        <input
          className="input"
          type="text"
          required
          value={values.name}
          onChange={(event) => onChange("name", event.target.value)}
        />
      </label>
      <label className="field">
        <span>Color</span>
        <input
          className="input input-color"
          type="color"
          value={values.color}
          onChange={(event) => onChange("color", event.target.value)}
        />
      </label>
    </section>
  );
}
