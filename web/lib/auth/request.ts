/**
 * Calling the API from a form. Every outcome comes back as data or as one plain problem a form can
 * show: the API's own error (its message is written for people), or a network failure.
 */
import { browserApiBaseUrl, createApiClient, type ApiClient } from "@/lib/api/client";

export interface Problem {
  /** The API's `error.code` (for example `INVALID_CREDENTIALS`), or `NETWORK`. */
  code: string;
  message: string;
  /** The form field the API says it is about. */
  field?: string;
  /** Seconds to wait, from a 429. */
  retryAfter?: number;
}

export type Outcome<T> = { ok: true; data: T } | { ok: false; problem: Problem };

const NETWORK: Problem = {
  code: "NETWORK",
  message: "We could not reach the server. Check your connection and try again.",
};

let shared: ApiClient | undefined;
/** One client for the browser. Built on first use, so a missing API address fails where it is used. */
export function api(): ApiClient {
  // Next.js puts a NEXT_PUBLIC_* value into the browser bundle only where it is written out in full
  // (`process.env.NEXT_PUBLIC_API_URL`), never where `process.env` is passed around as an object.
  shared ??= createApiClient({
    baseUrl: browserApiBaseUrl({
      NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
      NODE_ENV: process.env.NODE_ENV,
    }),
  });
  return shared;
}

interface Result<T> {
  data?: T | undefined;
  error?: unknown;
  response: Response;
}

function problemFrom(error: unknown, response: Response): Problem {
  const body = (error as { error?: { code?: string; message?: string; field?: string | null } })
    ?.error;
  const retry = Number(response.headers.get("Retry-After"));
  return {
    code: body?.code ?? `HTTP_${response.status}`,
    message: body?.message ?? "Something went wrong. Try again.",
    ...(body?.field ? { field: body.field } : {}),
    ...(Number.isFinite(retry) && retry > 0 ? { retryAfter: retry } : {}),
  };
}

/** Runs one API call. A successful call with no body (204, 202) comes back as `data: undefined`. */
export async function attempt<T>(
  run: (client: ApiClient) => Promise<Result<T>>,
): Promise<Outcome<T>> {
  let result: Result<T>;
  try {
    result = await run(api());
  } catch {
    return { ok: false, problem: NETWORK };
  }
  if (result.response.ok) return { ok: true, data: result.data as T };
  return { ok: false, problem: problemFrom(result.error, result.response) };
}
