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
    return redirectTo(`/session-required?code=${code}`);
  }
  const response = redirectTo(next);
  for (const cookie of outcome.setCookies) response.headers.append("set-cookie", cookie);
  return response;
}

/**
 * A 307 with a RELATIVE Location. An absolute URL built from `request.url` carries the server's bind
 * address (0.0.0.0 behind the proxy), so the browser would be sent to an address nobody can reach
 * and land on the main host's 404. A relative one is resolved against the host the browser asked for.
 */
function redirectTo(path: string): NextResponse {
  return new NextResponse(null, { status: 307, headers: { location: path } });
}
