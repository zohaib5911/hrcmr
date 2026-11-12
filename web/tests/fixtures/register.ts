import type { components } from "@/lib/api/client";

export const registerFixture: components["schemas"]["ExploreOut"] = {
  publications: [
    {
      id: "00000000-0000-0000-0000-000000000001",
      published_on: "2026-11-10",
      source_url: "https://www.gov.uk/register.csv",
    },
    {
      id: "00000000-0000-0000-0000-000000000002",
      published_on: "2026-11-11",
      source_url: "https://www.gov.uk/register.csv",
    },
  ],
  selected: {
    id: "00000000-0000-0000-0000-000000000002",
    published_on: "2026-11-11",
    source_url: "https://www.gov.uk/register.csv",
  },
  baseline: {
    id: "00000000-0000-0000-0000-000000000001",
    published_on: "2026-11-10",
    source_url: "https://www.gov.uk/register.csv",
  },
  total: 51,
  previous_total: 50,
  page: 1,
  page_size: 50,
  results: [
    {
      id: "stable",
      name: "Stable Ltd",
      town: "Leeds",
      region: "Yorkshire and The Humber",
      industry: "J",
      precision: "town",
      first_seen: "2026-11-10",
      routes: ["Skilled Worker"],
      ratings: ["Worker (A rating)"],
    },
  ],
  newest: [],
  facets: {
    region: ["Yorkshire and The Humber"],
    route: ["Skilled Worker"],
    rating: ["Worker (A rating)"],
    industry: ["J"],
  },
  sections: {
    regions: [{ label: "Yorkshire and The Humber", count: 51 }],
    towns: [{ label: "Leeds", count: 51 }],
    routes: [{ label: "Skilled Worker", count: 51 }],
    ratings: [{ label: "Worker (A rating)", count: 51 }],
    types: [{ label: "Worker", count: 51 }],
    precision: [{ label: "town", count: 51 }],
    industries: [{ label: "J", count: 51 }],
  },
  previous_regions: [{ label: "Yorkshire and The Humber", count: 50 }],
  daily_previous_regions: [{ label: "Yorkshire and The Humber", count: 50 }],
  timeline: [
    { published_on: "2026-11-10", count: 50, added: 50, removed: 0 },
    { published_on: "2026-11-11", count: 51, added: 2, removed: 1 },
  ],
};
