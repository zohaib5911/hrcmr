/** Avatars: initials, and a colour that is the same for the same person every time. */

export const AVATAR_TONES = ["accent", "success", "warning", "danger", "info", "neutral"] as const;
export type AvatarTone = (typeof AVATAR_TONES)[number];

/** "Ada Byron Lovelace" is "AL": the first and last words. A single word gives one letter. */
export function initials(name: string): string {
  const letters = name
    .trim()
    .split(/\s+/)
    .map((word) => /\p{L}/u.exec(word)?.[0])
    .filter((letter): letter is string => letter !== undefined);
  if (letters.length === 0) return "?";
  const first = letters[0] ?? "";
  const last = letters.length > 1 ? (letters.at(-1) ?? "") : "";
  return `${first}${last}`.toLocaleUpperCase("en-GB");
}

/** FNV-1a, a fixed hash: the colour never depends on the run, the browser or the server. */
function hash(text: string): number {
  let value = 0x811c9dc5;
  for (let i = 0; i < text.length; i += 1) {
    value ^= text.charCodeAt(i);
    value = Math.imul(value, 0x01000193) >>> 0;
  }
  return value;
}

export function avatarTone(name: string): AvatarTone {
  const normalised = name.trim().toLocaleLowerCase("en-GB");
  return AVATAR_TONES[hash(normalised) % AVATAR_TONES.length] ?? "neutral";
}
