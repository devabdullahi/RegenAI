#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# dev.sh — Start the RegenAI stack for local development (macOS / Linux)
#
#   Supabase  — only when Docker is running
#   Backend   — Poetry when installed, otherwise a plain venv
#   Frontend  — npm install when node_modules is absent, then next dev
#
# Usage:
#   ./scripts/dev.sh              # full stack
#   ./scripts/dev.sh --no-db      # skip Supabase (UI work, no Docker needed)
#   ./scripts/dev.sh --seed       # seed eqip_practices after backend is up
#   ./scripts/dev.sh --stop       # kill anything on the dev ports
#   ./scripts/dev.sh --reinstall  # force dependency reinstall
# ---------------------------------------------------------------------------
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_DIR="$REPO_ROOT/frontend"
BACKEND_PORT=8000
FRONTEND_PORT=3000

NO_DATABASE=false
SEED=false
STOP=false
REINSTALL=false

# --- Parse flags -----------------------------------------------------------
for arg in "$@"; do
  case "$arg" in
    --no-db|--no-database) NO_DATABASE=true ;;
    --seed)                SEED=true ;;
    --stop)                STOP=true ;;
    --reinstall)           REINSTALL=true ;;
    *) echo "Unknown flag: $arg"; exit 1 ;;
  esac
done

# --- Helpers ---------------------------------------------------------------
cyan()   { printf '\n\033[36m==> %s\033[0m\n' "$1"; }
green()  { printf '    \033[32m%s\033[0m\n' "$1"; }
yellow() { printf '    \033[33m%s\033[0m\n' "$1"; }
red()    { printf '    \033[31m%s\033[0m\n' "$1"; }

PIDS=()

cleanup() {
  cyan "Stopping"
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null && wait "$pid" 2>/dev/null || true
  done
  # Kill anything still on the ports
  kill_port $BACKEND_PORT  "backend"  || true
  kill_port $FRONTEND_PORT "frontend" || true
  green "all stopped"
}

kill_port() {
  local port=$1 label=$2
  local pids
  pids=$(lsof -ti :"$port" 2>/dev/null || true)
  if [[ -z "$pids" ]]; then
    green "$label: nothing on port $port"
    return 0
  fi
  echo "$pids" | xargs kill -9 2>/dev/null || true
  green "$label: stopped processes on port $port"
}

has_cmd() { command -v "$1" &>/dev/null; }

url_alive() {
  local code
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "$1" 2>/dev/null || echo "000")
  [[ "$code" != "000" ]]
}

wait_for_url() {
  local url=$1 timeout=${2:-90} label=${3:-service}
  local deadline=$((SECONDS + timeout))
  while (( SECONDS < deadline )); do
    local code
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "$url" 2>/dev/null || echo "000")
    if [[ "$code" != "000" ]]; then
      echo "$code"
      return 0
    fi
    sleep 0.7
  done
  echo "0"
}

# ---------------------------------------------------------------------------
# --stop
# ---------------------------------------------------------------------------
if $STOP; then
  cyan "Stopping RegenAI"
  kill_port $BACKEND_PORT  "backend"
  kill_port $FRONTEND_PORT "frontend"
  echo ""
  echo "  Supabase, if running, is left alone. Stop it with: npx supabase stop"
  exit 0
fi

trap cleanup EXIT INT TERM

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------
cyan "Checking tools"

if ! has_cmd node || ! has_cmd npm; then
  red "node and npm are required — https://nodejs.org"
  exit 1
fi
green "node $(node --version)"

HAS_POETRY=false
has_cmd poetry && HAS_POETRY=true

HAS_DOCKER=false
has_cmd docker && docker info &>/dev/null && HAS_DOCKER=true

# Find a usable Python
PYTHON=""
for cand in python3.11 python3.12 python3.13 python3 python; do
  if has_cmd "$cand"; then
    PYTHON="$cand"
    green "python: $($PYTHON --version 2>&1)"
    break
  fi
done

if [[ -z "$PYTHON" ]] && ! $HAS_POETRY; then
  red "No usable Python found — install 3.11+ to match CI"
  exit 1
fi

if $HAS_POETRY; then
  green "poetry found — using it for the backend"
else
  yellow "poetry not found — falling back to a plain venv"
fi

# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------
if ! $NO_DATABASE; then
  cyan "Supabase"
  if ! $HAS_DOCKER; then
    yellow "Docker not running — continuing WITHOUT a database."
    yellow "No auth, no data. Install/start Docker Desktop for the full stack."
    NO_DATABASE=true
  else
    (cd "$REPO_ROOT" && npx --yes supabase start) || {
      yellow "supabase start failed — continuing without a database"
      NO_DATABASE=true
    }
    if ! $NO_DATABASE; then
      green "Supabase up (API :54321, Studio :54323)"
    fi
  fi
fi

# ---------------------------------------------------------------------------
# Backend environment
# ---------------------------------------------------------------------------
cyan "Backend environment"
ENV_FILE="$BACKEND_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  yellow "backend/.env not found (see backend/.env.example)"
fi

check_env_var() {
  if [[ -f "$ENV_FILE" ]]; then
    grep -q "^$1=" "$ENV_FILE" 2>/dev/null && return 0
  fi
  return 1
}

MISSING=()
for var in SUPABASE_URL SUPABASE_ANON_KEY DEEPSEEK_API_KEY; do
  check_env_var "$var" || MISSING+=("$var")
done

if (( ${#MISSING[@]} > 0 )); then
  if $NO_DATABASE; then
    yellow "Missing in backend/.env: ${MISSING[*]}"
    yellow "Using placeholders (no database mode)."
    # Export placeholders so the app can boot
    export SUPABASE_URL="${SUPABASE_URL:-http://127.0.0.1:54321}"
    export SUPABASE_ANON_KEY="${SUPABASE_ANON_KEY:-placeholder-anon-key}"
    export DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY:-placeholder}"
  else
    red "Missing in backend/.env: ${MISSING[*]}"
    red "Copy backend/.env.example to backend/.env and fill these in"
    red "(npx supabase status prints the local URL and anon key),"
    red "or re-run with --no-db to start without one."
    exit 1
  fi
fi

# Export .env file vars into the shell
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

# ---------------------------------------------------------------------------
# Backend dependencies
# ---------------------------------------------------------------------------
cyan "Backend dependencies"
VENV_PY="$BACKEND_DIR/.venv/bin/python"

PIP_PACKAGES=(
  fastapi "uvicorn[standard]" pydantic pydantic-settings supabase
  httpx slowapi python-multipart python-dotenv resend openai
)

if $HAS_POETRY; then
  (cd "$BACKEND_DIR" && poetry install --no-root --no-interaction)
  green "poetry install complete"
else
  VENV_OK=false
  if [[ -f "$VENV_PY" ]] && ! $REINSTALL; then
    "$VENV_PY" --version &>/dev/null && VENV_OK=true
    $VENV_OK || yellow "backend/.venv is broken — rebuilding"
  fi
  if ! $VENV_OK; then
    rm -rf "$BACKEND_DIR/.venv"
    $PYTHON -m venv "$BACKEND_DIR/.venv"
    green "created backend/.venv"
  fi
  "$VENV_PY" -m pip install --quiet --upgrade pip
  "$VENV_PY" -m pip install --quiet "${PIP_PACKAGES[@]}"
  green "backend packages installed"
fi

# ---------------------------------------------------------------------------
# Start the backend
# ---------------------------------------------------------------------------
cyan "Starting backend on :$BACKEND_PORT"
kill_port $BACKEND_PORT "backend"

if $HAS_POETRY; then
  (cd "$BACKEND_DIR" && poetry run python -m uvicorn app.main:app \
    --host 127.0.0.1 --port "$BACKEND_PORT" --reload) &
else
  (cd "$BACKEND_DIR" && "$VENV_PY" -m uvicorn app.main:app \
    --host 127.0.0.1 --port "$BACKEND_PORT" --reload) &
fi
PIDS+=($!)

CODE=$(wait_for_url "http://127.0.0.1:$BACKEND_PORT/health" 90 "backend")
if [[ "$CODE" == "0" ]]; then
  red "backend did not answer on :$BACKEND_PORT"
  exit 1
elif [[ "$CODE" == "200" ]]; then
  green "backend healthy (200)"
else
  yellow "backend up but /health returned $CODE — expected when there is no database"
fi

# ---------------------------------------------------------------------------
# Seed (optional)
# ---------------------------------------------------------------------------
if $SEED; then
  cyan "Seeding eqip_practices"
  if $NO_DATABASE; then
    yellow "skipped — there is no database to seed"
  else
    if $HAS_POETRY; then
      (cd "$BACKEND_DIR" && poetry run python scripts/seed_eqip.py) && green "seeded" || yellow "seeding failed"
    else
      (cd "$BACKEND_DIR" && "$VENV_PY" scripts/seed_eqip.py) && green "seeded" || yellow "seeding failed"
    fi
  fi
fi

# ---------------------------------------------------------------------------
# Start the frontend
# ---------------------------------------------------------------------------
cyan "Starting frontend on :$FRONTEND_PORT"
if [[ ! -d "$FRONTEND_DIR/node_modules" ]] || $REINSTALL; then
  green "installing npm dependencies (first run)"
  (cd "$FRONTEND_DIR" && npm install)
fi
kill_port $FRONTEND_PORT "frontend"

(cd "$FRONTEND_DIR" && npm run dev) &
PIDS+=($!)

FE_CODE=$(wait_for_url "http://localhost:$FRONTEND_PORT" 120 "frontend")
if [[ "$FE_CODE" == "0" ]]; then
  yellow "frontend has not answered yet — may still be compiling"
else
  green "frontend responding ($FE_CODE)"
fi

# ---------------------------------------------------------------------------
# Ready
# ---------------------------------------------------------------------------
echo ""
printf '  \033[32mRegenAI is running\033[0m\n'
echo "    Frontend   http://localhost:$FRONTEND_PORT"
echo "    API docs   http://127.0.0.1:$BACKEND_PORT/docs"
echo "    Health     http://127.0.0.1:$BACKEND_PORT/health"
if ! $NO_DATABASE; then
  echo "    Supabase   http://127.0.0.1:54323  (Studio)"
else
  echo ""
  yellow "No database: API calls return 401/403 and pages show empty states."
fi
echo ""
echo "  Ctrl+C to stop"
echo ""

# ---------------------------------------------------------------------------
# Keep alive — watch both services
# ---------------------------------------------------------------------------
MISS_BE=0
MISS_FE=0

while true; do
  sleep 3
  if url_alive "http://127.0.0.1:$BACKEND_PORT/health"; then MISS_BE=0; else ((MISS_BE++)) || true; fi
  if url_alive "http://localhost:$FRONTEND_PORT";         then MISS_FE=0; else ((MISS_FE++)) || true; fi

  if (( MISS_BE >= 3 )); then yellow "backend stopped responding — shutting down"; break; fi
  if (( MISS_FE >= 3 )); then yellow "frontend stopped responding — shutting down"; break; fi
done
