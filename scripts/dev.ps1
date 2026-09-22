<#
.SYNOPSIS
    Start the RegenAI stack (Supabase + FastAPI backend + Next.js frontend) for local development.

.DESCRIPTION
    Brings up whatever this machine can actually run, in one command:

      * Supabase  - only when Docker is available. Without it there is no
                    database and no auth, so every page stops at "Select a
                    farm first". The script says so rather than failing.
      * Backend   - Poetry when installed, otherwise a plain venv at
                    backend/.venv. A venv left pointing at a deleted
                    interpreter is detected and rebuilt.
      * Frontend  - npm install when node_modules is absent, then next dev.

    Ctrl+C stops everything it started.

.PARAMETER NoDatabase
    Skip Supabase and run without a database. Implied when Docker is missing.

.PARAMETER Seed
    Run backend/scripts/seed_eqip.py after the backend is up. The AI
    hallucination guard needs the eqip_practices table populated.

.PARAMETER Stop
    Stop anything listening on the two ports and exit.

.PARAMETER Reinstall
    Force dependency reinstall (rebuilds the backend venv).

.EXAMPLE
    .\scripts\dev.ps1
.EXAMPLE
    .\scripts\dev.ps1 -NoDatabase        # UI work, no Docker needed
.EXAMPLE
    .\scripts\dev.ps1 -Stop
#>
[CmdletBinding()]
param(
    [switch] $NoDatabase,
    [switch] $Seed,
    [switch] $Stop,
    [switch] $Reinstall,
    [int]    $BackendPort  = 8000,
    [int]    $FrontendPort = 3000
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RepoRoot "backend"
$FrontendDir = Join-Path $RepoRoot "frontend"
$script:Started = @()

# Packages needed to import app.main. tzdata is NOT in pyproject.toml yet, but
# without it ZoneInfo("America/Chicago") raises and GET /csp/deadlines 500s on
# Windows, which has no system IANA database.
$PipPackages = @(
    "fastapi", "uvicorn[standard]", "pydantic", "pydantic-settings", "supabase",
    "httpx", "slowapi", "python-multipart", "python-dotenv", "resend", "openai", "tzdata"
)

function Write-Step  { param($m) Write-Host "`n==> $m" -ForegroundColor Cyan }
function Write-Ok    { param($m) Write-Host "    $m" -ForegroundColor Green }
function Write-Warn2 { param($m) Write-Host "    $m" -ForegroundColor Yellow }
function Write-Err2  { param($m) Write-Host "    $m" -ForegroundColor Red }

function Test-Tool {
    param([string] $Name)
    $c = Get-Command $Name -ErrorAction SilentlyContinue
    if ($c) { return $c.Source } else { return $null }
}

function Stop-Port {
    param([int] $Port, [string] $Label)
    if (-not (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)) {
        Write-Ok "$Label : nothing on port $Port"
        return
    }
    # Sweep repeatedly: uvicorn --reload keeps a reloader parent that respawns
    # the worker, and an orphaned worker can outlive its parent. One snapshot
    # kill is not enough, so re-check and kill the parent too.
    $killed = @()
    for ($round = 0; $round -lt 6; $round++) {
        $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if (-not $conns) { break }
        # Not $pid - that is a read-only automatic variable in PowerShell.
        foreach ($procId in ($conns.OwningProcess | Select-Object -Unique)) {
            # The reported owner is the process that BOUND the socket, which is
            # not always the one holding it. uvicorn --reload binds in the
            # reloader and hands the socket to a worker, so once the reloader
            # exits the port is still owned by a pid that no longer exists while
            # the worker serves on. Kill the owner, its supervisor, and any
            # child that inherited the socket.
            $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$procId" -ErrorAction SilentlyContinue
            if ($proc) {
                $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.ParentProcessId)" -ErrorAction SilentlyContinue
                if ($parent -and $parent.Name -match '^(python|pythonw|node)(\.exe)?$') {
                    Invoke-Taskkill -ProcessId $parent.ProcessId
                }
            }
            foreach ($child in @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$procId" -ErrorAction SilentlyContinue)) {
                Invoke-Taskkill -ProcessId $child.ProcessId
                if ($killed -notcontains $child.ProcessId) { $killed += $child.ProcessId }
            }
            Invoke-Taskkill -ProcessId $procId
            if ($killed -notcontains $procId) { $killed += $procId }
        }
        Start-Sleep -Milliseconds 400
    }
    if ($killed.Count -gt 0) { Write-Ok "$Label : stopped pid $($killed -join ', ') on port $Port" }
    if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
        Write-Warn2 "$Label : port $Port is still in use"
    }
}

function Invoke-Taskkill {
    <#
        Kill a process tree, quietly.

        taskkill writes to stderr when a pid is already gone, which PowerShell
        turns into a NativeCommandError - and with $ErrorActionPreference =
        'Stop' that aborts the caller mid-sweep. Redirecting inside cmd.exe
        keeps the output away from PowerShell entirely.
    #>
    param([int] $ProcessId)
    & cmd.exe /c "taskkill /PID $ProcessId /T /F >nul 2>&1"
}

function Stop-Tree {
    <#
        Kill a process and its descendants.

        Both servers spawn children: npm.cmd launches node, and uvicorn --reload
        runs a reloader parent plus a worker. Killing only the pid we launched
        leaves the real server listening, so kill the whole tree.
    #>
    param([int] $ProcessId)
    Invoke-Taskkill -ProcessId $ProcessId
}

function Test-UrlAlive {
    <# Any HTTP response means alive - 401/503 included. #>
    param([string] $Url)
    try {
        $null = Invoke-WebRequest -Uri $Url -TimeoutSec 3 -UseBasicParsing
        return $true
    } catch {
        $resp = $_.Exception.Response
        if ($resp -and $resp.StatusCode) { return $true }
        return $false
    }
}

function Wait-ForUrl {
    param([string] $Url, [int] $TimeoutSec = 90, [string] $Label = "service")
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            # 503 is a pass: /health reports "degraded" when Supabase is absent.
            $r = Invoke-WebRequest -Uri $Url -TimeoutSec 3 -UseBasicParsing
            return $r.StatusCode
        } catch {
            $resp = $_.Exception.Response
            if ($resp -and $resp.StatusCode) { return [int] $resp.StatusCode }
        }
        Start-Sleep -Milliseconds 700
    }
    return 0
}

function Import-DotEnv {
    <# Read KEY=VALUE pairs from a .env file. Values are taken literally. #>
    param([string] $Path)
    $map = @{}
    if (-not (Test-Path $Path)) { return $map }
    foreach ($line in Get-Content $Path) {
        $t = $line.Trim()
        if ($t -eq "" -or $t.StartsWith("#")) { continue }
        $i = $t.IndexOf("=")
        if ($i -lt 1) { continue }
        $map[$t.Substring(0, $i).Trim()] = $t.Substring($i + 1).Trim()
    }
    return $map
}

# ---------------------------------------------------------------------------
# -Stop
# ---------------------------------------------------------------------------
if ($Stop) {
    Write-Step "Stopping RegenAI"
    Stop-Port -Port $BackendPort  -Label "backend"
    Stop-Port -Port $FrontendPort -Label "frontend"
    Write-Host ""
    Write-Host "Supabase, if running, is left alone. Stop it with: npx supabase stop" -ForegroundColor DarkGray
    exit 0
}

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------
Write-Step "Checking tools"
$node = Test-Tool "node"
$npm  = Test-Tool "npm"
if (-not $node -or -not $npm) { Write-Err2 "node and npm are required - https://nodejs.org"; exit 1 }
Write-Ok "node $(& node --version)"

$poetry = Test-Tool "poetry"
$docker = Test-Tool "docker"

# Prefer 3.11 to match CI. Each candidate is {exe, args-before-the-real-args}.
$pyExe = $null; $pyPre = @()
foreach ($cand in @(@("py", @("-3.11")), @("py", @("-3.12")), @("py", @("-3.13")),
                    @("python", @()), @("python3", @()))) {
    $exe = $cand[0]; $pre = $cand[1]
    if (-not (Test-Tool $exe)) { continue }
    try {
        $v = & $exe @pre --version 2>$null
        if ($LASTEXITCODE -eq 0 -and $v) {
            $pyExe = $exe; $pyPre = $pre
            Write-Ok "python: $v"
            break
        }
    } catch { }
}
$python = $pyExe
if (-not $python -and -not $poetry) { Write-Err2 "No usable Python found - install 3.11 to match CI"; exit 1 }
if ($poetry) { Write-Ok "poetry found - using it for the backend" }
else { Write-Warn2 "poetry not found - falling back to a plain venv (CI uses Poetry 2.3.3)" }

# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------
if (-not $NoDatabase) {
    Write-Step "Supabase"
    if (-not $docker) {
        Write-Warn2 "Docker not found, so 'supabase start' cannot run."
        Write-Warn2 "Continuing WITHOUT a database: no auth, no data - pages will show"
        Write-Warn2 "their empty states. Install Docker Desktop for the full stack."
        $NoDatabase = $true
    } else {
        Push-Location $RepoRoot
        try {
            & npx --yes supabase start
            if ($LASTEXITCODE -ne 0) {
                Write-Warn2 "supabase start failed - continuing without a database"
                $NoDatabase = $true
            } else { Write-Ok "Supabase up (API :54321, Studio :54323)" }
        } finally { Pop-Location }
    }
}

# ---------------------------------------------------------------------------
# Backend environment
# ---------------------------------------------------------------------------
Write-Step "Backend environment"
$envFile = Join-Path $BackendDir ".env"
$envMap = Import-DotEnv $envFile
if (-not (Test-Path $envFile)) { Write-Warn2 "backend/.env not found (see backend/.env.example)" }

# config.py refuses to start unless these three are set.
$required = @("SUPABASE_URL", "SUPABASE_ANON_KEY", "DEEPSEEK_API_KEY")
$missing = @($required | Where-Object { -not $envMap.ContainsKey($_) -or $envMap[$_] -eq "" })

if ($missing.Count -gt 0) {
    if ($NoDatabase) {
        # Placeholders only. They let the app boot; every DB call still fails,
        # which is what "no database" means. Never use these against real data.
        foreach ($k in $missing) {
            switch ($k) {
                "SUPABASE_URL"      { $envMap[$k] = "http://127.0.0.1:54321" }
                "SUPABASE_ANON_KEY" { $envMap[$k] = "placeholder-anon-key" }
                default             { $envMap[$k] = "placeholder" }
            }
        }
        Write-Warn2 "Missing in backend/.env: $($missing -join ', ')"
        Write-Warn2 "Using placeholders because we are running without a database."
    } else {
        Write-Err2 "Missing in backend/.env: $($missing -join ', ')"
        Write-Err2 "Copy backend/.env.example to backend/.env and fill these in"
        Write-Err2 "(npx supabase status prints the local URL and anon key),"
        Write-Err2 "or re-run with -NoDatabase to start without one."
        exit 1
    }
}
foreach ($k in $envMap.Keys) { Set-Item -Path "env:$k" -Value $envMap[$k] }

# ---------------------------------------------------------------------------
# Backend dependencies
# ---------------------------------------------------------------------------
Write-Step "Backend dependencies"
$venvPy = Join-Path $BackendDir ".venv\Scripts\python.exe"
$usePoetry = [bool] $poetry

if ($usePoetry) {
    Push-Location $BackendDir
    try {
        & poetry install --no-root --no-interaction
        if ($LASTEXITCODE -ne 0) { Write-Err2 "poetry install failed"; exit 1 }
        Write-Ok "poetry install complete"
    } finally { Pop-Location }
} else {
    # A venv whose base interpreter was deleted still has python.exe but cannot
    # run. Probe it and rebuild rather than failing later with a confusing error.
    $venvOk = $false
    if ((Test-Path $venvPy) -and -not $Reinstall) {
        try {
            & $venvPy --version *> $null
            if ($LASTEXITCODE -eq 0) { $venvOk = $true }
        } catch { }
        if (-not $venvOk) { Write-Warn2 "backend/.venv is broken (dead interpreter) - rebuilding" }
    }
    if (-not $venvOk) {
        $venvDir = Join-Path $BackendDir ".venv"
        if (Test-Path $venvDir) { Remove-Item -Recurse -Force $venvDir }
        & $pyExe @pyPre -m venv $venvDir
        if ($LASTEXITCODE -ne 0) { Write-Err2 "could not create backend/.venv"; exit 1 }
        Write-Ok "created backend/.venv"
    }
    & $venvPy -m pip install --quiet --upgrade pip
    & $venvPy -m pip install --quiet @PipPackages
    if ($LASTEXITCODE -ne 0) { Write-Err2 "pip install failed"; exit 1 }
    Write-Ok "backend packages installed (including tzdata)"
}

# ---------------------------------------------------------------------------
# Start the backend
# ---------------------------------------------------------------------------
Write-Step "Starting backend on :$BackendPort"
Stop-Port -Port $BackendPort -Label "backend"
$uvArgs = @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$BackendPort", "--reload")
if ($usePoetry) {
    $beProc = Start-Process -FilePath "poetry" `
        -ArgumentList (@("run", "python") + $uvArgs) `
        -WorkingDirectory $BackendDir -PassThru -NoNewWindow
} else {
    $beProc = Start-Process -FilePath $venvPy -ArgumentList $uvArgs `
        -WorkingDirectory $BackendDir -PassThru -NoNewWindow
}
$script:Started += $beProc

$code = Wait-ForUrl -Url "http://127.0.0.1:$BackendPort/health" -TimeoutSec 90 -Label "backend"
if ($code -eq 0) {
    Write-Err2 "backend did not answer on :$BackendPort"
    foreach ($p in $script:Started) { if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } }
    exit 1
}
if ($code -eq 200) { Write-Ok "backend healthy (200)" }
else { Write-Warn2 "backend up but /health returned $code - expected when there is no database" }

if ($Seed) {
    Write-Step "Seeding eqip_practices"
    if ($NoDatabase) {
        Write-Warn2 "skipped - there is no database to seed"
    } else {
        Push-Location $BackendDir
        try {
            if ($usePoetry) { & poetry run python scripts/seed_eqip.py }
            else { & $venvPy scripts/seed_eqip.py }
            if ($LASTEXITCODE -eq 0) { Write-Ok "seeded" } else { Write-Warn2 "seeding failed" }
        } finally { Pop-Location }
    }
}

# ---------------------------------------------------------------------------
# Start the frontend
# ---------------------------------------------------------------------------
Write-Step "Starting frontend on :$FrontendPort"
if (-not (Test-Path (Join-Path $FrontendDir "node_modules")) -or $Reinstall) {
    Write-Ok "installing npm dependencies (first run)"
    Push-Location $FrontendDir
    try {
        & npm install
        if ($LASTEXITCODE -ne 0) { Write-Err2 "npm install failed"; exit 1 }
    } finally { Pop-Location }
}
Stop-Port -Port $FrontendPort -Label "frontend"
$feProc = Start-Process -FilePath "npm.cmd" -ArgumentList @("run", "dev") `
    -WorkingDirectory $FrontendDir -PassThru -NoNewWindow
$script:Started += $feProc

$feCode = Wait-ForUrl -Url "http://localhost:$FrontendPort/login" -TimeoutSec 120 -Label "frontend"
if ($feCode -eq 0) { Write-Warn2 "frontend has not answered yet - it may still be compiling" }
else { Write-Ok "frontend responding ($feCode)" }

# ---------------------------------------------------------------------------
# Ready
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "  RegenAI is running" -ForegroundColor Green
Write-Host "    Frontend   http://localhost:$FrontendPort"
Write-Host "    API docs   http://127.0.0.1:$BackendPort/docs"
Write-Host "    Health     http://127.0.0.1:$BackendPort/health"
if (-not $NoDatabase) { Write-Host "    Supabase   http://127.0.0.1:54323  (Studio)" }
else {
    Write-Host ""
    Write-Host "  No database: API calls return 401/403 and pages show empty states." -ForegroundColor Yellow
}
Write-Host ""
Write-Host "  Ctrl+C to stop, or run: .\scripts\dev.ps1 -Stop" -ForegroundColor DarkGray
Write-Host ""

# Liveness is judged by the URLs, not by the pids we launched. npm.cmd is a
# wrapper that exits while node keeps serving, and uvicorn --reload hands off to
# a worker, so HasExited on the launched pid reports a death that never happened.
$backendHealth  = "http://127.0.0.1:$BackendPort/health"
$frontendHealth = "http://localhost:$FrontendPort/login"
$missBackend = 0
$missFrontend = 0

try {
    while ($true) {
        Start-Sleep -Seconds 3
        if (Test-UrlAlive $backendHealth)  { $missBackend  = 0 } else { $missBackend++ }
        if (Test-UrlAlive $frontendHealth) { $missFrontend = 0 } else { $missFrontend++ }

        # Three consecutive misses (~9s) - a restart or slow compile is not a death.
        if ($missBackend -ge 3) { Write-Warn2 "backend stopped responding - shutting down"; break }
        if ($missFrontend -ge 3) { Write-Warn2 "frontend stopped responding - shutting down"; break }
    }
} finally {
    Write-Step "Stopping"
    foreach ($p in $script:Started) { Stop-Tree -ProcessId $p.Id }
    Stop-Port -Port $BackendPort  -Label "backend"
    Stop-Port -Port $FrontendPort -Label "frontend"

    # Report the truth: a port still listening means something survived.
    $leftovers = @()
    foreach ($pair in @(@($BackendPort, "backend"), @($FrontendPort, "frontend"))) {
        if (Get-NetTCPConnection -LocalPort $pair[0] -State Listen -ErrorAction SilentlyContinue) {
            $leftovers += "$($pair[1]) (port $($pair[0]))"
        }
    }
    if ($leftovers.Count -gt 0) {
        Write-Err2 "still listening: $($leftovers -join ', ') - re-run with -Stop"
    } else {
        Write-Ok "all stopped"
    }
}
