import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setSuccess("");

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    setBusy(true);
    try {
      await register(fullName, email, password);
      setSuccess("Account created successfully. Redirecting to sign in…");
      setTimeout(() => navigate("/login", { replace: true }), 1500);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to create account";
      if (message.includes("409") || message.toLowerCase().includes("already")) {
        setError("An account with this email already exists");
      } else {
        setError(message);
      }
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
        <div className="eyebrow">CREATE ACCOUNT</div>
        <h1>Join your workspace</h1>
        <p className="muted">Enter your details to register.</p>
        {error && <div className="form-error">{error}</div>}
        {success && <div className="success-banner">{success}</div>}
        <label>
          Full Name
          <input
            required
            type="text"
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
            placeholder="Jane Doe"
          />
        </label>
        <label>
          Email
          <input
            required
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@company.com"
          />
        </label>
        <label>
          Password
          <input
            required
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="••••••••"
            minLength={8}
          />
        </label>
        <label>
          Confirm Password
          <input
            required
            type="password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            placeholder="••••••••"
            minLength={8}
          />
        </label>
        <button className="primary-button wide" disabled={busy}>
          {busy ? "Creating account…" : "Create account"}
        </button>
        <p className="muted center">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </form>
    </div>
  );
}