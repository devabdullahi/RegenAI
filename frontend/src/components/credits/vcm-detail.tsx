"use client";

import { useState } from "react";
import { toast } from "sonner";
import {
  Leaf,
  ChevronDown,
  ChevronUp,
  Sprout,
  TrendingUp,
  ArrowRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";
import type { CreditEligibility, Field } from "@/lib/api/types";

// VCM field-level breakdown row — one row per field
interface FieldBreakdown {
  fieldId: string;
  fieldName: string;
  practice: string;
  acres: number;
  creditsPerAcre: number;
  estimatedCredits: number;
}

// Build field breakdown from available data
function buildFieldBreakdown(
  credit: CreditEligibility,
  fields: Field[]
): FieldBreakdown[] {
  const CREDITS_PER_ACRE_BY_PRACTICE: Record<string, number> = {
    "340": 1.2, // cover crops
    "329": 0.9, // no-till
    "590": 0.5, // nutrient management
    "600": 0.4, // pest management
  };

  const PRACTICE_NAMES: Record<string, string> = {
    "340": "Cover crops",
    "329": "No-till",
    "590": "Nutrient management",
    "600": "Pest management",
  };

  const rows: FieldBreakdown[] = [];

  for (const field of fields) {
    for (const practiceCode of credit.practices_documented) {
      const creditsPerAcre =
        CREDITS_PER_ACRE_BY_PRACTICE[practiceCode] ?? 0.8;
      rows.push({
        fieldId: field.id,
        fieldName: field.name,
        practice: PRACTICE_NAMES[practiceCode] ?? `Practice ${practiceCode}`,
        acres: field.acres,
        creditsPerAcre,
        estimatedCredits: parseFloat(
          (field.acres * creditsPerAcre).toFixed(1)
        ),
      });
    }
  }

  return rows;
}

function HowCreditsDialog() {
  return (
    <Dialog>
      <DialogTrigger
        render={
          <Button
            variant="outline"
            className="w-full min-h-[48px] cursor-pointer border-border"
          />
        }
      >
        <ChevronDown className="mr-2 h-4 w-4" aria-hidden="true" />
        How credits are calculated
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>How VCM credits are calculated</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 text-sm text-muted-foreground leading-relaxed">
          <p>
            Voluntary carbon credits represent one metric ton of CO₂ (or
            equivalent greenhouse gas) removed from the atmosphere or prevented
            from being released.
          </p>
          <div className="rounded-lg bg-muted p-3 space-y-2">
            <p className="font-semibold text-foreground">The formula:</p>
            <p className="font-mono text-xs bg-background rounded px-2 py-1.5">
              Acres &times; credits/acre &times; verification factor
            </p>
          </div>
          <ul className="space-y-2 list-none">
            <li className="flex gap-2">
              <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
              <span>
                <strong className="text-foreground">Cover crops</strong> sequester
                roughly 0.9–1.5 tonnes of carbon per acre per year by keeping
                living roots in the soil through winter.
              </span>
            </li>
            <li className="flex gap-2">
              <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
              <span>
                <strong className="text-foreground">No-till</strong> reduces soil
                disturbance, locking in existing organic matter and saving roughly
                0.7–1.1 tonnes per acre per year.
              </span>
            </li>
            <li className="flex gap-2">
              <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
              <span>
                A third-party verifier audits your records annually and issues
                certified credits, which can then be sold on carbon markets.
              </span>
            </li>
          </ul>
          <p>
            Your estimates above use the{" "}
            <strong className="text-foreground">Soil Carbon Protocol</strong> methodology
            — the leading standard for row-crop farming in the Midwest.
          </p>
        </div>
        <DialogFooter showCloseButton />
      </DialogContent>
    </Dialog>
  );
}

interface VcmDetailProps {
  credit: CreditEligibility;
  fields: Field[];
}

export function VcmDetail({ credit, fields }: VcmDetailProps) {
  const breakdown = buildFieldBreakdown(credit, fields);

  const totalCredits = breakdown.reduce(
    (sum, row) => sum + row.estimatedCredits,
    0
  );
  // Approximate market value at $18/credit (Soil Carbon Protocol mid-range)
  const estimatedValue = Math.round(totalCredits * 18);

  function handleEnroll() {
    toast.info("Enrollment guide coming soon", {
      description:
        "We'll walk you through signing up for the Soil Carbon Protocol step by step.",
    });
  }

  return (
    <section aria-labelledby="vcm-heading" className="space-y-4">
      {/* Section header */}
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent/10">
          <Leaf className="h-5 w-5 text-accent" aria-hidden="true" />
        </div>
        <div>
          <h2
            id="vcm-heading"
            className="font-heading text-lg font-semibold text-foreground"
          >
            VCM Credit Estimator
          </h2>
          <p className="text-sm text-muted-foreground">
            Voluntary Carbon Markets — sell carbon credits to buyers
          </p>
        </div>
      </div>

      {/* Big number display */}
      <Card>
        <CardContent className="pt-6 pb-6">
          <div className="flex flex-col items-center gap-1 text-center">
            <div className="flex items-end gap-2">
              <span
                className="font-heading text-6xl font-bold text-foreground tabular-nums"
                aria-label={`${totalCredits.toFixed(1)} estimated carbon credits`}
              >
                {totalCredits.toFixed(1)}
              </span>
              <span className="mb-2 text-lg font-medium text-muted-foreground">
                credits
              </span>
            </div>
            <p className="text-sm text-muted-foreground">
              estimated per year across all fields
            </p>
            <div className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-accent/10 px-3 py-1.5">
              <TrendingUp className="h-4 w-4 text-accent" aria-hidden="true" />
              <span className="text-sm font-semibold text-accent">
                ~${estimatedValue.toLocaleString()} potential annual value
              </span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Based on ~$18/credit mid-market estimate
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Per-field breakdown table */}
      <Card>
        <CardHeader className="border-b">
          <CardTitle className="text-base">Field-by-field breakdown</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {breakdown.length === 0 ? (
            <p className="px-4 py-6 text-sm text-center text-muted-foreground">
              No field data available. Add fields to your farm to see estimates.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" aria-label="Per-field carbon credit breakdown">
                <thead>
                  <tr className="border-b border-border bg-muted/50">
                    <th
                      scope="col"
                      className="px-4 py-3 text-left font-medium text-muted-foreground"
                    >
                      Field
                    </th>
                    <th
                      scope="col"
                      className="px-4 py-3 text-left font-medium text-muted-foreground"
                    >
                      Practice
                    </th>
                    <th
                      scope="col"
                      className="px-4 py-3 text-right font-medium text-muted-foreground"
                    >
                      Acres
                    </th>
                    <th
                      scope="col"
                      className="px-4 py-3 text-right font-medium text-muted-foreground"
                    >
                      Est. credits
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {breakdown.map((row, idx) => (
                    <tr
                      key={`${row.fieldId}-${row.practice}-${idx}`}
                      className="border-b border-border last:border-0 hover:bg-muted/30 transition-colors"
                    >
                      <td className="px-4 py-3 font-medium text-foreground">
                        {row.fieldName}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {row.practice}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums text-foreground">
                        {row.acres.toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums font-semibold text-primary">
                        {row.estimatedCredits.toFixed(1)}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t-2 border-border bg-muted/50">
                    <td
                      colSpan={3}
                      className="px-4 py-3 font-semibold text-foreground"
                    >
                      Total estimated credits
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums font-bold text-primary">
                      {totalCredits.toFixed(1)}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Program info */}
      <div className="rounded-xl border border-border bg-card p-4 flex gap-3">
        <div className="shrink-0 mt-0.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
            <Sprout className="h-4 w-4 text-primary" aria-hidden="true" />
          </div>
        </div>
        <div className="space-y-1">
          <p className="text-sm font-semibold text-foreground">
            Soil Carbon Protocol
          </p>
          <p className="text-sm text-muted-foreground leading-relaxed">
            The Soil Carbon Protocol is the leading methodology for certifying
            carbon credits from row-crop farms in the US. It measures the
            organic carbon your soil gains each year and converts it into
            tradeable credits verified by an independent auditor.
          </p>
        </div>
      </div>

      {/* How credits are calculated — expandable */}
      <HowCreditsDialog />

      {/* Enroll CTA */}
      <Button
        onClick={handleEnroll}
        className="w-full min-h-[48px] bg-accent text-accent-foreground hover:bg-accent/90 cursor-pointer font-semibold"
        aria-label="Start carbon credit enrollment"
      >
        Start Enrollment
        <ArrowRight className="ml-2 h-4 w-4" aria-hidden="true" />
      </Button>

      {credit.notes && (
        <p className="text-xs text-muted-foreground text-center px-2">
          {credit.notes}
        </p>
      )}
    </section>
  );
}
