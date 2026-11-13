# StuffHub artwork

The nine supplied assets were copied byte for byte from the owner's `/home/zohaib/cmr_hr/logo/` directory:

| Committed asset | Owner source                               |
| --------------- | ------------------------------------------ |
| logo.svg        | stuffhub-logo.svg                          |
| logo-dark.svg   | derived/stuffhub-logo-dark-transparent.svg |
| logo-mono.svg   | stuffhub-logo-mono.svg                     |
| mark.svg        | stuffhub-icon.svg                          |
| mark-dark.svg   | derived/stuffhub-icon-dark-transparent.svg |
| mark-mono.svg   | stuffhub-icon-mono.svg                     |
| mark-small.svg  | stuffhub-icon-small.svg                    |
| favicon-512.png | favicon-512.png                            |
| icon-512.png    | stuffhub-icon-512.png                      |

The owner's derived dark SVGs remove the black background plate from the original dark artwork. No other artwork edits are made here. At 32 px and below, use the simplified small mark in either theme.

From `web/`, run `node scripts/generate-brand-assets.mjs` to regenerate the committed PNG derivatives:

- `app/icon.png`: 512 px mark; `app/icon1.png`: 32 px simplified mark.
- `app/apple-icon.png`: 180 px mark on opaque white, with approximately 12% padding on each side.
- `clock-{192,512}.png`: regular PWA marks.
- `clock-maskable-{192,512}.png`: opaque white with the entire mark inside the central 80% safe circle.
- `logo-email.png`: 538 × 128 px lockup on white, displayed at 269 × 64 px in email.

The Open Graph route embeds the original light SVG lockup in its generated PNG. `BrandLogo` uses CSS to select the light or dark SVG before first paint, reserving fixed dimensions.
