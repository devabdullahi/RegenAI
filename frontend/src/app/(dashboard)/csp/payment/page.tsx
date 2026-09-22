import Link from "next/link";
import { redirect } from "next/navigation";
import { ButtonLink } from "@/components/shared/button-link";
import { RuleHead, Stamp } from "@/components/shared/record";

import {
  CSPPaymentSummary,
  CSPRulesCitation,
} from "@/components/csp/csp-payment-summary";
import { CSPDeadlineBanners } from "@/components/csp/csp-deadline-banner";

import { api } from "@/lib/api/server-client";
import { adaptDeadlines, adaptPayment } from "@/lib/api/adapters";
import type { CSPDeadline, CSPPaymentEstimate } from "@/lib/api/types";

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "CSP Payment Estimate — RegenAI",
};

// ── Error state ───────────────────────────────────────────────────────────────

function PaymentError({ message }: { message: string }) {
  return (
    <div className="max-w-[62ch] space-y-4 pb-20 sm:pb-0">
      <div className="border-b-2 border-rule-strong pb-3">
        <h1 className="font-heading text-[1.75rem] leading-tight font-bold text-foreground">
          Payment Estimate
        </h1>
      </div>
      <RuleHead label="Could not load payment data" />
      <p className="text-sm leading-relaxed text-muted-foreground">{message}</p>
      <ButtonLink href="/farms" variant="outline">
        Back to farms
      </ButtonLink>
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
  let payment: CSPPaymentEstimate;
  let deadlines: CSPDeadline[];

  try {
    const [farm, paymentsResp] = await Promise.all([
      api.farms.get(farmId),
      api.csp.getPayments(farmId),
    ]);
    const deadlinesResp = await api.csp
      .getDeadlines(farm.state)
      .catch(() => null);

    farmName = farm.name;
    payment = adaptPayment(paymentsResp);
    deadlines = adaptDeadlines(deadlinesResp);
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Failed to load payment data.";
    return <PaymentError message={message} />;
  }

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
            Payment Estimate
          </span>
        </nav>
        <div className="border-b-2 border-rule-strong pb-3">
          <h1 className="font-heading text-[1.75rem] leading-tight font-bold text-foreground sm:text-3xl">
            Payment Estimate
          </h1>
          <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[0.6875rem] tracking-[0.14em] text-muted-foreground uppercase">
            <span>{payment.state_code}</span>
            <span aria-hidden="true">&middot;</span>
            <span>{payment.contract_years}-year contract</span>
            <Stamp>FY{payment.fiscal_year}</Stamp>
          </p>
        </div>
      </div>

      {/* Deadline alerts */}
      <CSPDeadlineBanners deadlines={deadlines} />

      {/* How payment works */}
      <section aria-labelledby="how-heading" className="space-y-2">
        <div className="rule-head">
          <h2 id="how-heading">How the CSP payment is worked out</h2>
          <span aria-hidden="true" className="h-px flex-1 bg-rule" />
        </div>
        <p className="reading max-w-[62ch] text-foreground">
          Your estimate adds two parts: the{" "}
          <strong>Existing Activity Payment</strong> ({payment.eap_label}) and{" "}
          <strong>conservation activity payments</strong> for the activities you
          adopt. The {payment.contract_years}-year total is checked against the{" "}
          {payment.contract_limit_label}.
        </p>
        <ul
          className="reading max-w-[62ch] space-y-2 text-muted-foreground"
          aria-label="CSP payment rules"
        >
          {[
            payment.rule_notes.existing_activity_payment,
            payment.rule_notes.annual_payment_limit,
            payment.rule_notes.activity_model,
          ]
            .filter((note) => note.length > 0)
            .map((note) => (
              <li key={note}>{note}</li>
            ))}
        </ul>
        <CSPRulesCitation rules={payment.rules} />
      </section>

      {/* The ticket */}
      <CSPPaymentSummary payment={payment} compact={false} />

      {/* Add more activities */}
      <section aria-labelledby="more-heading" className="space-y-3">
        <div className="rule-head">
          <h2 id="more-heading">Want a higher payment?</h2>
          <span aria-hidden="true" className="h-px flex-1 bg-rule" />
        </div>
        <p className="reading max-w-[62ch] text-foreground">
          Adding more conservation activities increases your annual payment and
          your application score.
        </p>
        <ButtonLink href={`/csp/enhancements?farm_id=${encodeURIComponent(farmId)}`}>
          Browse conservation activities
        </ButtonLink>
      </section>
    </div>
  );
}
