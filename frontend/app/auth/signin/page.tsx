import { AuthError } from "next-auth";
import { redirect } from "next/navigation";

import { auth, signIn } from "@/auth";

function safeCallbackUrl(value: string | string[] | undefined) {
  const callbackUrl = Array.isArray(value) ? value[0] : value;
  return callbackUrl?.startsWith("/") && !callbackUrl.startsWith("//")
    ? callbackUrl
    : "/";
}

export default async function SignInPage({
  searchParams,
}: {
  searchParams: Promise<{ callbackUrl?: string | string[]; error?: string }>;
}) {
  const session = await auth();
  const params = await searchParams;
  const callbackUrl = safeCallbackUrl(params.callbackUrl);

  if (session?.user) redirect(callbackUrl);

  async function requestMagicLink(formData: FormData) {
    "use server";
    const email = formData.get("email");
    if (typeof email !== "string" || !email.trim()) {
      redirect(`/auth/signin?error=EmailRequired&callbackUrl=${encodeURIComponent(callbackUrl)}`);
    }

    try {
      await signIn("nodemailer", {
        email: email.trim(),
        redirectTo: callbackUrl,
      });
    } catch (error) {
      if (error instanceof AuthError) {
        redirect(`/auth/signin?error=EmailSignIn&callbackUrl=${encodeURIComponent(callbackUrl)}`);
      }
      throw error;
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="sign-in-title">
        <span className="auth-brand-mark" aria-hidden="true">DQ</span>
        <p className="eyebrow">DataQuay access</p>
        <h1 id="sign-in-title">Sign in with email</h1>
        <p>We will send a single-use link. No password is required.</p>
        {params.error ? (
          <div className="auth-error" role="alert">
            The sign-in link could not be sent. Check the email address and mail configuration, then try again.
          </div>
        ) : null}
        <form className="auth-form" action={requestMagicLink}>
          <label htmlFor="email">Email address</label>
          <input id="email" name="email" type="email" autoComplete="email" required />
          <button type="submit">Send magic link</button>
        </form>
        <small>Local development email is available in Mailpit at localhost:8025.</small>
      </section>
    </main>
  );
}
