/** Server-only identity bridge. The ingress must overwrite both headers; see deployment requirements. */
import { createHash, createHmac, timingSafeEqual } from "node:crypto";
import { isIP } from "node:net";

export function visitorFromIngress(
  headers: Headers,
  env: Record<string, string | undefined> = process.env,
): { ip: string; userAgent: string } | null {
  const expected = env.PLATFORM_INGRESS_SECRET;
  const supplied = headers.get("x-platform-ingress-key") ?? "";
  if (!expected || expected.length < 32 || !supplied) return null;
  if (
    !timingSafeEqual(
      createHash("sha256").update(supplied).digest(),
      createHash("sha256").update(expected).digest(),
    )
  )
    return null;
  const ip = headers.get("x-platform-visitor-ip") ?? "";
  if (!isIP(ip)) return null;
  return { ip, userAgent: headers.get("user-agent") ?? "" };
}

export function signVisitor(
  request: Request,
  visitor: { ip: string; userAgent: string },
  secret: string,
): void {
  const url = new URL(request.url);
  const payload = Buffer.from(
    JSON.stringify({
      ip: visitor.ip,
      ua: visitor.userAgent,
      at: Math.floor(Date.now() / 1000),
      method: request.method,
      target: url.pathname + url.search,
      cookie: createHash("sha256")
        .update(request.headers.get("cookie") ?? "")
        .digest("hex"),
    }),
  ).toString("base64url");
  request.headers.set("x-platform-visitor", payload);
  request.headers.set(
    "x-platform-signature",
    createHmac("sha256", secret).update(payload).digest("hex"),
  );
}
