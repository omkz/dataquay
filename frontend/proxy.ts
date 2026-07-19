import { auth } from "@/auth";
import { NextResponse } from "next/server";

export const proxy = auth((request) => {
  if (request.auth) return NextResponse.next();

  if (request.nextUrl.pathname.startsWith("/api/")) {
    return Response.json(
      { detail: "Authentication is required." },
      { status: 401 },
    );
  }

  const signInUrl = new URL("/auth/signin", request.url);
  signInUrl.searchParams.set(
    "callbackUrl",
    `${request.nextUrl.pathname}${request.nextUrl.search}`,
  );
  return NextResponse.redirect(signInUrl);
});

export const config = {
  matcher: [
    "/((?!api/auth|auth|_next/static|_next/image|favicon.ico|.*\\..*).*)",
  ],
};
