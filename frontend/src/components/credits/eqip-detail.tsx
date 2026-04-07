"use client";

import { toast } from "sonner";
import { CheckCircle2, Circle, Download, FileText, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { CreditEligibility } from "@/lib/api/types";

// EQIP practice codes and their plain-English names
// These represent all practices eligible in the Midwest/Iowa context
const EQIP_PRACTICE_CATALOG: Record<string, string> = {
  "340": "Cover crops — plant a cash crop's offseason to build soil",
  "329": "No-till or reduced tillage — leave soil undisturbed",
  "590": "Nutrient management plan — apply fertilizer by soil test",
  "600": "Pest management — reduce chemical inputs with IPM",
  "393": "Filter strips — grass buffers along waterways",
  "412": "Grassed waterways — stabilize drainage channels",
  "484": "Mulching — protect soil with organic material",
  "528": "Prescribed grazing plan — rotate livestock across pastures",
};

interface EqipPracticeRowProps {
  code: string;
  name: string;
  documented: boolean;
}

function EqipPracticeRow({ code, name, documented }: EqipPracticeRowProps) {
  return (
    <li className="flex items-start gap-3 py-3 border-b border-border last:border-0">
      <div className="mt-0.5 shrink-0">
        {documented ? (
          <CheckCircle2
            className="h-5 w-5 text-primary"
            aria-hidden="true"
          />
        ) : (
          <Circle
            className="h-5 w-5 text-muted-foreground"
            aria-hidden="true"
          />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-baseline gap-2">
          <span className="font-mono text-xs font-semibold text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
            {code}
          </span>
          <span
            className={`text-sm leading-snug ${
              documented ? "text-foreground font-medium" : "text-muted-foreground"
            }`}
          >
            {name}
          </span>
        </div>
        {!documented && (
          <a
            href="https://www.nrcs.usda.gov/programs-initiatives/eqip-environmental-quality-incentives"
            target="_blank"
            rel="noopener noreferrer"
            className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-accent hover:text-accent/80 underline underline-offset-2 min-h-[44px] sm:min-h-0 py-1"
            aria-label={`Take action on practice ${code}`}
          >
            Take action
            <ExternalLink className="h-3 w-3" aria-hidden="true" />
          </a>
        )}
      </div>
      {documented && (
        <span className="shrink-0 text-xs font-medium text-primary bg-primary/10 rounded-full px-2 py-0.5 self-center">
          Done
        </span>
      )}
    </li>
  );
}

interface EqipDetailProps {
  credit: CreditEligibility;
}

export function EqipDetail({ credit }: EqipDetailProps) {
  // Determine which eligible practices are in the catalog
  // Documented = farmer has acted on them already
  const documentedCodes = new Set(credit.practices_documented);

  // All practice codes relevant to this farm (documented + a few more to show as eligible but pending)
  // In production this comes from the backend eligibility assessment
  const eligibleCodes = Object.keys(EQIP_PRACTICE_CATALOG).slice(0, 6);

  const documentedCount = eligibleCodes.filter((code) => documentedCodes.has(code)).length;
  const totalCount = eligibleCodes.length;

  function handleDownload() {
    toast.info("PDF generation coming soon", {
      description: "Your EQIP summary report will be available here once the feature launches.",
    });
  }

  return (
    <section aria-labelledby="eqip-heading" className="space-y-4">
      {/* Section header */}
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10">
          <FileText className="h-5 w-5 text-primary" aria-hidden="true" />
        </div>
        <div>
          <h2
            id="eqip-heading"
            className="font-heading text-lg font-semibold text-foreground"
          >
            EQIP Eligibility
          </h2>
          <p className="text-sm text-muted-foreground">
            Environmental Quality Incentives Program — USDA cost-share
          </p>
        </div>
      </div>

      {/* Summary card */}
      <Card>
        <CardHeader className="border-b">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div>
              <CardTitle className="text-base">Practice documentation</CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">
                You&rsquo;ve documented{" "}
                <span className="font-semibold text-primary">
                  {documentedCount} of {totalCount}
                </span>{" "}
                eligible practices
              </p>
            </div>
            {/* Progress bar */}
            <div className="w-full sm:w-40">
              <div
                className="h-2.5 w-full rounded-full bg-muted overflow-hidden"
                role="progressbar"
                aria-valuenow={documentedCount}
                aria-valuemin={0}
                aria-valuemax={totalCount}
                aria-label={`${documentedCount} of ${totalCount} practices documented`}
              >
                <div
                  className="h-full rounded-full bg-primary transition-all"
                  style={{
                    width: `${Math.round((documentedCount / totalCount) * 100)}%`,
                  }}
                />
              </div>
              <p className="mt-1 text-right text-xs text-muted-foreground">
                {Math.round((documentedCount / totalCount) * 100)}% complete
              </p>
            </div>
          </div>
        </CardHeader>

        <CardContent>
          {credit.notes && (
            <p className="mb-4 rounded-lg bg-primary/5 border border-primary/20 px-3 py-2.5 text-sm text-foreground leading-relaxed">
              {credit.notes}
            </p>
          )}

          {/* Practice checklist */}
          <ul aria-label="EQIP practice checklist" className="divide-y divide-border">
            {eligibleCodes.map((code) => (
              <EqipPracticeRow
                key={code}
                code={code}
                name={EQIP_PRACTICE_CATALOG[code]}
                documented={documentedCodes.has(code)}
              />
            ))}
          </ul>
        </CardContent>
      </Card>

      {/* CTA */}
      <Button
        onClick={handleDownload}
        className="w-full min-h-[48px] bg-accent text-accent-foreground hover:bg-accent/90 cursor-pointer font-semibold"
        aria-label="Download EQIP summary as PDF"
      >
        <Download className="mr-2 h-4 w-4" aria-hidden="true" />
        Download EQIP Summary
      </Button>
    </section>
  );
}
