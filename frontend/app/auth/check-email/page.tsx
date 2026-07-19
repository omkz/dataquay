import Link from "next/link";

export default function CheckEmailPage() {
  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="check-email-title">
        <span className="auth-brand-mark" aria-hidden="true">MAIL</span>
        <p className="eyebrow">Magic link sent</p>
        <h1 id="check-email-title">Check your email</h1>
        <p>Open the latest DataQuay message and use its sign-in link. The link expires after 15 minutes.</p>
        <Link className="auth-secondary-link" href="/auth/signin">Use another email</Link>
      </section>
    </main>
  );
}
