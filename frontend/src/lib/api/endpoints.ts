/**
 * Shared endpoint map for the RegenAI FastAPI backend.
 *
 * Both the browser client (client.ts) and the server client (server-client.ts)
 * build their `api` object from `createEndpoints(request)`, so the two always
 * expose the same shape and hit the same routes.
 *
 * Routes mirror backend/app/routers/*.py mounted under /api/v1 (the base URL
 * already includes /api/v1). Rules the backend enforces:
 *   - Non-path parameters are QUERY params (e.g. GET /fields/?farm_id=).
 *   - Routers declared as prefix + "/" need the trailing slash
 *     (/farms/, /fields/, /recommendations/, /credits/, /documents/);
 *     omitting it triggers a 307 redirect.
 *   - The activities router has no prefix and no trailing slash
 *     (/activities, /activities/summary, /yield-history, /yield-history/aph).
 *
 * This module must stay free of browser-only and server-only imports.
 */

import type {
  ActivityCreateInput,
  ActivityListParams,
  ActivityListResponse,
  ActivityRecord,
  ActivitySummaryResponse,
  ActivityUpdateInput,
  APHResponse,
  CreditEligibilityGetResponse,
  CreditEvaluateResponse,
  CreditReportResponse,
  CSPDeadlinesResponse,
  CSPEligibilityResponse,
  CSPEnhancementsResponse,
  CSPEvaluateResponse,
  CSPPaymentEstimateResponse,
  CSPScoreBreakdown,
  Document,
  DocumentListParams,
  Farm,
  FarmCreateInput,
  FarmUpdateInput,
  Field,
  FieldCreateInput,
  FieldEnrichResponse,
  FieldUpdateInput,
  Recommendation,
  RecommendationGenerateResponse,
  RecommendationStatus,
  SoilProfile,
  WeatherData,
  YieldHistoryCreateInput,
  YieldHistoryRecord,
} from "./types";

// ── Base URL ──────────────────────────────────────────────────────────────────

const DEFAULT_API_BASE_URL = "http://localhost:8000/api/v1";

// Dot access (not a dynamic lookup) so Next.js inlines the value at build time.
const configuredApiUrl = process.env.NEXT_PUBLIC_API_URL;

if (!configuredApiUrl && process.env.NODE_ENV === "production") {
  console.warn(
    `NEXT_PUBLIC_API_URL is not set; API calls will go to ${DEFAULT_API_BASE_URL}.`
  );
}

/** Backend base URL, including the /api/v1 prefix. */
export const API_BASE_URL = configuredApiUrl || DEFAULT_API_BASE_URL;

// ── Error type ────────────────────────────────────────────────────────────────

export interface ApiError {
  code: number;
  message: string;
}

/** Thrown by every api method. `code` is the HTTP status, or 0 for network failures. */
export class ApiRequestError extends Error {
  readonly code: number;

  constructor(error: ApiError) {
    super(error.message);
    this.name = "ApiRequestError";
    this.code = error.code;
  }
}

// ── Request plumbing ──────────────────────────────────────────────────────────

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  headers?: Record<string, string>;
}

export type RequestFn = <T>(path: string, options?: RequestOptions) => Promise<T>;

type QueryValue = string | number | boolean | null | undefined;

/** Append query params to a path, skipping undefined/null/empty values. */
export function withQuery(
  path: string,
  params: Record<string, QueryValue>
): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.append(key, String(value));
  }
  const qs = search.toString();
  return qs ? `${path}?${qs}` : path;
}

/**
 * Turn a FastAPI error body into a readable message. `detail` is a string for
 * HTTPException and an array of { loc, msg } objects for 422 validation errors.
 */
export function extractErrorMessage(json: unknown, fallback: string): string {
  if (!json || typeof json !== "object") return fallback;
  const { detail, message } = json as { detail?: unknown; message?: unknown };
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d) =>
        d && typeof d === "object" && "msg" in d
          ? String((d as { msg: unknown }).msg)
          : null
      )
      .filter((m): m is string => !!m);
    if (msgs.length > 0) return msgs.join("; ");
  }
  if (typeof message === "string") return message;
  return fallback;
}

/** Read a readable error message from a failed response, or return `fallback`. */
export async function readErrorMessage(
  response: Response,
  fallback: string
): Promise<string> {
  try {
    return extractErrorMessage(await response.json(), fallback);
  } catch {
    return fallback;
  }
}

export interface TransportConfig {
  /** Returns the Supabase access token, or null when signed out. */
  getAuthToken: () => Promise<string | null>;
  /** Extra fetch options applied to every call (e.g. `cache: "no-store"`). */
  fetchInit?: RequestInit;
  /** Side effect on 401 before the error is thrown (e.g. browser redirect). */
  onUnauthorized?: () => void;
}

async function send(
  config: TransportConfig,
  path: string,
  init: RequestInit
): Promise<Response> {
  const token = await config.getAuthToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);

  try {
    return await fetch(`${API_BASE_URL}${path}`, {
      ...config.fetchInit,
      ...init,
      headers,
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
}

async function handleResponse<T>(
  config: TransportConfig,
  response: Response,
  failureLabel: "Request" | "Upload"
): Promise<T> {
  if (response.status === 401) {
    config.onUnauthorized?.();
    throw new ApiRequestError({ code: 401, message: "Unauthorized" });
  }

  if (response.status === 404) {
    throw new ApiRequestError({
      code: 404,
      message: await readErrorMessage(response, "Resource not found"),
    });
  }

  if (response.status === 429) {
    throw new ApiRequestError({
      code: 429,
      message: "Too many requests — please wait before retrying",
    });
  }

  if (response.status >= 500) {
    throw new ApiRequestError({
      code: response.status,
      message: await readErrorMessage(response, "Internal server error"),
    });
  }

  if (!response.ok) {
    throw new ApiRequestError({
      code: response.status,
      message: await readErrorMessage(
        response,
        `${failureLabel} failed with status ${response.status}`
      ),
    });
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

/**
 * Build the JSON `request` and multipart `upload` functions from a token
 * resolver. client.ts and server-client.ts differ only in the config they pass.
 */
export function createTransport(config: TransportConfig) {
  const request: RequestFn = async <T>(
    path: string,
    options: RequestOptions = {}
  ): Promise<T> => {
    const { method = "GET", body, headers = {} } = options;
    const init: RequestInit = {
      method,
      headers: { "Content-Type": "application/json", ...headers },
    };
    if (body !== undefined) init.body = JSON.stringify(body);

    const response = await send(config, path, init);
    return handleResponse<T>(config, response, "Request");
  };

  // No Content-Type header: fetch sets the multipart boundary itself.
  const upload = async <T>(path: string, formData: FormData): Promise<T> => {
    const response = await send(config, path, {
      method: "POST",
      body: formData,
    });
    return handleResponse<T>(config, response, "Upload");
  };

  return { request, upload };
}

const seg = encodeURIComponent;

// ── Endpoint factory ──────────────────────────────────────────────────────────

export function createEndpoints(request: RequestFn) {
  const farms = {
    /** GET /farms/ */
    list: (): Promise<Farm[]> => request<Farm[]>("/farms/"),

    /** GET /farms/{id} */
    get: (id: string): Promise<Farm> => request<Farm>(`/farms/${seg(id)}`),

    /** POST /farms/ */
    create: (data: FarmCreateInput): Promise<Farm> =>
      request<Farm>("/farms/", { method: "POST", body: data }),

    /** PATCH /farms/{id} */
    update: (id: string, data: FarmUpdateInput): Promise<Farm> =>
      request<Farm>(`/farms/${seg(id)}`, { method: "PATCH", body: data }),

    /** DELETE /farms/{id} */
    delete: (id: string): Promise<void> =>
      request<void>(`/farms/${seg(id)}`, { method: "DELETE" }),
  };

  const fields = {
    /** GET /fields/?farm_id= */
    list: (farmId: string): Promise<Field[]> =>
      request<Field[]>(withQuery("/fields/", { farm_id: farmId })),

    /** GET /fields/{id} */
    get: (id: string): Promise<Field> => request<Field>(`/fields/${seg(id)}`),

    /** POST /fields/ (body includes farm_id) */
    create: (data: FieldCreateInput): Promise<Field> =>
      request<Field>("/fields/", { method: "POST", body: data }),

    /** PATCH /fields/{id} */
    update: (id: string, data: FieldUpdateInput): Promise<Field> =>
      request<Field>(`/fields/${seg(id)}`, { method: "PATCH", body: data }),

    /** DELETE /fields/{id} */
    delete: (id: string): Promise<void> =>
      request<void>(`/fields/${seg(id)}`, { method: "DELETE" }),

    /** GET /fields/{id}/soil — null when no profile has been fetched yet */
    getSoil: (fieldId: string): Promise<SoilProfile | null> =>
      request<SoilProfile | null>(`/fields/${seg(fieldId)}/soil`),

    /** GET /fields/{id}/weather — up to 7 rows, newest date first */
    getWeather: (fieldId: string): Promise<WeatherData[]> =>
      request<WeatherData[]>(`/fields/${seg(fieldId)}/weather`),

    /** POST /fields/{id}/enrich — fetch + persist weather and soil (202) */
    enrich: (fieldId: string): Promise<FieldEnrichResponse> =>
      request<FieldEnrichResponse>(`/fields/${seg(fieldId)}/enrich`, {
        method: "POST",
      }),
  };

  const recommendations = {
    /** GET /recommendations/?field_id= */
    list: (fieldId: string): Promise<Recommendation[]> =>
      request<Recommendation[]>(
        withQuery("/recommendations/", { field_id: fieldId })
      ),

    /** POST /recommendations/generate?farm_id= (202, rate limited 10/hour) */
    generate: (farmId: string): Promise<RecommendationGenerateResponse> =>
      request<RecommendationGenerateResponse>(
        withQuery("/recommendations/generate", { farm_id: farmId }),
        { method: "POST" }
      ),

    /** PATCH /recommendations/{id}/status */
    updateStatus: (
      recommendationId: string,
      status: RecommendationStatus
    ): Promise<Recommendation> =>
      request<Recommendation>(
        `/recommendations/${seg(recommendationId)}/status`,
        { method: "PATCH", body: { status } }
      ),
  };

  const activities = {
    /** GET /activities?field_id=&activity_type=&start_date=&end_date=&limit=&offset= */
    list: (
      fieldId: string,
      params: ActivityListParams = {}
    ): Promise<ActivityListResponse> =>
      request<ActivityListResponse>(
        withQuery("/activities", { field_id: fieldId, ...params })
      ),

    /** GET /activities/{id} */
    get: (activityId: string): Promise<ActivityRecord> =>
      request<ActivityRecord>(`/activities/${seg(activityId)}`),

    /** POST /activities */
    create: (data: ActivityCreateInput): Promise<ActivityRecord> =>
      request<ActivityRecord>("/activities", { method: "POST", body: data }),

    /** PATCH /activities/{id} */
    update: (
      activityId: string,
      data: ActivityUpdateInput
    ): Promise<ActivityRecord> =>
      request<ActivityRecord>(`/activities/${seg(activityId)}`, {
        method: "PATCH",
        body: data,
      }),

    /** DELETE /activities/{id} */
    delete: (activityId: string): Promise<void> =>
      request<void>(`/activities/${seg(activityId)}`, { method: "DELETE" }),

    /** GET /activities/summary?farm_id= */
    summary: (farmId: string): Promise<ActivitySummaryResponse> =>
      request<ActivitySummaryResponse>(
        withQuery("/activities/summary", { farm_id: farmId })
      ),

    /** GET /yield-history?field_id= */
    getYieldHistory: (fieldId: string): Promise<YieldHistoryRecord[]> =>
      request<YieldHistoryRecord[]>(
        withQuery("/yield-history", { field_id: fieldId })
      ),

    /** POST /yield-history (upserts on field_id + crop_year) */
    createYieldHistory: (
      data: YieldHistoryCreateInput
    ): Promise<YieldHistoryRecord> =>
      request<YieldHistoryRecord>("/yield-history", {
        method: "POST",
        body: data,
      }),

    /** GET /yield-history/aph?field_id= — 422 when fewer than 4 years exist */
    getAPH: (fieldId: string): Promise<APHResponse> =>
      request<APHResponse>(
        withQuery("/yield-history/aph", { field_id: fieldId })
      ),
  };

  const csp = {
    /** GET /csp/eligibility?farm_id= */
    getEligibility: (farmId: string): Promise<CSPEligibilityResponse> =>
      request<CSPEligibilityResponse>(
        withQuery("/csp/eligibility", { farm_id: farmId })
      ),

    /** GET /csp/score?farm_id= */
    getScore: (farmId: string): Promise<CSPScoreBreakdown> =>
      request<CSPScoreBreakdown>(withQuery("/csp/score", { farm_id: farmId })),

    /** GET /csp/payments?farm_id= */
    getPayments: (farmId: string): Promise<CSPPaymentEstimateResponse> =>
      request<CSPPaymentEstimateResponse>(
        withQuery("/csp/payments", { farm_id: farmId })
      ),

    /** GET /csp/enhancements?farm_id= */
    getEnhancements: (farmId: string): Promise<CSPEnhancementsResponse> =>
      request<CSPEnhancementsResponse>(
        withQuery("/csp/enhancements", { farm_id: farmId })
      ),

    /** POST /csp/evaluate?farm_id= (rate limited 20/hour) */
    evaluate: (farmId: string): Promise<CSPEvaluateResponse> =>
      request<CSPEvaluateResponse>(
        withQuery("/csp/evaluate", { farm_id: farmId }),
        { method: "POST" }
      ),

    /** GET /csp/deadlines[?state=XX] */
    getDeadlines: (state?: string): Promise<CSPDeadlinesResponse> =>
      request<CSPDeadlinesResponse>(withQuery("/csp/deadlines", { state })),
  };

  const credits = {
    /** GET /credits/?farm_id= — latest stored EQIP and VCM records */
    get: (farmId: string): Promise<CreditEligibilityGetResponse> =>
      request<CreditEligibilityGetResponse>(
        withQuery("/credits/", { farm_id: farmId })
      ),

    /** POST /credits/evaluate?farm_id= (rate limited 20/hour) */
    evaluate: (farmId: string): Promise<CreditEvaluateResponse> =>
      request<CreditEvaluateResponse>(
        withQuery("/credits/evaluate", { farm_id: farmId }),
        { method: "POST" }
      ),

    /** GET /credits/report?farm_id= */
    getReport: (farmId: string): Promise<CreditReportResponse> =>
      request<CreditReportResponse>(
        withQuery("/credits/report", { farm_id: farmId })
      ),
  };

  const documents = {
    /** GET /documents/?farm_id=&doc_type=&limit=&offset= */
    list: (farmId: string, params: DocumentListParams = {}): Promise<Document[]> =>
      request<Document[]>(
        withQuery("/documents/", { farm_id: farmId, ...params })
      ),

    /** DELETE /documents/{id} */
    delete: (docId: string): Promise<void> =>
      request<void>(`/documents/${seg(docId)}`, { method: "DELETE" }),
  };

  return {
    farms,
    fields,
    recommendations,
    activities,
    csp,
    credits,
    documents,
  };
}
