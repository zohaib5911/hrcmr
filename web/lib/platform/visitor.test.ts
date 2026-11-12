import { describe, expect, it } from "vitest";
import { signVisitor, visitorFromIngress } from "./visitor";

const env = { PLATFORM_INGRESS_SECRET: "iiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii" };
const headers = () =>
  new Headers({
    "x-platform-ingress-key": env.PLATFORM_INGRESS_SECRET,
    "x-platform-visitor-ip": "203.0.113.7",
    "user-agent": "Admin browser",
  });

describe("verified SSR identity", () => {
  it("accepts only the authenticated ingress IP and user agent", () => {
    expect(visitorFromIngress(headers(), env)).toEqual({
      ip: "203.0.113.7",
      userAgent: "Admin browser",
    });
  });
  it.each(["", "forged", "é".repeat(33)])("refuses an untrusted ingress key %s", (key) => {
    const incoming = headers();
    incoming.set("x-platform-ingress-key", key);
    incoming.set("x-forwarded-for", "203.0.113.7");
    expect(visitorFromIngress(incoming, env)).toBeNull();
  });
  it("refuses missing configuration and malformed ingress IPs", () => {
    expect(visitorFromIngress(headers(), {})).toBeNull();
    const incoming = headers();
    incoming.set("x-platform-visitor-ip", "203.0.113.7, 127.0.0.1");
    expect(visitorFromIngress(incoming, env)).toBeNull();
  });
  it("binds the signed identity to the exact outgoing GET and cookies", () => {
    const request = new Request("https://api.test/api/v1/platform/companies?q=Acme", {
      headers: { cookie: "platform=token" },
    });
    signVisitor(request, visitorFromIngress(headers(), env)!, "ssssssssssssssssssssssssssssssss");
    const value = JSON.parse(
      Buffer.from(request.headers.get("x-platform-visitor")!, "base64url").toString(),
    );
    expect(value).toMatchObject({
      ip: "203.0.113.7",
      ua: "Admin browser",
      method: "GET",
      target: "/api/v1/platform/companies?q=Acme",
    });
    expect(value.cookie).toMatch(/^[a-f0-9]{64}$/);
    expect(request.headers.get("x-platform-signature")).toMatch(/^[a-f0-9]{64}$/);
  });
});
