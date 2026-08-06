import type { ConnectorFieldSchema, FieldValue } from "./types";

export function ConnectorField({ field, value, disabled, onChange }: {
  field: ConnectorFieldSchema;
  value: FieldValue;
  disabled: boolean;
  onChange: (value: FieldValue) => void;
}) {
  if (field.type === "checkbox") {
    return <label className={`checkbox-field${field.span ? " field-span" : ""}`}>
      <input type="checkbox" name={field.name} checked={Boolean(value)} disabled={disabled} onChange={(event) => onChange(event.target.checked)} />
      {field.label}
    </label>;
  }
  return <label className={`field${field.span ? " field-span" : ""}`}>
    <span>{field.label}{field.required && <span aria-hidden="true"> *</span>}</span>
    {field.type === "select" ? (
      <select className="select" name={field.name} value={String(value)} required={field.required} disabled={disabled} onChange={(event) => onChange(event.target.value)}>
        {(field.options ?? []).map((option) => <option value={option} key={option}>{option}</option>)}
      </select>
    ) : (
      <input className="input" type={field.type} name={field.name} value={String(value)} placeholder={field.placeholder} required={field.required} min={field.min} max={field.max} disabled={disabled} autoComplete={field.secret ? "new-password" : undefined} onChange={(event) => onChange(event.target.value)} />
    )}
  </label>;
}
