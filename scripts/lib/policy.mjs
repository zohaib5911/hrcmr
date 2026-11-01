/**
 * Shared policy for the secret guard-rails (plan.md sections 4.1 and 9 / T0.2).
 *
 * Imported by scripts/check-public-env.mjs and scripts/scan-bundle.mjs.
 * Node built-ins only: these scripts must run in CI before any dependency install.
 *
 * The regular expressions avoid look-behind so the same text also works in Go RE2,
 * which is what gitleaks uses (see .gitleaks.toml).
 */

/**
 * The only NEXT_PUBLIC_* variables allowed in the browser bundle.
 * Source: deployment-requirements.txt section 4.2. All are non-secret.
 */
export const ALLOWED_PUBLIC_ENV = Object.freeze([
  "NEXT_PUBLIC_SITE_URL",
  "NEXT_PUBLIC_API_URL",
  "NEXT_PUBLIC_ADMIN_URL",
  "NEXT_PUBLIC_TURNSTILE_SITE_KEY",
  "NEXT_PUBLIC_SENTRY_DSN_WEB",
  "NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY",
  "NEXT_PUBLIC_META_PIXEL_ID",
  "NEXT_PUBLIC_REDDIT_PIXEL_ID",
  "NEXT_PUBLIC_GOOGLE_ADS_ID",
]);

/**
 * Variables whose VALUES must never appear in a built bundle.
 * Source: deployment-requirements.txt sections 4.1 ([SECRET]) and 6 (CI secrets).
 * SENTRY_DSN_API is "public-ish" but belongs to the API project, so it is treated as secret.
 */
export const SECRET_ENV_NAMES = Object.freeze([
  "DATABASE_URL",
  "DATABASE_URL_OWNER",
  "DATABASE_APP_USER_PASSWORD",
  "REDIS_URL",
  "SESSION_SECRET",
  "FIELD_ENCRYPTION_KEYS",
  "BLIND_INDEX_KEY",
  "R2_ACCESS_KEY_ID",
  "R2_SECRET_ACCESS_KEY",
  "R2_BACKUP_ACCESS_KEY_ID",
  "R2_BACKUP_SECRET_ACCESS_KEY",
  "RESEND_API_KEY",
  "ANTHROPIC_API_KEY",
  "STRIPE_SECRET_KEY",
  "STRIPE_WEBHOOK_SECRET",
  "TURNSTILE_SECRET_KEY",
  "COMPANIES_HOUSE_API_KEY",
  "SENTRY_DSN_API",
  "RAILWAY_TOKEN",
  "RAILWAY_TOKEN_STAGING",
  "RAILWAY_TOKEN_PRODUCTION",
  "SENTRY_AUTH_TOKEN",
]);

/** Minimum length for an environment value to be searched for literally in a bundle. */
export const MIN_SECRET_VALUE_LENGTH = 8;

/**
 * Secret-shaped strings that must not be in client code. `flags` is optional.
 * Prefix patterns are deliberately strict (plan.md 4.1.5 lists sk_live, sk_test, rk_, re_,
 * sk-ant-, whsec_): even a bare prefix in browser code is treated as a leak.
 */
export const SECRET_VALUE_PATTERNS = Object.freeze([
  { id: "stripe-secret-key-prefix", source: String.raw`\b(?:sk|rk)_(?:live|test)` },
  { id: "stripe-restricted-key", source: String.raw`\brk_[A-Za-z0-9]{20,}` },
  { id: "stripe-webhook-secret", source: String.raw`\bwhsec_` },
  { id: "anthropic-api-key", source: String.raw`\bsk-ant-` },
  { id: "resend-api-key", source: String.raw`\bre_[A-Za-z0-9_]{24,}` },
  { id: "age-secret-key", source: String.raw`AGE-SECRET-KEY-1[A-Z0-9]{20,}` },
  { id: "private-key-block", source: String.raw`-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----` },
  { id: "sentry-auth-token", source: String.raw`\bsntry[su]_[A-Za-z0-9+/=_-]{20,}` },
  {
    id: "database-url-with-password",
    source: String.raw`\bpostgres(?:ql)?(?:\+[a-z0-9]+)?://[^\s:@/]+:[^\s@/]+@`,
    flags: "i",
  },
  {
    id: "redis-url-with-password",
    source: String.raw`\brediss?://[^\s:@/]*:[^\s@/]+@`,
    flags: "i",
  },
]);

/** Build a fresh RegExp for a pattern entry (fresh so `lastIndex` state is never shared). */
export function compilePattern(pattern, extraFlags = "") {
  const flags = new Set(`${pattern.flags ?? ""}${extraFlags}`.split(""));
  return new RegExp(pattern.source, [...flags].join(""));
}

/** Names of the first pattern that matches `text`, or `null`. Never returns the match itself. */
export function firstSecretPatternId(text) {
  for (const pattern of SECRET_VALUE_PATTERNS) {
    if (compilePattern(pattern).test(text)) return pattern.id;
  }
  return null;
}
