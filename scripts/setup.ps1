<#
.SYNOPSIS
    One command: set up the database, verify the code, and run RegenAI.

.DESCRIPTION
    Takes a fresh clone (or a half-finished setup) to a running app:

      1. Preflight    - node, npm, python; reports what is missing and why.
      2. Environment  - checks backend/.env and frontend/.env.local for the
                        keys config.py and the frontend actually require.
      3. Database     - applies supabase/migrations to a hosted project with
                        the Supabase CLI, or to a local stack when Docker is
                        available. Then seeds eqip_practices, and optionally a
                        demo farm.
      4. Checks       - runs exactly what CI runs (ruff, pytest, tsc, lint,
                        build), so a green run here means a green run there.
      5. Run          - hands off to dev.ps1, which owns starting the servers.

    Every step reports what actually happened. A step that cannot run says so
    and the script keeps going where that is safe, rather than pretending.

.PARAMETER ProjectRef
    Supabase project ref (the subdomain of https://<ref>.supabase.co). Links
    the repo and pushes migrations to that hosted project.

.PARAMETER DbPassword
    Database password for the hosted project. Prompted for if omitted. Can
    also come from the SUPABASE_DB_PASSWORD environment variable.

.PARAMETER SeedDemo
    Email address to attach the demo farm to (creates the account if needed).
    Requires SUPABASE_SERVICE_ROLE_KEY in backend/.env.

.PARAMETER SkipDb
    Leave the database alone. Use when migrations are already applied.

.PARAMETER SkipChecks
    Skip ruff/pytest/tsc/lint/build. Faster, but you lose the CI signal.

.PARAMETER NoRun
    Do the setup and checks, then stop without starting the servers.

.EXAMPLE
    .\scripts\setup.ps1 -ProjectRef abcdefghijklmnop -SeedDemo you@example.com
    First run against a hosted project: migrations, seeds, checks, then serve.

.EXAMPLE
    .\scripts\setup.ps1 -SkipDb
    Day-to-day: verify the code and run the stack.

.EXAMPLE
    .\scripts\setup.ps1 -NoRun
    What CI will say, without starting anything.
#>
[CmdletBinding()]
param(
    [string] $ProjectRef,
    [string] $DbPassword,
    [string] $SeedDemo,
    [switch] $SkipDb,
    [switch] $SkipChecks,
    [switch] $NoRun
)

$ErrorActionPreference = "Stop"
$RepoRoot    = Split-Path -Parent $PSScriptRoot
$BackendDir  = Join-Path $RepoRoot "backend"
$FrontendDir = Join-Path $RepoRoot "frontend"

# Collected as we go and printed at the end, so a warning in step 2 is still
# visible after step 5 has scrolled past.
$script:Notes    = @()
$script:Failures = @()

function Write-Step { param($m) Write-Host "`n==> $m" -ForegroundColor Cyan }
function Write-Ok   { param($m) Write-Host "    $m" -ForegroundColor Green }
function Write-Warn2 { param($m) Write-Host "    $m" -ForegroundColor Yellow; $script:Notes += $m }
function Write-Err2 { param($m) Write-Host "    $m" -ForegroundColor Red; $script:Failures += $m }

function Invoke-Native {
    <#
        Run an external command and return its exit code.

        Native tools (npm, npx, python) write warnings and progress to stderr.
        With $ErrorActionPreference = "Stop" PowerShell turns any of that into a
        terminating NativeCommandError, which would abort this script over a
        harmless warning. Exit codes are what actually tell us pass or fail, so
        relax the preference for the call and judge on $LASTEXITCODE.
    #>
    param([Parameter(Mandatory)] [string] $Exe, [string[]] $Arguments = @())
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        # Out-Host, not the pipeline: anything the tool prints would otherwise
        # be returned alongside the exit code, and the caller would compare an
        # array against 0 and read every success as a failure.
        & $Exe @Arguments 2>&1 | Out-Host
        return $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
}

function Test-Tool {
    param([string] $Name)
    $c = Get-Command $Name -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    return $null
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

function Get-BackendPython {
    <#
        The interpreter that runs backend code: Poetry's if it is installed,
        otherwise backend/.venv, which dev.ps1 creates. Returns $null when
        neither exists yet.
    #>
    if (Test-Tool "poetry") { return @{ Exe = "poetry"; Pre = @("run", "python") } }
    $venvPy = Join-Path $BackendDir ".venv\Scripts\python.exe"
    if (Test-Path $venvPy) { return @{ Exe = $venvPy; Pre = @() } }
    return $null
}

# ---------------------------------------------------------------------------
# 1. Preflight
# ---------------------------------------------------------------------------
Write-Step "Checking tools"
foreach ($tool in @("node", "npm")) {
    $found = Test-Tool $tool
    if ($found) { Write-Ok "$tool $(& $tool --version)" }
    else { Write-Err2 "$tool is required - https://nodejs.org" }
}
if ($script:Failures.Count -gt 0) { exit 1 }

$python = Get-BackendPython
if ($python) {
    Write-Ok "backend interpreter ready"
} else {
    # dev.ps1 owns dependency installation; -PrepareOnly runs just that part so
    # the logic lives in one place.
    Write-Ok "no backend interpreter yet - building one via dev.ps1 -PrepareOnly"
    & (Join-Path $PSScriptRoot "dev.ps1") -PrepareOnly -NoDatabase
    $python = Get-BackendPython
    if ($python) { Write-Ok "backend interpreter ready" }
    else { Write-Warn2 "could not build a backend interpreter - backend checks will be skipped" }
}

# ---------------------------------------------------------------------------
# 2. Environment
# ---------------------------------------------------------------------------
Write-Step "Environment files"
$backendEnvPath  = Join-Path $BackendDir ".env"
$frontendEnvPath = Join-Path $FrontendDir ".env.local"
$backendEnv  = Import-DotEnv $backendEnvPath
$frontendEnv = Import-DotEnv $frontendEnvPath

# config.py refuses to start without these three.
$requiredBackend = @("SUPABASE_URL", "SUPABASE_ANON_KEY", "DEEPSEEK_API_KEY")
$missingBackend = @($requiredBackend | Where-Object {
    -not $backendEnv.ContainsKey($_) -or $backendEnv[$_] -eq ""
})
if ($missingBackend.Count -gt 0) {
    Write-Warn2 "backend/.env is missing: $($missingBackend -join ', ') (see backend/.env.example)"
} else {
    Write-Ok "backend/.env has the required keys"
}

$requiredFrontend = @("NEXT_PUBLIC_SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_ANON_KEY", "NEXT_PUBLIC_API_URL")
$missingFrontend = @($requiredFrontend | Where-Object {
    -not $frontendEnv.ContainsKey($_) -or $frontendEnv[$_] -eq ""
})
if ($missingFrontend.Count -gt 0) {
    Write-Warn2 "frontend/.env.local is missing: $($missingFrontend -join ', ')"
} else {
    Write-Ok "frontend/.env.local has the required keys"
}

# A local URL in one file and a hosted one in the other points the browser and
# the API at different databases, which looks like missing data, not a config
# error. Worth catching here.
if ($backendEnv["SUPABASE_URL"] -and $frontendEnv["NEXT_PUBLIC_SUPABASE_URL"] -and
    $backendEnv["SUPABASE_URL"] -ne $frontendEnv["NEXT_PUBLIC_SUPABASE_URL"]) {
    Write-Warn2 "backend and frontend point at different Supabase URLs"
}

if ($frontendEnv["DEV_AUTH_BYPASS"] -eq "true") {
    Write-Warn2 "DEV_AUTH_BYPASS=true - local only; the app refuses to serve with it in production"
}

# ---------------------------------------------------------------------------
# 3. Database
# ---------------------------------------------------------------------------
if ($SkipDb) {
    Write-Step "Database (skipped)"
} else {
    Write-Step "Database"
    $supabaseUrl = $backendEnv["SUPABASE_URL"]
    $isHosted = $supabaseUrl -and $supabaseUrl -notmatch "127\.0\.0\.1|localhost"

    if ($ProjectRef -or $isHosted) {
        # Hosted: link once, then push migrations. No Docker needed.
        if (-not $ProjectRef -and $supabaseUrl -match "https://([^.]+)\.supabase\.co") {
            $ProjectRef = $Matches[1]
            Write-Ok "project ref from backend/.env: $ProjectRef"
        }
        if (-not $ProjectRef) {
            Write-Err2 "Need -ProjectRef (the subdomain of your Supabase URL) to push migrations"
        } else {
            if (-not $DbPassword) { $DbPassword = $env:SUPABASE_DB_PASSWORD }
            if (-not $DbPassword) {
                $secure = Read-Host "Supabase database password for $ProjectRef" -AsSecureString
                $DbPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
                    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
            }
            Push-Location $RepoRoot
            try {
                # The CLI reads the password from this variable, so it never
                # appears in the command line or in shell history.
                $env:SUPABASE_DB_PASSWORD = $DbPassword
                $code = Invoke-Native "npx" @("--yes", "supabase@latest", "link", "--project-ref", $ProjectRef)
                if ($code -ne 0) {
                    Write-Err2 "supabase link failed"
                } else {
                    $code = Invoke-Native "npx" @("--yes", "supabase@latest", "db", "push")
                    if ($code -ne 0) { Write-Err2 "supabase db push failed - migrations NOT applied" }
                    else { Write-Ok "migrations applied to $ProjectRef" }
                }
            } finally {
                Remove-Item Env:SUPABASE_DB_PASSWORD -ErrorAction SilentlyContinue
                Pop-Location
            }
        }
    } elseif (Test-Tool "docker") {
        Push-Location $RepoRoot
        try {
            $code = Invoke-Native "npx" @("--yes", "supabase@latest", "start")
            if ($code -ne 0) { Write-Err2 "supabase start failed" }
            else { Write-Ok "local Supabase up - migrations applied automatically" }
        } finally { Pop-Location }
    } else {
        Write-Warn2 "No hosted project configured and Docker is not installed, so there is no database."
        Write-Warn2 "Pages will show empty states. Pass -ProjectRef <ref> for a hosted project."
    }

    # Seeds. eqip_practices must be populated or the AI hallucination guard
    # rejects every recommendation it is given.
    if ($script:Failures.Count -eq 0) {
        $python = Get-BackendPython
        if (-not $python) {
            Write-Warn2 "skipping seeds - no backend interpreter yet; re-run after dev.ps1 builds it"
        } else {
            Push-Location $BackendDir
            try {
                foreach ($k in $backendEnv.Keys) { Set-Item -Path "env:$k" -Value $backendEnv[$k] }
                $code = Invoke-Native $python.Exe (@($python.Pre) + @("scripts/seed_eqip.py"))
                if ($code -eq 0) { Write-Ok "eqip_practices seeded" }
                else { Write-Warn2 "seeding eqip_practices failed" }

                if ($SeedDemo) {
                    if (-not $backendEnv["SUPABASE_SERVICE_ROLE_KEY"]) {
                        Write-Warn2 "demo farm needs SUPABASE_SERVICE_ROLE_KEY in backend/.env"
                    } else {
                        $code = Invoke-Native $python.Exe (@($python.Pre) + @("scripts/seed_demo_farm.py", "--email", $SeedDemo))
                        if ($code -eq 0) { Write-Ok "demo farm seeded for $SeedDemo" }
                        else { Write-Warn2 "seeding the demo farm failed" }
                    }
                }
            } finally { Pop-Location }
        }
    }
}

# ---------------------------------------------------------------------------
# 4. Checks - the same commands CI runs
# ---------------------------------------------------------------------------
if ($SkipChecks) {
    Write-Step "Checks (skipped)"
} else {
    Write-Step "Checks (same as CI)"
    $python = Get-BackendPython
    if (-not $python) {
        Write-Warn2 "skipping backend checks - no interpreter yet"
    } else {
        # dev.ps1 installs only what the app needs to serve. The checks need the
        # dev tools too, and they are declared in pyproject's dev group, which a
        # plain venv does not read.
        if ($python.Exe -ne "poetry") {
            $code = Invoke-Native $python.Exe @("-m", "pip", "install", "--quiet", "pytest", "pytest-asyncio", "ruff")
            if ($code -ne 0) { Write-Warn2 "could not install pytest/ruff into backend/.venv" }
        }
        Push-Location $BackendDir
        try {
            # Dummy values satisfy config.py's startup validator without
            # touching a real project, exactly as ci.yml does.
            $env:SUPABASE_URL = "http://localhost"
            $env:SUPABASE_ANON_KEY = "x"
            $env:DEEPSEEK_API_KEY = "x"
            $code = Invoke-Native $python.Exe (@($python.Pre) + @("-m", "ruff", "check", "app/"))
            if ($code -eq 0) { Write-Ok "ruff clean" } else { Write-Err2 "ruff found problems" }

            $code = Invoke-Native $python.Exe (@($python.Pre) + @("-m", "pytest", "-q"))
            if ($code -eq 0) { Write-Ok "pytest passed" } else { Write-Err2 "pytest failed" }
        } finally { Pop-Location }
    }

    Push-Location $FrontendDir
    try {
        if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
            Write-Ok "installing npm dependencies"
            $null = Invoke-Native "npm" @("install")
        }
        $code = Invoke-Native "npx" @("tsc", "--noEmit")
        if ($code -eq 0) { Write-Ok "tsc clean" } else { Write-Err2 "tsc found type errors" }

        $code = Invoke-Native "npm" @("run", "lint")
        if ($code -eq 0) { Write-Ok "eslint clean" } else { Write-Err2 "eslint found problems" }

        # next build reads .env.local, so it uses the same values as `npm run dev`.
        $code = Invoke-Native "npm" @("run", "build")
        if ($code -eq 0) { Write-Ok "build succeeded" } else { Write-Err2 "build failed" }
    } finally { Pop-Location }
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
Write-Step "Summary"
if ($script:Notes.Count -gt 0) {
    Write-Host "  Warnings:" -ForegroundColor Yellow
    foreach ($n in $script:Notes) { Write-Host "    - $n" -ForegroundColor Yellow }
}
if ($script:Failures.Count -gt 0) {
    Write-Host "  Failures:" -ForegroundColor Red
    foreach ($f in $script:Failures) { Write-Host "    - $f" -ForegroundColor Red }
    Write-Host ""
    Write-Host "  Not starting the app while checks are failing." -ForegroundColor Red
    exit 1
}
Write-Ok "everything passed"

# ---------------------------------------------------------------------------
# 5. Run - dev.ps1 owns starting and stopping the servers
# ---------------------------------------------------------------------------
if ($NoRun) {
    Write-Host ""
    Write-Host "  Setup complete. Start the app with: .\scripts\dev.ps1" -ForegroundColor DarkGray
    exit 0
}
Write-Step "Starting the app"
& (Join-Path $PSScriptRoot "dev.ps1") -NoDatabase:$SkipDb
exit $LASTEXITCODE
