import type { components } from "@/lib/api/client";

export type OrgPerson = components["schemas"]["OrgPerson"];

/** Size of one person's card on the canvas, in CSS pixels before zoom. */
export const NODE_WIDTH = 220;
export const NODE_HEIGHT = 76;
const GAP_X = 24;
const GAP_Y = 56;

export interface Placed {
  person: OrgPerson;
  /** Top-left corner of the card. */
  x: number;
  y: number;
  depth: number;
}

/** A reporting line: from the bottom centre of a manager to the top centre of a report. */
export interface Link {
  from: readonly [number, number];
  to: readonly [number, number];
}

export interface Layout {
  nodes: Placed[];
  links: Link[];
  width: number;
  height: number;
}

export interface Row {
  person: OrgPerson;
  depth: number;
}

/**
 * Lays the tree out top-down. Each person sits centred over their reports; people with no reports
 * take the next free column, so no two cards overlap. Roots sit side by side.
 */
export function layoutTree(roots: readonly OrgPerson[]): Layout {
  const nodes: Placed[] = [];
  const links: Link[] = [];
  let column = 0;
  let deepest = -1;
  const rowTop = (depth: number) => depth * (NODE_HEIGHT + GAP_Y);

  function place(person: OrgPerson, depth: number): number {
    deepest = Math.max(deepest, depth);
    let centre: number;
    if (person.reports.length === 0) {
      centre = column * (NODE_WIDTH + GAP_X) + NODE_WIDTH / 2;
      column += 1;
    } else {
      const childCentres = person.reports.map((child) => place(child, depth + 1));
      centre = (Math.min(...childCentres) + Math.max(...childCentres)) / 2;
      childCentres.forEach((childCentre) => {
        links.push({
          from: [centre, rowTop(depth) + NODE_HEIGHT],
          to: [childCentre, rowTop(depth + 1)],
        });
      });
    }
    nodes.push({ person, x: centre - NODE_WIDTH / 2, y: rowTop(depth), depth });
    return centre;
  }

  roots.forEach((root) => place(root, 0));
  if (column === 0) return { nodes, links, width: 0, height: 0 };
  return {
    nodes,
    links,
    width: column * (NODE_WIDTH + GAP_X) - GAP_X,
    height: rowTop(deepest) + NODE_HEIGHT,
  };
}

/** Everyone in depth-first order, with how far down the chart each one sits (for the list view). */
export function flatten(roots: readonly OrgPerson[]): Row[] {
  const rows: Row[] = [];
  const stack: Row[] = roots.map((person) => ({ person, depth: 0 })).reverse();
  for (let row = stack.pop(); row !== undefined; row = stack.pop()) {
    rows.push(row);
    const reports = [...row.person.reports].reverse();
    for (const report of reports) {
      stack.push({ person: report, depth: row.depth + 1 });
    }
  }
  return rows;
}

/** People whose name contains the query (ignoring case and spaces at the ends), at most `limit`. */
export function findPeople(roots: readonly OrgPerson[], query: string, limit = 8): OrgPerson[] {
  const wanted = query.trim().toLowerCase();
  if (wanted === "") return [];
  return flatten(roots)
    .map((row) => row.person)
    .filter((person) => person.name.toLowerCase().includes(wanted))
    .slice(0, limit);
}
