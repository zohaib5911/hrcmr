# Guides

These original guides are repository content, reviewed through pull requests. Their metadata
and source links are in `web/lib/guides/catalogue.ts`; the page always renders the sources,
last-reviewed date and disclaimer. MDX is imported statically and compiled by `@next/mdx`.

Only the Markdown subset is allowed. `web/scripts/remark-safe-guides.mjs` rejects raw HTML,
JSX (including components), expressions, imports, exports, images and non-HTTPS links at
compilation. Keep interactive components in reviewed TSX outside the content files.
No content is uploaded or evaluated at request time.

For a review, open every linked official source, check the effective dates and scope, update
the guide and its `reviewedOn`, and run the guide compilation and self-test unit tests.
The October 2026 guide was checked against the Home Office guide dated 1 October 2026;
the verified copy used elsewhere in the project is `web/rates/right-to-work.json`.
