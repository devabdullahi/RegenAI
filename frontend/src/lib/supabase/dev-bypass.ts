// DEV ONLY: auth bypass flag.
// Uses the server-only DEV_AUTH_BYPASS env var (never NEXT_PUBLIC_*), so the
// flag is not inlined into client bundles. Only call this from server code
// (server components, route handlers, proxy).

/**
 * `next build` runs with NODE_ENV=production even on a developer's machine, and
 * it evaluates module top-level code while collecting page data. Throwing then
 * would make a local build fail purely because .env.local enables the bypass,
 * so the guard is skipped during the build and enforced when the server runs.
 */
function isProductionBuildPhase(): boolean {
  return process.env.NEXT_PHASE === "phase-production-build";
}

export function isDevAuthBypassEnabled(): boolean {
  const enabled = process.env.DEV_AUTH_BYPASS === "true";

  if (!enabled) return false;

  // Production guard: never serve requests with auth bypassed.
  if (process.env.NODE_ENV === "production") {
    if (isProductionBuildPhase()) {
      console.warn(
        "DEV_AUTH_BYPASS is set. It is ignored in production builds and will " +
          "fail at runtime — remove it before deploying."
      );
      return false;
    }
    throw new Error(
      "DEV_AUTH_BYPASS cannot be enabled in production. Remove it from your environment."
    );
  }

  return true;
}
