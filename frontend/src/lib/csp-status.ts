/**
 * CSP eligibility status display config and shared NRCS copy/links.
 *
 * Backend semantics (backend/app/services/csp_eligibility.py):
 *   act_now        eligible AND meets the state ranking threshold. ACT NOW is
 *                  at state discretion, so the copy says "may qualify".
 *   eligible       at least min_concerns_required (from the API) resource
 *                  concerns meet the stewardship threshold
 *   pending_review at least one, but fewer than the required number
 *   not_eligible   fewer than that
 *
 * The status is printed as a word — a stamp or a left edge bar, never a pill
 * and never colour on its own.
 */

import type { CSPEligibilityStatus } from "@/lib/api/types";
import { toneTextClasses, type Tone } from "@/lib/status-styles";

export interface CspStatusConfig {
  /** Full label for detail sheets, e.g. "Eligible · May qualify for ACT NOW". */
  label: string;
  /** Compact label for widgets/stamps. */
  shortLabel: string;
  tone: Tone;
  /** Text-only classes for the status word. */
  textClasses: string;
}

function status(
  label: string,
  shortLabel: string,
  tone: Tone
): CspStatusConfig {
  return { label, shortLabel, tone, textClasses: toneTextClasses[tone] };
}

export const CSP_STATUS_CONFIG: Record<CSPEligibilityStatus, CspStatusConfig> = {
  act_now: status(
    "Eligible · May qualify for ACT NOW",
    "Eligible · ACT NOW possible",
    "success"
  ),
  eligible: status("Eligible", "Eligible", "success"),
  pending_review: status("Almost Eligible", "Almost Eligible", "warning"),
  not_eligible: status("Not Yet Eligible", "Not Yet Eligible", "destructive"),
};

/** Shown when the farm has never been evaluated. */
export const CSP_STATUS_NOT_EVALUATED: CspStatusConfig = status(
  "Not Evaluated",
  "Not Evaluated",
  "neutral"
);

/** Config for a status; null/undefined/unknown -> "Not Evaluated". */
export function getCspStatusConfig(
  value: CSPEligibilityStatus | string | null | undefined
): CspStatusConfig {
  return (
    CSP_STATUS_CONFIG[value as CSPEligibilityStatus] ?? CSP_STATUS_NOT_EVALUATED
  );
}

/**
 * Print an NRCS conservation practice standard code the way it appears on a
 * plan sheet ("CPS 340"). The backend sends the bare number; nothing is added
 * when it already carries the prefix.
 */
export function practiceStandardStamp(code: string): string {
  const trimmed = code.trim();
  return /^cps\b/i.test(trimmed) ? trimmed : `CPS ${trimmed}`;
}

// ── Shared NRCS copy and links ───────────────────────────────────────────────

/** USDA Service Center Locator (find the local NRCS office). */
export const NRCS_SERVICE_CENTER_LOCATOR_URL =
  "https://www.farmers.gov/contact/service-center-locator";

/** General disclaimer for pages showing RegenAI CSP scores and estimates. */
export const NRCS_DISCLAIMER =
  "CSP eligibility scores and payment estimates on this page are calculated by RegenAI based on publicly available NRCS payment schedules and your farm data. They are not official NRCS determinations. Contact your local NRCS service center to submit an application and receive official program determinations. This tool does not replace professional agronomic or legal advice.";

/** Disclaimer for CSP payment estimates; the default in adapters.ts adaptPayment(). */
export const CSP_PAYMENT_DISCLAIMER =
  "This is an estimate based on NRCS payment schedules and may differ from the final payment determined by your local NRCS office. Contact your NRCS service center to get an official payment estimate before applying.";
