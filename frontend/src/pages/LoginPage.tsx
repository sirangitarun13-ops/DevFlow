import { FormEvent, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (user) return <Navigate to={(location.state as { from?: string } | null)?.from ?? "/"} replace />;
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(email, password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sign in");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="login-page">
      <div className="login-brand">
        <span className="brand-mark">D</span>
        <strong>DevFlow</strong>
        <span>SDLC intelligence workspace</span>
      </div>
      <form className="login-card" onSubmit={submit}>
        <div className="eyebrow">WELCOME BACK</div>
        <h1>Sign in to your workspace</h1>
        <p className="muted">Use your DevFlow account to continue.</p>
        {error && <div className="form-error">{error}</div>}
        <label>Email<input required type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" /></label>
        <label>Password<input required type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="••••••••" /></label>
        <button className="primary-button wide" disabled={busy} type="submit">{busy ? "Signing in…" : "Sign in"}</button>
        <small className="muted center">Your role controls available navigation and actions.</small>
        <p className="muted center">Don&apos;t have an account? <Link to="/register">Create an account</Link></p>
      </form>
    </div>
  );
}
