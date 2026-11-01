// @vitest-environment jsdom
import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { DataTable, type Column } from "./data-table";
import { MenuItem } from "./menu";

interface Person {
  id: string;
  name: string;
  department: string;
  salary: number | null;
}

const PEOPLE: Person[] = [
  { id: "1", name: "Grace Hopper", department: "Care", salary: 31000 },
  { id: "2", name: "Ada Lovelace", department: "Operations", salary: 28000 },
  { id: "3", name: "Alan Turing", department: "Finance", salary: null },
  { id: "4", name: "Katherine Johnson", department: "Care", salary: 45000 },
];

const COLUMNS: Column<Person>[] = [
  { id: "name", header: "Name", primary: true, sortValue: (p) => p.name, cell: (p) => p.name },
  {
    id: "department",
    header: "Department",
    sortValue: (p) => p.department,
    cell: (p) => p.department,
  },
  {
    id: "salary",
    header: "Salary",
    align: "end",
    sortValue: (p) => p.salary,
    cell: (p) => String(p.salary ?? ""),
  },
];

function names(table: HTMLElement) {
  return (
    within(table)
      .getAllByRole("row")
      .slice(1) // header row
      // A <td> in a role="grid" table is a gridcell in browsers; Testing Library models it as a cell.
      .map((row) => within(row).getAllByRole("cell")[0]?.textContent)
  );
}

function Table(props: Partial<React.ComponentProps<typeof DataTable<Person>>>) {
  return (
    <DataTable caption="People" columns={COLUMNS} rows={PEOPLE} getRowId={(p) => p.id} {...props} />
  );
}

describe("DataTable sorting", () => {
  it("starts in the order given, then sorts ascending, descending, and back", async () => {
    render(<Table />);
    const table = screen.getByRole("grid", { name: "People" });
    expect(names(table)).toEqual([
      "Grace Hopper",
      "Ada Lovelace",
      "Alan Turing",
      "Katherine Johnson",
    ]);
    const header = screen.getByRole("columnheader", { name: /Name/ });
    await userEvent.click(within(header).getByRole("button"));
    expect(header).toHaveAttribute("aria-sort", "ascending");
    expect(names(table)).toEqual([
      "Ada Lovelace",
      "Alan Turing",
      "Grace Hopper",
      "Katherine Johnson",
    ]);
    await userEvent.click(within(header).getByRole("button"));
    expect(header).toHaveAttribute("aria-sort", "descending");
    expect(names(table)).toEqual([
      "Katherine Johnson",
      "Grace Hopper",
      "Alan Turing",
      "Ada Lovelace",
    ]);
    await userEvent.click(within(header).getByRole("button"));
    expect(header).toHaveAttribute("aria-sort", "none");
    expect(names(table)).toEqual([
      "Grace Hopper",
      "Ada Lovelace",
      "Alan Turing",
      "Katherine Johnson",
    ]);
  });

  it("sorts numbers as numbers and keeps empty values last either way", async () => {
    render(<Table />);
    const table = screen.getByRole("grid", { name: "People" });
    const header = screen.getByRole("columnheader", { name: /Salary/ });
    await userEvent.click(within(header).getByRole("button"));
    expect(names(table)).toEqual([
      "Ada Lovelace",
      "Grace Hopper",
      "Katherine Johnson",
      "Alan Turing",
    ]);
    await userEvent.click(within(header).getByRole("button"));
    expect(names(table)).toEqual([
      "Katherine Johnson",
      "Grace Hopper",
      "Ada Lovelace",
      "Alan Turing",
    ]);
  });

  it("only marks sortable columns as sortable", () => {
    render(<Table columns={[...COLUMNS, { id: "plain", header: "Notes", cell: () => "-" }]} />);
    expect(screen.getByRole("columnheader", { name: "Notes" })).not.toHaveAttribute("aria-sort");
  });

  it("can start sorted", () => {
    render(<Table defaultSort={{ column: "department", direction: "asc" }} />);
    expect(names(screen.getByRole("grid", { name: "People" }))[0]).toBe("Grace Hopper"); // Care, ties keep order
  });
});

describe("DataTable selection", () => {
  function Selectable() {
    const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
    return <Table selectable selected={selected} onSelectedChange={setSelected} />;
  }

  it("selects rows, names each box after the person, and counts them", async () => {
    render(<Selectable />);
    await userEvent.click(screen.getByRole("checkbox", { name: "Select Ada Lovelace" }));
    expect(screen.getByRole("checkbox", { name: "Select Ada Lovelace" })).toBeChecked();
    expect(screen.getByText(/1 selected/)).toBeInTheDocument();
  });

  it("the header box selects everything on the page, shows a dash for some, and clears", async () => {
    render(<Selectable />);
    const all = screen.getByRole("checkbox", { name: "Select all rows on this page" });
    expect(all).not.toBeChecked();
    await userEvent.click(all);
    expect(screen.getByText(/4 selected/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: "Select Alan Turing" }));
    expect(all).toHaveAttribute("aria-checked", "mixed");
    await userEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(screen.getByText("4 rows")).toBeInTheDocument();
  });

  it("selection survives sorting", async () => {
    render(<Selectable />);
    await userEvent.click(screen.getByRole("checkbox", { name: "Select Grace Hopper" }));
    await userEvent.click(
      within(screen.getByRole("columnheader", { name: /Name/ })).getByRole("button"),
    );
    expect(screen.getByRole("checkbox", { name: "Select Grace Hopper" })).toBeChecked();
  });
});

describe("DataTable keyboard", () => {
  it("J and K move the highlight, Enter opens the row, Space selects it", async () => {
    const onRowOpen = vi.fn();
    function Keyed() {
      const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
      return (
        <Table
          selectable
          selected={selected}
          onSelectedChange={setSelected}
          onRowOpen={onRowOpen}
        />
      );
    }
    render(<Keyed />);
    const table = screen.getByRole("grid", { name: "People" });
    act(() => table.focus());
    const active = () => table.querySelector("tr[data-active]")?.textContent ?? "";
    expect(active()).toContain("Grace Hopper");
    await userEvent.keyboard("j");
    expect(active()).toContain("Ada Lovelace");
    await userEvent.keyboard("j");
    await userEvent.keyboard("k");
    expect(active()).toContain("Ada Lovelace");
    await userEvent.keyboard("{Enter}");
    expect(onRowOpen).toHaveBeenCalledWith(expect.objectContaining({ id: "2" }));
    await userEvent.keyboard(" ");
    expect(screen.getByRole("checkbox", { name: "Select Ada Lovelace" })).toBeChecked();
    await userEvent.keyboard("{End}");
    expect(active()).toContain("Katherine Johnson");
    await userEvent.keyboard("j");
    expect(active()).toContain("Katherine Johnson"); // stops at the last row
  });

  it("points assistive technology at the highlighted row", async () => {
    render(<Table />);
    const table = screen.getByRole("grid", { name: "People" });
    act(() => table.focus());
    await userEvent.keyboard("j");
    const row = table.querySelector("tr[data-active]");
    expect(table).toHaveAttribute("aria-activedescendant", row?.id);
  });
});

describe("DataTable states and paging", () => {
  it("shows what it is given when there are no rows", () => {
    render(<Table rows={[]} empty={<p>Nobody here yet</p>} />);
    expect(screen.getByText("Nobody here yet")).toBeInTheDocument();
    expect(screen.queryByRole("grid")).not.toBeInTheDocument();
  });

  it("shows a loading placeholder, announced politely, instead of the rows", () => {
    render(<Table loading />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading");
    expect(screen.queryByRole("grid")).not.toBeInTheDocument();
  });

  it("pages, with the range and page count", async () => {
    render(<Table pageSize={3} />);
    expect(screen.getByText("1–3 of 4")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Next page" }));
    expect(screen.getByText("4–4 of 4")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
  });

  it("starts with default-hidden columns hidden, and the menu lists every column", async () => {
    render(
      <Table
        columns={COLUMNS.map((c) => (c.id === "salary" ? { ...c, defaultHidden: true } : c))}
      />,
    );
    expect(screen.queryByRole("columnheader", { name: /Salary/ })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Columns/ }));
    expect(await screen.findByRole("menuitemcheckbox", { name: "Salary" })).toHaveAttribute(
      "aria-checked",
      "false",
    );
    // The column that names the row cannot be hidden.
    expect(screen.getByRole("menuitemcheckbox", { name: "Name" })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
  });

  it("hands the rows in the order shown, and the visible columns, to the export hook", async () => {
    const onExport = vi.fn();
    render(<Table onExport={onExport} defaultSort={{ column: "name", direction: "asc" }} />);
    await userEvent.click(screen.getByRole("button", { name: "Export" }));
    const [rows, columns] = onExport.mock.calls[0] as [Person[], Column<Person>[]];
    expect(rows.map((r) => r.name)).toEqual([
      "Ada Lovelace",
      "Alan Turing",
      "Grace Hopper",
      "Katherine Johnson",
    ]);
    expect(columns.map((c) => c.id)).toEqual(["name", "department", "salary"]);
  });

  // How many rows are DRAWN needs a real layout, so the browser test (tests/e2e/design-components.spec.ts)
  // checks that. Here: which mode is chosen at the 200-row line.
  const people = (count: number): Person[] =>
    Array.from({ length: count }, (_, i) => ({
      id: String(i),
      name: `Person ${i}`,
      department: "Care",
      salary: i,
    }));

  it("pages up to 200 rows", () => {
    render(<Table rows={people(200)} />);
    expect(screen.getByText("1–25 of 200")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next page" })).toBeEnabled();
  });

  it("over 200 rows it stops paging and scrolls, still telling assistive technology how many rows there are", () => {
    render(<Table rows={people(201)} />);
    expect(screen.queryByRole("button", { name: "Next page" })).not.toBeInTheDocument();
    expect(screen.getByRole("grid", { name: "People" })).toHaveAttribute("aria-rowcount", "201");
  });

  it("the line can be moved", () => {
    render(<Table rows={people(60)} virtualiseAfter={50} />);
    expect(screen.queryByRole("button", { name: "Next page" })).not.toBeInTheDocument();
  });
});

describe("DataTable row menu", () => {
  const onArchive = vi.fn();
  const rowMenu = (person: Person) => (
    <>
      <MenuItem onSelect={() => onArchive(person.id)}>Archive</MenuItem>
      <MenuItem>Copy link</MenuItem>
    </>
  );

  it("has no menu button unless a menu is given", () => {
    render(<Table />);
    expect(screen.queryByRole("button", { name: /^Actions for/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Actions" })).not.toBeInTheDocument();
  });

  it("adds a button to every row, named after the person, and a hidden column heading for it", () => {
    render(<Table rowMenu={rowMenu} />);
    for (const person of PEOPLE)
      expect(screen.getByRole("button", { name: `Actions for ${person.name}` })).toBeVisible();
    expect(screen.getByRole("columnheader", { name: "Actions" })).toBeInTheDocument();
  });

  it("the button opens that row's menu, and choosing an item runs it", async () => {
    onArchive.mockClear();
    render(<Table rowMenu={rowMenu} />);
    await userEvent.click(screen.getByRole("button", { name: "Actions for Alan Turing" }));
    const menu = screen.getByRole("menu");
    expect(within(menu).getAllByRole("menuitem")).toHaveLength(2);
    await userEvent.click(within(menu).getByRole("menuitem", { name: "Archive" }));
    expect(onArchive).toHaveBeenCalledExactlyOnceWith("3");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it('"." opens the menu of the highlighted row; Esc closes it and the cursor is back in the table', async () => {
    onArchive.mockClear();
    render(<Table rowMenu={rowMenu} />);
    const table = screen.getByRole("grid", { name: "People" });
    act(() => table.focus());
    await userEvent.keyboard("jj"); // Alan Turing
    await userEvent.keyboard(".");
    const menu = screen.getByRole("menu");
    expect(menu).toBeVisible();
    // It is Alan's menu: it hangs from his button.
    expect(
      screen.getByRole("button", { name: "Actions for Alan Turing", hidden: true }),
    ).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByRole("button", { name: "Actions for Ada Lovelace", hidden: true }),
    ).toHaveAttribute("aria-expanded", "false");
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(table).toHaveFocus();
    // The highlight is where it was left, so J carries on from there.
    await userEvent.keyboard("j");
    expect(table.querySelector("tr[data-active]")?.textContent).toContain("Katherine Johnson");
  });

  it('choosing an item from the "." menu runs it and puts the cursor back in the table', async () => {
    onArchive.mockClear();
    render(<Table rowMenu={rowMenu} />);
    const table = screen.getByRole("grid", { name: "People" });
    act(() => table.focus());
    await userEvent.keyboard(".");
    await userEvent.keyboard("{Enter}"); // the first item
    expect(onArchive).toHaveBeenCalledExactlyOnceWith("1");
    expect(table).toHaveFocus();
  });

  it("a menu opened with the mouse gives focus back to its button, not the table", async () => {
    render(<Table rowMenu={rowMenu} />);
    const button = screen.getByRole("button", { name: "Actions for Ada Lovelace" });
    await userEvent.click(button);
    await userEvent.keyboard("{Escape}");
    expect(button).toHaveFocus();
  });

  it('"." does nothing without a menu, or before a row is highlighted', async () => {
    render(<Table />);
    const table = screen.getByRole("grid", { name: "People" });
    act(() => table.focus());
    await userEvent.keyboard(".");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });
});
