import "server-only";

import { SignJWT } from "jose";

import { auth } from "@/auth";
import { getBackendUrl } from "@/lib/dataquay";

const TOKEN_ISSUER = "dataquay-next";
const TOKEN_AUDIENCE = "dataquay-fastapi";
const TOKEN_LIFETIME_SECONDS = 60;

export class AuthenticationRequiredError extends Error {}
export class BackendAuthenticationConfigurationError extends Error {}

export async function authenticatedBackendFetch(
  path: string,
  init: RequestInit = {},
) {
  const session = await auth();
  const userId = session?.user?.id;
  if (!userId || !/^\d+$/.test(userId)) {
    throw new AuthenticationRequiredError("Authentication is required.");
  }

  const secret = process.env.DATAQUAY_INTERNAL_AUTH_SECRET?.trim();
  if (!secret || new TextEncoder().encode(secret).byteLength < 32) {
    throw new BackendAuthenticationConfigurationError(
      "DATAQUAY_INTERNAL_AUTH_SECRET must contain at least 32 bytes.",
    );
  }

  const now = Math.floor(Date.now() / 1000);
  const token = await new SignJWT({})
    .setProtectedHeader({ alg: "HS256", typ: "JWT" })
    .setSubject(userId)
    .setIssuer(TOKEN_ISSUER)
    .setAudience(TOKEN_AUDIENCE)
    .setIssuedAt(now)
    .setExpirationTime(now + TOKEN_LIFETIME_SECONDS)
    .sign(new TextEncoder().encode(secret));

  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  return fetch(`${getBackendUrl()}${path}`, {
    ...init,
    headers,
  });
}

export function isAuthenticationRequiredError(
  error: unknown,
): error is AuthenticationRequiredError {
  return error instanceof AuthenticationRequiredError;
}
