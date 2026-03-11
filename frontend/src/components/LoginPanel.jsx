export function LoginPanel({ onSubmit, pending, errorMessage }) {
  async function handleSubmit(event) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    await onSubmit({
      username: String(formData.get("username") || ""),
      password: String(formData.get("password") || "")
    });
  }

  return (
    <main className="login-shell">
      <section className="login-card">
        <p className="eyebrow">Secure Access</p>
        <h1>Hospital occupancy command center</h1>
        <p>Authenticate to access live forecasts, alert history, thresholds, and HIS retraining controls.</p>
        <form className="login-form" onSubmit={handleSubmit}>
          <label>
            <span>Username</span>
            <input defaultValue="admin" name="username" placeholder="admin" required />
          </label>
          <label>
            <span>Password</span>
            <input defaultValue="admin123" name="password" placeholder="admin123" required type="password" />
          </label>
          {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
          <button className="primary-button" disabled={pending} type="submit">
            {pending ? "Signing in..." : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}
