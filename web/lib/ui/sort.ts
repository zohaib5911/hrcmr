/** Sorting for DataTable: numbers by value, text by natural order, empty cells always last. */

export type SortValue = string | number | null;

const collator = new Intl.Collator("en-GB", { numeric: true, sensitivity: "base" });

export function compareValues(a: string | number, b: string | number): number {
  if (typeof a === "number" && typeof b === "number") return a - b;
  if (typeof a === "number") return -1;
  if (typeof b === "number") return 1;
  return collator.compare(a, b);
}

/** A new, sorted list. Ties keep their original order. */
export function sortRows<Row>(
  rows: readonly Row[],
  value: (row: Row) => SortValue,
  direction: "asc" | "desc",
): Row[] {
  const sign = direction === "asc" ? 1 : -1;
  return rows
    .map((row, index) => ({ row, index, key: value(row) }))
    .sort((a, b) => {
      if (a.key === null || b.key === null) {
        // Empty cells go last whichever way the column is sorted.
        return a.key === b.key ? a.index - b.index : a.key === null ? 1 : -1;
      }
      return sign * compareValues(a.key, b.key) || a.index - b.index;
    })
    .map(({ row }) => row);
}
