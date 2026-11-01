import { describe, expect, it } from "vitest";

import { csvCell, toCsv } from "./csv";

describe("csvCell", () => {
  it("writes plain values as they are", () => {
    expect(csvCell("Ada Lovelace")).toBe("Ada Lovelace");
    expect(csvCell(42)).toBe("42");
    expect(csvCell(-3.5)).toBe("-3.5");
    expect(csvCell(0)).toBe("0");
  });

  it("writes empty for nothing", () => {
    expect(csvCell(null)).toBe("");
    expect(csvCell(undefined)).toBe("");
    expect(csvCell("")).toBe("");
  });

  it("quotes commas, quotes and line breaks, doubling inner quotes", () => {
    expect(csvCell("Lovelace, Ada")).toBe('"Lovelace, Ada"');
    expect(csvCell('say "hi"')).toBe('"say ""hi"""');
    expect(csvCell("line one\nline two")).toBe('"line one\nline two"');
    expect(csvCell("a\r\nb")).toBe('"a\r\nb"');
  });

  it.each([
    "=SUM(A1:A9)",
    "+1+1",
    "-2+3",
    "@cmd",
    "\tcmd",
    "\rcmd",
    '=HYPERLINK("http://evil","click")',
  ])("defuses spreadsheet formulas: %j (CSV injection)", (text) => {
    const cell = csvCell(text);
    // A leading apostrophe makes Excel, Sheets and LibreOffice treat the cell as text.
    expect(cell.replace(/^"/, "").startsWith("'")).toBe(true);
  });

  it("does not touch real numbers, only text that looks like a formula", () => {
    expect(csvCell(-3)).toBe("-3");
    expect(csvCell("-3")).toBe("'-3");
  });

  it("keeps non-English text intact", () => {
    expect(csvCell("Łukasz Żak")).toBe("Łukasz Żak");
    expect(csvCell("日本語")).toBe("日本語");
  });
});

describe("toCsv", () => {
  it("writes a header and rows with Windows line endings, which every spreadsheet accepts", () => {
    expect(
      toCsv(
        ["Name", "Salary"],
        [
          ["Ada", 41700],
          ["Grace, H.", null],
        ],
      ),
    ).toBe('Name,Salary\r\nAda,41700\r\n"Grace, H.",\r\n');
  });

  it("defuses a formula in a header too", () => {
    expect(toCsv(["=evil"], [])).toBe("'=evil\r\n");
  });

  it("can start with a byte order mark so Excel reads accents correctly", () => {
    expect(toCsv(["Name"], [["Zoë"]], { bom: true }).startsWith("﻿Name")).toBe(true);
  });
});
