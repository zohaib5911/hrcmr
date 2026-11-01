/** Checks for FileDrop. These are a convenience for the person; the API checks every upload again. */

export interface FileLike {
  readonly name: string;
  readonly size: number;
  readonly type: string;
}

export interface FileRules {
  /** Extensions (".pdf"), exact types ("application/pdf") or wildcards ("image/*"). */
  readonly accept?: readonly string[];
  readonly maxBytes: number;
}

export function formatBytes(bytes: number): string {
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${Number(value.toFixed(1))} ${units[unit]}`;
}

function matches(file: FileLike, rule: string): boolean {
  const lower = rule.toLowerCase();
  if (lower.startsWith(".")) {
    const dot = file.name.lastIndexOf(".");
    return dot > 0 && file.name.slice(dot).toLowerCase() === lower;
  }
  if (lower.endsWith("/*")) return file.type.toLowerCase().startsWith(lower.slice(0, -1));
  return file.type.toLowerCase() === lower;
}

function describe(rules: readonly string[]): string {
  const names = rules.map((rule) =>
    rule.startsWith(".") ? rule.slice(1).toUpperCase() : rule === "image/*" ? "an image" : rule,
  );
  if (names.length <= 1) return names.join("");
  return `${names.slice(0, -1).join(", ")} or ${names.at(-1)}`;
}

/** An explanation in plain words, or null if the file is fine. */
export function validateFile(file: FileLike, rules: FileRules): string | null {
  if (
    rules.accept &&
    rules.accept.length > 0 &&
    !rules.accept.some((rule) => matches(file, rule))
  ) {
    return `This file type is not allowed. Use ${describe(rules.accept)}.`;
  }
  if (file.size === 0) return "This file is empty.";
  if (file.size > rules.maxBytes) return `This file is larger than ${formatBytes(rules.maxBytes)}.`;
  return null;
}
