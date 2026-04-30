import Link from "next/link";
import { redirect } from "next/navigation";
import { Info, ChevronRight, AlertCircle } from "lucide-react";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

import { CSPPaymentSummary } from "@/components/csp/csp-payment-summary";
import { CSPDeadlineBanners } from "@/components/csp/csp-deadline-banner";

import { api } from "@/lib/api/client";
import type { CSPEligibility, CSPPaymentEstimate } from "@/lib/api/types";

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "CSP Payment Estimate — RegenAI",
};

// ── Derive a CSPPaymentEstimate from the eligibility response ─────────────────
// The backend exposes payment figures directly on the eligibility object.
// There is no separate /csp/payment endpoint, so we project from eligibility.

function derivePayment(eligibility: CSPEligibility): CSPPaymentEstimate {
  const annual = eligibility.estimated_annual_payment ?? 0;
  return {
    farm_id: eligibility.farm_id,
    state_code: "IA",
    fiscal_year: eligibility.fiscal_year,
    total_cropland_acres: 0,
    rc_count_above_threshold: eligibility.rc_count_above_threshold,
    eap_annual: annual,
    enap_annual: 0,
    raw_annual: annual,
    capped_annual: annual,
    contract_5yr_total: eligibility.estimated_5yr_payment ?? annual * 5,
    per_acre_annual: 0,
    min_applied: false,
    max_applied: false,
    enhancement_breakdown: [],
    disclaimer:
      "This is an estimate based on NRCS payment schedules and may differ from the final payment determined by your local NRCS office. Contact your NRCS service center to get an official payment estimate before applying.",
  };
}

// ── Error state ───────────────────────────────────────────────────────────────

function PaymentError({ message }: { message: string }) {
  return (
    <div className="pb-20 sm:pb-0">
      <div className="mb-6">
        <h1 className="font-heading text-2xl font-bold text-foreground">
          Payment Estimate
        </h1>
      </div>
      <Card className="py-12 text-center">
        <CardContent className="flex flex-col items-center gap-5">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-destructive/10">
            <AlertCircle
              className="h-8 w-8 text-destructive"
              aria-hidden="true"
            />
          </div>
          <div className="max-w-sm">
            <h2 className="font-heading text-lg font-semibold text-foreground">
              Could not load payment data
            </h2>
            <p className="mt-1.5 text-sm text-muted-foreground leading-relaxed">
              {message}
            </p>
          </div>
          <Link href="/farms">
            <Button variant="outline" className="min-h-[48px] cursor-pointer">
              Back to farms
            </Button>
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

interface PaymentPageProps {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

export default async function CspPaymentPage({
  searchParams,
}: PaymentPageProps) {
  const params = await searchParams;
  const farmId =
    typeof params.farm_id === "string" ? params.farm_id : undefined;

  if (!farmId) {
    redirect("/farms");
  }

  let farmName: string;
  let eligibility: CSPEligibility;

  try {
    const [farm, cspEligibility] = await Promise.all([
      api.farms.get(farmId),
      api.csp.getEligibility(farmId),
    ]);
    farmName = farm.name;
    eligibility = cspEligibility;
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Failed to load payment data.";
    return <PaymentError message={message} />;
  }

  const payment = derivePayment(eligibility);

  return (
    <div className="pb-20 sm:pb-0 space-y-8">
      {/* Breadcrumb */}
      <div className="space-y-1">
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <Link href="/farms" className="hover:text-foreground transition-colors">
            {farmName}
          </Link>
          <span aria-hidden="true">&rsaquo;</span>
          <Link
            href={`/csp?farm_id=${farmId}`}
            className="hover:text-foreground transition-colors"
          >
            CSP Navigator
          </Link>
          <span aria-hidden="true">&rsaquo;</span>
          <span className="text-foreground font-medium">Payment Estimate</span>
        </div>
        <h1 className="font-heading text-2xl font-bold text-foreground sm:text-3xl">
          Payment Estimate
        </h1>
        <p className="text-sm text-muted-foreground">
          How much CSP could pay your farm over a 5-year contract
        </p>
      </div>

      {/* Deadline alerts */}
      <CSPDeadlineBanners deadlines={eligibility.upcoming_deadlines} />

      {/* How payment works */}
      <div className="rounded-xl border border-border bg-card px-4 py-4 space-y-2">
        <p className="text-sm font-semibold text-foreground">
          How the CSP payment is calculated
        </p>
        <p className="text-sm text-muted-foreground leading-relaxed">
          Your payment has two parts: (1){" "}
          <strong>Existing Activity Payment</strong> — a per-acre rate
          multiplied by how many conservation areas you already meet, and (2){" "}
          <strong>Enhancement Payment</strong> — paid for each new activity you
          commit to adding. Both are paid annually for 5 years.
        </p>
      </div>

      {/* Full payment summary */}
      <CSPPaymentSummary payment={payment} compact={false} />

      <Separator />

      {/* Add more enhancements CTA */}
      <div className="rounded-xl border border-primary/20 bg-primary/5 px-4 py-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-foreground">
            Want a higher payment?
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Adding more enhancement activities increases your annual payment
            and your application score.
          </p>
        </div>
        <Link href={`/csp/enhancements?farm_id=${farmId}`}>
          <Button className="min-h-[48px] bg-primary text-primary-foreground hover:bg-primary/90 cursor-pointer">
            Browse More Enhancements
            <ChevronRight className="ml-1 h-4 w-4" aria-hidden="true" />
          </Button>
        </Link>
      </div>

      {/* Disclaimer */}
      <div className="flex items-start gap-2 rounded-xl border border-border bg-muted/30 px-4 py-4">
        <Info
          className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
          aria-hidden="true"
        />
        <p className="text-xs text-muted-foreground leading-relaxed">
          {payment.disclaimer}
        </p>
      </div>
    </div>
  );
}
