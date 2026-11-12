# Unpublished comparison templates

`lib/comparison-drafts.ts` contains worksheets for `/compare/hr-software-uk`,
`/compare/sponsor-compliance-software-uk`, and `/vs/{competitor}`.
`components/marketing/comparison-template.tsx` renders them for editorial work.
Both public route families deliberately return 404 and declare noindex metadata.
There is no preview query parameter or environment switch that publishes them.

Before wiring any template into a public page:

- Replace placeholders with evidence for the actual products and plans.
- Verify competitor prices from each competitor's public pricing page. Show that
  source link and the date checked on the finished page, including billing period,
  currency, VAT, minimum charges and per-person fees where applicable.
- Use our pricing configuration for our prices; do not duplicate figures in copy.
- Obtain the owner's approval for each page before changing its route guard.
- Review metadata, canonical URL, sitemap entries and navigation in that change.

No competitor prices, claims or approval records have been supplied in this block.
