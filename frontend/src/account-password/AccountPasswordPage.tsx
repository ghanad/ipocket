import {
  type FormEvent,
  type RefObject,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  AccountPasswordApiError,
  type AccountPasswordValues,
  changePassword,
} from "./api";

interface AccountPasswordPageProps {
  endpoint: string;
  initialErrors?: string[];
  onAuthenticationRequired?: (loginUrl: string) => void;
}

type PasswordField = keyof AccountPasswordValues;

const emptyValues: AccountPasswordValues = {
  current_password: "",
  new_password: "",
  confirm_new_password: "",
};

const labels: Record<PasswordField, string> = {
  current_password: "Current password",
  new_password: "New password",
  confirm_new_password: "Confirm new password",
};

function defaultAuthenticationRedirect(loginUrl: string) {
  window.location.assign(loginUrl);
}

function firstInvalidField(messages: string[]): PasswordField {
  if (
    messages.some((message) => message.startsWith("Confirm new password")) ||
    messages.includes("New password and confirmation do not match.")
  ) {
    return "confirm_new_password";
  }
  if (
    messages.some((message) => message.startsWith("New password")) ||
    messages.includes("New password must be different from current password.")
  ) {
    return "new_password";
  }
  return "current_password";
}

export function AccountPasswordPage({
  endpoint,
  initialErrors = [],
  onAuthenticationRequired = defaultAuthenticationRedirect,
}: AccountPasswordPageProps) {
  const [values, setValues] = useState<AccountPasswordValues>(emptyValues);
  const [errors, setErrors] = useState<string[]>(initialErrors);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [focusField, setFocusField] = useState<PasswordField | null>(
    initialErrors.length ? firstInvalidField(initialErrors) : null,
  );
  const currentRef = useRef<HTMLInputElement>(null);
  const newRef = useRef<HTMLInputElement>(null);
  const confirmRef = useRef<HTMLInputElement>(null);

  const refs: Record<PasswordField, RefObject<HTMLInputElement | null>> = {
    current_password: currentRef,
    new_password: newRef,
    confirm_new_password: confirmRef,
  };

  useEffect(() => {
    if (!focusField) return;
    refs[focusField].current?.focus();
    setFocusField(null);
  }, [focusField]);

  const complete = Boolean(
    values.current_password &&
      values.new_password &&
      values.confirm_new_password,
  );

  function updateValue(field: PasswordField, value: string) {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors([]);
  }

  function fail(messages: string[]) {
    setValues(emptyValues);
    setErrors(messages);
    setFocusField(firstInvalidField(messages));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!complete || submitting) return;

    if (values.new_password !== values.confirm_new_password) {
      fail(["New password and confirmation do not match."]);
      return;
    }
    if (values.current_password === values.new_password) {
      fail(["New password must be different from current password."]);
      return;
    }

    setSubmitting(true);
    setErrors([]);
    try {
      const response = await changePassword(endpoint, values);
      setValues(emptyValues);
      setToast(response.message);
      setFocusField("current_password");
    } catch (error) {
      if (error instanceof AccountPasswordApiError && error.loginUrl) {
        setValues(emptyValues);
        onAuthenticationRequired(error.loginUrl);
        return;
      }
      fail(
        error instanceof AccountPasswordApiError
          ? error.messages
          : ["Password could not be changed. Please try again."],
      );
    } finally {
      setSubmitting(false);
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
          <h1>Change Password</h1>
          <p className="subtitle">
            Update your account password for UI and API login.
          </p>
        </div>
      </section>

      <section className="card account-password-card">
        {errors.length > 0 && (
          <div className="alert alert-error" role="alert">
            <p className="alert-title">Could not change password</p>
            <ul className="alert-list">
              {errors.map((error) => (
                <li key={error}>{error}</li>
              ))}
            </ul>
          </div>
        )}
        <form className="form-grid" aria-busy={submitting} onSubmit={submit}>
          {(Object.keys(labels) as PasswordField[]).map((field) => (
            <label className="field" key={field}>
              <span>{labels[field]}</span>
              <input
                ref={refs[field]}
                className="input"
                type="password"
                required
                autoComplete={
                  field === "current_password"
                    ? "current-password"
                    : "new-password"
                }
                value={values[field]}
                onChange={(event) => updateValue(field, event.target.value)}
              />
            </label>
          ))}
          <div className="form-actions">
            <button
              className="btn btn-primary"
              type="submit"
              disabled={!complete || submitting}
            >
              {submitting ? "Changing…" : "Change password"}
            </button>
            {submitting && (
              <span className="visually-hidden" role="status">
                Changing password
              </span>
            )}
          </div>
        </form>
      </section>
    </>
  );
}
