import { describe, expect, it, vi } from "vitest";

import { formatRecoveryCodes, groupKey } from "./mfa";
import { ENROL_PATH, enrolmentRedirect } from "./request";

describe("two-step verification helpers", () => {
  it("groups the key in fours and the file says what the codes are for", () => {
    expect(groupKey("JBSWY3DPEHPK3PXP")).toBe("JBSW Y3DP EHPK 3PXP");
    const file = formatRecoveryCodes(
      "Brand",
      ["aaaaa-bbbbb", "ccccc-ddddd"],
      new Date("2026-11-02"),
    );
    expect(file).toContain("Brand recovery codes");
    expect(file).toContain("Made on 2026-11-02");
    expect(file).toContain("aaaaa-bbbbb\nccccc-ddddd");
  });

  it("sends someone to set-up when the API refuses them for not having done it, and only then", async () => {
    const go = vi.fn();
    const middleware = enrolmentRedirect(go, () => "/dashboard");
    const refuse = (status: number, code: string) =>
      new Response(JSON.stringify({ error: { code, message: "x", request_id: "r" } }), { status });
    const run = (response: Response) =>
      (middleware.onResponse as (o: { response: Response }) => Promise<unknown>)({ response });

    await run(refuse(403, "FORBIDDEN"));
    await run(refuse(401, "MFA_ENROLMENT_REQUIRED"));
    await run(new Response("not json", { status: 403 }));
    expect(go).not.toHaveBeenCalled();

    await run(refuse(403, "MFA_ENROLMENT_REQUIRED"));
    expect(go).toHaveBeenCalledWith(ENROL_PATH);
  });
});
