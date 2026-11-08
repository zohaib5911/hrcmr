import { NextResponse, type NextRequest } from "next/server";

import { CSRF_COOKIE, serverApiBaseUrl } from "@/lib/api/client";
import { safeNextPath, startPlatformSession } from "@/lib/platform/session";

/**
 * Start the platform session (T17.1, owner answer 5), then go on to `next`. The API sets the
 * platform cookie; this forwards its Set-Cookie to the browser. A refusal goes to a page that says
 * why, never to a 404.
 */
export async function GET(request: NextRequest): Promise<NextResponse> {
  const next = safeNextPath(request.nextUrl.searchParams.get("next"));
  const outcome = await startPlatformSession({
    apiBase: serverApiBaseUrl(),
    cookieHeader: request.headers.get("cookie") ?? "",
    csrfToken: request.cookies.get(CSRF_COOKIE)?.value,
  });
  if (!outcome.ok) {
    const code = encodeURIComponent(outcome.code);
    return NextResponse.redirect(new URL(`/session-required?code=${code}`, request.url));
  }
  const response = NextResponse.redirect(new URL(next, request.url));
  for (const cookie of outcome.setCookies) response.headers.append("set-cookie", cookie);
  return response;
}
