import { readFile } from "node:fs/promises";
import path from "node:path";
import { isPublishable, loadTemplates } from "@/lib/templates/manifest";

/** Files stay outside public/: direct requests must pass the same review gate as the listing. */
export async function GET(_request: Request, { params }: { params: Promise<{ file: string }> }) {
  const { file } = await params;
  const template = loadTemplates().find((entry) => entry.file === file && isPublishable(entry));
  if (!template) return new Response(null, { status: 404 });
  const bytes = await readFile(path.join(process.cwd(), "content", "templates", template.file));
  return new Response(bytes, {
    headers: {
      "Content-Type": file.endsWith(".pdf")
        ? "application/pdf"
        : "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "Content-Disposition": `attachment; filename="${template.file}"`,
      "X-Content-Type-Options": "nosniff",
      "Cache-Control": "no-store",
    },
  });
}
