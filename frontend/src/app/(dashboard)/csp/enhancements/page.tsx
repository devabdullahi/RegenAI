import Link from "next/link";
import { redirect } from "next/navigation";
import { ButtonLink } from "@/components/shared/button-link";
import { LedgerRow, RuleHead } from "@/components/shared/record";

import { CSPEnhancementList } from "@/components/csp/csp-enhancement-list";
import { CSPDeadlineBanners } from "@/components/csp/csp-deadline-banner";
import { CSPRulesCitation } from "@/components/csp/csp-payment-summary";

import { api } from "@/lib/api/server-client";
import {
  adaptDeadlines,
  adaptEnhancement,
  ruleCitation,
  ruleNotes,
} from "@/lib/api/adapters";
import type {
  CSPDeadline,
  CSPEnhancement,
  CSPRuleCitation,
  CSPRuleNotes,
} from "@/lib/api/types";

import { formatUsd, pluralize } from "@/lib/format";

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "CSP Enhancements — RegenAI",
};

// ── Error state ───────────────────────────────────────────────────────────────

function EnhancementsError({ message }: { message: string }) {
  return (
    <div className="max-w-[62ch] space-y-4 pb-20 sm:pb-0">
      <div className="border-b-2 border-rule-strong pb-3">
        <h1 className="font-heading text-[1.75rem] leading-tight font-bold text-foreground">
          Conservation Activities
        </h1>
      </div>
      <RuleHead label="Could not load enhancements" />
      <p className="text-sm leading-relaxed text-muted-foreground">{message}</p>
      <ButtonLink href="/farms" variant="outline">
        Back to farms
      </ButtonLink>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

interface EnhancementsPageProps {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

export default async function CspEnhancementsPage({
  searchParams,
}: EnhancementsPageProps) {
  const params = await searchParams;
  const farmId =
    typeof params.farm_id === "string" ? params.farm_id : undefined;

  if (!farmId) {
    redirect("/farms");
  }

  let farmName: string;
  let enhancements: CSPEnhancement[];
  let recommendedCodes: Set<string>;
  let deadlines: CSPDeadline[];
  let rules: CSPRuleCitation | null;
  let notes: CSPRuleNotes | null;

  try {
    // Eligibility first: it persists the assessment that
    // GET /csp/enhancements uses to rank activities against current gaps.
    const [farm, eligibility] = await Promise.all([
      api.farms.get(farmId),
      api.csp.getEligibility(farmId),
    ]);
    const [enhancementsResp, deadlinesResp] = await Promise.all([
      api.csp.getEnhancements(farmId),
      api.csp.getDeadlines(farm.state).catch(() => null),
    ]);

    farmName = farm.name;
    enhancements = enhancementsResp.enhancements.map(adaptEnhancement);
    recommendedCodes = new Set(eligibility.recommended_enhancements);
    deadlines = adaptDeadlines(deadlinesResp);
    rules = enhancementsResp.rules ? ruleCitation(enhancementsResp.rules) : null;
    notes = enhancementsResp.rules ? ruleNotes(enhancementsResp.rules) : null;
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Failed to load enhancements data.";
    return <EnhancementsError message={message} />;
  }

  const gapClosingEnhancements = enhancements.filter((e) =>
    recommendedCodes.has(e.code)
  );
  const otherEnhancements = enhancements.filter(
    (e) => !recommendedCodes.has(e.code)
  );

  const gapClosingPayment = gapClosingEnhancements.reduce(
    (sum, e) => sum + (e.estimated_payment ?? 0),
    0
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
            Enhancements
          </span>
        </nav>
        <div className="border-b-2 border-rule-strong pb-3">
          <h1 className="font-heading text-[1.75rem] leading-tight font-bold text-foreground sm:text-3xl">
            Conservation Activities
          </h1>
          <p className="mt-2 font-mono text-[0.6875rem] tracking-[0.14em] text-muted-foreground uppercase">
            Activities that add to your score and your payment
          </p>
        </div>
      </div>

      {/* Deadline alerts */}
      <CSPDeadlineBanners deadlines={deadlines} />

      {/* What is recommended */}
      {gapClosingEnhancements.length > 0 && (
        <section aria-labelledby="recommended-summary-heading" className="space-y-2">
          <div className="rule-head">
            <h2 id="recommended-summary-heading">Recommended for your gaps</h2>
            <span aria-hidden="true" className="h-px flex-1 bg-rule" />
          </div>
          <LedgerRow
            label={`${pluralize(gapClosingEnhancements.length, "Activity", "Activities")} recommended to close your gaps`}
            note={gapClosingEnhancements.map((e) => e.name).join(", ")}
            value={`${gapClosingEnhancements.length}`}
          />
          {gapClosingPayment > 0 && (
            <div className="border-t border-rule pt-1">
              <LedgerRow
                label="Estimated value if you adopt them"
                value={`+${formatUsd(gapClosingPayment)}/yr`}
              />
            </div>
          )}
        </section>
      )}

      {/* Gap-closing enhancements */}
      {gapClosingEnhancements.length > 0 && (
        <CSPEnhancementList
          enhancements={gapClosingEnhancements}
          title="Recommended to close your stewardship gaps"
          showEmpty={false}
        />
      )}

      {/* Additional enhancements to consider */}
      {otherEnhancements.length > 0 && (
        <CSPEnhancementList
          enhancements={otherEnhancements}
          title="More activities to consider"
          showEmpty={false}
        />
      )}

      {enhancements.length === 0 && (
        <p className="max-w-[62ch] text-sm text-muted-foreground">
          No activities available yet. Complete your eligibility evaluation to
          see which conservation activities are relevant for your operation.
        </p>
      )}

      {/* How the list is put together */}
      <div className="space-y-2 border-t border-rule pt-3">
        <p className="max-w-[62ch] text-xs leading-relaxed text-muted-foreground">
          Activities are ranked by how much they help close your current
          stewardship gaps.
          {notes && ` ${notes.activity_model} Per-acre rates: ${notes.activity_rate_basis}.`}{" "}
          Contact your NRCS office to confirm activity eligibility and finalize
          your selections.
        </p>
        {rules && <CSPRulesCitation rules={rules} />}
      </div>
    </div>
  );
}
