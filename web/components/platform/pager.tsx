import { Button } from "@/components/ui/button";

export const PAGE_SIZE = 50;

/** Previous/Next controls for a platform list that pages by offset. */
export function Pager({
  label,
  offset,
  total,
  onChange,
}: {
  label: string;
  offset: number;
  total: number;
  onChange: (offset: number) => void;
}) {
  return (
    <nav aria-label={`${label} pages`} className="mt-4 flex items-center justify-between gap-3">
      <Button
        variant="gray"
        size="sm"
        disabled={offset === 0}
        onClick={() => onChange(Math.max(0, offset - PAGE_SIZE))}
      >
        Previous
      </Button>
      <span className="text-footnote text-label-secondary">{total} in total</span>
      <Button
        variant="gray"
        size="sm"
        disabled={offset + PAGE_SIZE >= total}
        onClick={() => onChange(offset + PAGE_SIZE)}
      >
        Next
      </Button>
    </nav>
  );
}
