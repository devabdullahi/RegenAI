import Link from "next/link";
import { redirect } from "next/navigation";
import { Info, ChevronRight } from "lucide-react";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";

import { CSPPaymentSummary } from "@/components/csp/csp-payment-summary";
import { CSPDeadlineBanners } from "@/components/csp/csp-deadline-banner";

import { mockFarms } from "@/lib/mocks/farms";
import { mockCSPPayment, mockCSPEligibility } from "@/lib/mocks/csp";

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "CSP Payment Estimate — RegenAI",
};

interface PaymentPageProps {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

export default async function CspPaymentPage({
  searchParams,
}: PaymentPageProps) {
  const params = await searchParams;
  const farmIdParam =
    typeof params.farm_id === "string" ? params.farm_id : undefined;

  const farm =
    mockFarms.find((f) => f.id === farmIdParam) ?? mockFarms[0] ?? null;

  if (!farm) {
    redirect("/farms");
  }

  const payment = mockCSPPayment;
  const eligibility = mockCSPEligibility;

  return (
    <div className="pb-20 sm:pb-0 space-y-8">
      {/* Breadcrumb */}
      <div className="space-y-1">
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <Link href="/farms" className="hover:text-foreground transition-colors">
            {farm.name}
          </Link>
          <span aria-hidden="true">&rsaquo;</span>
          <Link
            href={`/csp?farm_id=${farm.id}`}
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
        <Link href={`/csp/enhancements?farm_id=${farm.id}`}>
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
