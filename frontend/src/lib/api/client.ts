/**
 * Typed API client for the RegenAI backend.
 *
 * All methods automatically attach the Supabase session token and normalise
 * error responses to { code, message }.  Callers import the singleton `api`
 * exported at the bottom of this file.
 *
 * Base URL resolution order:
 *   1. NEXT_PUBLIC_API_URL env var
 *   2. http://localhost:8000/api/v1
 */

import { createClient } from "@/lib/supabase/client";
import type {
  Farm,
  Field,
  FieldActivity,
  YieldRecord,
  APHResult,
  ActivitySummary,
  Recommendation,
  CSPEligibility,
  CSPDeadline,
  CreditEligibility,
  Document,
} from "./types";

// ── Constants ─────────────────────────────────────────────────────────────────

const BASE_URL =
  process.env["NEXT_PUBLIC_API_URL"] ?? "http://localhost:8000/api/v1";

// ── Error type ────────────────────────────────────────────────────────────────

export interface ApiError {
  code: number;
  message: string;
}

export class ApiRequestError extends Error {
  readonly code: number;

  constructor(error: ApiError) {
    super(error.message);
    this.name = "ApiRequestError";
    this.code = error.code;
  }
}

// ── Token resolution ──────────────────────────────────────────────────────────

async function getAuthToken(): Promise<string | null> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session?.access_token ?? null;
}

// ── Core fetch wrapper ────────────────────────────────────────────────────────

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  headers?: Record<string, string>;
}

async function request<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const { method = "GET", body, headers: extraHeaders = {} } = options;

  const token = await getAuthToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...extraHeaders,
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const init: RequestInit = {
    method,
    headers,
  };

  if (body !== undefined) {
    init.body = JSON.stringify(body);
  }

  let response: Response;

  try {
    response = await fetch(`${BASE_URL}${path}`, init);
  } catch (networkError) {
    throw new ApiRequestError({
      code: 0,
      message:
        networkError instanceof Error
          ? networkError.message
          : "Network request failed",
    });
  }

  // Handle specific status codes
  if (response.status === 401) {
    // Redirect to login — clear any stale session first
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new ApiRequestError({ code: 401, message: "Unauthorized" });
  }

  if (response.status === 404) {
    throw new ApiRequestError({ code: 404, message: "Resource not found" });
  }

  if (response.status === 429) {
    throw new ApiRequestError({
      code: 429,
      message: "Too many requests — please wait before retrying",
    });
  }

  if (response.status >= 500) {
    let serverMessage = "Internal server error";
    try {
      const json = (await response.json()) as { detail?: string };
      if (json.detail) serverMessage = json.detail;
    } catch {
      // ignore parse failure, use default message
    }
    throw new ApiRequestError({ code: response.status, message: serverMessage });
  }

  if (!response.ok) {
    let errorMessage = `Request failed with status ${response.status}`;
    try {
      const json = (await response.json()) as { detail?: string; message?: string };
      errorMessage = json.detail ?? json.message ?? errorMessage;
    } catch {
      // ignore parse failure
    }
    throw new ApiRequestError({ code: response.status, message: errorMessage });
  }

  // 204 No Content — return empty object cast to T
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

// ── Upload helper (multipart) ─────────────────────────────────────────────────

async function upload<T>(path: string, formData: FormData): Promise<T> {
  const token = await getAuthToken();

  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  let response: Response;

  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method: "POST",
      headers,
      body: formData,
    });
  } catch (networkError) {
    throw new ApiRequestError({
      code: 0,
      message:
        networkError instanceof Error
          ? networkError.message
          : "Network request failed",
    });
  }

  if (response.status === 401) {
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new ApiRequestError({ code: 401, message: "Unauthorized" });
  }

  if (!response.ok) {
    let errorMessage = `Upload failed with status ${response.status}`;
    try {
      const json = (await response.json()) as { detail?: string };
      errorMessage = json.detail ?? errorMessage;
    } catch {
      // ignore
    }
    throw new ApiRequestError({ code: response.status, message: errorMessage });
  }

  return response.json() as Promise<T>;
}

// ── Partial / create input types ──────────────────────────────────────────────

type FarmCreateInput = Omit<Farm, "id" | "user_id" | "created_at">;
type FarmUpdateInput = Partial<FarmCreateInput>;
type FieldCreateInput = Omit<Field, "id" | "created_at">;
type ActivityCreateInput = Omit<FieldActivity, "id" | "created_at">;

// ── API namespace ─────────────────────────────────────────────────────────────

const farms = {
  list: (): Promise<Farm[]> => request<Farm[]>("/farms"),

  get: (id: string): Promise<Farm> => request<Farm>(`/farms/${id}`),

  create: (data: FarmCreateInput): Promise<Farm> =>
    request<Farm>("/farms", { method: "POST", body: data }),

  update: (id: string, data: FarmUpdateInput): Promise<Farm> =>
    request<Farm>(`/farms/${id}`, { method: "PATCH", body: data }),

  delete: (id: string): Promise<void> =>
    request<void>(`/farms/${id}`, { method: "DELETE" }),
};

const fields = {
  list: (farmId: string): Promise<Field[]> =>
    request<Field[]>(`/farms/${farmId}/fields`),

  get: (id: string): Promise<Field> => request<Field>(`/fields/${id}`),

  create: (data: FieldCreateInput): Promise<Field> =>
    request<Field>("/fields", { method: "POST", body: data }),
};

const activities = {
  list: (farmId: string): Promise<ActivitySummary> =>
    request<ActivitySummary>(`/farms/${farmId}/activities`),

  create: (data: ActivityCreateInput): Promise<FieldActivity> =>
    request<FieldActivity>("/activities", { method: "POST", body: data }),

  getYieldHistory: (farmId: string): Promise<APHResult[]> =>
    request<APHResult[]>(`/farms/${farmId}/yield-history`),
};

const recommendations = {
  generate: (fieldId: string): Promise<Recommendation[]> =>
    request<Recommendation[]>(`/fields/${fieldId}/recommendations`, {
      method: "POST",
    }),

  list: (farmId: string): Promise<Recommendation[]> =>
    request<Recommendation[]>(`/farms/${farmId}/recommendations`),
};

const csp = {
  getEligibility: (farmId: string): Promise<CSPEligibility> =>
    request<CSPEligibility>(`/farms/${farmId}/csp/eligibility`),

  evaluate: (farmId: string): Promise<CSPEligibility> =>
    request<CSPEligibility>(`/farms/${farmId}/csp/evaluate`, {
      method: "POST",
    }),

  getDeadlines: (): Promise<CSPDeadline[]> =>
    request<CSPDeadline[]>("/csp/deadlines"),
};

const credits = {
  evaluate: (farmId: string): Promise<CreditEligibility[]> =>
    request<CreditEligibility[]>(`/farms/${farmId}/credits/evaluate`, {
      method: "POST",
    }),

  getReport: (farmId: string): Promise<CreditEligibility[]> =>
    request<CreditEligibility[]>(`/farms/${farmId}/credits`),
};

const documents = {
  upload: (
    farmId: string,
    file: File,
    docType: Document["doc_type"]
  ): Promise<Document> => {
    const form = new FormData();
    form.append("file", file);
    form.append("doc_type", docType);
    return upload<Document>(`/farms/${farmId}/documents`, form);
  },

  list: (farmId: string): Promise<Document[]> =>
    request<Document[]>(`/farms/${farmId}/documents`),

  delete: (docId: string): Promise<void> =>
    request<void>(`/documents/${docId}`, { method: "DELETE" }),
};

// ── Public singleton ──────────────────────────────────────────────────────────

export const api = {
  farms,
  fields,
  activities,
  recommendations,
  csp,
  credits,
  documents,
} as const;
