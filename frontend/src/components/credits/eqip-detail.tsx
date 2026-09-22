"use client";

import { toast } from "sonner";
import { Download, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EdgeNote, LedgerRow, RuleHead, Stamp } from "@/components/shared/record";
import type { CreditEligibility } from "@/lib/api/types";

const EQIP_PROGRAM_URL =
  "https://www.nrcs.usda.gov/programs-initiatives/eqip-environmental-quality-incentives";

// Common row-crop conservation practices (NRCS practice standard code -> plain
// name). This is a reference list, not a per-farm eligibility result: the API
// does not return which practices a farm is eligible for yet.
const COMMON_EQIP_PRACTICES: Record<string, string> = {
  "340": "Cover crops — plant a crop in the off-season to protect and build soil",
  "329": "No-till — leave crop residue and skip tillage",
  "590": "Nutrient management — apply fertilizer based on soil tests",
  "595": "Pest management — plan pest control to cut risk and chemical use",
  "393": "Filter strips — grass buffers along waterways",
  "412": "Grassed waterways — stabilize drainage channels",
};

interface EqipPracticeRowProps {
  code: string;
  name: string;
  documented: boolean;
}

/** One line of the plan sheet: the stamped code, what it is, whether it is on file. */
function EqipPracticeRow({ code, name, documented }: EqipPracticeRowProps) {
  return (
    <li className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-border py-3">
      <Stamp className="shrink-0">CPS {code}</Stamp>

      <div className="min-w-0 flex-1">
        <p
          className={
            documented
              ? "text-sm leading-snug font-medium text-foreground"
              : "text-sm leading-snug text-muted-foreground"
          }
        >
          {name}
        </p>
        {!documented && (
          <a
            href={EQIP_PROGRAM_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-h-12 items-center gap-1 text-sm font-medium text-primary underline underline-offset-2 hover:text-accent"
            aria-label={`Take action on practice ${code}`}
          >
            Take action
            <ExternalLink className="h-3 w-3" aria-hidden="true" />
            <span className="sr-only">(opens in new tab)</span>
          </a>
        )}
      </div>

      {/* The word carries the status, never the color on its own. */}
      <span
        className={
          documented
            ? "font-mono text-[0.6875rem] tracking-[0.08em] text-success uppercase"
            : "font-mono text-[0.6875rem] tracking-[0.08em] text-muted-foreground uppercase"
        }
      >
        {documented ? "Documented" : "Not documented"}
      </span>
    </li>
  );
}

interface EqipDetailProps {
  credit: CreditEligibility;
}

export function EqipDetail({ credit }: EqipDetailProps) {
  const documentedCodes = new Set(credit.practices_documented);
  // Reference list plus anything the farmer documented that isn't on it.
  const practiceCodes = Array.from(
    new Set([...Object.keys(COMMON_EQIP_PRACTICES), ...credit.practices_documented])
  );

  const documentedCount = practiceCodes.filter((code) => documentedCodes.has(code)).length;
  const totalCount = practiceCodes.length;
  const documentedPct = totalCount > 0 ? Math.round((documentedCount / totalCount) * 100) : 0;

  function handleDownload() {
    toast.info("PDF generation coming soon", {
      description: "Your EQIP summary report will be available here once the feature launches.",
    });
  }

  return (
    <section aria-labelledby="eqip-heading">
      <h2
        id="eqip-heading"
        className="font-heading text-xl font-semibold text-foreground"
      >
        EQIP eligibility
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Environmental Quality Incentives Program — USDA cost-share
      </p>

      <div className="mt-6">
        <RuleHead label="Practice documentation" />

        <div className="mt-2 divide-y divide-border">
          <LedgerRow
            label="Common conservation practices documented"
            value={`${documentedCount} of ${totalCount}`}
          />
        </div>

        {/* Flat gauge under the figure it belongs to */}
        <div
          className="mt-1 h-1.5 w-full bg-muted"
          role="progressbar"
          aria-valuenow={documentedCount}
          aria-valuemin={0}
          aria-valuemax={totalCount}
          aria-label={`${documentedCount} of ${totalCount} practices documented`}
        >
          <div
            className="h-full bg-primary transition-all"
            style={{ width: `${documentedPct}%` }}
          />
        </div>
        <p className="mt-1 text-right font-mono text-xs tabular-nums text-muted-foreground">
          {documentedPct}%
        </p>

        {credit.notes && (
          <EdgeNote tone="info" className="mt-4">
            {credit.notes}
          </EdgeNote>
        )}

        <ul
          aria-label="EQIP practice checklist"
          className="mt-4 border-t border-border"
        >
          {practiceCodes.map((code) => (
            <EqipPracticeRow
              key={code}
              code={code}
              name={COMMON_EQIP_PRACTICES[code] ?? `Practice ${code}`}
              documented={documentedCodes.has(code)}
            />
          ))}
        </ul>

        <Button
          onClick={handleDownload}
          variant="outline"
          className="mt-5 min-h-12 cursor-pointer"
          aria-label="Download EQIP summary as PDF"
        >
          <Download aria-hidden="true" />
          Download EQIP summary
        </Button>
      </div>
    </section>
  );
}
