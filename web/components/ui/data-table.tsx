"use client";

import { useVirtualizer } from "@tanstack/react-virtual";
import {
  ArrowDown,
  ArrowUp,
  ChevronLeft,
  ChevronRight,
  ChevronsUpDown,
  Columns3,
  Download,
  Ellipsis,
} from "lucide-react";
import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type KeyboardEvent,
  type ReactNode,
} from "react";

import { sortRows, type SortValue } from "@/lib/ui/sort";
import { cn } from "@/lib/utils";

import { Button, IconButton } from "./button";
import { CheckboxControl } from "./checkbox";
import { Icon } from "./icon";
import { Menu, MenuCheckboxItem, MenuContent, MenuLabel, MenuTrigger } from "./menu";
import { SegmentedControl } from "./segmented-control";
import { SkeletonTable } from "./skeleton";

export interface Column<Row> {
  id: string;
  header: string;
  cell: (row: Row) => ReactNode;
  /** Makes the column sortable. Empty values (null) always sort last. */
  sortValue?: (row: Row) => SortValue;
  /** Plain text for exports. Defaults to `sortValue`. */
  exportValue?: (row: Row) => SortValue;
  align?: "start" | "end";
  /** The column that names the row: the card title on phones, and what "Select ..." says. */
  primary?: boolean;
  defaultHidden?: boolean;
  className?: string;
}

type Density = "comfortable" | "compact";
const ROW_HEIGHT: Record<Density, { class: string; estimate: number }> = {
  comfortable: { class: "h-13", estimate: 52 },
  compact: { class: "h-9", estimate: 36 },
};

interface DataTableProps<Row> {
  /** What the table lists ("Employees"). Read by screen readers; not shown. */
  caption: string;
  columns: readonly Column<Row>[];
  rows: readonly Row[];
  getRowId: (row: Row) => string;
  loading?: boolean;
  /** Shown instead of the rows when there are none. Use an EmptyState. */
  empty?: ReactNode;
  selectable?: boolean;
  selected?: ReadonlySet<string>;
  onSelectedChange?: (ids: ReadonlySet<string>) => void;
  /** Enter on the highlighted row, or a click on the row's open button on phones. */
  onRowOpen?: (row: Row) => void;
  /**
   * The actions for one row, as `MenuItem`s. Adds a "more" button to every row, and "." opens the menu
   * of the highlighted row. Leave it out for a table whose rows have no actions.
   */
  rowMenu?: (row: Row) => ReactNode;
  /** Adds an Export button. It is given the rows in the order shown and the columns that are visible. */
  onExport?: (rows: readonly Row[], columns: readonly Column<Row>[]) => void;
  pageSize?: number;
  /** Above this many rows the table scrolls and draws only the rows in view, instead of paging. */
  virtualiseAfter?: number;
  defaultSort?: { column: string; direction: "asc" | "desc" };
  className?: string;
}

const PHONE = "(max-width: 47.99rem)";
const subscribePhone = (onChange: () => void) => {
  const query = window.matchMedia(PHONE);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
};

interface RowActionsProps {
  /** Names the row for assistive technology: "Actions for Ada Lovelace". */
  label: string;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  onCloseAutoFocus?: (event: Event) => void;
  children: ReactNode;
}

/** The "more" button at the end of a row, and the menu it opens. */
function RowActions({ label, open, onOpenChange, onCloseAutoFocus, children }: RowActionsProps) {
  return (
    <Menu {...(open === undefined ? {} : { open })} {...(onOpenChange ? { onOpenChange } : {})}>
      <MenuTrigger asChild>
        <IconButton label={label} size="sm">
          <Icon icon={Ellipsis} size={20} />
        </IconButton>
      </MenuTrigger>
      <MenuContent {...(onCloseAutoFocus ? { onCloseAutoFocus } : {})}>{children}</MenuContent>
    </Menu>
  );
}

const textOf = (value: SortValue | undefined, fallback: string) =>
  value === null || value === undefined ? fallback : String(value);

/**
 * A table for people records (plan 5.7). Sticky header, sortable columns, column visibility, row
 * selection, a density toggle and an export hook. J and K (or the arrow keys) move through rows,
 * Enter opens one, Space selects it and "." opens its menu. Over 200 rows it draws only what is on screen; below 768 px each
 * row becomes a card.
 */
export function DataTable<Row>({
  caption,
  columns,
  rows,
  getRowId,
  loading = false,
  empty,
  selectable = false,
  selected,
  onSelectedChange,
  onRowOpen,
  rowMenu,
  onExport,
  pageSize = 25,
  virtualiseAfter = 200,
  defaultSort,
  className,
}: DataTableProps<Row>) {
  const tableId = useId();
  const scroller = useRef<HTMLDivElement>(null);
  const grid = useRef<HTMLTableElement>(null);
  // The row whose menu is open, and whether the "." key opened it (focus then goes back to the table).
  const [menuRowId, setMenuRowId] = useState<string | null>(null);
  const menuOpenedByKey = useRef(false);
  const [sort, setSort] = useState(defaultSort ?? null);
  const [hidden, setHidden] = useState<ReadonlySet<string>>(
    () => new Set(columns.filter((c) => c.defaultHidden).map((c) => c.id)),
  );
  const [density, setDensity] = useState<Density>("comfortable");
  const [page, setPage] = useState(0);
  const [activeId, setActiveId] = useState<string | null>(null);
  const phone = useSyncExternalStore(
    subscribePhone,
    () => window.matchMedia(PHONE).matches,
    () => false,
  );

  const visible = columns.filter((column) => !hidden.has(column.id));
  const primary = columns.find((column) => column.primary) ?? columns[0];

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const column = columns.find((c) => c.id === sort.column);
    return column?.sortValue ? sortRows(rows, column.sortValue, sort.direction) : rows;
  }, [rows, columns, sort]);

  // Phones always page: a long list of cards is too heavy to draw whole, and has no fixed row height.
  const virtual = sorted.length > virtualiseAfter && !phone;
  const pageCount = Math.max(1, Math.ceil(sorted.length / pageSize));
  const currentPage = Math.min(page, pageCount - 1);
  const shown = virtual
    ? sorted
    : sorted.slice(currentPage * pageSize, (currentPage + 1) * pageSize);

  const rowHeight = ROW_HEIGHT[density];
  // TanStack Virtual returns functions the React Compiler cannot memoize, so it skips memoizing this one
  // component, which is safe and is what it says it will do. Nothing else here depends on it.
  // eslint-disable-next-line react-hooks/incompatible-library
  const virtualizer = useVirtualizer({
    count: virtual ? shown.length : 0,
    getScrollElement: () => scroller.current,
    estimateSize: () => rowHeight.estimate,
    overscan: 10,
    // Lets the first render (and server render) draw rows before the scroll area is measured.
    initialRect: { width: 960, height: 640 },
  });
  const windowed = virtual ? virtualizer.getVirtualItems() : null;
  const start = windowed?.[0]?.start ?? 0;
  const end = windowed?.at(-1)?.end ?? 0;
  const rowsToDraw = windowed
    ? windowed.map((item) => ({ row: shown[item.index] as Row, index: item.index }))
    : shown.map((row, index) => ({ row, index }));

  const domId = (row: Row) => `${tableId}-row-${encodeURIComponent(getRowId(row))}`;
  const activeIndex = activeId === null ? -1 : shown.findIndex((row) => getRowId(row) === activeId);
  const pickedIds = selected ?? new Set<string>();
  const pagePicked = shown.filter((row) => pickedIds.has(getRowId(row))).length;

  // Keeps the highlighted row in view.
  useEffect(() => {
    if (activeIndex < 0) return;
    if (virtual) virtualizer.scrollToIndex(activeIndex, { align: "auto" });
    else
      document
        .getElementById(`${tableId}-row-${encodeURIComponent(activeId ?? "")}`)
        ?.scrollIntoView({ block: "nearest" });
  }, [activeIndex, activeId, virtual, virtualizer, tableId]);

  function toggleRow(row: Row) {
    if (!onSelectedChange) return;
    const next = new Set(pickedIds);
    const id = getRowId(row);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onSelectedChange(next);
  }

  function togglePage(checked: boolean) {
    if (!onSelectedChange) return;
    const next = new Set(pickedIds);
    for (const row of shown) {
      if (checked) next.add(getRowId(row));
      else next.delete(getRowId(row));
    }
    onSelectedChange(next);
  }

  function moveTo(index: number) {
    const row = shown[Math.min(Math.max(index, 0), shown.length - 1)];
    if (row) setActiveId(getRowId(row));
  }

  function onKeyDown(event: KeyboardEvent<HTMLTableElement>) {
    // Only when the table itself has focus: a checkbox or sort button inside keeps its own keys.
    if (event.target !== event.currentTarget || shown.length === 0) return;
    const current = activeIndex < 0 ? 0 : activeIndex;
    const key = event.key;
    if (key === "j" || key === "ArrowDown") moveTo(activeIndex < 0 ? 0 : current + 1);
    else if (key === "k" || key === "ArrowUp") moveTo(current - 1);
    else if (key === "Home") moveTo(0);
    else if (key === "End") moveTo(shown.length - 1);
    else if (key === "PageDown") moveTo(current + 10);
    else if (key === "PageUp") moveTo(current - 10);
    else if (key === "Enter" && activeIndex >= 0 && onRowOpen) onRowOpen(shown[activeIndex] as Row);
    else if (key === " " && selectable && activeIndex >= 0) toggleRow(shown[activeIndex] as Row);
    else if (key === "." && rowMenu && activeIndex >= 0) {
      menuOpenedByKey.current = true;
      setMenuRowId(getRowId(shown[activeIndex] as Row));
    } else return;
    event.preventDefault();
  }

  function cycleSort(column: Column<Row>) {
    setPage(0);
    setSort((current) =>
      current?.column !== column.id
        ? { column: column.id, direction: "asc" }
        : current.direction === "asc"
          ? { column: column.id, direction: "desc" }
          : null,
    );
  }

  const nameOf = (row: Row) =>
    textOf(primary?.exportValue?.(row) ?? primary?.sortValue?.(row), getRowId(row));

  const toolbar = (
    <div className="flex flex-wrap items-center justify-between gap-3 pb-3">
      <p aria-live="polite" className="text-callout text-label-secondary">
        {selectable && pickedIds.size > 0 ? (
          <>
            {pickedIds.size} selected{" "}
            <button
              type="button"
              className="text-accent-text font-medium underline underline-offset-2"
              onClick={() => onSelectedChange?.(new Set())}
            >
              Clear
            </button>
          </>
        ) : (
          `${sorted.length} ${sorted.length === 1 ? "row" : "rows"}`
        )}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        {phone ? null : (
          <SegmentedControl
            label="Row density"
            size="sm"
            value={density}
            onValueChange={setDensity}
            segments={[
              { value: "comfortable", label: "Comfortable" },
              { value: "compact", label: "Compact" },
            ]}
          />
        )}
        <Menu>
          <MenuTrigger asChild>
            <Button variant="gray" size="sm">
              <Icon icon={Columns3} size={16} />
              Columns
            </Button>
          </MenuTrigger>
          <MenuContent>
            <MenuLabel>Show columns</MenuLabel>
            {columns.map((column) => (
              <MenuCheckboxItem
                key={column.id}
                checked={!hidden.has(column.id)}
                disabled={column === primary}
                onSelect={(event) => event.preventDefault()}
                onCheckedChange={(checked) =>
                  setHidden((current) => {
                    const next = new Set(current);
                    if (checked) next.delete(column.id);
                    else next.add(column.id);
                    return next;
                  })
                }
              >
                {column.header}
              </MenuCheckboxItem>
            ))}
          </MenuContent>
        </Menu>
        {onExport ? (
          <Button variant="gray" size="sm" onClick={() => onExport(sorted, visible)}>
            <Icon icon={Download} size={16} />
            Export
          </Button>
        ) : null}
      </div>
    </div>
  );

  const footer = virtual ? null : (
    <nav aria-label={`${caption}: pages`} className="flex items-center justify-between gap-3 pt-3">
      <p className="text-callout text-label-secondary tabular-nums">
        {sorted.length === 0
          ? "0 rows"
          : `${currentPage * pageSize + 1}–${currentPage * pageSize + shown.length} of ${sorted.length}`}
      </p>
      <div className="flex items-center gap-1">
        <IconButton
          label="Previous page"
          size="sm"
          disabled={currentPage === 0}
          onClick={() => setPage(currentPage - 1)}
        >
          <Icon icon={ChevronLeft} size={20} />
        </IconButton>
        <span className="text-callout text-label-secondary px-1 tabular-nums">
          Page {currentPage + 1} of {pageCount}
        </span>
        <IconButton
          label="Next page"
          size="sm"
          disabled={currentPage >= pageCount - 1}
          onClick={() => setPage(currentPage + 1)}
        >
          <Icon icon={ChevronRight} size={20} />
        </IconButton>
      </div>
    </nav>
  );

  if (loading) {
    return (
      <div className={className}>
        <SkeletonTable rows={Math.min(pageSize, 8)} columns={Math.max(visible.length, 3)} />
      </div>
    );
  }

  if (rows.length === 0) return <div className={className}>{empty ?? null}</div>;

  // ---- Phones: one card per row -------------------------------------------------------------
  if (phone) {
    return (
      <div className={className}>
        {toolbar}
        <ul aria-label={caption} className="flex flex-col gap-3">
          {shown.map((row) => {
            const id = getRowId(row);
            const isPicked = pickedIds.has(id);
            return (
              <li
                key={id}
                className={cn(
                  "bg-elevated rounded-card shadow-e1 flex flex-col gap-2 p-4",
                  isPicked && "bg-accent-tint",
                )}
              >
                <div className="flex items-start gap-3">
                  {selectable ? (
                    <CheckboxControl
                      aria-label={`Select ${nameOf(row)}`}
                      checked={isPicked}
                      onCheckedChange={() => toggleRow(row)}
                    />
                  ) : null}
                  <div className="text-headline text-label min-w-0 flex-1">
                    {primary?.cell(row)}
                  </div>
                  {rowMenu ? (
                    <RowActions label={`Actions for ${nameOf(row)}`}>{rowMenu(row)}</RowActions>
                  ) : null}
                </div>
                <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
                  {visible
                    .filter((column) => column !== primary)
                    .map((column) => (
                      <div key={column.id} className="col-span-2 grid grid-cols-subgrid">
                        <dt className="text-footnote text-label-secondary">{column.header}</dt>
                        <dd className="text-callout text-label text-right">{column.cell(row)}</dd>
                      </div>
                    ))}
                </dl>
                {onRowOpen ? (
                  <Button
                    variant="tinted"
                    size="sm"
                    className="self-start"
                    onClick={() => onRowOpen(row)}
                  >
                    Open<span className="sr-only"> {nameOf(row)}</span>
                  </Button>
                ) : null}
              </li>
            );
          })}
        </ul>
        {footer}
      </div>
    );
  }

  // ---- Wider screens: a table ---------------------------------------------------------------
  const columnCount = visible.length + (selectable ? 1 : 0) + (rowMenu ? 1 : 0);
  return (
    <div className={className}>
      {toolbar}
      <div ref={scroller} className="bg-elevated rounded-card shadow-e1 max-h-[75vh] overflow-auto">
        <table
          ref={grid}
          role="grid"
          tabIndex={0}
          aria-label={caption}
          aria-rowcount={sorted.length}
          aria-activedescendant={activeIndex >= 0 ? domId(shown[activeIndex] as Row) : undefined}
          aria-multiselectable={selectable || undefined}
          onKeyDown={onKeyDown}
          onFocus={(event) => {
            if (event.target === event.currentTarget && activeId === null) moveTo(0);
          }}
          className="group/table w-full border-collapse text-left outline-none focus-visible:outline-accent focus-visible:outline-2 focus-visible:-outline-offset-2"
        >
          <thead>
            <tr>
              {selectable ? (
                <th
                  scope="col"
                  className="bg-elevated border-separator sticky top-0 z-10 w-12 border-b px-4"
                >
                  <CheckboxControl
                    aria-label="Select all rows on this page"
                    checked={
                      pagePicked === 0
                        ? false
                        : pagePicked === shown.length
                          ? true
                          : "indeterminate"
                    }
                    onCheckedChange={(checked) => togglePage(checked === true)}
                  />
                </th>
              ) : null}
              {visible.map((column) => {
                const direction = sort?.column === column.id ? sort.direction : null;
                return (
                  <th
                    key={column.id}
                    scope="col"
                    aria-sort={
                      column.sortValue
                        ? direction === "asc"
                          ? "ascending"
                          : direction === "desc"
                            ? "descending"
                            : "none"
                        : undefined
                    }
                    className={cn(
                      "bg-elevated border-separator text-footnote text-label-secondary sticky top-0 z-10 border-b px-4 py-3 font-medium whitespace-nowrap",
                      column.align === "end" && "text-right",
                    )}
                  >
                    {column.sortValue ? (
                      <button
                        type="button"
                        onClick={() => cycleSort(column)}
                        className="text-label-secondary hover:text-label rounded-control inline-flex cursor-pointer items-center gap-1 font-medium"
                      >
                        {column.header}
                        <Icon
                          icon={
                            direction === "asc"
                              ? ArrowUp
                              : direction === "desc"
                                ? ArrowDown
                                : ChevronsUpDown
                          }
                          size={16}
                          className={direction ? "text-label" : "opacity-60"}
                        />
                      </button>
                    ) : (
                      column.header
                    )}
                  </th>
                );
              })}
              {rowMenu ? (
                <th
                  scope="col"
                  className="bg-elevated border-separator sticky top-0 z-10 w-14 border-b px-2"
                >
                  <span className="sr-only">Actions</span>
                </th>
              ) : null}
            </tr>
          </thead>
          <tbody>
            {virtual && start > 0 ? (
              <tr aria-hidden="true">
                <td colSpan={columnCount} height={start} className="p-0" />
              </tr>
            ) : null}
            {rowsToDraw.map(({ row, index }) => {
              const id = getRowId(row);
              const isPicked = pickedIds.has(id);
              return (
                <tr
                  key={id}
                  id={domId(row)}
                  data-index={index}
                  ref={virtual ? virtualizer.measureElement : undefined}
                  aria-selected={selectable ? isPicked : undefined}
                  aria-rowindex={index + 1 + (virtual ? 0 : currentPage * pageSize)}
                  data-active={id === activeId || undefined}
                  onDoubleClick={() => onRowOpen?.(row)}
                  className={cn(
                    ROW_HEIGHT[density].class,
                    "border-separator border-b last:border-b-0",
                    isPicked && "bg-accent-tint",
                    "data-[active]:group-focus-visible/table:ring-accent data-[active]:group-focus-visible/table:ring-2 data-[active]:group-focus-visible/table:ring-inset",
                  )}
                >
                  {selectable ? (
                    <td className="w-12 px-4">
                      <CheckboxControl
                        aria-label={`Select ${nameOf(row)}`}
                        checked={isPicked}
                        onCheckedChange={() => toggleRow(row)}
                      />
                    </td>
                  ) : null}
                  {visible.map((column) => (
                    <td
                      key={column.id}
                      className={cn(
                        "text-body text-label px-4",
                        column.align === "end" && "text-right tabular-nums",
                        column.className,
                      )}
                    >
                      {column.cell(row)}
                    </td>
                  ))}
                  {rowMenu ? (
                    <td className="w-14 px-2 text-right">
                      <RowActions
                        label={`Actions for ${nameOf(row)}`}
                        open={menuRowId === id}
                        onOpenChange={(open) => {
                          // A click on the button opened it (the "." key sets the row itself).
                          if (open) menuOpenedByKey.current = false;
                          setMenuRowId(open ? id : null);
                        }}
                        onCloseAutoFocus={(event) => {
                          // Opened with ".", the person was in the table: put them back there.
                          if (!menuOpenedByKey.current) return;
                          menuOpenedByKey.current = false;
                          event.preventDefault();
                          grid.current?.focus();
                        }}
                      >
                        {rowMenu(row)}
                      </RowActions>
                    </td>
                  ) : null}
                </tr>
              );
            })}
            {virtual && windowed ? (
              <tr aria-hidden="true">
                <td
                  colSpan={columnCount}
                  height={Math.max(virtualizer.getTotalSize() - end, 0)}
                  className="p-0"
                />
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
      {footer}
    </div>
  );
}
