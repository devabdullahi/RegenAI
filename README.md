# RegenAI

AI platform for regenerative agriculture. RegenAI helps US row-crop farmers (typically 500–5,000 acres) nationwide discover USDA EQIP and CSP cost-share eligibility, estimate carbon credit revenue, and act on AI-generated agronomic recommendations — all in a mobile-first interface designed for the field.

**MVP target:** 5 paying pilot farms at $99–$299/month across Illinois, Iowa, Indiana, Kansas, Minnesota, Missouri, Nebraska, Ohio, and Wisconsin.

For a plain-language overview of what the product does and how it works, see [`docs/RegenAI_Explained.pdf`](docs/RegenAI_Explained.pdf).

---

## Features

**Onboarding**
- 6-step farm setup flow (welcome, farm profile, fields, current practices, goals, confirm)
- Farm step collects state, county, and a 5-digit county FIPS code (validated against the state)
- Confirm step creates the farm and its fields through the API (retry-safe: a partially saved farm is not created twice), then kicks off field enrichment and recommendation generation in the background and redirects to `/dashboard?farm=<id>`
- Mobile-first design with large touch targets, plain-language copy

**AI Recommendation Engine**
- Calls DeepSeek (`deepseek-flash`, non-thinking mode) with farm context assembled from soil, weather, and current practices
- Validates every recommendation against the USDA EQIP practice code table before showing it to the farmer
- Drops recommendations with hallucinated practice codes or field IDs before they are stored
- Returns 3–6 prioritized recommendations per farm, each with a plain-English rationale and CSP impact note

**Field Enrichment**
- Fetches weather from Open-Meteo concurrently with soil data from USDA SSURGO SDA (runs synchronously in the request — there is no background queue)
- Resolves field coordinates from the GeoJSON boundary centroid, falling back to a county-centroid lookup keyed by county FIPS. The lookup table covers every US county (generated from the Census Gazetteer; see `scripts/generate_county_centroids.py`), so a field without a boundary can still be enriched anywhere in the US
- Results persisted to `weather_cache` and `soil_profiles` tables and shown in the dashboard weather and soil widgets

**EQIP Eligibility Evaluator**
- Checks the farm's acted-on recommendations against EQIP practice codes and requires at least one supporting document
- Persists eligibility status and practice list to `credit_eligibility`

**VCM Carbon Credit Estimator**
- Estimates Voluntary Carbon Market credits using a simplified Soil Carbon Protocol model
- Per-field breakdown included in the credit report endpoint

**CSP Navigator**
- CART stewardship scoring across 8 NRCS priority resource concern categories
- Eligibility determination with four statuses: `act_now`, `eligible`, `pending_review`, `not_eligible`
- ACT NOW fast-track pathway when the CART score exceeds the state ranking threshold. Only the ~12 states in `program_rules/csp_scoring.py` have an (unverified) threshold on file; for every other state `state_ranking_threshold` and `meets_ranking_threshold` are `null`, the status is never `act_now`, and `scoring_rules.state_ranking_threshold.status` is `not_published`.
- Payment estimation using FY2026 NRCS rules (NRCS National Bulletin 440-26-2): $4,000/year existing activity payment per contract, plus activity payments; no annual payment limit; $300,000 contract limit ($600,000 for joint operations; pre-FY2026 contracts stay at $200,000/$400,000). Rules live in `backend/app/services/program_rules/` with as-of dates and sources. Per-acre activity rates are pre-FY2026 estimates until state FY2026 payment schedules are loaded.
- Ranked enhancement recommendations sorted by gap-closure priority
- Application deadline table covering all 50 states, DC and the territories NRCS serves (`backend/app/services/program_deadlines.py`). States without a published cutoff are marked `not_announced` and link to their own NRCS office. Each entry has a source link, an as-of date, and a status: confirmed, expected, or not announced. Shows days remaining in the CSP banner and on the dashboard. Update it by hand when states announce new cutoffs.

**Field Activity Log**
- Log planting, spraying, scouting, harvest, tillage, and cover crop events
- Restricted-use spray validation (requires applicator name and license)
- Yield history recording with automatic APH (Actual Production History) calculation using up to 10 years of data per USDA FSA standards
- Activity summary statistics per farm for dashboard cards

**Dashboard**
- Weather widget, soil profile widget (live data for the selected field), recommendation cards, credit status panel, CSP status widget, offline banner

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16.2.2 (App Router), React 19, Tailwind CSS v4, shadcn/ui |
| Backend | FastAPI 0.115+, Python 3.11+, Uvicorn, Pydantic v2 |
| Database | PostgreSQL 17 via Supabase (managed), Row Level Security on all tables |
| Auth | Supabase magic link (passwordless), JWT passed as Bearer token to API |
| AI | DeepSeek API (`deepseek-flash`, OpenAI-compatible, via the `openai` SDK) |
| Background jobs | Not implemented. There are no Celery/Redis dependencies and `app/tasks/` is empty; enrichment and recommendation generation run inside the request |
| Email | Resend (dependency installed, not used by any code yet) |
| PDF reports | WeasyPrint 63+ (dependency installed, not used yet — `/credits/report` returns JSON report data only) |
| Package management | Poetry 2.x (backend), npm (frontend) |
| CI | GitHub Actions (`.github/workflows/ci.yml`) + Dependabot |

---

## Project Structure

```
RegenAI/
├── .github/
│   ├── dependabot.yml               # npm, pip, docker, github-actions (weekly)
│   └── workflows/ci.yml             # Backend ruff + pytest, frontend lint + tsc + build
├── backend/
│   ├── app/
│   │   ├── auth/
│   │   │   └── middleware.py        # JWT extraction, authenticated Supabase client
│   │   ├── models/                  # Pydantic models, one module per domain
│   │   │   ├── schemas.py           # re-exports every model (import surface kept stable)
│   │   │   ├── enums.py  farm.py  field.py  soil_weather.py  recommendation.py
│   │   │   └── credit.py  csp.py  activity.py  yield_history.py  document.py  program_deadline.py
│   │   ├── routers/
│   │   │   ├── activities.py        # Field activity log + yield history + APH
│   │   │   ├── credits.py           # EQIP and VCM eligibility + report data
│   │   │   ├── csp.py               # CSP Navigator (score, eligibility, payments, enhancements, deadlines)
│   │   │   ├── documents.py         # Document upload/list/delete (Supabase Storage)
│   │   │   ├── farms.py             # Farm CRUD
│   │   │   ├── fields.py            # Field CRUD + soil + weather + enrichment
│   │   │   ├── health.py            # GET /health
│   │   │   └── recommendations.py   # AI recommendation generation and status updates
│   │   ├── services/
│   │   │   ├── activity_log/        # Activity and yield business logic (crud, summary,
│   │   │   │                        #   yield_history, helpers, common)
│   │   │   ├── context.py           # Farm context assembly for AI prompt
│   │   │   ├── csp_eligibility.py   # CART eligibility determination
│   │   │   ├── csp_payment.py       # EAP + EnAP payment estimation
│   │   │   ├── csp_scoring.py       # CART stewardship scoring engine
│   │   │   ├── enrichment.py        # Weather + soil orchestration, county-centroid fallback
│   │   │   ├── eqip.py              # EQIP eligibility evaluator
│   │   │   ├── prompts.py           # LLM system prompt and user message builder
│   │   │   ├── recommendations.py   # DeepSeek API call, JSON parsing, hallucination guard
│   │   │   ├── soil.py              # USDA SSURGO SDA client
│   │   │   ├── validators.py        # LLM output validation (Pydantic + hallucination guard)
│   │   │   ├── vcm.py               # Voluntary Carbon Market estimator
│   │   │   └── weather.py           # Open-Meteo client
│   │   ├── tasks/                   # Empty (background jobs not implemented)
│   │   ├── config.py                # Settings via pydantic-settings
│   │   ├── rate_limit.py            # slowapi limiter
│   │   └── main.py                  # FastAPI app, CORS, request IDs, router registration
│   ├── scripts/
│   │   └── seed_eqip.py             # Seeds eqip_practices reference table
│   ├── tests/                       # pytest suite with mocked Supabase (see Running Tests)
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── poetry.lock                  # Generated by Poetry 2.x
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── (auth)/login/        # Magic link login page
│   │   │   ├── (dashboard)/         # Protected dashboard routes
│   │   │   │   ├── activities/      # Activity log list + new activity form
│   │   │   │   ├── credits/         # EQIP and VCM credit status
│   │   │   │   ├── csp/             # CSP Navigator (score, eligibility, payments, enhancements, checklist)
│   │   │   │   ├── dashboard/       # Main dashboard
│   │   │   │   ├── farms/           # Farm management
│   │   │   │   └── yield-history/   # Yield history view
│   │   │   ├── (onboarding)/        # 6-step onboarding flow
│   │   │   │   └── onboarding/      # welcome, farm, fields, practices, goals, confirm
│   │   │   └── auth/callback/       # Supabase auth callback handler
│   │   ├── components/
│   │   │   ├── activities/          # Activity card, form, filters, yield summary
│   │   │   ├── credits/             # EQIP detail, VCM detail, document upload
│   │   │   ├── csp/                 # Score gauge, eligibility card, payment summary, enhancements
│   │   │   ├── dashboard/           # Weather, soil, recommendation, credit, field selector widgets
│   │   │   ├── shared/              # Nav, offline banner, onboarding progress indicator
│   │   │   └── ui/                  # shadcn/ui primitives
│   │   ├── lib/
│   │   │   ├── api/endpoints.ts     # Shared endpoint map (single source of backend routes)
│   │   │   ├── api/client.ts        # Browser API client
│   │   │   ├── api/server-client.ts # Server-component API client (cookie session)
│   │   │   ├── api/adapters.ts      # Backend response → UI shape adapters
│   │   │   ├── api/types.ts         # Shared TypeScript types
│   │   │   └── supabase/            # Supabase client/server/middleware helpers + dev-bypass.ts
│   │   └── proxy.ts                 # Next 16 proxy (formerly middleware.ts); refreshes the Supabase session
│   ├── components.json              # shadcn/ui config (style: base-nova, icon: lucide)
│   ├── next.config.ts
│   ├── package.json
│   └── .env.local.example
│
├── supabase/
│   ├── config.toml                  # Local Supabase config
│   ├── seed.sql
│   └── migrations/
│       ├── 20260402000001_schema_v1.sql              # Core tables + RLS policies
│       ├── 20260402000002_add_insert_rls_policies.sql
│       ├── 20260406000003_csp_navigator.sql          # CSP tables
│       ├── 20260406000004_csp_seed_data.sql          # CSP reference data
│       ├── 20260406000005_field_activity_log.sql     # Activity log + yield history tables
│       ├── 20260422000006_add_indexes.sql            # Indexes
│       ├── 20260913000007_csp_fy2026_activities.sql  # FY2026 CSP activity list
│       ├── 20260913000008_fix_write_paths.sql        # Missing columns, storage bucket, CSP statuses
│       └── 20260920000009_rls_update_with_check.sql  # WITH CHECK on UPDATE policies
│
├── docs/RegenAI_Explained.pdf       # Plain-language product overview
├── docker-compose.yml               # Runs the API service only
└── design-system/regenai/MASTER.md  # Design tokens, component specs, touch target rules
```

---

## API Endpoints

The backend exposes 38 endpoints across 8 routers. Everything except `/health` is mounted under **`/api/v1`**. Parameters not in the path are **query parameters** (e.g. `GET /api/v1/fields/?farm_id=<uuid>`). Note the trailing slash on the collection routes (`/farms/`, `/fields/`, `/recommendations/`, `/credits/`, `/documents/`) — omitting it causes a redirect. In development the interactive docs are at `http://localhost:8000/docs` (disabled in production).

| Router | Method | Path | Description |
|---|---|---|---|
| Health | GET | `/health` | Liveness check (no prefix) |
| Farms | GET | `/api/v1/farms/` | List farms for current user |
| Farms | POST | `/api/v1/farms/` | Create farm |
| Farms | GET | `/api/v1/farms/{farm_id}` | Get farm |
| Farms | PATCH | `/api/v1/farms/{farm_id}` | Update farm |
| Farms | DELETE | `/api/v1/farms/{farm_id}` | Delete farm |
| Fields | GET | `/api/v1/fields/?farm_id=` | List fields for a farm |
| Fields | POST | `/api/v1/fields/` | Create field |
| Fields | GET | `/api/v1/fields/{field_id}` | Get field |
| Fields | PATCH | `/api/v1/fields/{field_id}` | Update field |
| Fields | DELETE | `/api/v1/fields/{field_id}` | Delete field |
| Fields | GET | `/api/v1/fields/{field_id}/soil` | Latest soil profile |
| Fields | GET | `/api/v1/fields/{field_id}/weather` | Last 7 days of weather |
| Fields | POST | `/api/v1/fields/{field_id}/enrich` | Fetch and persist weather + soil data |
| Recommendations | GET | `/api/v1/recommendations/?field_id=` | List recommendations for a field |
| Recommendations | PATCH | `/api/v1/recommendations/{recommendation_id}/status` | Update status (pending/acted/dismissed) |
| Recommendations | POST | `/api/v1/recommendations/generate?farm_id=` | Run AI recommendation pipeline for a farm |
| Credits | GET | `/api/v1/credits/?farm_id=` | Get latest EQIP and VCM records |
| Credits | POST | `/api/v1/credits/evaluate?farm_id=` | Run fresh EQIP + VCM evaluation |
| Credits | GET | `/api/v1/credits/report?farm_id=` | Assemble report data payload (JSON) |
| CSP | GET | `/api/v1/csp/eligibility?farm_id=` | Run CSP eligibility assessment |
| CSP | GET | `/api/v1/csp/score?farm_id=` | CART stewardship score breakdown |
| CSP | GET | `/api/v1/csp/payments?farm_id=` | Estimate annual and 5-year CSP payments |
| CSP | GET | `/api/v1/csp/enhancements?farm_id=` | Ranked enhancement recommendations |
| CSP | POST | `/api/v1/csp/evaluate?farm_id=` | Run full CSP pipeline (score + eligibility + payments) |
| CSP | GET | `/api/v1/csp/deadlines?state=` | Application deadlines by state |
| Activities | POST | `/api/v1/activities` | Log a field activity |
| Activities | GET | `/api/v1/activities?field_id=` | List a field's activities (filters + pagination) |
| Activities | GET | `/api/v1/activities/summary?farm_id=` | Activity count by type per farm |
| Activities | GET | `/api/v1/activities/{activity_id}` | Get single activity |
| Activities | PATCH | `/api/v1/activities/{activity_id}` | Partial update |
| Activities | DELETE | `/api/v1/activities/{activity_id}` | Delete activity |
| Yield History | POST | `/api/v1/yield-history` | Record yield history entry |
| Yield History | GET | `/api/v1/yield-history?field_id=` | Get yield history for a field |
| Yield History | GET | `/api/v1/yield-history/aph?field_id=` | Calculate APH yield (min 4 years required) |
| Documents | POST | `/api/v1/documents/` | Upload a document (multipart: `farm_id`, `doc_type`, `file`, max 10 MB) |
| Documents | GET | `/api/v1/documents/?farm_id=` | List a farm's documents |
| Documents | DELETE | `/api/v1/documents/{doc_id}` | Delete a document |

All endpoints except `/health` require a Supabase JWT passed as `Authorization: Bearer <token>`. Row Level Security policies on the database ensure users can only access their own farm data.

---

## Database Schema

Nine migrations define the schema. All tables have RLS enabled.

**Core tables** (migration 001, INSERT policies in 002):
`users`, `farms`, `fields`, `soil_profiles`, `weather_cache`, `recommendations`, `credit_eligibility`, `documents`, `eqip_practices`

**CSP tables** (migration 003, reference data seeded in 004):
`csp_resource_concerns`, `csp_enhancement_activities`, `csp_state_payment_rates`, `csp_application_deadlines`, `csp_eligibility_assessments`, `csp_farm_enhancements`

**Activity tables** (migration 005):
`field_activities`, `yield_history`

**Indexes** (migration 006)

A database trigger (`on_auth_user_created`) automatically creates a row in `public.users` when a new Supabase Auth user signs up.

---

## Getting Started (Local Development)

### Prerequisites

- Node.js 20+
- Python 3.11+
- Poetry 2.x (`poetry.lock` is generated by Poetry 2.x; Poetry 1.x cannot read it)
- Docker (for local Supabase)
- Supabase CLI (`brew install supabase/tap/supabase` on macOS)

### Quick start (Windows)

`scripts/dev.ps1` does everything below in one command — Supabase, backend and
frontend — and stops them all on Ctrl+C:

```powershell
.\scripts\dev.ps1               # full stack
.\scripts\dev.ps1 -NoDatabase   # no Docker: UI only, pages show empty states
.\scripts\dev.ps1 -Seed         # also seed eqip_practices after startup
.\scripts\dev.ps1 -Stop         # stop the backend and frontend
```

It falls back to a plain `venv` when Poetry is absent, rebuilds `backend/.venv`
if its interpreter has gone missing, and installs `tzdata` (which Windows needs
for `America/Chicago`, used by `GET /csp/deadlines`). Without Docker it says so
and continues without a database rather than failing.

The manual steps follow, and are what the script automates.

### 1. Clone the repo

```bash
git clone https://github.com/devabdullahi/RegenAI.git
cd RegenAI
```

### 2. Start local Supabase

```bash
supabase start
```

This starts a local Postgres instance on port 54322, the API on 54321, and Supabase Studio on 54323. Migrations in `supabase/migrations/` run automatically.

After `supabase start` completes, copy the printed `API URL`, `anon key`, and `service_role key` — you will need them in the next step.

### 3. Backend setup

```bash
cd backend
cp .env.example .env
```

Edit `backend/.env`:

```env
# Supabase
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_ANON_KEY=<anon key from supabase start>
SUPABASE_SERVICE_ROLE_KEY=<service_role key from supabase start>
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres

# DeepSeek API (https://platform.deepseek.com/api_keys)
DEEPSEEK_API_KEY=sk-...

# Resend (optional, not used yet)
RESEND_API_KEY=re_...

# App
ENVIRONMENT=development
CORS_ORIGINS=["http://localhost:3000"]
```

Install dependencies and start the server:

```bash
poetry install --no-root
poetry run uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000` (routes under `/api/v1`). Interactive docs at `http://localhost:8000/docs`.

**Seed EQIP practice codes** (required for the AI recommendation hallucination guard):

```bash
poetry run python scripts/seed_eqip.py
```

### 4. Frontend setup

```bash
cd frontend
cp .env.local.example .env.local
```

Edit `frontend/.env.local`:

```env
NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key from supabase start>
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1

# Optional, local development only: skip Supabase auth checks.
# Server-side flag; the app throws if it is enabled with NODE_ENV=production.
# DEV_AUTH_BYPASS=true
```

Install dependencies and start the dev server:

```bash
npm install
npm run dev
```

The frontend will be available at `http://localhost:3000`.

### 5. Verify the stack

```bash
curl http://localhost:8000/health
# {"status":"healthy","service":"regenai-api","checks":{...}}  (503 + "degraded" if a check fails)
```

Open `http://localhost:3000` and sign in with any email address. Supabase sends magic links to the local Inbucket mail catcher at `http://localhost:54324`. During onboarding you will need the farm's 5-digit county FIPS code (e.g. `19153` for Polk County, Iowa).

---

## Running Tests

Tests are in `backend/tests/` and cover the CSP scoring, eligibility, and payment engines, EQIP, VCM, the activity log, auth, LLM output validators, the recommendation pipeline, and the farms and fields routers. All tests use mock Supabase clients — no live database required.

```bash
cd backend
poetry run pytest
poetry run ruff check app/
```

To run a specific test file:

```bash
poetry run pytest tests/test_csp_eligibility.py -v
```

Frontend checks:

```bash
cd frontend
npm run lint
npx tsc --noEmit
npm run build
```

**CI:** `.github/workflows/ci.yml` runs on pushes to `main` and on pull requests. The backend job uses Python 3.11, Poetry 2.3.3, `poetry install --no-root`, ruff, and pytest. The frontend job uses Node 20, `npm ci`, lint, `tsc --noEmit`, and `npm run build`.

---

## Environment Variables Reference

### Backend (`backend/.env`)

| Variable | Required | Description |
|---|---|---|
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_ANON_KEY` | Yes | Supabase anon key (public) |
| `SUPABASE_SERVICE_ROLE_KEY` | Scripts only | Supabase service role key (bypasses RLS; used by `scripts/seed_eqip.py`) |
| `DATABASE_URL` | No | Direct Postgres connection string |
| `DEEPSEEK_API_KEY` | Yes | DeepSeek API key used for recommendations |
| `RESEND_API_KEY` | No | Resend API key (email not implemented yet) |
| `ENVIRONMENT` | No | `development` or `production` (default: `development`) |
| `CORS_ORIGINS` | No | JSON array of allowed CORS origins (default: `["http://localhost:3000"]`) |

The app refuses to start if `SUPABASE_URL`, `SUPABASE_ANON_KEY`, or `DEEPSEEK_API_KEY` is missing.

### Frontend (`frontend/.env.local`)

See `frontend/.env.local.example`.

| Variable | Required | Description |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Yes | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Yes | Supabase anon key |
| `NEXT_PUBLIC_API_URL` | Yes | Backend API base URL **including `/api/v1`** (default: `http://localhost:8000/api/v1`) |
| `DEV_AUTH_BYPASS` | No | `true` skips auth checks. Local development only; throws in production |

---

## Docker (Backend)

A Dockerfile is provided for the backend. It installs WeasyPrint system dependencies and runs Uvicorn on port 8000.

```bash
cd backend
docker build -t regenai-backend .
docker run --env-file .env -p 8000:8000 regenai-backend
```

`docker compose up` from the repo root runs the API service only (not Supabase or the frontend).

---

## Contributing

This is a private MVP repository. If you have access:

1. Create a feature branch from `main`.
2. Run `poetry run pytest` and `poetry run ruff check app/` (target: Python 3.11, line length 100) before opening a pull request. For frontend changes, run `npm run lint`, `npx tsc --noEmit`, and `npm run build`. CI runs the same checks.
3. Do not commit `.env`, `.env.local`, or any file containing API keys or secrets — the `.gitignore` covers these but double-check before pushing.
4. Do not commit `CATCHING_UP.txt`, `PLAN.md`, `CSP_NAVIGATOR_SPEC.json`, or `regenai_agent_execution_brief.md` — these are internal planning files excluded from the repo.

---

## License

Private and confidential. All rights reserved.
