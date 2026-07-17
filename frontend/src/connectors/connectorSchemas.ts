import type { ConnectorSchema, FieldValue } from "./types";

export function defaultFormState(schema: ConnectorSchema): Record<string, FieldValue> {
  return Object.fromEntries(schema.fields.map((field) => [field.name, field.secret ? "" : field.default]));
}

export function clearSecrets(schema: ConnectorSchema, values: Record<string, FieldValue>): Record<string, FieldValue> {
  return { ...values, ...Object.fromEntries(schema.fields.filter((field) => field.secret).map((field) => [field.name, ""])) };
}
