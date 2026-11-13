import { describe, expect, it } from "vitest";

import {
  ADMIN_SEGMENT,
  classifyHost,
  decideRoute,
  hostnameOf,
  isInternalAdminPath,
  normalizeForComparison,
} from "./hosts";

describe("hostnameOf", () => {
  it.each([
    ["Example.com", "example.com"],
    ["example.com:3000", "example.com"],
    ["ADMIN.Example.Com:8443", "admin.example.com"],
    ["  admin.localhost:3000 ", "admin.localhost"],
    ["[::1]:3000", "[::1]"],
    ["", ""],
  ])("%j -> %j", (input, expected) => {
    expect(hostnameOf(input)).toBe(expected);
  });

  it("copes with a missing header", () => {
    expect(hostnameOf(null)).toBe("");
    expect(hostnameOf(undefined)).toBe("");
  });
});

describe("classifyHost", () => {
  it.each(["admin.example.com", "admin.staging.example.com", "admin.localhost"])(
    "%s is the admin host",
    (host) => {
      expect(classifyHost(host)).toBe("admin");
    },
  );

  it.each([
    "example.com",
    "www.example.com",
    "staging.example.com",
    "api.example.com",
    "localhost",
    "administrator.example.com",
    "notadmin.example.com",
    "admin-example.com",
    "",
  ])("%s is the main host", (host) => {
    expect(classifyHost(host)).toBe("main");
  });

  it("also honours the configured admin URL", () => {
    expect(classifyHost("ops.example.com", "https://ops.example.com")).toBe("admin");
    expect(classifyHost("example.com", "https://ops.example.com")).toBe("main");
  });

  it("survives a malformed configured admin URL", () => {
    expect(classifyHost("admin.example.com", "not a url")).toBe("admin");
    expect(classifyHost("example.com", "not a url")).toBe("main");
  });
});

describe("normalizeForComparison", () => {
  it.each([
    ["/platform", "/platform"],
    ["/Platform", "/platform"],
    ["/%70latform", "/platform"],
    ["/%50LATFORM", "/platform"],
    ["/x/../platform", "/platform"],
    ["/./platform", "/platform"],
    ["//platform", "/platform"],
    ["/platform/", "/platform"],
    ["/", "/"],
    ["/%zz", "/%zz"],
  ])("%j -> %j", (input, expected) => {
    expect(normalizeForComparison(input)).toBe(expected);
  });
});

describe("isInternalAdminPath", () => {
  it.each([
    "/platform",
    "/platform/",
    "/platform/companies",
    "/Platform",
    "/%70latform/x",
    "/a/../platform",
  ])("%s is internal", (path) => expect(isInternalAdminPath(path)).toBe(true));

  it.each(["/", "/platformer", "/platform-x", "/my/platform", "/api/platform"])(
    "%s is not internal",
    (path) => expect(isInternalAdminPath(path)).toBe(false),
  );
});

describe("decideRoute on the main host", () => {
  it.each(["/", "/login", "/dashboard", "/pricing", "/platformer", "/careers/acme"])(
    "%s passes through",
    (path) => {
      expect(decideRoute("main", path)).toEqual({ action: "next" });
    },
  );

  it.each([
    "/platform",
    "/platform/",
    "/platform/companies",
    "/Platform",
    "/%70latform",
    "/x/../platform",
  ])("%s is a 404: the admin pages do not exist here", (path) => {
    expect(decideRoute("main", path)).toEqual({ action: "not-found" });
  });
});

describe("decideRoute on the admin host", () => {
  it.each([
    "/brand/logo.svg",
    "/brand/logo-dark.svg",
    "/brand/mark-small.svg",
    "/brand/logo-email.png",
    "/icon.png",
    "/icon1.png",
    "/apple-icon.png",
    "/opengraph-image",
  ])("serves shared public artwork %s without rewriting it into an admin page", (path) =>
    expect(decideRoute("admin", path)).toEqual({ action: "next" }),
  );

  it.each(["/brand/../platform", "/brand/%2e%2e/platform", "/brand/logo.svg/../../platform"])(
    "keeps internal paths blocked even under an artwork prefix: %s",
    (path) => expect(decideRoute("admin", path)).toEqual({ action: "not-found" }),
  );

  it("maps the root to the admin home", () => {
    expect(decideRoute("admin", "/")).toEqual({ action: "rewrite", pathname: ADMIN_SEGMENT });
  });

  it.each([
    ["/companies", "/platform/companies"],
    ["/companies/0192a-b", "/platform/companies/0192a-b"],
    ["/login", "/platform/login"],
  ])("maps %s onto %s", (path, destination) => {
    expect(decideRoute("admin", path)).toEqual({ action: "rewrite", pathname: destination });
  });

  it.each(["/platform", "/platform/companies", "/%70latform", "/Platform/x"])(
    "refuses the internal path %s",
    (path) => {
      expect(decideRoute("admin", path)).toEqual({ action: "not-found" });
    },
  );

  it.each(["/a/../login", "/%2e%2e/login", "/a/%2e%2e/b", "/a%2fb", "//x", "/a\\b", "/./x"])(
    "refuses the ambiguous path %s so it cannot climb out of /platform",
    (path) => {
      expect(decideRoute("admin", path)).toEqual({ action: "not-found" });
    },
  );
});
