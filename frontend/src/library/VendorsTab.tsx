import {
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { RowActions } from "../shared/RowActions";
import {
  ApiError,
  createLibraryItem,
  deleteLibraryItem,
  updateLibraryItem,
} from "./api";
import { DeleteFields } from "./DeleteFields";
import { LibraryDrawer } from "./LibraryDrawer";
import type { DrawerMode, LibraryBootstrap, VendorRow } from "./types";
import { useLibraryData } from "./useLibraryData";

export function VendorsTab({
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
    useLibraryData<VendorRow>(endpoint, "vendors", onPermissionChange);
  const bootstrapName = bootstrap?.values?.name ?? "";
  const [mode, setMode] = useState<DrawerMode>(bootstrap?.mode ?? null);
  const [active, setActive] = useState<VendorRow | null>(null);
  const [name, setName] = useState(bootstrapName);
  const [initialName, setInitialName] = useState(bootstrapName);
  const [errors, setErrors] = useState<string[]>(bootstrap?.errors ?? []);
  const [success, setSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [confirmName, setConfirmName] = useState(bootstrap?.confirm_name ?? "");
  const [acknowledged, setAcknowledged] = useState(false);
  const [queryApplied, setQueryApplied] = useState(false);
  const handledCreateRequest = useRef(0);

  const dirty = useMemo(
    () => name.trim() !== initialName.trim(),
    [initialName, name],
  );
  const deleteValid = Boolean(
    active && acknowledged && confirmName.trim() === active.name,
  );

  const openCreate = useCallback(() => {
    setMode("create");
    setActive(null);
    setName("");
    setInitialName("");
    setErrors([]);
    setSuccess(null);
  }, []);

  const openEdit = useCallback((vendor: VendorRow) => {
    setMode("edit");
    setActive(vendor);
    setName(vendor.name);
    setInitialName(vendor.name);
    setErrors([]);
    setSuccess(null);
  }, []);

  const openDelete = useCallback((vendor: VendorRow) => {
    setMode("delete");
    setActive(vendor);
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
      setInitialName(editTarget.name);
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

  async function submit(
    event: FormEvent<HTMLFormElement>,
    operation: "create" | "edit",
  ) {
    event.preventDefault();
    if (!dirty || !name.trim() || saving || (operation === "edit" && !active)) {
      return;
    }
    setSaving(true);
    setErrors([]);
    try {
      if (operation === "create") {
        await createLibraryItem<VendorRow>(endpoint, "vendors", { name });
        setSuccess("Vendor created.");
      } else {
        await updateLibraryItem<VendorRow>(
          endpoint,
          "vendors",
          active!.id,
          { name },
        );
        setSuccess("Vendor updated.");
      }
      setMode(null);
      onClearQuery();
      await load(false);
    } catch (error) {
      setErrors(
        error instanceof ApiError
          ? error.messages
          : [`Vendor could not be ${operation === "create" ? "created" : "updated"}.`],
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
      await deleteLibraryItem(endpoint, "vendors", active.id, confirmName);
      setMode(null);
      setSuccess("Vendor deleted.");
      onClearQuery();
      await load(false);
    } catch (error) {
      setErrors(
        error instanceof ApiError
          ? error.messages
          : ["Vendor could not be deleted."],
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
      <section className="card table-card projects-existing-card">
        <div className="card-header">
          <div>
            <h2>Existing vendors</h2>
            <p className="subtitle">Keep host vendor values consistent.</p>
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
                <th>IPs</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={3} className="empty-state" role="status">
                    Loading vendors…
                  </td>
                </tr>
              ) : loadError ? (
                <tr>
                  <td colSpan={3} className="empty-state" role="alert">
                    {loadError}
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={3} className="empty-state">
                    No vendors yet.
                  </td>
                </tr>
              ) : (
                items.map((vendor) => (
                  <tr
                    key={vendor.id}
                    className={
                      metadata?.can_edit ? "row-with-actions" : undefined
                    }
                    tabIndex={metadata?.can_edit ? 0 : undefined}
                  >
                    <td>{vendor.name}</td>
                    <td>{vendor.usage_count}</td>
                    <td className="asset-actions-cell">
                      {metadata?.can_edit ? (
                        <RowActions
                          itemLabel={vendor.name}
                          onEdit={() => openEdit(vendor)}
                          actions={[
                            {
                              label: "Delete",
                              destructive: true,
                              onSelect: () => openDelete(vendor),
                            },
                          ]}
                        />
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
        formId="vendor-create-form"
        label="Create Vendor"
        title="Create Vendor"
        subtitle="Add vendor names for host selection."
        errors={mode === "create" ? errors : []}
        footerStatus={dirty ? "Ready to create" : "Enter details"}
        primaryLabel={saving ? "Creating…" : "Create vendor"}
        primaryDisabled={!dirty || !name.trim() || saving}
        onClose={closeDrawer}
        onSubmit={(event) => void submit(event, "create")}
      >
        <VendorFields name={name} onChange={setNameAndClearErrors} />
      </LibraryDrawer>

      <LibraryDrawer
        open={mode === "edit"}
        formId="vendor-edit-form"
        label="Edit Vendor"
        title="Edit Vendor"
        subtitle="Update vendor name used in host forms."
        errors={mode === "edit" ? errors : []}
        footerStatus={dirty ? "Ready to save" : "No changes yet"}
        primaryLabel={saving ? "Saving…" : "Save changes"}
        primaryDisabled={!active || !dirty || !name.trim() || saving}
        onClose={closeDrawer}
        onSubmit={(event) => void submit(event, "edit")}
      >
        <VendorFields name={name} onChange={setNameAndClearErrors} />
      </LibraryDrawer>

      <LibraryDrawer
        open={mode === "delete"}
        formId="vendor-delete-form"
        label="Delete Vendor"
        title="Delete Vendor"
        subtitle={active?.name ?? "Permanent removal"}
        errors={mode === "delete" ? errors : []}
        footerStatus={
          !acknowledged
            ? "Acknowledge delete"
            : deleteValid
              ? "Ready to delete"
              : "Type exact vendor name"
        }
        primaryLabel={saving ? "Deleting…" : "Delete permanently"}
        primaryClassName="btn btn-danger"
        primaryDisabled={!deleteValid || saving}
        initialFocus="confirm"
        onClose={closeDrawer}
        onSubmit={(event) => void submitDelete(event)}
      >
        <DeleteFields
          entityLabel="vendor"
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

  function setNameAndClearErrors(value: string) {
    setName(value);
    setErrors([]);
  }
}

function VendorFields({
  name,
  onChange,
}: {
  name: string;
  onChange: (value: string) => void;
}) {
  return (
    <section className="ip-drawer-section">
      <h3>Vendor details</h3>
      <label className="field">
        <span>Name</span>
        <input
          className="input"
          type="text"
          required
          value={name}
          onChange={(event) => onChange(event.target.value)}
        />
      </label>
    </section>
  );
}
