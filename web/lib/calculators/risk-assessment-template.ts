export type Hazard = {
  hazard: string;
  who: string;
  controls: string;
  furtherAction: string;
  owner: string;
  due: string;
  status: "open" | "in-progress" | "done";
};
export type RiskAssessment = {
  organisation: string;
  site: string;
  country: string;
  employees: string;
  activity: string;
  assessor: string;
  assessedOn: string;
  reviewOn: string;
  consulted: string;
  atRiskGroups: string;
  reference: string;
  version: string;
  hazards: Hazard[];
  acknowledgement: boolean;
};

export const storageKey = "risk-assessment-template:v1";
export const emptyHazard = (): Hazard => ({
  hazard: "",
  who: "",
  controls: "",
  furtherAction: "",
  owner: "",
  due: "",
  status: "open",
});
export const emptyAssessment = (): RiskAssessment => ({
  organisation: "",
  site: "",
  country: "England",
  employees: "",
  activity: "",
  assessor: "",
  assessedOn: "",
  reviewOn: "",
  consulted: "",
  atRiskGroups: "",
  reference: "",
  version: "1.0",
  hazards: [emptyHazard()],
  acknowledgement: false,
});

type Store = Pick<Storage, "getItem" | "setItem" | "removeItem">;
const browserStore = (): Store | null => {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
};
/** Saved only in this browser. Every access is guarded: storage may be blocked or full. */
export function saveAssessment(value: RiskAssessment, store: Store | null = browserStore()) {
  try {
    store?.setItem(storageKey, JSON.stringify(value));
    return store !== null;
  } catch {
    return false;
  }
}
export function loadAssessment(store: Store | null = browserStore()): RiskAssessment | null {
  try {
    const raw = store?.getItem(storageKey);
    if (!raw) return null;
    const data = JSON.parse(raw) as Partial<RiskAssessment>;
    if (typeof data !== "object" || data === null || !Array.isArray(data.hazards)) return null;
    return { ...emptyAssessment(), ...data };
  } catch {
    return null;
  }
}
export function clearAssessment(store: Store | null = browserStore()) {
  try {
    store?.removeItem(storageKey);
  } catch {
    /* ignore */
  }
}

export function validateAssessment(a: RiskAssessment): string[] {
  const errors: string[] = [];
  if (!a.organisation.trim()) errors.push("Enter the organisation name.");
  if (!a.assessor.trim()) errors.push("Enter the assessor’s name.");
  if (!a.activity.trim()) errors.push("Describe the activity or area assessed.");
  if (!a.hazards.some((h) => h.hazard.trim())) errors.push("Add at least one hazard.");
  if (!a.acknowledgement) errors.push("Tick the acknowledgement.");
  return errors;
}

const statusLabel = { open: "Open", "in-progress": "In progress", done: "Done" } as const;
const summaryRows = (a: RiskAssessment): [string, string][] => [
  ["Organisation", a.organisation],
  ["Site", a.site],
  ["Country", a.country],
  ["Employees", a.employees],
  ["Activity", a.activity],
  ["Assessor", a.assessor],
  ["Date assessed", a.assessedOn],
  ["Review date", a.reviewOn],
  ["People consulted", a.consulted],
  ["Groups at particular risk", a.atRiskGroups],
  ["Reference", a.reference],
  ["Version", a.version],
];
/** Plain-text lines shared by the PDF and DOCX builders. */
export function assessmentLines(a: RiskAssessment): string[] {
  const lines = ["Risk assessment", ""];
  for (const [k, v] of summaryRows(a)) lines.push(`${k}: ${v || "-"}`);
  lines.push("", "Hazards");
  a.hazards
    .filter((h) => h.hazard.trim())
    .forEach((h, i) => {
      lines.push(
        `${i + 1}. ${h.hazard}`,
        `   Who might be harmed: ${h.who || "-"}`,
        `   Controls in place: ${h.controls || "-"}`,
        `   Further action: ${h.furtherAction || "-"}`,
        `   Owner: ${h.owner || "-"}   Due: ${h.due || "-"}   Status: ${statusLabel[h.status]}`,
      );
    });
  lines.push(
    "",
    a.acknowledgement
      ? "Acknowledged: the assessor confirms this assessment reflects the work as done."
      : "Not yet acknowledged.",
  );
  return lines;
}

const enc = new TextEncoder();
const bytes = (s: string) => enc.encode(s);
const concat = (parts: Uint8Array[]) => {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let o = 0;
  for (const p of parts) {
    out.set(p, o);
    o += p.length;
  }
  return out;
};

function wrap(line: string, width: number): string[] {
  const out: string[] = [];
  let cur = "";
  for (const word of line.split(" ")) {
    if (cur && (cur + " " + word).length > width) {
      out.push(cur);
      cur = "  " + word;
    } else cur = cur ? cur + " " + word : word;
  }
  out.push(cur);
  return out;
}
// WinAnsi-safe: replace anything outside Latin-1 so the PDF text stays valid.
const latin = (s: string) => s.replace(/[^\x20-\x7e\xa0-\xff]/g, "?");
const pdfEscape = (s: string) => latin(s).replace(/[\\()]/g, "\\$&");

/** Minimal text-only PDF (Helvetica, A4, paginated). */
export function buildPdf(a: RiskAssessment): Uint8Array {
  const rows = assessmentLines(a).flatMap((l) => wrap(l, 90));
  const perPage = 50;
  const pages: string[][] = [];
  for (let i = 0; i < rows.length; i += perPage) pages.push(rows.slice(i, i + perPage));
  const objs: string[] = [];
  const kids = pages.map((_, i) => `${5 + i * 2} 0 R`).join(" ");
  objs[1] = "<< /Type /Catalog /Pages 2 0 R >>";
  objs[2] = `<< /Type /Pages /Kids [${kids}] /Count ${pages.length} >>`;
  objs[3] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>";
  pages.forEach((p, i) => {
    const stream =
      "BT /F1 10 Tf 14 TL 50 800 Td\n" +
      p.map((l) => `(${pdfEscape(l)}) Tj T*`).join("\n") +
      "\nET";
    objs[5 + i * 2] =
      `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents ${6 + i * 2} 0 R >>`;
    objs[6 + i * 2] = `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`;
  });
  objs[4] = "<< >>";
  let out = "%PDF-1.4\n";
  const offsets: number[] = [];
  for (let n = 1; n < objs.length; n++) {
    offsets[n] = out.length;
    out += `${n} 0 obj\n${objs[n]}\nendobj\n`;
  }
  const xref = out.length;
  out += `xref\n0 ${objs.length}\n0000000000 65535 f \n`;
  for (let n = 1; n < objs.length; n++) out += `${String(offsets[n]).padStart(10, "0")} 00000 n \n`;
  out += `trailer\n<< /Size ${objs.length} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
  // all characters are Latin-1, so map 1:1 to bytes
  return Uint8Array.from(out, (c) => c.charCodeAt(0) & 0xff);
}

const crcTable = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});
export function crc32(data: Uint8Array): number {
  let c = 0xffffffff;
  for (const b of data) c = crcTable[(c ^ b) & 0xff]! ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}
const u16 = (n: number) => Uint8Array.of(n & 255, (n >>> 8) & 255);
const u32 = (n: number) =>
  Uint8Array.of(n & 255, (n >>> 8) & 255, (n >>> 16) & 255, (n >>> 24) & 255);

/** Store-only (uncompressed) zip writer. */
export function zipStore(files: { name: string; data: Uint8Array }[]): Uint8Array {
  const local: Uint8Array[] = [];
  const central: Uint8Array[] = [];
  let offset = 0;
  for (const f of files) {
    const name = bytes(f.name);
    const crc = crc32(f.data);
    const head = concat([
      u32(0x04034b50),
      u16(20),
      u16(0x0800),
      u16(0),
      u16(0),
      u16(0x21),
      u32(crc),
      u32(f.data.length),
      u32(f.data.length),
      u16(name.length),
      u16(0),
      name,
    ]);
    local.push(head, f.data);
    central.push(
      concat([
        u32(0x02014b50),
        u16(20),
        u16(20),
        u16(0x0800),
        u16(0),
        u16(0),
        u16(0x21),
        u32(crc),
        u32(f.data.length),
        u32(f.data.length),
        u16(name.length),
        u16(0),
        u16(0),
        u16(0),
        u16(0),
        u32(0),
        u32(offset),
        name,
      ]),
    );
    offset += head.length + f.data.length;
  }
  const cd = concat(central);
  return concat([
    ...local,
    cd,
    u32(0x06054b50),
    u16(0),
    u16(0),
    u16(files.length),
    u16(files.length),
    u32(cd.length),
    u32(offset),
    u16(0),
  ]);
}

const xmlEscape = (s: string) =>
  s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);

export function buildDocx(a: RiskAssessment): Uint8Array {
  const paras = assessmentLines(a)
    .map((l, i) => {
      const bold = i === 0 || l === "Hazards";
      const text = xmlEscape(l);
      return `<w:p><w:r>${bold ? "<w:rPr><w:b/></w:rPr>" : ""}<w:t xml:space="preserve">${text}</w:t></w:r></w:p>`;
    })
    .join("");
  const ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"';
  const xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>';
  return zipStore([
    {
      name: "[Content_Types].xml",
      data: bytes(
        `${xml}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>`,
      ),
    },
    {
      name: "_rels/.rels",
      data: bytes(
        `${xml}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>`,
      ),
    },
    {
      name: "word/document.xml",
      data: bytes(`${xml}<w:document ${ns}><w:body>${paras}</w:body></w:document>`),
    },
  ]);
}
