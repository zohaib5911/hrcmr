#!/usr/bin/env node
/**
 * Runs the production server from the standalone build, the same way the Docker image does:
 * `next build` writes the server to .next/standalone, but not the static assets or `public/`.
 *
 * Usage: PORT=3100 node scripts/start-standalone.mjs   (after `pnpm build`)
 *
 * It listens on 0.0.0.0, like the container. Do not bind a loopback address: Next.js decides whether
 * a proxy rewrite is internal by comparing origins, and a loopback bind makes the admin-host
 * rewrite in proxy.ts look external, so admin pages fail with a 500 (closed, never exposed).
 */
import { spawn } from "node:child_process";
import { cpSync, existsSync } from "node:fs";
import path from "node:path";

const standalone = path.join(".next", "standalone", "web");
if (!existsSync(path.join(standalone, "server.js"))) {
  console.error("No standalone build found. Run `pnpm build` first.");
  process.exit(1);
}

cpSync(path.join(".next", "static"), path.join(standalone, ".next", "static"), { recursive: true });
if (existsSync("public")) cpSync("public", path.join(standalone, "public"), { recursive: true });

const server = spawn(process.execPath, [path.join(standalone, "server.js")], {
  stdio: "inherit",
  env: {
    ...process.env,
    HOSTNAME: process.env.HOSTNAME ?? "0.0.0.0",
    PORT: process.env.PORT ?? "3000",
  },
});
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => server.kill(signal));
server.on("exit", (code) => process.exit(code ?? 0));
