import Link from "next/link";
import { Check } from "lucide-react";
import { ButtonLink } from "@/components/shared/button-link";
import { EdgeNote, LedgerRow, RuleHead } from "@/components/shared/record";

import { CSPDeadlineBanners } from "@/components/csp/csp-deadline-banner";
import { api } from "@/lib/api/server-client";

import { adaptDeadlines, adaptEligibility } from "@/lib/api/adapters";
import { NRCS_DISCLAIMER, NRCS_SERVICE_CENTER_LOCATOR_URL } from "@/lib/csp-status";
import { cn } from "@/lib/utils";

import type { Metadata } from "next";
import type { CSPChecklistItem, CSPEligibility } from "@/lib/api/types";

export const metadata: Metadata = {
  title: "CSP Application Checklist — RegenAI",
};

interface ChecklistPageProps {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

// ── Derive checklist from live eligibility data ───────────────────────────────

function buildChecklist(
  eligibility: CSPEligibility,
  farmHasFields: boolean
): CSPChecklistItem[] {
  const hasEnhancements = eligibility.active_enhancement_codes.length > 0;
  const hasCommitment = eligibility.rc_count_will_meet > 0;
  const rcMet = eligibility.meets_min_concerns;
  const minRequired = eligibility.min_concerns_required;
  const rcCount = eligibility.rc_count_above_threshold;
  const additionalRequired = eligibility.additional_concerns_required;
  const additionalAreas =
    additionalRequired !== undefined
      ? `at least ${additionalRequired} more conservation area${additionalRequired === 1 ? "" : "s"}`
      : "additional conservation areas";

  const checklist: CSPChecklistItem[] = [
    {
      item_id: "has_fields",
      label: "Farm has registered fields",
      completed: farmHasFields,
      detail: farmHasFields
        ? "Fields are registered in your farm profile"
        : "Add at least one field to your farm profile",
      action: farmHasFields ? undefined : "Add fields in your farm settings",
    },
    {
      item_id: "rc_threshold_min",
      label:
        minRequired !== undefined
          ? `Meets conservation threshold on ${minRequired} or more areas`
          : "Meets conservation threshold on the required number of areas",
      completed: rcMet,
      detail: rcMet
        ? `${rcCount} of ${eligibility.resource_concerns_met.length} resource concerns currently above the stewardship threshold`
        : minRequired !== undefined
          ? `${rcCount} of ${minRequired} required areas met — additional practices needed`
          : `${rcCount} areas met so far — additional practices needed`,
      action: rcMet ? undefined : "Review your resource concerns in the Eligibility tab",
    },
    {
      item_id: "commitment_selected",
      label: `Committed to improving ${additionalAreas}`,
      completed: hasCommitment,
      detail: hasCommitment
        ? "Enhancement activities selected and committed"
        : `Select enhancement activities to commit to improving ${additionalAreas}`,
      action: hasCommitment ? undefined : "Choose an enhancement to add to your committed list",
    },
    {
      item_id: "enhancements_selected",
      label: "Enhancement activities selected",
      completed: hasEnhancements,
      detail: hasEnhancements
        ? `${eligibility.active_enhancement_codes.length} enhancement${eligibility.active_enhancement_codes.length !== 1 ? "s" : ""} selected: ${eligibility.active_enhancement_codes.join(", ")}`
        : "No enhancement activities chosen yet",
      action: hasEnhancements ? undefined : "Browse available enhancements",
    },
    {
      item_id: "contact_nrcs",
      label: "Contact your local NRCS office to submit your application",
      completed: false,
      detail:
        "Final step: your local NRCS conservation planner will schedule a site visit and finalize your contract",
      action: "Find your local NRCS office",
    },
  ];

  return checklist;
}

// ── Conservation-area count ───────────────────────────────────────────────────

// A plain count from the API (areas meeting the threshold out of all areas
// scored), not a weighted readiness percentage.
function ConcernProgress({ eligibility }: { eligibility: CSPEligibility }) {
  const metCount = eligibility.rc_count_above_threshold;
  const totalCount = eligibility.resource_concerns_met.length;
  const minRequired = eligibility.min_concerns_required;
  const meetsMin = eligibility.meets_min_concerns;

  let summary: string;
  if (meetsMin) {
    summary =
      minRequired !== undefined
        ? `You meet the minimum of ${minRequired} areas for CSP eligibility.`
        : "You meet the minimum number of areas for CSP eligibility.";
  } else {
    summary =
      minRequired !== undefined
        ? `You need at least ${minRequired} to be eligible.`
        : "You need the required number of conservation areas to be eligible.";
  }

  return (
    <div className="space-y-1">
      <LedgerRow
        label="Conservation areas meeting the threshold"
        value={
          <span className="text-lg font-medium text-foreground">
            {totalCount > 0 ? `${metCount} of ${totalCount}` : metCount}
          </span>
        }
      />
      <p className="border-t border-rule pt-2 text-sm text-foreground">
        {summary}
      </p>
    </div>
  );
}

// ── A box on a form ───────────────────────────────────────────────────────────

function CheckBox({ checked }: { checked: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center border",
        checked ? "border-foreground text-foreground" : "border-border"
      )}
    >
      {checked && <Check className="h-3 w-3" />}
    </span>
  );
}

// ── Single checklist row ──────────────────────────────────────────────────────

function ChecklistRow({ item, farmId }: { item: CSPChecklistItem; farmId: string }) {
  const isNrcsLink = item.item_id === "contact_nrcs";

  const isEnhancementsAction =
    item.item_id === "enhancements_selected" ||
    item.item_id === "commitment_selected";

  return (
    <li className="flex items-start gap-3 border-b border-rule py-3 last:border-0">
      <CheckBox checked={item.completed} />
      <div className="min-w-0 flex-1">
        <p className="text-sm leading-snug font-medium text-foreground">
          {item.label}
        </p>
        <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
          {item.detail}
        </p>
        {!item.completed &&
          item.action &&
          (isNrcsLink ? (
            <a
              href={NRCS_SERVICE_CENTER_LOCATOR_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex min-h-12 items-center text-sm font-medium text-primary underline-offset-4 hover:underline"
            >
              Find my local NRCS office
              <span className="sr-only"> (opens in new tab)</span>
            </a>
          ) : isEnhancementsAction ? (
            <Link
              href={`/csp/enhancements?farm_id=${encodeURIComponent(farmId)}`}
              className="inline-flex min-h-12 items-center text-sm font-medium text-primary underline-offset-4 hover:underline"
            >
              Browse enhancements
            </Link>
          ) : (
            <p className="mt-1 text-xs font-medium text-warning-foreground">
              {item.action}
            </p>
          ))}
      </div>
      <span
        className={cn(
          "shrink-0 font-mono text-[0.6875rem] tracking-[0.08em] uppercase",
          item.completed ? "text-success" : "text-muted-foreground"
        )}
      >
        {item.completed ? "Done" : "To do"}
      </span>
    </li>
  );
}

// ── Grouped checklist ─────────────────────────────────────────────────────────

function ChecklistGroup({
  label,
  items,
  farmId,
}: {
  label: string;
  items: CSPChecklistItem[];
  farmId: string;
}) {
  const completedCount = items.filter((i) => i.completed).length;

  return (
    <div className="space-y-2">
      <RuleHead
        label={label}
        action={
          <span className="font-mono text-[0.6875rem] text-foreground">
            {completedCount}/{items.length}
          </span>
        }
      />
      <ul className="mt-1" aria-label={label}>
        {items.map((item) => (
          <ChecklistRow key={item.item_id} item={item} farmId={farmId} />
        ))}
      </ul>
    </div>
  );
}

// ── Error / no-farm states ────────────────────────────────────────────────────

function ErrorState({ message }: { message: string }) {
  return (
    <div className="max-w-[62ch] space-y-4 py-10">
      <RuleHead label="Application checklist" />
      <h2 className="font-heading text-xl font-semibold text-foreground">
        Unable to load checklist
      </h2>
      <p className="text-sm text-muted-foreground">{message}</p>
      <ButtonLink href="/farms" variant="outline">
        Back to farms
      </ButtonLink>
    </div>
  );
}

function NoFarmSelected() {
  return (
    <div className="max-w-[62ch] space-y-4 py-10">
      <RuleHead label="Application checklist" />
      <h2 className="font-heading text-xl font-semibold text-foreground">
        Select a farm first
      </h2>
      <p className="text-sm text-muted-foreground">
        Choose a farm to view your CSP application checklist.
      </p>
      <ButtonLink href="/farms">Go to My Farms</ButtonLink>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default async function CspChecklistPage({
  searchParams,
}: ChecklistPageProps) {
  const params = await searchParams;
  const farmId =
    typeof params.farm_id === "string" ? params.farm_id : undefined;

  if (!farmId) {
    return <NoFarmSelected />;
  }

  let eligibility: CSPEligibility;
  let farmName: string;
  let hasFields: boolean;

  try {
    const [eligibilityResp, farm, fields] = await Promise.all([
      api.csp.getEligibility(farmId),
      api.farms.get(farmId),
      api.fields.list(farmId),
    ]);
    const deadlinesResp = await api.csp
      .getDeadlines(farm.state)
      .catch(() => null);
    eligibility = adaptEligibility(eligibilityResp, {
      deadlines: adaptDeadlines(deadlinesResp),
    });
    farmName = farm.name;
    hasFields = fields.length > 0;
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "An unexpected error occurred.";
    return <ErrorState message={message} />;
  }

  const checklist = buildChecklist(eligibility, hasFields);

  const programItems = checklist.filter((i) =>
    ["has_fields", "rc_threshold_min", "commitment_selected", "enhancements_selected"].includes(i.item_id)
  );
  const nextStepItems = checklist.filter((i) =>
    ["contact_nrcs"].includes(i.item_id)
  );

  return (
    <div className="space-y-8 pb-20 sm:pb-0">
      {/* Breadcrumb + masthead */}
      <div className="space-y-2">
        <nav
          aria-label="Breadcrumb"
          className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground"
        >
          <Link href="/farms" className="hover:text-foreground">
            {farmName}
          </Link>
          <span aria-hidden="true">&rsaquo;</span>
          <Link
            href={`/csp?farm_id=${encodeURIComponent(farmId)}`}
            className="hover:text-foreground"
          >
            CSP Navigator
          </Link>
          <span aria-hidden="true">&rsaquo;</span>
          <span aria-current="page" className="font-medium text-foreground">
            Checklist
          </span>
        </nav>
        <div className="border-b-2 border-rule-strong pb-3">
          <h1 className="font-heading text-[1.75rem] leading-tight font-bold text-foreground sm:text-3xl">
            Application Checklist
          </h1>
          <p className="mt-2 font-mono text-[0.6875rem] tracking-[0.14em] text-muted-foreground uppercase">
            What to have ready before contacting NRCS
          </p>
        </div>
      </div>

      {/* Deadline alerts */}
      <CSPDeadlineBanners deadlines={eligibility.upcoming_deadlines} />

      {/* Where the farm stands */}
      <section aria-labelledby="standing-heading" className="space-y-2">
        <div className="rule-head">
          <h2 id="standing-heading">Where you stand</h2>
          <span aria-hidden="true" className="h-px flex-1 bg-rule" />
        </div>
        <ConcernProgress eligibility={eligibility} />
      </section>

      {/* Checklist groups */}
      <div className="space-y-8">
        {programItems.length > 0 && (
          <ChecklistGroup
            label="Program requirements"
            items={programItems}
            farmId={farmId}
          />
        )}
        {nextStepItems.length > 0 && (
          <ChecklistGroup
            label="Next steps"
            items={nextStepItems}
            farmId={farmId}
          />
        )}
      </div>

      {/* Missing requirements */}
      {eligibility.missing_requirements.length > 0 && (
        <EdgeNote
          tone="warning"
          title="Still needed to strengthen your application"
        >
          <ul className="mt-1 space-y-1">
            {eligibility.missing_requirements.map((req, i) => (
              <li key={i} className="text-sm text-foreground">
                {req}
              </li>
            ))}
          </ul>
        </EdgeNote>
      )}

      {/* Disclaimer */}
      <p className="max-w-[62ch] border-t border-rule pt-3 text-xs leading-relaxed text-muted-foreground">
        {NRCS_DISCLAIMER}
      </p>
    </div>
  );
}
