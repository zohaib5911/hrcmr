import { describe, expect, it } from "vitest";

import { formatBytes, validateFile } from "./files";

const file = (name: string, size: number, type = "") => ({ name, size, type });

describe("validateFile", () => {
  const rules = { accept: [".pdf", ".docx", "image/*"], maxBytes: 10 * 1024 * 1024 };

  it("accepts a listed extension, whatever its case", () => {
    expect(validateFile(file("passport.pdf", 1000), rules)).toBeNull();
    expect(validateFile(file("CONTRACT.DOCX", 1000), rules)).toBeNull();
  });

  it("accepts a wildcard type such as image/*", () => {
    expect(validateFile(file("scan", 1000, "image/png"), rules)).toBeNull();
    expect(validateFile(file("scan", 1000, "application/zip"), rules)).toMatch(
      /PDF, DOCX or an image/,
    );
  });

  it("rejects files that are not on the list and says what is allowed", () => {
    expect(validateFile(file("run.exe", 1000), rules)).toBe(
      "This file type is not allowed. Use PDF, DOCX or an image.",
    );
  });

  it("is not fooled by a double extension", () => {
    expect(validateFile(file("invoice.pdf.exe", 1000), rules)).toMatch(/not allowed/);
    expect(validateFile(file("pdf", 1000), rules)).toMatch(/not allowed/);
  });

  it("rejects empty and oversized files with the limit in words", () => {
    expect(validateFile(file("a.pdf", 0), rules)).toBe("This file is empty.");
    expect(validateFile(file("a.pdf", 10 * 1024 * 1024 + 1), rules)).toBe(
      "This file is larger than 10 MB.",
    );
    expect(validateFile(file("a.pdf", 10 * 1024 * 1024), rules)).toBeNull();
  });

  it("allows anything when no list is given", () => {
    expect(validateFile(file("x.anything", 5), { maxBytes: 1000 })).toBeNull();
  });
});

describe("formatBytes", () => {
  it("uses units people read", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(999)).toBe("999 B");
    expect(formatBytes(1024)).toBe("1 KB");
    expect(formatBytes(1536)).toBe("1.5 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5 MB");
    expect(formatBytes(1234 * 1024 * 1024)).toBe("1.2 GB");
  });
});
