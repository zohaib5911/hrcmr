/** Groups an authenticator key in fours (`ABCD EFGH`), which is how people copy it by eye. */
export function groupKey(secret: string): string {
  return (
    secret
      .replace(/\s+/g, "")
      .match(/.{1,4}/g)
      ?.join(" ") ?? ""
  );
}

/** The text of the recovery-codes file: what it is for, the codes, and when they were made. */
export function formatRecoveryCodes(
  brandName: string,
  codes: readonly string[],
  now: Date,
): string {
  return [
    `${brandName} recovery codes`,
    `Made on ${now.toISOString().slice(0, 10)}`,
    "",
    "Each code works once, if you cannot use your authenticator app.",
    "Keep this file somewhere safe and private.",
    "",
    ...codes,
    "",
  ].join("\n");
}
