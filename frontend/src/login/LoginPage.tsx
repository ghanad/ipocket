import { type FormEvent, useEffect, useRef, useState } from "react";

import { LoginApiError, login } from "./api";

interface LoginPageProps {
  endpoint: string;
  returnTo?: string;
  initialError?: string;
  initialUsername?: string;
  onNavigate?: (target: string) => void;
}

const GENERIC_REQUEST_ERROR = "Login could not be completed. Please try again.";

function defaultNavigate(target: string) {
  window.location.assign(target);
}

export function LoginPage({
  endpoint,
  returnTo = "",
  initialError = "",
  initialUsername = "",
  onNavigate = defaultNavigate,
}: LoginPageProps) {
  const [username, setUsername] = useState(initialUsername);
  const [password, setPassword] = useState("");
  const [error, setError] = useState(initialError);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const usernameRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (initialError) {
      passwordRef.current?.focus();
      return;
    }
    usernameRef.current?.focus();
  }, [initialError]);

  const complete = Boolean(username.trim() && password);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!complete || submittingRef.current) return;

    submittingRef.current = true;
    setSubmitting(true);
    setError("");
    try {
      const response = await login(endpoint, {
        username,
        password,
        return_to: returnTo,
      });
      setUsername("");
      setPassword("");
      onNavigate(response.redirect_to);
    } catch (requestError) {
      setPassword("");
      setError(
        requestError instanceof LoginApiError
          ? requestError.message
          : GENERIC_REQUEST_ERROR,
      );
      passwordRef.current?.focus();
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <div className="login-card">
        <div className="login-header">
          <div className="login-icon">ip</div>
          <h1>ipocket</h1>
          <p>Internal IP asset management</p>
        </div>
        {error && (
          <div className="alert alert-error" role="alert">
            <p className="alert-title">{error}</p>
          </div>
        )}
        <form
          method="post"
          action="/ui/login"
          className="login-form"
          aria-busy={submitting}
          onSubmit={submit}
        >
          <label className="field">
            <span>Username</span>
            <input
              ref={usernameRef}
              className="input"
              type="text"
              name="username"
              placeholder="Enter your username"
              required
              autoComplete="username"
              value={username}
              onChange={(event) => {
                setUsername(event.target.value);
                setError("");
              }}
            />
          </label>
          <label className="field">
            <span>Password</span>
            <input
              ref={passwordRef}
              className="input"
              type="password"
              name="password"
              placeholder="Enter your password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(event) => {
                setPassword(event.target.value);
                setError("");
              }}
            />
          </label>
          <button
            className="btn btn-primary btn-block"
            type="submit"
            disabled={!complete || submitting}
          >
            {submitting ? "Logging in…" : "Login"}
          </button>
          {submitting && (
            <span className="visually-hidden" role="status">
              Logging in
            </span>
          )}
        </form>
        <p className="login-footnote">Authorized personnel only</p>
      </div>
    </main>
  );
}
