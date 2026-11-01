# syntax=docker/dockerfile:1
#
# Web image (plan.md T0.6): multi-stage, Next.js standalone output, non-root, base pinned by digest.
#
# The build context is the REPOSITORY ROOT, because brand.config.ts and scripts/ live outside web/:
#   docker build -f web/Dockerfile -t brand-web:dev .
#
# NEXT_PUBLIC_* values are compiled into the browser bundle, so they are build arguments. Only the
# nine allow-listed names exist (scripts/check-public-env.mjs fails the build on any other), and
# none is secret. The web service holds no third-party secret keys.
#
# Refresh the pin deliberately: pull the tag, read the digest with
#   docker image inspect --format '{{index .RepoDigests 0}}' node:24-slim

ARG NODE_IMAGE=node:24-slim@sha256:c86ecead9e55a5210ac1727de38a4ca840bf03dcaf34dc9749addbf383b1920c

# --- deps: install exactly what pnpm-lock.yaml says -------------------------------------------------
FROM ${NODE_IMAGE} AS deps
ENV PNPM_HOME=/pnpm
ENV PATH="${PNPM_HOME}:${PATH}"
# The pnpm version comes from "packageManager" in web/package.json.
RUN corepack enable
WORKDIR /repo/web
COPY web/package.json web/pnpm-lock.yaml web/pnpm-workspace.yaml ./
RUN --mount=type=cache,target=/pnpm/store pnpm install --frozen-lockfile

# --- builder: runs the checks and builds ----------------------------------------------------------
FROM deps AS builder
ARG NEXT_PUBLIC_SITE_URL
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_ADMIN_URL
ARG NEXT_PUBLIC_TURNSTILE_SITE_KEY
ARG NEXT_PUBLIC_SENTRY_DSN_WEB
ARG NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY
ARG NEXT_PUBLIC_META_PIXEL_ID
ARG NEXT_PUBLIC_REDDIT_PIXEL_ID
ARG NEXT_PUBLIC_GOOGLE_ADS_ID
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /repo
COPY brand.config.ts ./brand.config.ts
COPY scripts ./scripts
COPY web ./web
WORKDIR /repo/web
# check-public-env, next build, then scan the browser bundle for secrets.
RUN pnpm build && mkdir -p public

# --- runtime: only the traced server files; no pnpm, no source, no dev dependencies -----------------
FROM ${NODE_IMAGE} AS runtime
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid 10001 --no-create-home --home-dir /nonexistent \
        --shell /usr/sbin/nologin app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
WORKDIR /srv
# With the tracing root at the repository root, the server lands in web/. Files are owned by root
# and read-only to the app user.
COPY --from=builder /repo/web/.next/standalone ./
COPY --from=builder /repo/web/.next/static ./web/.next/static
COPY --from=builder /repo/web/public ./web/public

USER 10001:10001
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["node", "-e", "fetch('http://127.0.0.1:'+process.env.PORT+'/healthz').then(r=>process.exit(r.ok?0:1),()=>process.exit(1))"]

CMD ["node", "web/server.js"]
