import Link from "next/link";

export default function AuthenticationErrorPage() {
  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="auth-error-title">
        <span className="auth-brand-mark" aria-hidden="true">!</span>
        <p className="eyebrow">Authentication failed</p>
        <h1 id="auth-error-title">This sign-in link is invalid or expired</h1>
        <p>Magic links are single-use and expire after 15 minutes. Request a new link to continue.</p>
        <Link className="auth-primary-link" href="/auth/signin">Request a new link</Link>
      </section>
    </main>
  );
}
