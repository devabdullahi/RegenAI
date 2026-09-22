/**
 * Typed API client for the RegenAI backend (browser / Client Components).
 *
 * All methods automatically attach the Supabase session token and throw
 * ApiRequestError ({ code, message }) on failure. Callers import the singleton
 * `api` exported at the bottom of this file.
 *
 * Routes, error handling and the base URL (NEXT_PUBLIC_API_URL, falling back to
 * http://localhost:8000/api/v1) live in ./endpoints.ts, shared with
 * server-client.ts. This file only supplies browser token resolution.
 */

import { createClient } from "@/lib/supabase/client";
import { createEndpoints, createTransport } from "./endpoints";
import type { Document, DocumentType } from "./types";

export {
  ApiRequestError,
  readErrorMessage,
  type ApiError,
} from "./endpoints";

// ── Transport ─────────────────────────────────────────────────────────────────

const { request, upload } = createTransport({
  getAuthToken: async () => {
    const supabase = createClient();
    const {
      data: { session },
    } = await supabase.auth.getSession();
    return session?.access_token ?? null;
  },
  onUnauthorized: () => {
    // The session is missing or expired — send the user to sign in again.
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  },
});

// ── Public singleton ──────────────────────────────────────────────────────────

const endpoints = createEndpoints(request);

export const api = {
  ...endpoints,
  documents: {
    ...endpoints.documents,

    /** POST /documents/ — multipart form with farm_id, doc_type, file, description */
    upload: (
      farmId: string,
      file: File,
      docType: DocumentType,
      description?: string
    ): Promise<Document> => {
      const form = new FormData();
      form.append("farm_id", farmId);
      form.append("doc_type", docType);
      form.append("file", file);
      if (description) form.append("description", description);
      return upload<Document>("/documents/", form);
    },
  },
} as const;
