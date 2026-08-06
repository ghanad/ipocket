import {
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import { RowActions } from "../shared/RowActions";
import {
  ApiError,
  createRange,
  deleteRange,
  fetchRanges,
  updateRange,
} from "./api";
import { RangeDrawer } from "./RangeDrawer";
import type {
  RangeFormValues,
  RangeRow,
  RangesBootstrap,
} from "./types";

interface RangesPageProps {
  endpoint: string;
  initialEditId?: number;
  initialDeleteId?: number;
  bootstrap?: RangesBootstrap | null;
}

type DrawerMode = "create" | "edit" | "delete" | null;

const emptyValues: RangeFormValues = { name: "", cidr: "", notes: "" };

function valuesForRange(range: RangeRow): RangeFormValues {
  return {
    name: range.name,
    cidr: range.cidr,
    notes: range.notes ?? "",
  };
}

function normalized(values: RangeFormValues): RangeFormValues {
  return {
    name: values.name.trim(),
    cidr: values.cidr.trim(),
    notes: values.notes.trim(),
  };
}

export function RangesPage({
  endpoint,
  initialEditId,
  initialDeleteId,
  bootstrap,
}: RangesPageProps) {
  const [ranges, setRanges] = useState<RangeRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [drawerMode, setDrawerMode] = useState<DrawerMode>(
    bootstrap?.mode ?? null,
  );
  const [activeRange, setActiveRange] = useState<RangeRow | null>(
    bootstrap?.range
      ? {
          ...bootstrap.range,
          total_usable: null,
          used: null,
          free: null,
          utilization_percent: null,
        }
      : null,
  );
  const [values, setValues] = useState<RangeFormValues>(
    bootstrap?.values ??
      (bootstrap?.range
        ? {
            name: bootstrap.range.name,
            cidr: bootstrap.range.cidr,
            notes: bootstrap.range.notes ?? "",
          }
        : emptyValues),
  );
  const [initialValues, setInitialValues] = useState<RangeFormValues>(
    bootstrap?.values ??
      (bootstrap?.range
        ? {
            name: bootstrap.range.name,
            cidr: bootstrap.range.cidr,
            notes: bootstrap.range.notes ?? "",
          }
        : emptyValues),
  );
  const [errors, setErrors] = useState<string[]>(bootstrap?.errors ?? []);
  const [confirmName, setConfirmName] = useState(bootstrap?.confirm_name ?? "");
  const [acknowledged, setAcknowledged] = useState(false);
  const [saving, setSaving] = useState(false);
  const [initialQueryApplied, setInitialQueryApplied] = useState(false);

  const loadRanges = useCallback(
    async (showLoading = true) => {
      if (showLoading) {
        setLoading(true);
      }
      setLoadError(null);
      try {
        const response = await fetchRanges(endpoint);
        setRanges(response.ranges);
      } catch {
        setLoadError("IP ranges could not be loaded. Please try again.");
      } finally {
        if (showLoading) {
          setLoading(false);
        }
      }
    },
    [endpoint],
  );

  useEffect(() => {
    void loadRanges();
  }, [loadRanges]);

  useEffect(() => {
    if (initialQueryApplied || loading || bootstrap?.mode) {
      return;
    }
    const editRange = initialEditId
      ? ranges.find((range) => range.id === initialEditId)
      : undefined;
    const deleteTarget = initialDeleteId
      ? ranges.find((range) => range.id === initialDeleteId)
      : undefined;
    if (editRange) {
      openEdit(editRange);
    } else if (deleteTarget) {
      openDelete(deleteTarget);
    }
    setInitialQueryApplied(true);
  }, [
    bootstrap?.mode,
    initialDeleteId,
    initialEditId,
    initialQueryApplied,
    loading,
    ranges,
  ]);

  useEffect(() => {
    if (!activeRange) {
      return;
    }
    const freshRange = ranges.find((range) => range.id === activeRange.id);
    if (freshRange) {
      setActiveRange(freshRange);
    }
  }, [activeRange?.id, ranges]);

  const dirty = useMemo(
    () =>
      JSON.stringify(normalized(values)) !==
      JSON.stringify(normalized(initialValues)),
    [initialValues, values],
  );
  const formValid = Boolean(values.name.trim() && values.cidr.trim());
  const deleteValid = Boolean(
    activeRange &&
      acknowledged &&
      confirmName.trim() === activeRange.name,
  );

  function openCreate() {
    setDrawerMode("create");
    setActiveRange(null);
    setValues(emptyValues);
    setInitialValues(emptyValues);
    setErrors([]);
  }

  function openEdit(range: RangeRow) {
    const nextValues = valuesForRange(range);
    setDrawerMode("edit");
    setActiveRange(range);
    setValues(nextValues);
    setInitialValues(nextValues);
    setErrors([]);
  }

  function openDelete(range: RangeRow) {
    setDrawerMode("delete");
    setActiveRange(range);
    setConfirmName("");
    setAcknowledged(false);
    setErrors([]);
  }

  const closeDrawer = useCallback(() => {
    if (
      (drawerMode === "create" || drawerMode === "edit") &&
      dirty &&
      !window.confirm("Discard changes?")
    ) {
      return;
    }
    setDrawerMode(null);
    setErrors([]);
  }, [dirty, drawerMode]);

  function updateValue(field: keyof RangeFormValues, value: string) {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors([]);
  }

  async function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!dirty || !formValid || saving) {
      return;
    }
    setSaving(true);
    setErrors([]);
    try {
      await createRange(endpoint, values);
      setDrawerMode(null);
      await loadRanges(false);
    } catch (error) {
      setErrors(
        error instanceof ApiError
          ? error.messages
          : ["IP range could not be created."],
      );
    } finally {
      setSaving(false);
    }
  }

  async function submitEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeRange || !dirty || !formValid || saving) {
      return;
    }
    setSaving(true);
    setErrors([]);
    try {
      await updateRange(endpoint, activeRange.id, values);
      setDrawerMode(null);
      await loadRanges(false);
    } catch (error) {
      setErrors(
        error instanceof ApiError
          ? error.messages
          : ["IP range could not be updated."],
      );
    } finally {
      setSaving(false);
    }
  }

  async function submitDelete(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeRange || !deleteValid || saving) {
      return;
    }
    setSaving(true);
    setErrors([]);
    try {
      await deleteRange(endpoint, activeRange.id, confirmName);
      setDrawerMode(null);
      await loadRanges(false);
    } catch (error) {
      setErrors(
        error instanceof ApiError
          ? error.messages
          : ["IP range could not be deleted."],
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <section className="page-header">
        <div>
          <h1>IP Ranges</h1>
          <p className="page-subtitle">
            Define CIDR ranges and review utilization across active IP assets.
          </p>
        </div>
        <div className="page-header-actions">
          <button className="btn btn-primary" type="button" onClick={openCreate}>
            New Range
          </button>
        </div>
      </section>

      <section className="card table-card">
        <div className="card-header card-header-padded">
          <div>
            <h2>IP Ranges</h2>
            <p className="subtitle">
              Click used or free to review addresses within each range.
            </p>
          </div>
          {loadError && (
            <button
              className="btn btn-secondary btn-small"
              type="button"
              onClick={() => void loadRanges()}
            >
              Try again
            </button>
          )}
        </div>
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>CIDR</th>
                <th>Total usable</th>
                <th>Used</th>
                <th>Free</th>
                <th>Utilization</th>
                <th className="asset-actions-cell">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} className="empty-state" role="status">
                    Loading IP ranges…
                  </td>
                </tr>
              ) : loadError ? (
                <tr>
                  <td colSpan={7} className="empty-state" role="alert">
                    {loadError}
                  </td>
                </tr>
              ) : ranges.length === 0 ? (
                <tr>
                  <td colSpan={7} className="empty-state">
                    No ranges yet. Add ranges to see utilization.
                  </td>
                </tr>
              ) : (
                ranges.map((range) => (
                  <tr key={range.id} className="row-with-actions" tabIndex={0}>
                    <td>{range.name}</td>
                    <td>{range.cidr}</td>
                    <td>{range.total_usable ?? "—"}</td>
                    <td>
                      {range.used === null ? (
                        "—"
                      ) : (
                        <a
                          className="link"
                          href={`/ui/ranges/${range.id}/addresses?status=used#used`}
                        >
                          {range.used}
                        </a>
                      )}
                    </td>
                    <td>
                      {range.free === null ? (
                        "—"
                      ) : (
                        <a
                          className="link"
                          href={`/ui/ranges/${range.id}/addresses?status=free#free`}
                        >
                          {range.free}
                        </a>
                      )}
                    </td>
                    <td>
                      {range.utilization_percent === null
                        ? "—"
                        : `${range.utilization_percent.toFixed(1)}%`}
                    </td>
                    <td className="asset-actions-cell">
                      <RowActions
                        itemLabel={range.name}
                        onEdit={() => openEdit(range)}
                        actions={[
                          {
                            label: "Delete",
                            destructive: true,
                            onSelect: () => openDelete(range),
                          },
                        ]}
                      />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <RangeDrawer
        open={drawerMode === "create"}
        label="Add IP range"
        title="Add IP Range"
        subtitle="Use CIDR notation to group ranges for reporting."
        errors={drawerMode === "create" ? errors : []}
        footerStatus={dirty ? "Ready to create" : "Enter details"}
        primaryLabel={saving ? "Saving…" : "Save range"}
        primaryClassName="btn btn-primary"
        primaryDisabled={!dirty || !formValid || saving}
        onClose={closeDrawer}
        onSubmit={submitCreate}
      >
        <RangeFields values={values} onChange={updateValue} />
      </RangeDrawer>

      <RangeDrawer
        open={drawerMode === "edit"}
        label="Edit IP range"
        title="Edit IP Range"
        subtitle="Update the CIDR definition and notes for this range."
        errors={drawerMode === "edit" ? errors : []}
        footerStatus={
          activeRange ? (dirty ? "Ready to save" : "No changes yet") : "Choose range"
        }
        primaryLabel={saving ? "Saving…" : "Save changes"}
        primaryClassName="btn btn-primary"
        primaryDisabled={!activeRange || !dirty || !formValid || saving}
        onClose={closeDrawer}
        onSubmit={submitEdit}
      >
        <RangeFields values={values} onChange={updateValue} />
      </RangeDrawer>

      <RangeDrawer
        open={drawerMode === "delete"}
        label="Delete IP range"
        title="Delete IP Range"
        subtitle={activeRange?.name || "Permanent removal"}
        errors={drawerMode === "delete" ? errors : []}
        footerStatus={
          !activeRange
            ? "Choose range"
            : !acknowledged
              ? "Acknowledge delete"
              : deleteValid
                ? "Ready to delete"
                : "Type exact range name"
        }
        primaryLabel={saving ? "Deleting…" : "Delete permanently"}
        primaryClassName="btn btn-danger"
        primaryDisabled={!deleteValid || saving}
        onClose={closeDrawer}
        onSubmit={submitDelete}
        initialFocus="confirm"
      >
        <section className="ip-drawer-section">
          <h3 className="ip-drawer-delete-heading">Delete this range?</h3>
          <p className="ip-drawer-delete-warning">
            This action permanently removes the range.
          </p>
          <dl className="ip-drawer-delete-details">
            <div>
              <dt>Name</dt>
              <dd>{activeRange?.name ?? "—"}</dd>
            </div>
            <div>
              <dt>CIDR</dt>
              <dd className="mono">{activeRange?.cidr ?? "—"}</dd>
            </div>
            <div>
              <dt>Used addresses</dt>
              <dd>{activeRange?.used ?? "—"}</dd>
            </div>
          </dl>
          <label className="field field-inline">
            <input
              className="checkbox"
              type="checkbox"
              checked={acknowledged}
              onChange={(event) => setAcknowledged(event.target.checked)}
            />
            <span>I understand this cannot be undone</span>
          </label>
          <label className="field">
            <span>
              Type the range name to confirm:{" "}
              <strong>{activeRange?.name ?? "—"}</strong>
            </span>
            <input
              className="input"
              type="text"
              autoComplete="off"
              data-range-confirm
              value={confirmName}
              onChange={(event) => {
                setConfirmName(event.target.value);
                setErrors([]);
              }}
            />
          </label>
        </section>
      </RangeDrawer>
    </>
  );
}

function RangeFields({
  values,
  onChange,
}: {
  values: RangeFormValues;
  onChange: (field: keyof RangeFormValues, value: string) => void;
}) {
  return (
    <section className="ip-drawer-section">
      <h3>Range details</h3>
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
        <span>CIDR</span>
        <input
          className="input"
          type="text"
          required
          placeholder="192.168.10.0/24"
          value={values.cidr}
          onChange={(event) => onChange("cidr", event.target.value)}
        />
      </label>
      <label className="field">
        <span>Notes</span>
        <textarea
          className="textarea"
          rows={3}
          value={values.notes}
          onChange={(event) => onChange("notes", event.target.value)}
        />
      </label>
    </section>
  );
}
