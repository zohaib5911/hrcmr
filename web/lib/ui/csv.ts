/**
 * CSV for table exports. Two things matter here:
 *  - quoting, so a name like `Lovelace, Ada` stays one cell;
 *  - CSV injection: a cell that starts with = + - @ (or a tab or carriage return) is run as a
 *    formula by Excel, Sheets and LibreOffice. An employee called `=HYPERLINK(...)` would attack
 *    whoever opens the export, so such text is made harmless with a leading apostrophe (OWASP).
 */

export type CsvValue = string | number | null | undefined;

const FORMULA_START = /^[=+\-@\t\r]/;

export function csvCell(value: CsvValue): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "number") return String(value);
  const safe = FORMULA_START.test(value) ? `'${value}` : value;
  return /[",\r\n]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe;
}

export function toCsv(
  headers: readonly string[],
  rows: readonly (readonly CsvValue[])[],
  { bom = false }: { bom?: boolean } = {},
): string {
  const lines = [headers, ...rows].map((row) => row.map(csvCell).join(","));
  return `${bom ? "﻿" : ""}${lines.join("\r\n")}\r\n`;
}
