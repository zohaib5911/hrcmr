import { describe, expect, it } from "vitest";

import { findPeople, flatten, layoutTree, NODE_HEIGHT, NODE_WIDTH, type OrgPerson } from "./layout";

function person(name: string, reports: OrgPerson[] = []): OrgPerson {
  return {
    id: name.toLowerCase().replace(/\s+/g, "-"),
    name,
    job_title: null,
    department: null,
    level: null,
    rtw_status: null,
    reports,
  };
}

function placed(layout: ReturnType<typeof layoutTree>, name: string) {
  const found = layout.nodes.find((node) => node.person.name === name);
  if (!found) throw new Error(`${name} is not on the canvas`);
  return found;
}

const centre = (node: { x: number }) => node.x + NODE_WIDTH / 2;

describe("layoutTree", () => {
  const tree = [
    person("Boss", [
      person("Mid One", [person("Dee"), person("Eli")]),
      person("Mid Two", [person("Fay")]),
    ]),
  ];

  it("centres each manager over their reports and draws one line per report", () => {
    const layout = layoutTree(tree);
    expect(layout.nodes).toHaveLength(6);
    expect(layout.links).toHaveLength(5); // every person but the root has one line in
    const midOne = placed(layout, "Mid One");
    const dee = placed(layout, "Dee");
    const eli = placed(layout, "Eli");
    expect(centre(midOne)).toBeCloseTo((centre(dee) + centre(eli)) / 2);
    const boss = placed(layout, "Boss");
    expect(centre(boss)).toBeCloseTo((centre(midOne) + centre(placed(layout, "Mid Two"))) / 2);
  });

  it("puts each level one row lower and reports the depth", () => {
    const layout = layoutTree(tree);
    expect(placed(layout, "Boss").depth).toBe(0);
    expect(placed(layout, "Mid One").depth).toBe(1);
    expect(placed(layout, "Eli").depth).toBe(2);
    expect(placed(layout, "Eli").y).toBeGreaterThan(placed(layout, "Mid One").y);
    expect(layout.height).toBe(3 * NODE_HEIGHT + 2 * 56);
  });

  it("never overlaps two cards in the same row, even for a flat team of 60", () => {
    const team = person(
      "Head",
      Array.from({ length: 59 }, (_, index) => person(`Member ${index}`)),
    );
    const layout = layoutTree([team]);
    expect(layout.nodes).toHaveLength(60);
    const seen = layout.nodes.filter((node) => node.depth === 1).map((node) => node.x);
    seen.sort((a, b) => a - b);
    const gaps = seen.slice(1).map((x, i) => x - (seen[i] ?? 0));
    for (const gap of gaps) expect(gap).toBeGreaterThanOrEqual(NODE_WIDTH);
  });

  it("sets roots side by side on the first row", () => {
    const layout = layoutTree([person("First"), person("Second")]);
    const first = placed(layout, "First");
    const second = placed(layout, "Second");
    expect(first.y).toBe(0);
    expect(second.y).toBe(0);
    expect(second.x).toBeGreaterThanOrEqual(first.x + NODE_WIDTH);
    expect(layout.links).toHaveLength(0);
  });

  it("has no size when there is nobody to draw", () => {
    expect(layoutTree([])).toEqual({ nodes: [], links: [], width: 0, height: 0 });
  });
});

describe("flatten", () => {
  it("lists everyone depth first with their depth", () => {
    const rows = flatten([person("A", [person("B"), person("C", [person("D")])]), person("E")]);
    expect(rows.map((row) => [row.person.name, row.depth])).toEqual([
      ["A", 0],
      ["B", 1],
      ["C", 1],
      ["D", 2],
      ["E", 0],
    ]);
  });
});

describe("findPeople", () => {
  const roots = [person("Ada Boss", [person("Sam Lee"), person("Samira Khan")])];

  it("finds names regardless of case and surrounding spaces", () => {
    expect(findPeople(roots, "  sam ").map((p) => p.name)).toEqual(["Sam Lee", "Samira Khan"]);
    expect(findPeople(roots, "BOSS").map((p) => p.name)).toEqual(["Ada Boss"]);
  });

  it("finds nothing for an empty or blank query", () => {
    expect(findPeople(roots, "")).toEqual([]);
    expect(findPeople(roots, "   ")).toEqual([]);
  });

  it("stops at the limit", () => {
    expect(findPeople(roots, "a", 2)).toHaveLength(2);
  });
});
