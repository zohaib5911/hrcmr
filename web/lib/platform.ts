/** Keys are written differently on a Mac (Cmd) and elsewhere (Ctrl). */

export function isApplePlatform(platform: string): boolean {
  return /Mac|iPhone|iPad|iPod/.test(platform);
}

/** "Mod" in a shortcut means Cmd on Apple devices and Ctrl on the rest. */
export function keyLabel(key: string, apple: boolean): string {
  if (key === "Mod") return apple ? "⌘" : "Ctrl";
  return key;
}
