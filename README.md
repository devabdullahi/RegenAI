# RegenAI

AI platform for regenerative agriculture. RegenAI helps mid-size Midwest row crop farmers (500–5,000 acres) discover USDA EQIP and CSP cost-share eligibility, estimate carbon credit revenue, and act on AI-generated agronomic recommendations — all in a mobile-first interface designed for the field.

**MVP target:** 5 paying pilot farms at $99–$299/month across Illinois, Iowa, Indiana, Kansas, Minnesota, Missouri, Nebraska, Ohio, and Wisconsin.

---

## Features

**Onboarding**
- 6-step farm setup flow (welcome, farm profile, fields, current practices, goals, confirm)
- Mobile-first design with large touch targets, plain-language copy

**AI Recommendation Engine**
- Calls `claude-sonnet-4-20250514` with farm context assembled from soil, weather, and current practices
- Validates every recommendation against the USDA EQIP practice code table before showing it to the farmer
- Flags hallucinated practice codes and field IDs rather than discarding them silently
- Returns 3–6 prioritized recommendations per farm, each with a plain-English rationale and CSP impact note

**Field Enrichment**
- Fetches 7-day weather forecast from Open-Meteo concurrently with soil data from USDA SSURGO SDA
- Resolves field coordinates from GeoJSON boundary centroid, falling back to a county-centroid lookup table covering Iowa, Illinois, and Kansas
- Results persisted to `weather_cache` and `soil_profiles` tables, available on dashboard widgets

**EQIP Eligibility Evaluator**
- Scores farms against documented conservation practices
- Persists eligibility status and practice list to `credit_eligibility`

**VCM Carbon Credit Estimator**
- Estimates Voluntary Carbon Market credits using a Soil Carbon Protocol model
- Per-field breakdown included in the credit report endpoint

**CSP Navigator**
- CART stewardship scoring across 8 NRCS priority resource concern categories
- Eligibility determination with four statuses: `act_now`, `eligible`, `pending_review`, `not_eligible`
- ACT NOW fast-track pathway when CART score exceeds the state ranking threshold
- Payment estimation: Existing Activity Payment (EAP) + Enhancement Activity Payment (EnAP), with NRCS caps ($4,000 min / $50,000 annual max / $200,000 over 5-year contract)
- Ranked enhancement recommendations sorted by gap-closure priority
- Application deadline calendar for IL, IN, IA, KS, MN, MO, NE, OH, WI (FY2025 quarterly batching schedule)

**Field Activity Log**
- Log planting, spraying, scouting, harvest, tillage, and cover crop events
- Restricted-use spray validation (requires applicator name and license)
- Yield history recording with automatic APH (Actual Production History) calculation using up to 10 years of data per USDA FSA standards
- Activity summary statistics per farm for dashboard cards

**Dashboard**
- Weather widget (last 7 days), soil profile widget, recommendation cards, credit status panel, CSP status widget

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16.2.2 (App Router), React 19, Tailwind CSS v4, shadcn/ui |
| Backend | FastAPI 0.115+, Python 3.11+, Uvicorn, Pydantic v2 |
| Database | PostgreSQL 17 via Supabase (managed), Row Level Security on all tables |
| Auth | Supabase magic link (passwordless), JWT passed as Bearer token to API |
| AI | Anthropic Claude API (`claude-sonnet-4-20250514`) |
| Background jobs | Celery 5.4 + Redis (wired, Celery tasks not yet active — enrichment runs synchronously) |
| Email | Resend (dependency installed, not yet active) |
| PDF reports | WeasyPrint 63+ (dependency installed, report data endpoint live, PDF rendering not yet active) |
| Package management | Poetry (backend), npm (frontend) |

---

## Project Structure

```
Farm_startup/
├── backend/
│   ├── app/
│   │   ├── auth/
│   │   │   └── middleware.py        # JWT extraction, authenticated Supabase client
│   │   ├── models/
│   │   │   └── schemas.py           # Pydantic request/response models
│   │   ├── routers/
│   │   │   ├── activities.py        # Field activity log + yield history + APH
│   │   │   ├── credits.py           # EQIP and VCM eligibility + report data
│   │   │   ├── csp.py               # CSP Navigator (score, eligibility, payments, enhancements)
│   │   │   ├── farms.py             # Farm CRUD
│   │   │   ├── fields.py            # Field CRUD + soil + weather + enrichment
│   │   │   ├── health.py            # GET /health
│   │   │   └── recommendations.py  # AI recommendation generation and status updates
│   │   ├── services/
│   │   │   ├── activity_log.py      # Activity and yield business logic
│   │   │   ├── context.py           # Farm context assembly for AI prompt
│   │   │   ├── csp_eligibility.py   # CART eligibility determination
│   │   │   ├── csp_payment.py       # EAP + EnAP payment estimation
│   │   │   ├── csp_scoring.py       # CART stewardship scoring engine
│   │   │   ├── enrichment.py        # Weather + soil orchestration
│   │   │   ├── eqip.py              # EQIP eligibility evaluator
│   │   │   ├── prompts.py           # Claude system prompt and user message builder
│   │   │   ├── recommendations.py   # Claude API call, JSON parsing, hallucination guard
│   │   │   ├── soil.py              # USDA SSURGO SDA client
│   │   │   ├── validators.py        # LLM output validation (Pydantic + hallucination guard)
│   │   │   ├── vcm.py               # Voluntary Carbon Market estimator
│   │   │   └── weather.py           # Open-Meteo client
│   │   ├── tasks/                   # Celery task stubs (not yet active)
│   │   ├── config.py                # Settings via pydantic-settings
│   │   └── main.py                  # FastAPI app, CORS, router registration
│   ├── migrations/                  # SQL files mirrored from supabase/migrations/
│   ├── scripts/
│   │   └── seed_eqip.py             # Seeds eqip_practices reference table
│   ├── tests/
│   │   ├── conftest.py              # Shared Supabase mock, farm/field fixtures
│   │   ├── test_csp_eligibility.py
│   │   ├── test_csp_models.py
│   │   ├── test_csp_payment.py
│   │   └── test_csp_scoring.py
│   ├── Dockerfile
│   ├── pyproject.toml
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
│   │   │   ├── shared/              # Nav, onboarding progress indicator
│   │   │   └── ui/                  # shadcn/ui primitives
│   │   └── lib/
│   │       ├── api/types.ts          # Shared TypeScript types
│   │       ├── mocks/               # Local mock data for UI development
│   │       └── supabase/            # Supabase client, server, and middleware helpers
│   ├── components.json              # shadcn/ui config (style: base-nova, icon: lucide)
│   ├── next.config.ts
│   ├── package.json
│   └── .env.local.example
│
├── supabase/
│   ├── config.toml                  # Local Supabase config (project_id: Farm_startup)
│   └── migrations/
│       ├── 20260402000001_schema_v1.sql              # Core tables + RLS policies
│       ├── 20260402000002_add_insert_rls_policies.sql
│       ├── 20260406000003_csp_navigator.sql          # CSP tables
│       ├── 20260406000004_csp_seed_data.sql          # CSP enhancement activities reference data
│       └── 20260406000005_field_activity_log.sql     # Activity log + yield history tables
│
└── design-system/regenai/MASTER.md  # Design tokens, component specs, touch target rules
```

---

## API Endpoints

The backend exposes 33 endpoints across 7 routers. In development the interactive docs are at `http://localhost:8000/docs` (disabled in production).

| Router | Method | Path | Description |
|---|---|---|---|
| Health | GET | `/health` | Liveness check |
| Farms | GET | `/farms/` | List farms for current user |
| Farms | POST | `/farms/` | Create farm |
| Farms | GET | `/farms/{farm_id}` | Get farm |
| Farms | PATCH | `/farms/{farm_id}` | Update farm |
| Farms | DELETE | `/farms/{farm_id}` | Delete farm |
| Fields | GET | `/fields/` | List fields for a farm |
| Fields | POST | `/fields/` | Create field |
| Fields | GET | `/fields/{field_id}` | Get field |
| Fields | GET | `/fields/{field_id}/soil` | Latest soil profile |
| Fields | GET | `/fields/{field_id}/weather` | Last 7 days of weather |
| Fields | POST | `/fields/{field_id}/enrich` | Fetch and persist weather + soil data |
| Recommendations | GET | `/recommendations/` | List recommendations for a field |
| Recommendations | PATCH | `/recommendations/{id}/status` | Update status (pending/acted/dismissed) |
| Recommendations | POST | `/recommendations/generate` | Run AI recommendation pipeline |
| Credits | GET | `/credits/` | Get latest EQIP and VCM records |
| Credits | POST | `/credits/evaluate` | Run fresh EQIP + VCM evaluation |
| Credits | GET | `/credits/report` | Assemble report data payload |
| CSP | GET | `/csp/eligibility` | Run CSP eligibility assessment |
| CSP | GET | `/csp/score` | CART stewardship score breakdown |
| CSP | GET | `/csp/payments` | Estimate annual and 5-year CSP payments |
| CSP | GET | `/csp/enhancements` | Ranked enhancement recommendations |
| CSP | POST | `/csp/evaluate` | Run full CSP pipeline (score + eligibility + payments) |
| CSP | GET | `/csp/deadlines` | Upcoming application deadlines by state |
| Activities | POST | `/activities` | Log a field activity |
| Activities | GET | `/activities` | List activities with filters and pagination |
| Activities | GET | `/activities/summary` | Activity count by type per farm |
| Activities | GET | `/activities/{activity_id}` | Get single activity |
| Activities | PATCH | `/activities/{activity_id}` | Partial update |
| Activities | DELETE | `/activities/{activity_id}` | Delete activity |
| Yield History | POST | `/yield-history` | Record yield history entry |
| Yield History | GET | `/yield-history` | Get yield history for a field |
| Yield History | GET | `/yield-history/aph` | Calculate APH yield (min 4 years required) |

All endpoints except `/health` require a Supabase JWT passed as `Authorization: Bearer <token>`. Row Level Security policies on the database ensure users can only access their own farm data.

---

## Database Schema

Five migrations define the schema. All tables have RLS enabled.

**Core tables** (migration 001):
`users`, `farms`, `fields`, `soil_profiles`, `weather_cache`, `recommendations`, `credit_eligibility`, `documents`, `eqip_practices`

**CSP tables** (migration 003):
`csp_assessments`, `csp_enhancement_activities` (seeded in migration 004)

**Activity tables** (migration 005):
`field_activities`, `yield_history`

A database trigger (`on_auth_user_created`) automatically creates a row in `public.users` when a new Supabase Auth user signs up.

---

## Getting Started (Local Development)

### Prerequisites

- Node.js 20+
- Python 3.11+
- Poetry 1.8+
- Docker (for local Supabase)
- Supabase CLI (`brew install supabase/tap/supabase` on macOS)

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

# Claude API
ANTHROPIC_API_KEY=sk-ant-...

# Redis (optional until Celery tasks are activated)
REDIS_URL=redis://localhost:6379/0

# Resend (optional until email is activated)
RESEND_API_KEY=re_...

# App
ENVIRONMENT=development
CORS_ORIGINS=["http://localhost:3000"]
```

Install dependencies and start the server:

```bash
poetry install
poetry run uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

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
NEXT_PUBLIC_API_URL=http://localhost:8000
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
# {"status":"healthy","service":"regenai-api"}
```

Open `http://localhost:3000` and sign in with any email address. Supabase sends magic links to the local Inbucket mail catcher at `http://localhost:54324`.

---

## Running Tests

Tests are in `backend/tests/` and cover the CSP scoring, eligibility, and payment engines. All tests use mock Supabase clients — no live database required.

```bash
cd backend
poetry run pytest
```

To run a specific test file:

```bash
poetry run pytest tests/test_csp_eligibility.py -v
```

---

## Environment Variables Reference

### Backend (`backend/.env`)

| Variable | Required | Description |
|---|---|---|
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_ANON_KEY` | Yes | Supabase anon key (public) |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Supabase service role key (bypasses RLS, server-side only) |
| `DATABASE_URL` | Yes | Direct Postgres connection string (used for admin operations) |
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key for Claude |
| `REDIS_URL` | No | Redis connection URL (default: `redis://localhost:6379/0`) |
| `RESEND_API_KEY` | No | Resend API key for transactional email |
| `ENVIRONMENT` | No | `development` or `production` (default: `development`) |
| `CORS_ORIGINS` | No | JSON array of allowed CORS origins (default: `["http://localhost:3000"]`) |

### Frontend (`frontend/.env.local`)

| Variable | Required | Description |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Yes | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Yes | Supabase anon key |
| `NEXT_PUBLIC_API_URL` | Yes | Backend API base URL (default: `http://localhost:8000`) |

---

## Docker (Backend)

A Dockerfile is provided for the backend. It installs WeasyPrint system dependencies and runs Uvicorn on port 8000.

```bash
cd backend
docker build -t regenai-backend .
docker run --env-file .env -p 8000:8000 regenai-backend
```

---

## Contributing

This is a private MVP repository. If you have access:

1. Create a feature branch from `main`.
2. Run `poetry run pytest` before opening a pull request.
3. Run `poetry run ruff check app/` to lint Python code (target: Python 3.11, line length 100).
4. Do not commit `.env`, `.env.local`, or any file containing API keys or secrets — the `.gitignore` covers these but double-check before pushing.
5. Do not commit `CATCHING_UP.txt`, `PLAN.md`, `CSP_NAVIGATOR_SPEC.json`, or `regenai_agent_execution_brief.md` — these are internal planning files excluded from the repo.

---

## License

Private and confidential. All rights reserved.
