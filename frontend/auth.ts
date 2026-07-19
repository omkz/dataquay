import PostgresAdapter from "@auth/pg-adapter";
import NextAuth from "next-auth";
import Nodemailer from "next-auth/providers/nodemailer";
import { Pool } from "pg";

const globalForAuth = globalThis as unknown as { dataquayAuthPool?: Pool };

function requireServerEnvironment(name: string) {
  const value = process.env[name]?.trim();
  if (!value) {
    throw new Error(`${name} must be configured for DataQuay authentication.`);
  }
  return value;
}

const authDatabaseUrl = requireServerEnvironment("AUTH_DATABASE_URL");
const emailServer = requireServerEnvironment("EMAIL_SERVER");
const emailFrom = requireServerEnvironment("EMAIL_FROM");
const authSecret = requireServerEnvironment("AUTH_SECRET");
if (new TextEncoder().encode(authSecret).byteLength < 32) {
  throw new Error("AUTH_SECRET must contain at least 32 bytes.");
}

const authPool =
  globalForAuth.dataquayAuthPool ??
  new Pool({
    connectionString: authDatabaseUrl,
    max: 10,
    idleTimeoutMillis: 30_000,
    connectionTimeoutMillis: 5_000,
  });

if (process.env.NODE_ENV !== "production") {
  globalForAuth.dataquayAuthPool = authPool;
}

export const { auth, handlers, signIn, signOut } = NextAuth({
  secret: authSecret,
  adapter: PostgresAdapter(authPool),
  session: {
    strategy: "database",
    maxAge: 8 * 60 * 60,
    updateAge: 60 * 60,
  },
  providers: [
    Nodemailer({
      server: emailServer,
      from: emailFrom,
      maxAge: 15 * 60,
    }),
  ],
  pages: {
    signIn: "/auth/signin",
    verifyRequest: "/auth/check-email",
    error: "/auth/error",
  },
  callbacks: {
    session({ session, user }) {
      if (session.user) {
        session.user.id = String(user.id);
      }
      return session;
    },
  },
});
