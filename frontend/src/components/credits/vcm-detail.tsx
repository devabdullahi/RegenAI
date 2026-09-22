"use client";

import { toast } from "sonner";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EdgeNote, RuleHead } from "@/components/shared/record";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";
import { formatAcres, formatNumber } from "@/lib/format";
import type { CreditEligibility, VcmEstimate } from "@/lib/api/types";

function formatCredits(value: number): string {
  return formatNumber(value, { maxFractionDigits: 1 });
}

function HowCreditsDialog() {
  return (
    <Dialog>
      <DialogTrigger
        render={<Button variant="outline" className="min-h-12 cursor-pointer" />}
      >
        How this estimate works
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>How the carbon credit estimate works</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 text-sm leading-relaxed text-muted-foreground">
          <p>
            A carbon credit usually stands for one metric ton of CO₂ (or the
            same amount of another greenhouse gas) kept out of the air.
          </p>
          <div className="border-l-[3px] border-l-border bg-card py-3 pr-3 pl-4">
            <p className="font-mono text-[0.6875rem] font-medium tracking-[0.14em] text-muted-foreground uppercase">
              The formula
            </p>
            <p className="mt-1 font-mono text-xs text-foreground">
              Acres &times; estimated credits per acre, for each practice
            </p>
          </div>
          <ul className="space-y-2 border-t border-border pt-3">
            <li className="border-b border-border pb-2">
              The per-acre rates are RegenAI estimates. They do not come from a
              carbon registry.
            </li>
            <li className="border-b border-border pb-2">
              Fields with more soil organic matter on record use a higher rate
              within each practice&apos;s range.
            </li>
            <li>
              Real credits depend on the program you join, its rules, and a
              third-party check of your records.
            </li>
          </ul>
        </div>
        <DialogFooter showCloseButton />
      </DialogContent>
    </Dialog>
  );
}

const HEAD_CELL =
  "py-2 font-mono text-[0.6875rem] font-medium tracking-[0.14em] text-muted-foreground uppercase";

function BreakdownTable({ estimate }: { estimate: VcmEstimate }) {
  const rows = estimate.fields.flatMap((field) =>
    field.practices.map((practice) => ({ field, practice }))
  );

  if (rows.length === 0) {
    return (
      <p className="border-y border-border py-6 text-sm text-muted-foreground">
        No field-by-field breakdown is available for this estimate.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table
        className="w-full min-w-[30rem] text-sm"
        aria-label="Per-field carbon credit breakdown"
      >
        <thead>
          <tr className="border-y border-border">
            <th scope="col" className={`${HEAD_CELL} pr-4 text-left`}>
              Field
            </th>
            <th scope="col" className={`${HEAD_CELL} pr-4 text-left`}>
              Practice
            </th>
            <th scope="col" className={`${HEAD_CELL} pl-4 text-right`}>
              Acres ac
            </th>
            <th scope="col" className={`${HEAD_CELL} pl-4 text-right`}>
              Est. credits
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map(({ field, practice }) => (
            <tr key={`${field.field_id}-${practice.practice_code}`}>
              <td className="py-2.5 pr-4 font-medium text-foreground">
                {field.field_name}
              </td>
              <td className="py-2.5 pr-4 text-muted-foreground">
                {practice.practice_name}
              </td>
              <td className="py-2.5 pl-4 text-right font-mono tabular-nums text-muted-foreground">
                {formatAcres(field.acres, { short: true })}
              </td>
              <td className="py-2.5 pl-4 text-right font-mono tabular-nums text-foreground">
                {formatCredits(practice.estimated_credits)}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          {/* A heavy rule above the total, the way a ledger closes a column. */}
          <tr className="border-t-2 border-rule-strong">
            <td colSpan={3} className="py-2.5 pr-4 font-medium text-foreground">
              Total estimated credits
            </td>
            <td className="py-2.5 pl-4 text-right font-mono font-medium tabular-nums text-foreground">
              {formatCredits(estimate.estimated_total_credits)}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

interface VcmDetailProps {
  credit: CreditEligibility;
  /** From vcmEstimateFromReport(GET /credits/report). Omitted or null shows a fallback. */
  estimate?: VcmEstimate | null;
}

export function VcmDetail({ credit, estimate }: VcmDetailProps) {
  function handleEnroll() {
    toast.info("Enrollment guide coming soon", {
      description: "We'll walk you through choosing a carbon program step by step.",
    });
  }

  return (
    <section aria-labelledby="vcm-heading">
      <h2
        id="vcm-heading"
        className="font-heading text-xl font-semibold text-foreground"
      >
        VCM credit estimator
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Voluntary Carbon Markets — sell carbon credits to buyers
      </p>

      {estimate ? (
        <>
          <div className="mt-6">
            <RuleHead label="Estimated credits per year" />
            <p className="mt-3 font-mono text-[2rem] leading-none font-medium tabular-nums text-foreground">
              {formatCredits(estimate.estimated_total_credits)}
              <span className="ml-2 text-base text-muted-foreground">credits</span>
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
              estimated per year across all fields
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              RegenAI estimate, not from a carbon registry
            </p>
          </div>

          <div className="mt-6">
            <RuleHead label="Field-by-field breakdown" />
            <div className="mt-3">
              <BreakdownTable estimate={estimate} />
            </div>
          </div>
        </>
      ) : (
        <p className="mt-6 border-y border-border py-6 text-sm leading-relaxed text-muted-foreground">
          No field-by-field credit estimate to show yet. It appears after your
          farm is evaluated and practices like cover crops or no-till are marked
          as done.
        </p>
      )}

      <EdgeNote tone="info" title="Before you sign up" className="mt-6">
        Each carbon program sets its own rules, payments, and contract length.
        Compare programs and read the contract before you enroll.
      </EdgeNote>

      <div className="mt-5 flex flex-wrap gap-3">
        <Button
          onClick={handleEnroll}
          className="min-h-12 cursor-pointer"
          aria-label="Start carbon credit enrollment"
        >
          Start enrollment
          <ArrowRight aria-hidden="true" />
        </Button>
        <HowCreditsDialog />
      </div>

      {credit.notes && (
        <p className="mt-4 text-xs text-muted-foreground">{credit.notes}</p>
      )}
    </section>
  );
}
