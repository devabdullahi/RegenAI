/**
 * Server-side API client for the RegenAI backend.
 *
 * Use this in Server Components (async page/layout functions without "use client").
 * It resolves the auth token from the server-side Supabase session via cookies(),
 * which requires the Next.js request context — never use this in Client Components
 * (enforced for src/components by eslint no-restricted-imports).
 *
 * For Client Components, import `api` from "@/lib/api/client".
 *
 * Routes and error handling live in ./endpoints.ts, so this client exposes the
 * same shape as client.ts (minus documents.upload, which needs a browser File).
 */

import "server-only";

import { createClient } from "@/lib/supabase/server";
import { createEndpoints, createTransport } from "./endpoints";

export {
  ApiRequestError,
  readErrorMessage,
  type ApiError,
} from "./endpoints";

const { request } = createTransport({
  getAuthToken: async () => {
    const supabase = await createClient();
    const {
      data: { session },
    } = await supabase.auth.getSession();
    return session?.access_token ?? null;
  },
  // Always read fresh data; pages are per-user.
  fetchInit: { cache: "no-store" },
  // No onUnauthorized: Server Components cannot redirect via window, so the
  // 401 is thrown for the calling page or error boundary to handle.
});

// Note: document upload (multipart/form-data) requires a File object which is
// browser-only. Use the browser api client's documents.upload() instead.
export const api = createEndpoints(request);
