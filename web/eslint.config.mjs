import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

export default defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    // The Content-Security-Policy blocks inline style="" attributes in server-rendered HTML (plan 4.6),
    // so a `style` prop would silently do nothing in production. Use classes, SVG attributes, or a
    // <style nonce> element instead.
    rules: {
      "react/forbid-dom-props": [
        "error",
        {
          forbid: [
            {
              propName: "style",
              message: "Inline styles are blocked by the CSP. Use classes or SVG attributes.",
            },
          ],
        },
      ],
    },
  },
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts", "lib/api/schema.ts"]),
]);
