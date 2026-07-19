import { signOut } from "@/auth";

export function AuthSessionBar({
  user,
}: {
  user: { name?: string | null; email?: string | null };
}) {
  const label = user.name || user.email || "Signed-in user";

  return (
    <aside className="auth-session-bar" aria-label="Account session">
      <span>
        Signed in as <strong>{label}</strong>
      </span>
      <form
        action={async () => {
          "use server";
          await signOut({ redirectTo: "/auth/signin" });
        }}
      >
        <button type="submit">Sign out</button>
      </form>
    </aside>
  );
}
