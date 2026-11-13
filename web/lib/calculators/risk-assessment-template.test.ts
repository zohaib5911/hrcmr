import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  buildDocx,
  buildPdf,
  crc32,
  emptyAssessment,
  emptyHazard,
  loadAssessment,
  saveAssessment,
  validateAssessment,
  type RiskAssessment,
} from "./risk-assessment-template";

const sample = (): RiskAssessment => ({
  ...emptyAssessment(),
  organisation: "Acme & Sons",
  assessor: "A. Person",
  activity: "Warehouse picking",
  acknowledgement: true,
  hazards: [
    { ...emptyAssessment().hazards[0]!, hazard: "Manual handling (heavy)", status: "done" },
  ],
});
const text = (u: Uint8Array) => Buffer.from(u).toString("latin1");
const memory = () => {
  const m = new Map<string, string>();
  return {
    getItem: (k: string) => m.get(k) ?? null,
    setItem: (k: string, v: string) => void m.set(k, v),
    removeItem: (k: string) => void m.delete(k),
  };
};

describe("risk assessment template", () => {
  it("validates required fields", () => {
    expect(validateAssessment(emptyAssessment())).toHaveLength(5);
    expect(validateAssessment(sample())).toEqual([]);
  });
  it("saves and loads, and survives blocked storage", () => {
    const s = memory();
    expect(saveAssessment(sample(), s)).toBe(true);
    expect(loadAssessment(s)?.organisation).toBe("Acme & Sons");
    const broken = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("full");
      },
      removeItem: () => {},
    };
    expect(saveAssessment(sample(), broken)).toBe(false);
    expect(loadAssessment(broken)).toBeNull();
    s.setItem("risk-assessment-template:v1", "{bad json");
    expect(loadAssessment(s)).toBeNull();
  });
  it("restores only valid fields from a damaged draft", () => {
    const s = memory();
    const put = (v: unknown) => s.setItem("risk-assessment-template:v1", JSON.stringify(v));
    for (const bad of [null, [], "text", 3, {}, { hazards: "x" }, { hazards: null }]) {
      put(bad);
      expect(loadAssessment(s)).toBeNull();
    }
    put({ organisation: null, hazards: [null] });
    expect(loadAssessment(s)).toEqual(emptyAssessment());
    put({
      organisation: "Acme",
      site: 7,
      country: "Narnia",
      version: ["2"],
      acknowledgement: "yes",
      hazards: [
        null,
        "slip",
        [],
        { hazard: "Slips", who: 1, owner: "Sam", due: null, status: "closed" },
        { hazard: "Fire", status: "in-progress" },
      ],
    });
    const got = loadAssessment(s)!;
    expect(got).toMatchObject({
      organisation: "Acme",
      site: "",
      country: "England",
      version: "1.0",
      acknowledgement: false,
    });
    expect(got.hazards).toEqual([
      { ...emptyHazard(), hazard: "Slips", owner: "Sam" },
      { ...emptyHazard(), hazard: "Fire", status: "in-progress" },
    ]);
    // the restored draft renders and exports without crashing
    expect(validateAssessment(got)).toHaveLength(3);
    expect(text(buildPdf(got))).toContain("Slips");
    put(sample());
    expect(loadAssessment(s)).toEqual(sample());
  });
  it("builds a PDF with escaped text", () => {
    const pdf = text(buildPdf(sample()));
    expect(pdf.startsWith("%PDF-1.4")).toBe(true);
    expect(pdf).toContain("Manual handling \\(heavy\\)");
    expect(pdf.trimEnd().endsWith("%%EOF")).toBe(true);
  });
  it("builds a DOCX zip with valid entries", () => {
    const docx = buildDocx(sample());
    expect(Array.from(docx.slice(0, 4))).toEqual([0x50, 0x4b, 0x03, 0x04]);
    const s = text(docx);
    expect(s).toContain("word/document.xml");
    expect(s).toContain("Acme &amp; Sons");
  });
  it("crc32 matches the standard check value", () => {
    expect(crc32(new TextEncoder().encode("123456789"))).toBe(0xcbf43926);
  });
  it("makes no network calls", () => {
    const src = readFileSync(path.join(__dirname, "risk-assessment-template.ts"), "utf8");
    expect(src).not.toMatch(/fetch\(|XMLHttpRequest|sendBeacon/);
  });
});
