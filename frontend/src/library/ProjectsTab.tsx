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
import type { DrawerMode, LibraryBootstrap, ProjectRow } from "./types";
import { useLibraryData } from "./useLibraryData";

interface ProjectValues {
  name: string;
  description: string;
  color: string;
}

const defaultColor = "#94a3b8";

function valuesFor(project: ProjectRow): ProjectValues {
  return {
    name: project.name,
    description: project.description ?? "",
    color: project.color,
  };
}

function normalized(values: ProjectValues): ProjectValues {
  return {
    name: values.name.trim(),
    description: values.description.trim(),
    color: values.color.trim().toLowerCase(),
  };
}

export function ProjectsTab({
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
    useLibraryData<ProjectRow>(endpoint, "projects", onPermissionChange);
  const bootstrapValues = {
    name: bootstrap?.values?.name ?? "",
    description: bootstrap?.values?.description ?? "",
    color: bootstrap?.values?.color ?? defaultColor,
  };
  const [mode, setMode] = useState<DrawerMode>(bootstrap?.mode ?? null);
  const [active, setActive] = useState<ProjectRow | null>(null);
  const [values, setValues] = useState<ProjectValues>(bootstrapValues);
  const [initialValues, setInitialValues] = useState<ProjectValues>(
    bootstrapValues,
  );
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
  const formValid = Boolean(values.name.trim());
  const deleteValid = Boolean(
    active && acknowledged && confirmName.trim() === active.name,
  );

  const openCreate = useCallback(() => {
    const next = {
      name: "",
      description: "",
      color: metadata?.default_color ?? defaultColor,
    };
    setMode("create");
    setActive(null);
    setValues(next);
    setInitialValues(next);
    setErrors([]);
    setSuccess(null);
  }, [metadata?.default_color]);

  const openEdit = useCallback((project: ProjectRow) => {
    const next = valuesFor(project);
    setMode("edit");
    setActive(project);
    setValues(next);
    setInitialValues(next);
    setErrors([]);
    setSuccess(null);
  }, []);

  const openDelete = useCallback((project: ProjectRow) => {
    setMode("delete");
    setActive(project);
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
      setInitialValues(valuesFor(editTarget));
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

  function updateValue(field: keyof ProjectValues, value: string) {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors([]);
  }

  async function submit(
    event: FormEvent<HTMLFormElement>,
    operation: "create" | "edit",
  ) {
    event.preventDefault();
    if (!dirty || !formValid || saving || (operation === "edit" && !active)) {
      return;
    }
    setSaving(true);
    setErrors([]);
    try {
      if (operation === "create") {
        await createLibraryItem<ProjectRow>(endpoint, "projects", values);
        setSuccess("Project created.");
      } else {
        await updateLibraryItem<ProjectRow>(
          endpoint,
          "projects",
          active!.id,
          values,
        );
        setSuccess("Project updated.");
      }
      setMode(null);
      onClearQuery();
      await load(false);
    } catch (error) {
      setErrors(
        error instanceof ApiError
          ? error.messages
          : [`Project could not be ${operation === "create" ? "created" : "updated"}.`],
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
      await deleteLibraryItem(endpoint, "projects", active.id, confirmName);
      setMode(null);
      setSuccess("Project deleted.");
      onClearQuery();
      await load(false);
    } catch (error) {
      setErrors(
        error instanceof ApiError
          ? error.messages
          : ["Project could not be deleted."],
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
            <h2>Existing projects</h2>
            <p className="subtitle">
              Keep the catalog of project ownership current.
            </p>
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
                <th>Description</th>
                <th>Color</th>
                <th>IPs</th>
                <th className="asset-actions-cell">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} className="empty-state" role="status">
                    Loading projects…
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
                    No projects yet.
                  </td>
                </tr>
              ) : (
                items.map((project) => (
                  <tr
                    key={project.id}
                    className={
                      metadata?.can_edit ? "row-with-actions" : undefined
                    }
                    tabIndex={metadata?.can_edit ? 0 : undefined}
                  >
                    <td>{project.name}</td>
                    <td>{project.description || "—"}</td>
                    <td>
                      <input
                        className="input input-color"
                        type="color"
                        value={project.color}
                        disabled
                        aria-label={`${project.name} color`}
                      />
                    </td>
                    <td>{project.usage_count}</td>
                    <td className="asset-actions-cell">
                      {metadata?.can_edit ? (
                        <RowActions
                          itemLabel={project.name}
                          onEdit={() => openEdit(project)}
                          actions={[
                            {
                              label: "Delete",
                              destructive: true,
                              onSelect: () => openDelete(project),
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
        formId="project-create-form"
        label="Create Project"
        title="Create Project"
        subtitle="Add a project for IP asset assignment."
        errors={mode === "create" ? errors : []}
        footerStatus={dirty ? "Ready to create" : "Enter details"}
        primaryLabel={saving ? "Creating…" : "Create project"}
        primaryDisabled={!dirty || !formValid || saving}
        onClose={closeDrawer}
        onSubmit={(event) => void submit(event, "create")}
      >
        <ProjectFields values={values} onChange={updateValue} />
      </LibraryDrawer>

      <LibraryDrawer
        open={mode === "edit"}
        formId="project-edit-form"
        label="Edit Project"
        title="Edit Project"
        subtitle="Update project details used across IP assets."
        errors={mode === "edit" ? errors : []}
        footerStatus={dirty ? "Ready to save" : "No changes yet"}
        primaryLabel={saving ? "Saving…" : "Save changes"}
        primaryDisabled={!active || !dirty || !formValid || saving}
        onClose={closeDrawer}
        onSubmit={(event) => void submit(event, "edit")}
      >
        <ProjectFields values={values} onChange={updateValue} />
      </LibraryDrawer>

      <LibraryDrawer
        open={mode === "delete"}
        formId="project-delete-form"
        label="Delete Project"
        title="Delete Project"
        subtitle={active?.name ?? "Permanent removal"}
        errors={mode === "delete" ? errors : []}
        footerStatus={
          !acknowledged
            ? "Acknowledge delete"
            : deleteValid
              ? "Ready to delete"
              : "Type exact project name"
        }
        primaryLabel={saving ? "Deleting…" : "Delete permanently"}
        primaryClassName="btn btn-danger"
        primaryDisabled={!deleteValid || saving}
        initialFocus="confirm"
        onClose={closeDrawer}
        onSubmit={(event) => void submitDelete(event)}
      >
        <DeleteFields
          entityLabel="project"
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

function ProjectFields({
  values,
  onChange,
}: {
  values: ProjectValues;
  onChange: (field: keyof ProjectValues, value: string) => void;
}) {
  return (
    <section className="ip-drawer-section">
      <h3>Project details</h3>
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
        <span>Description</span>
        <textarea
          className="textarea"
          rows={3}
          value={values.description}
          onChange={(event) => onChange("description", event.target.value)}
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
