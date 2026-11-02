/**
 * A hint, not a rule. The API decides what is accepted (12 or more characters, not on the common
 * list, not found in a known breach); this only helps a person see how they are doing as they type.
 */
export const MIN_PASSWORD_LENGTH = 12;

export type StrengthLevel = 0 | 1 | 2 | 3 | 4;

export interface PasswordStrength {
  level: StrengthLevel;
  /** Empty until something is typed. */
  label: "" | "Too short" | "Weak" | "Fair" | "Good" | "Strong";
  meetsMinimum: boolean;
  tip: string;
}

function classes(password: string): number {
  return [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter((pattern) => pattern.test(password))
    .length;
}

function mostlyRepeated(password: string): boolean {
  return new Set(password.toLowerCase()).size <= 3;
}

export function passwordStrength(password: string): PasswordStrength {
  const length = [...password].length;
  if (length === 0) {
    return {
      level: 0,
      label: "",
      meetsMinimum: false,
      tip: `Use at least ${MIN_PASSWORD_LENGTH} characters. A few unrelated words make a good password.`,
    };
  }
  if (length < MIN_PASSWORD_LENGTH) {
    return {
      level: 1,
      label: "Too short",
      meetsMinimum: false,
      tip: `${MIN_PASSWORD_LENGTH - length} more ${MIN_PASSWORD_LENGTH - length === 1 ? "character" : "characters"} to go.`,
    };
  }
  if (mostlyRepeated(password)) {
    return {
      level: 1,
      label: "Weak",
      meetsMinimum: true,
      tip: "That repeats too much. Try a few unrelated words.",
    };
  }
  const variety = classes(password);
  if (length >= 24 || (length >= 16 && variety >= 3)) {
    return {
      level: 4,
      label: "Strong",
      meetsMinimum: true,
      tip: "Strong. We also check it against known breaches.",
    };
  }
  if (length >= 16 || variety >= 3) {
    return { level: 3, label: "Good", meetsMinimum: true, tip: "Good. Longer is stronger." };
  }
  return {
    level: 2,
    label: "Fair",
    meetsMinimum: true,
    tip: "Fair. Add a few more words to make it harder to guess.",
  };
}
