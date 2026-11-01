import {
  COLOUR_TOKENS,
  ELEVATIONS,
  RADII,
  type ColourToken,
  type TokenGroup,
} from "@/lib/design/catalog";

import { TokenValue } from "./token-value";

const GROUPS: readonly { group: TokenGroup; title: string }[] = [
  { group: "surface", title: "Surfaces" },
  { group: "text", title: "Text" },
  { group: "accent", title: "Accent" },
  { group: "status", title: "Status" },
  { group: "material", title: "Materials" },
];

// Written out in full so Tailwind finds every class.
const TEXT_SAMPLES = [
  { className: "text-label", name: "Label" },
  { className: "text-label-secondary", name: "Secondary" },
  { className: "text-label-tertiary", name: "Tertiary (large only)" },
  { className: "text-accent-text", name: "Link" },
  { className: "text-success", name: "Success" },
  { className: "text-warning", name: "Warning" },
  { className: "text-danger", name: "Danger" },
  { className: "text-info", name: "Info" },
] as const;

const SURFACE_SAMPLES = [
  { className: "bg-canvas", name: "Canvas" },
  { className: "bg-elevated", name: "Card" },
  { className: "bg-grouped", name: "Grouped" },
] as const;

const CHIPS = [
  { className: "bg-success-tint text-success", label: "Verified" },
  { className: "bg-warning-tint text-warning", label: "Expiring in 21 days" },
  { className: "bg-danger-tint text-danger", label: "Expired" },
  { className: "bg-info-tint text-info", label: "Pending" },
] as const;

function Swatch({ token }: { token: ColourToken }) {
  return (
    <li className="flex flex-col gap-2">
      <div className="bg-elevated rounded-control ring-separator ring-1">
        <div data-swatch={token.name} className={`${token.swatch} rounded-control h-14`} />
      </div>
      <div>
        <p className="text-footnote text-label font-mono font-medium">{token.name}</p>
        <p className="text-caption text-label-secondary font-mono break-all">
          <TokenValue token={token.name} />
        </p>
        <p className="text-caption text-label-secondary">{token.use}</p>
      </div>
    </li>
  );
}

/**
 * Every token, rendered inside a fixed `data-theme` scope, so light and dark can be compared on one
 * screen whatever the visitor's own setting is.
 */
export function ThemePanel({ theme }: { theme: "light" | "dark" }) {
  const title = theme === "light" ? "Light" : "Dark";
  return (
    <section
      data-theme={theme}
      data-testid={`panel-${theme}`}
      aria-labelledby={`panel-${theme}-title`}
      className="theme-surface rounded-sheet ring-separator flex flex-col gap-8 p-6 ring-1"
    >
      <h2 id={`panel-${theme}-title`} className="text-title-2">
        {title}
      </h2>

      {GROUPS.map(({ group, title: groupTitle }) => (
        <div key={group} className="flex flex-col gap-3">
          <h3 className="text-headline">{groupTitle}</h3>
          <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            {COLOUR_TOKENS.filter((token) => token.group === group).map((token) => (
              <Swatch key={token.name} token={token} />
            ))}
          </ul>
        </div>
      ))}

      <div className="flex flex-col gap-3">
        <h3 className="text-headline">Text on each surface</h3>
        <div className="grid gap-3 sm:grid-cols-3">
          {SURFACE_SAMPLES.map((surface) => (
            <div
              key={surface.name}
              className={`${surface.className} rounded-card ring-separator flex flex-col gap-1 p-4 ring-1`}
            >
              <p className="text-caption text-label-secondary font-medium tracking-wide uppercase">
                {surface.name}
              </p>
              {TEXT_SAMPLES.map((sample) => (
                <p key={sample.name} className={`${sample.className} text-callout`}>
                  {sample.name}
                </p>
              ))}
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <h3 className="text-headline">Status chips and buttons</h3>
        <div className="flex flex-wrap items-center gap-2">
          {CHIPS.map((chip) => (
            <span
              key={chip.label}
              className={`${chip.className} rounded-pill text-footnote px-2.5 py-0.5 font-medium`}
            >
              {chip.label}
            </span>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <span className="bg-accent text-on-accent rounded-control hit-target text-headline inline-flex items-center px-4">
            Filled
          </span>
          <span className="bg-accent-pressed text-on-accent rounded-control hit-target text-headline inline-flex items-center px-4">
            Pressed
          </span>
          <span className="text-accent-text text-body underline underline-offset-2">
            A link in the accent colour
          </span>
          <span className="bg-fill-secondary text-label-secondary rounded-control hit-target text-body inline-flex items-center px-3">
            Placeholder text
          </span>
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <h3 className="text-headline">Elevation</h3>
        <ul className="bg-grouped rounded-card grid grid-cols-3 gap-4 p-4">
          {ELEVATIONS.map((elevation) => (
            <li
              key={elevation.name}
              data-elevation={elevation.name}
              className={`${elevation.shadow} bg-elevated rounded-card text-footnote flex h-20 flex-col justify-center p-3`}
            >
              <span className="font-mono font-medium">{elevation.name}</span>
              <span className="text-label-secondary text-caption">{elevation.use}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="flex flex-col gap-3">
        <h3 className="text-headline">Radius</h3>
        <ul className="flex flex-wrap items-end gap-4">
          {RADII.map((radius) => (
            <li key={radius.key} className="flex flex-col items-center gap-1">
              <div
                className={`${radius.utility} bg-fill-secondary ring-separator h-12 w-20 ring-1`}
              />
              <span className="text-caption text-label-secondary">
                {radius.key} {radius.px === 999 ? "pill" : `${radius.px}px`}
              </span>
            </li>
          ))}
        </ul>
      </div>

      <div className="flex flex-col gap-3">
        <h3 className="text-headline">Materials</h3>
        <div className="from-accent to-success-fill rounded-card relative flex h-40 flex-col justify-between overflow-hidden bg-linear-to-br p-3">
          <div className="material-chrome rounded-control text-callout text-label px-3 py-2">
            Sidebar and toolbar material
          </div>
          <div className="material-sheet rounded-popover shadow-e2 text-callout text-label px-3 py-2">
            Sheet and popover material
          </div>
        </div>
      </div>
    </section>
  );
}
