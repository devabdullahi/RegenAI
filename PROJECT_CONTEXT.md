# RegenAI — Project Context

> Updated 2026-09-13 on branch `fix/context-audit-issues` (based on `main` @ `db87562`, after the Sprint 2 merge).
> Originally written from reading the code on `main`; §8 now tracks which audit findings were fixed on this branch and which are still open.

---

## 1. What it is

RegenAI is an AI platform for regenerative agriculture. It's aimed at US row-crop farms nationwide (typically 500–5,000 acres). It began as a 9-state Midwest product and was broadened on 2026-09-22. The goal is to help a farmer:

1. **Get agronomic recommendations** from an LLM (DeepSeek), based on soil, weather and current practices.
2. **Find USDA cost-share money:** EQIP eligibility and CSP (Conservation Stewardship Program) scoring, eligibility and payment estimates.
3. **Estimate carbon-credit revenue** in the Voluntary Carbon Market (VCM).
4. **Keep a field activity log:** planting, spraying, harvest and so on, plus yield history and APH (Actual Production History).

The business target is 5 paying pilot farms at $99–$299/month. The UI is mobile-first because farmers use it in the field: large touch targets (48px minimum) and plain language.

The repo is a private MVP by `devabdullahi`. Work is organized in sprints: Sprint 1 was infra, and Sprint 2 (PR #2) was "completion and QA fixes." A plain-language overview lives in `docs/RegenAI_Explained.pdf`.

---

## 2. Repository layout

```
RegenAI/
├── backend/            FastAPI app (Python 3.11, Poetry 2.x)
│   ├── app/
│   │   ├── main.py         App, CORS, request-ID middleware, router mounting under /api/v1
│   │   ├── config.py       pydantic-settings; fails at startup if SUPABASE_URL/ANON_KEY/DEEPSEEK_API_KEY are missing
│   │   ├── rate_limit.py   slowapi limiter singleton (split out to avoid a circular import)
│   │   ├── auth/middleware.py  JWT validation + per-request RLS-scoped Supabase client
│   │   ├── models/         Pydantic models per domain; schemas.py re-exports them all
│   │   ├── routers/        farms, fields, recommendations, credits, csp, activities, documents, health
│   │   ├── services/       all business logic (see §4)
│   │   └── tasks/          empty (Celery not implemented)
│   ├── scripts/seed_eqip.py   seeds the eqip_practices reference table
│   ├── tests/          pytest suite, all using mocked Supabase
│   └── Dockerfile      python:3.11-slim + WeasyPrint system libs, non-root user
├── frontend/           Next.js 16 App Router (React 19, Tailwind v4, shadcn/ui "base-nova", lucide)
│   ├── .env.local.example
│   └── src/
│       ├── app/(auth)/login          magic-link login
│       ├── app/(onboarding)/onboarding/{,farm,fields,practices,goals,confirm}
│       ├── app/(dashboard)/{dashboard,farms,farms/[id],activities,activities/new,credits,csp/*,yield-history}
│       ├── app/auth/callback/route.ts   Supabase code exchange
│       ├── components/{activities,credits,csp,dashboard,shared,ui}
│       ├── lib/api/endpoints.ts      shared endpoint factory — single source of backend routes
│       ├── lib/api/client.ts         browser API client (built from endpoints.ts)
│       ├── lib/api/server-client.ts  server-component API client ("server-only", cookie session)
│       ├── lib/api/adapters.ts       backend response → UI shape adapters
│       ├── lib/api/types.ts          shared TS types (match backend schemas)
│       ├── lib/supabase/{client,server,middleware,dev-bypass}.ts
│       └── proxy.ts                  Next 16 proxy (formerly middleware.ts); calls updateSession()
├── supabase/
│   ├── config.toml     local stack, Postgres 17, project_id "Farm_startup"
│   ├── migrations/     6 SQL migrations (see §5)
│   └── seed.sql
├── docs/RegenAI_Explained.pdf        plain-language overview
├── design-system/regenai/MASTER.md   design tokens and rules
├── docker-compose.yml  runs only the API service (hot reload), not Supabase or the frontend
└── .github/{dependabot.yml, workflows/ci.yml}
```

---

## 3. Architecture and request flow

```
Browser (Next.js) ──magic link──► Supabase Auth
     │  (session cookie; server components read it via @supabase/ssr)
     │
     ├── Server Components → lib/api/server-client.ts ─┐   (both built from lib/api/endpoints.ts)
     └── Client Components → lib/api/client.ts ────────┤  Authorization: Bearer <supabase JWT>
                                                       ▼
                                   FastAPI  /api/v1/*   (+ /health)
                                       │ get_current_user → supabase.auth.get_user(token)
                                       │ get_authenticated_client → fresh client per request,
                                       │   client.postgrest.auth(token) so RLS applies to the user
                                       ▼
                         Supabase Postgres (RLS on every table)
                                       │
         External: DeepSeek (LLM) · Open-Meteo (weather) · USDA SSURGO SDA (soil) · Supabase Storage (documents)
```

Key design decisions:

- **RLS is the security boundary.** The backend acts as the user by passing the user's JWT to PostgREST. Routers taking a farm or field ID (csp, credits, documents, recommendations generate, fields soil/weather/enrich/delete) also run the shared `assert_farm_access` / `assert_field_access` check from `app/auth/access.py` first. Only PostgREST's no-rows code (`PGRST_NO_ROWS`) maps to 404; other DB errors are logged and return 500. The service-role client (`get_admin_client`) is only meant for scripts.
- **A new Supabase client is created on every request.** Sprint 2 made this change to fix a race where a shared client could run one user's query with another user's token.
- **Every request gets an ID:** `X-Request-ID` is added to each response for log correlation.
- **Rate limits** (slowapi, `@limiter.limit`):
  - Recommendation generation and field enrichment: 10/hr
  - Credits evaluate, CSP evaluate and document upload: 20/hr
  - Farm create and field create/delete: 30/hr
- **API docs** (`/docs`, `/redoc`) are turned off when `ENVIRONMENT=production`.

---

## 4. Backend services

These live in `backend/app/services/`.

| Service | What it does |
|---|---|
| `context.py` | Builds the farm context for the LLM: the farm, its fields, soil, weather, practices and EQIP practice codes. |
| `prompts.py` | Holds the system prompt and the user-message builder. |
| `recommendations.py` | Runs the recommendation pipeline: build context → call DeepSeek through the OpenAI-compatible API (`deepseek-flash`, thinking mode disabled, temp 0.3, 4096 max tokens) → strictly parse a bare JSON array, rejecting code fences, prose and wrapped objects → Pydantic-validate each item → **hallucination guard**. The guard drops any recommendation whose `field_id` isn't one of the farm's fields or whose `practice_code` isn't in the `eqip_practices` table. Survivors are stored as `pending`. It retries malformed output once and doesn't retry API errors. If every attempt is unusable it raises `RecommendationOutputError`; it returns `[]` only when the farm has no fields or the guards reject everything. A failed insert raises instead of reporting success. |
| `validators.py` | `LLMRecommendation` schema, `validate_field_ids`, `validate_practice_codes`. |
| `enrichment.py`, `weather.py`, `soil.py` | Fetches Open-Meteo weather and SSURGO soil data concurrently. The field's coordinates come from its GeoJSON centroid, or a county-centroid lookup keyed by the farm's `county_fips` if there's no boundary (the table covers every US county, generated from the Census Gazetteer into `app/data/county_centroids.json`). Results are saved to `weather_cache` and `soil_profiles`. This runs synchronously; there's no background queue. |
| `eqip.py` | EQIP eligibility: checks the farm's *acted* recommendations against EQIP practice codes, and requires at least one qualifying document (`soil_report`, `field_photo` or `compliance`). The result is saved to `credit_eligibility`. |
| `vcm.py` | A simplified Soil Carbon Protocol. Cover crop (340) earns 0.5–1.2 credits/ac/yr, no-till (329) 0.3–0.8, and conservation rotation (328) 0.2–0.5. Where a field lands in its range depends on soil organic matter: ≥3% gets the top of the range, 1.5–2.9% the midpoint, and under 1.5% or no soil data the bottom. Includes a per-field breakdown. |
| `csp_scoring.py` | CART stewardship scoring across 8 resource concerns worth 100 points total (soil health 20, erosion 15, water quality 20, water quantity 10, air 10, plant 10, animals 5, energy 10). A practice-code-to-concern map converts the farm's practices into points. A concern "meets threshold" at 50% of its maximum points. Applies a state ranking threshold only for the states that have one on file; otherwise the threshold, the meets-flag and the gap are all `None`. |
| `csp_eligibility.py` | Sets the farm's CSP status: `act_now` means ≥2 concerns meet threshold *and* the score clears a known state ranking threshold (never on an unknown one); `eligible` means ≥2 concerns meet threshold; `pending_review` means exactly 1 does; `not_eligible` means none do. It also suggests up to about 6 gap-closing enhancement codes, and upserts the result into `csp_eligibility_assessments`. |
| `csp_payment.py` | Estimates EAP (Existing Activity Payment) plus EnAP (Enhancement Activity Payment). All limits come from `program_rules.py` (FY2026, NB 440-26-2): $4,000 EAP, no annual payment limit, and a $300K individual / $600K joint contract limit ($200K/$400K before FY2026). Reads the cached assessment; scores inline only if none exists. Also ranks enhancement recommendations. |
| `activity_log/` | Activity CRUD and summary. A restricted-use pesticide spray requires the applicator's name and license. APH is calculated from up to 10 years of yield data and needs at least 4. |

### Backend routes

Everything below except `/health` is mounted under **`/api/v1`**. Parameters that aren't in the path are **query params**, e.g. `GET /api/v1/fields/?farm_id=…`. 38 endpoints across 8 routers.

- `farms`: `GET/POST /farms/`, `GET/PATCH/DELETE /farms/{farm_id}`
- `fields`:
  - `GET /fields/?farm_id=`, `POST /fields/`
  - `GET/PATCH/DELETE /fields/{field_id}`
  - `GET /fields/{id}/soil`, `GET /fields/{id}/weather`, `POST /fields/{id}/enrich` (202)
- `recommendations` (UUID params): `GET /recommendations/?field_id=`, `PATCH /recommendations/{id}/status`, `POST /recommendations/generate?farm_id=` (202)
- `credits`: `GET /credits/?farm_id=`, `POST /credits/evaluate?farm_id=`, `GET /credits/report?farm_id=`
- `csp`: `GET /csp/{eligibility,score,payments,enhancements}?farm_id=`, `GET /csp/deadlines?state=`, `POST /csp/evaluate?farm_id=`
- `activities`: `POST /activities`, `GET /activities?field_id=` (field required), `GET /activities/summary?farm_id=`, `GET/PATCH/DELETE /activities/{id}`, `POST /yield-history`, `GET /yield-history?field_id=`, `GET /yield-history/aph?field_id=`
- `documents`: `POST /documents/` (multipart, checks Content-Length before reading), `GET /documents/?farm_id=`, `DELETE /documents/{doc_id}`

---

## 5. Database (Supabase / Postgres 17)

| Migration | Contents |
|---|---|
| `20260402000001_schema_v1` | `users`, `farms`, `fields`, `soil_profiles`, `weather_cache`, `recommendations`, `credit_eligibility`, `documents`, `eqip_practices`, plus RLS and the `on_auth_user_created` trigger that fills `public.users` |
| `…000002_add_insert_rls_policies` | INSERT policies |
| `20260406000003_csp_navigator` | `csp_resource_concerns`, `csp_enhancement_activities`, `csp_state_payment_rates`, `csp_application_deadlines`, `csp_eligibility_assessments`, `csp_farm_enhancements` |
| `…000004_csp_seed_data` | CSP reference data |
| `…000005_field_activity_log` | `field_activities`, `yield_history` |
| `20260422000006_add_indexes` | Indexes |
| `20260913000007_csp_fy2026_activities` | FY2026 CSP activity list keyed by NRCS practice code |
| `20260913000008_fix_write_paths` | Columns the API already wrote, `farm-documents` bucket + storage policies, widened CSP status CHECK, `weather_cache` UPDATE policy, deprecated FY2025 rows |
| `20260920000009_rls_update_with_check` | `WITH CHECK` added to nine UPDATE policies |

---

## 6. Frontend

- **Auth:** Supabase magic link. `proxy.ts` calls `updateSession`, and the dashboard layout redirects to `/login` when there's no user. `DEV_AUTH_BYPASS=true` (server-only env var) skips auth locally. Every check goes through `lib/supabase/dev-bypass.ts`, which throws if the flag is on with `NODE_ENV=production`.
- **Data fetching:** dashboard pages are server components using `lib/api/server-client.ts`. Both it and `client.ts` build their `api` object from `createEndpoints()` in `lib/api/endpoints.ts`, so they have an identical shape and hit the same flat, query-param routes (base URL includes `/api/v1`, and collection routes keep their trailing slash).
- **Dashboard** (`/dashboard?farm=&field=`) is built around four farmer questions: *What should I do this week?*, *How's my field doing?*, *Am I eligible for programs?* and *What happened recently?* The weather and soil widgets load real data for the selected field. The layout shows an `OfflineBanner`.
- **Onboarding** is 6 steps. Each step saves to `localStorage` (`onboarding_farm`, `onboarding_fields`, `onboarding_practices`, `onboarding_goal`). The farm step requires a 5-digit county FIPS code that matches the state's prefix. The confirm step works like this:
  1. It calls `POST /farms/`, then `POST /fields/` for each field, recording the created IDs in `localStorage`. A retry after a partial failure doesn't create the farm twice.
  2. It fires `POST /fields/{id}/enrich` and `POST /recommendations/generate` without waiting for them.
  3. It clears onboarding storage and redirects to `/dashboard?farm=<id>`.
  - Practice IDs are mapped to NRCS codes before being saved.
- **Design system** (`design-system/regenai/MASTER.md`):
  - Colors: earth green `#15803D` primary, harvest gold `#A16207` accent, light green `#F0FDF4` background
  - Fonts: Lexend for headings, Source Sans 3 for body
  - Body text 16px minimum on mobile, 48px touch targets
  - A page-specific file at `design-system/pages/<page>.md` overrides the master (none exist yet)

---

## 7. Local development

`scripts/dev.ps1` (Windows) runs all of the below in one command; `-NoDatabase` skips Supabase when Docker is unavailable, `-Stop` shuts it down.

```bash
supabase start                                   # Postgres :54322, API :54321, Studio :54323, Inbucket :54324
cd backend && cp .env.example .env && poetry install --no-root   # Poetry 2.x (lock generated by 2.3.3)
poetry run python scripts/seed_eqip.py           # required: the hallucination guard needs eqip_practices
poetry run uvicorn app.main:app --reload --port 8000   # or: docker compose up
cd frontend && cp .env.local.example .env.local  # NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
npm install && npm run dev
cd backend && poetry run pytest                  # mocked Supabase, no DB needed
poetry run ruff check app/                       # py311, line length 100
cd frontend && npm run lint && npx tsc --noEmit && npm run build
```

CI (`.github/workflows/ci.yml`) runs these checks on pushes to `main` and on every PR:
- Backend: Python 3.11, Poetry 2.3.3, ruff, pytest.
- Frontend: Node 20, `npm ci`, lint, tsc, build.

The internal planning files (`PLAN.md`, `CATCHING_UP.txt`, `CSP_NAVIGATOR_SPEC.json`, `regenai_agent_execution_brief.md`, `PM_*_TASKS.md`) are gitignored. So are `CLAUDE.md` and `AGENTS.md`.

---

## 8. Gaps, inconsistencies and likely bugs

These were first found by reading the code on `main`. The status after work on `fix/context-audit-issues` is shown next to each one.

**Backend tests/lint: Fixed.** `ruff check app/` is clean and `pytest` passes 396/396 on Python 3.11. Before this, 77 tests were failing.
- **Stale tests** (auth, farms/fields routers, CSP payment mock) were rewritten to match Sprint 2 behavior.
- **Real code bugs** were fixed:
  - EQIP/VCM returned the partial upsert row instead of the computed result.
  - VCM raised a KeyError on unknown practice codes.
  - Farm/field routers sent UUID objects to Supabase and returned 500 instead of 404.
  - The prompt builder read CSP keys that don't exist.
  - The LLM JSON parser accepted wrapped objects.
- **Dependencies:** `python-multipart` added, and `poetry.lock` regenerated with Poetry 2.3.3.
- **Seed data:** `seed.sql` / `seed_eqip.py` NRCS practice codes corrected, and the upsert now updates names that were already seeded.
- **NRCS practice codes: Fixed** (verified on nrcs.usda.gov). In `program_rules.py`, Irrigation Pipeline 484 → 430 and Microirrigation 657 → 441. The duplicate 666 "Irrigation Water Management" entry was removed; 449 already covers IWM. Scoring tests now assert the correct codes.
- **CLAUDE.md compliance audit (2026-09-13): Fixed.**
  - **Router bugs:**
    - `PATCH /fields/{id}` returned 500 on every call, because the update builder has no `.single()`.
    - Farm/field get and field delete turned every DB error into 404. Only `PGRST116` is 404 now.
    - Listing recommendations for a hidden field now returns 404.
    - Activities routers pass `str` IDs.
  - **Services:**
    - `pending_review` now follows the `CSP_MIN_PRIORITY_CONCERNS` rule instead of "exactly 1".
    - Unexpected weather/soil response shapes no longer crash.
    - Broad `except Exception` in eqip/vcm/enrichment/weather/soil was narrowed to DB/HTTP errors.
    - `prompts.py` and the APH year limits (7 CFR 400.55) read from `program_rules.py`.
  - **Tests:** `test_schema_drift.py` checks every status, upsert conflict target and RLS policy the services use against the migrations. 674 tests pass; the one failure is `test_today_central_returns_date` on Windows without tzdata, and it passes on Linux CI.
- **Second pass (2026-09-13): Fixed.**
  - **Practice data:** 430 is seeded in `seed.sql`, with a drift guard that every catalog code is in the seed. 441 now scores water quantity and energy.
  - **LLM parser:** it rejects any code-fenced output, which triggers the retry.
  - **EQIP documents:** only soil_report, field_photo and compliance qualify, via one `QUALIFYING_DOC_TYPES` constant.
  - **Prompt rules:** the unsourced organic-matter and pH cutoffs were removed. The prompt defers to state extension guidance.
  - **Router error handling:** farms, fields and credits catch only `APIError` / `httpx.HTTPError`. `credits._run_engine` returns a fixed message and logs the detail.
  - **Eligibility response:** `GET /csp/eligibility` now returns `min_concerns_required`, `additional_concerns_required` (7 CFR 1470.20) and `contract_years`. The frontend copy uses them.
  - **Weather units:** the weather widget was showing Open-Meteo's °C as °F. It now converts to °F.
- **Still open (backend):**
  - **Soil placeholders:** `soil.py` stores "UNKNOWN" when the map unit or texture is missing. The `soil_profiles.ssurgo_map_unit`/`texture` columns are NOT NULL, so fixing it needs a migration plus schema and type changes. `context.py` also fills in "Unknown" for the prompt.

### High impact: the frontend and backend don't match

1. **The API paths in the frontend didn't exist on the backend.** **Fixed.**
   - The clients were rewritten around a shared factory, `lib/api/endpoints.ts`. They now use flat routes with query params, trailing slashes and the `/api/v1` base.
   - Recommendation generation is called per farm.
   - `types.ts` and `adapters.ts` were brought in line with the backend schemas.
2. **The base URL was ambiguous.** **Fixed.** The README and `frontend/.env.local.example` now say `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1`. The README's API table lists every route with its prefix, including documents.
3. **Onboarding never saved anything.** **Fixed.**
   - The confirm step now creates the farm and its fields through the API, with a retry-safe partial save.
   - It then fires enrichment and recommendation generation and redirects to `/dashboard?farm=<id>`.
   - The farm step now collects `county_fips`, which the backend requires.
4. **The dashboard layout wouldn't build.** **Fixed.** The wrong `"use client"` directive was removed and `components/shared/offline-banner.tsx` was added. `npm run build` passes.

### Medium impact

5. **The weather and soil widgets were hardcoded empty.** **Fixed.** The dashboard now calls `fields.getWeather` and `fields.getSoil` for the selected field.
6. **The auth-bypass flags didn't match.** **Fixed.** All checks go through `lib/supabase/dev-bypass.ts`, which reads only the server-side `DEV_AUTH_BYPASS` and throws in production.
7. **The recommendations router typed IDs as `str`.** **Fixed.** It now uses `UUID` params.
8. **`frontend/.env.local.example` was missing.** **Fixed.** The file has been added, and `REDIS_URL` was removed from `backend/.env.example`.
9. **`.github/dependabot.yml` was invalid.** **Fixed.** It now covers `npm` (`/frontend`), `pip` (`/backend`), `docker` (`/backend`) and `github-actions`, all weekly.
10. **There was no CI workflow.** **Fixed.** `.github/workflows/ci.yml` runs ruff and pytest for the backend, and lint, tsc and build for the frontend.
11. **Frontend tsc and lint errors.** **Fixed.** `npm run build` passes. Warnings remain (see item 21).

### Documentation drift (README vs. code): Fixed

The README now:
- names the root `RegenAI/`
- drops the nonexistent `backend/migrations/`
- lists 6 migrations
- states that Celery and Redis are not implemented, and that Resend and WeasyPrint are installed but unused
- describes the full test scope and CI
- notes the Poetry 2.x requirement

### Newly found and still open

12. **There's no farm-wide activity list endpoint.** `GET /activities` requires `field_id`, so the UI fans out one request per field. `GET /activities/summary` returns counts and the last activity date per field, but no list of recent items.
13. **The activity form collects fields the backend doesn't store.** These are row spacing, depth, EPA reg #, wind, temperature, P/K, method, pest type, threshold, test weight and elevator ticket. They're currently packed into `notes`.
14. **The backend doesn't persist CSP enhancement selections or commitments.** Nothing in `backend/app` reads or writes `csp_farm_enhancements`, so checklist items can never complete.
15. **CSP deadlines: Fixed.** `backend/app/services/program_deadlines.py` holds a sourced deadline table for each state, with status confirmed / expected / not announced. `GET /csp/deadlines` returns days remaining and urgency, and the banner and dashboard widget show them. The table has to be updated by hand when states announce their FY2027 cutoffs (IL, KS, MN, MO, NE, OH are still pending).
    - **CSP payment rules updated to FY2026** (`program_rules.py`): $300K contract limit, no annual cap, $4,000 EAP. Activities are keyed by NRCS practice code because the official FY2026 activity list couldn't be verified. Rates are labelled as pre-FY2026 estimates.
    - **Assessment persistence: Fixed.** Migration 008 widens the status CHECK to allow `act_now` / `pending_review`. The service upserts on `ASSESSMENT_CONFLICT_TARGET` `(farm_id, fiscal_year)`. `test_schema_drift.py` guards both.
    - **Invented state ranking threshold: Fixed (2026-09-22).** `CSP_DEFAULT_STATE_RANKING_THRESHOLD = 42.0` was applied to every state outside the ~12 on file, which nationwide would be most users. It is deleted: an unlisted state now yields `state_ranking_threshold`, `meets_ranking_threshold` and `gap_to_threshold` of `None`, the status can never be `act_now`, the eligibility note says the state's cut-off is not published, and `scoring_rules.state_ranking_threshold` reports `known_estimate` or `not_published`. `tests/test_csp_scoring.py::TestNoInventedDefaultThreshold` is the drift guard.
    - **Still open:** payment estimates use a fixed default activity scenario.
    - **Still open:** alerts are in-app only; there's no email or SMS.
16. **Hardcoded UI strings: mostly Fixed.**
    - **Fixed:**
      - The Iowa threshold, Mississippi River Basin bonus text, "in Iowa" copy and "$2.65/acre" were removed; the threshold now comes from the API's `state_ranking_threshold`.
      - `vcm-detail.tsx` no longer invents its own credit rates or "$18/credit". It renders the `GET /credits/report` estimate through `vcmEstimateFromReport`.
      - `eqip-detail.tsx` had practice 600 labeled as pest management; it's actually Terrace, and pest management is 595.
      - The conservation-area count comes from the API list.
      - The NRCS locator URL and disclaimers are shared constants in `lib/csp-status.ts`.
    - **Also fixed (second pass):**
      - The minimum-concerns count comes from the API's `min_concerns_required`.
      - The invented score labels, percentile bands and bonus points were removed; the badge follows the backend's `eligibility_status`.
      - The checklist's 50/30/20 readiness percentage is now "N of M conservation areas meeting the threshold".
      - The payment and enhancements rule text comes from the API's rules block, with as-of date and source.
      - The invented improvement hints were replaced by API-recommended activities for each unmet area.
17. **CSP pages repeat computation on every load.** Every CSP page calls `GET /csp/eligibility`, which re-runs full CART scoring and upserts the assessment. `GET /csp/score` also re-scores. The payment and overview pages then call payments/enhancements as well; payments falls back to inline scoring when no assessment is cached. Nothing is cached or reused across the page's requests.
18. **Practices are captured once per farm and the county name isn't stored.** Onboarding copies the same practices to every field. The farm's county *name* is shown during onboarding but isn't saved; only `county_fips` is.
19. **Enrichment county coverage: Fixed (2026-09-22).** The hand-written ~90-county table (IA/IL/KS, with several mislabelled rows) is replaced by `app/data/county_centroids.json`: 3,230 entries covering all US counties plus Puerto Rico municipios and retired Connecticut counties, generated from the Census Gazetteer by `scripts/generate_county_centroids.py` (re-runnable, `--check` flag for drift). Coordinates are Census internal points, which always fall inside the county.
20. **Next.js 16 `middleware` convention: Fixed.** `src/middleware.ts` was renamed to `src/proxy.ts` (exports `proxy`), per the installed Next 16 docs. `lib/supabase/middleware.ts` is only a helper and keeps its name.
21. **ESLint warnings: Fixed.** `npm run lint` reports 0 errors and 0 warnings. The react-hook-form `watch()` calls became `useWatch({ control })`.
21a. **The eligibility page's Re-evaluate action doesn't refresh.** **Fixed.** `csp-reevaluate-button.tsx` calls `api.csp.evaluate`, then `router.refresh()`, and shows pending and error states.
22. **LLM provider: switched to DeepSeek (2026-09-13).** The backend uses `deepseek-flash` through the `openai` SDK at `https://api.deepseek.com`, configured by `DEEPSEEK_API_KEY` / `deepseek_model` / `deepseek_base_url` in `config.py`. Thinking mode is disabled because it ignores temperature. Still open: consider DeepSeek's JSON output mode or tool calls instead of parsing a bare array out of text.
23. **UPDATE row-level security policies had no `WITH CHECK`: Fixed.** A Postgres UPDATE policy tests `USING` against the old row and `WITH CHECK` against the new one. Nine policies (migrations 001, 002, 003, 005) declared only `USING`, so an owner could UPDATE a row to point at a farm or field belonging to another user, re-parenting it out of their own scope. Migration 008 had already used the correct shape for `weather_cache`; `supabase/migrations/20260920000009_rls_update_with_check.sql` applies it to `users`, `farms`, `fields`, `recommendations`, `credit_eligibility`, `csp_eligibility_assessments`, `csp_farm_enhancements`, `field_activities` and `yield_history`. Each policy is recreated with its original `USING` predicate unchanged, so no access is widened. `tests/test_rls_policies.py` is a drift guard that fails if a later migration reintroduces an UPDATE policy without `WITH CHECK`.
24. **Three oversized backend modules split into packages: Done.** `models/schemas.py` (917 lines), `services/program_rules.py` (892) and `services/activity_log.py` (765) each became a package of per-domain modules. Every definition was moved verbatim; only import blocks were regenerated. Each package's import surface is unchanged — `app.models.schemas`, `app.services.program_rules` and `app.services.activity_log` still export the same names, so no router or service call site changed. Three test patch targets and three private-helper imports in `test_activity_log.py` moved to `app.services.activity_log.helpers`, which is where `_today`, `_check_rules` and `_assert_field_access` now live. Largest remaining module is `models/csp.py` at 336 lines; `services/program_rules/practices.py` is 390, mostly the practice data table.

### Other notes (still open)

- The CART points, VCM credit rates and state thresholds are hardcoded approximations ("FY2024 CART worksheets", "per execution brief"). They should be checked against current NRCS and registry data before they're shown to paying farmers.
- Resend and WeasyPrint are installed but unused. `/credits/report` returns JSON only.
- The frontend types are written by hand. Generating them from FastAPI's OpenAPI schema would prevent drift from coming back.

---

## 9. Suggested next steps

1. **Push this branch and confirm CI passes on GitHub.** Locally (2026-09-13), backend ruff is clean and pytest passes 674 tests, with 1 Windows-only tzdata failure. Frontend tsc, lint (0 warnings) and build pass. Then seed practice 430 in `eqip_practices` and decide whether 441 should score water quantity.
2. **Test the onboarding-to-dashboard flow end to end against a local Supabase.** Onboarding, enrichment, recommendations, CSP and credits have only been verified by build/typecheck so far.
3. **Fill the activity API gaps.** Add a farm-wide `GET /activities?farm_id=`, return recent items from the summary endpoint, and add columns or a JSON field for the extra activity-form data (#12, #13).
4. **Make the CSP Navigator data-driven:**
   - Persist enhancement selections to `csp_farm_enhancements` (#14).
   - Move the deadlines to `csp_application_deadlines` with current fiscal-year dates (#15).
   - Serve state thresholds and rates from the API instead of hardcoded strings (#16).
   - Cache or reuse the assessment across CSP endpoints (#17).
5. **Enrichment coverage is nationwide (#19 done).** Still consider per-field practices and storing the county name (#18).
6. **Finish making the CSP UI data-driven.** Serve the minimum-concerns count, score bands and bonus points from the API, and fix the Re-evaluate refresh (#16, #21a). The frontend cleanup is done: `proxy.ts` rename, 0 lint warnings, and mocks deleted (#20, #21).
7. **Upgrade the LLM model and use structured outputs** (#22). Generate TS types from OpenAPI.
