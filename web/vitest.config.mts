import path from "node:path";

import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "@brand": path.resolve(import.meta.dirname, "../brand.config.ts"),
      "@": path.resolve(import.meta.dirname),
    },
  },
  // Components are written for React's automatic JSX runtime, as Next.js compiles them.
  oxc: { jsx: { runtime: "automatic" } },
  test: {
    // Pure logic runs in Node. A component test opts in to a browser-like DOM with
    // `// @vitest-environment jsdom` on its first line.
    environment: "node",
    include: [
      "lib/**/*.test.{ts,tsx}",
      "components/**/*.test.{ts,tsx}",
      "tests/unit/**/*.test.{ts,tsx}",
    ],
    setupFiles: ["tests/unit/setup.ts"],
  },
});
