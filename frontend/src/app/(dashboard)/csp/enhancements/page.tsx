import Link from "next/link";
import { redirect } from "next/navigation";
import { Info } from "lucide-react";
import { Separator } from "@/components/ui/separator";

import { CSPEnhancementList } from "@/components/csp/csp-enhancement-list";
import { CSPDeadlineBanners } from "@/components/csp/csp-deadline-banner";

import { mockFarms } from "@/lib/mocks/farms";
import { mockCSPEnhancements, mockCSPEligibility } from "@/lib/mocks/csp";

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "CSP Enhancements — RegenAI",
};

interface EnhancementsPageProps {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

export default async function CspEnhancementsPage({
  searchParams,
}: EnhancementsPageProps) {
  const params = await searchParams;
  const farmIdParam =
    typeof params.farm_id === "string" ? params.farm_id : undefined;

  const farm =
    mockFarms.find((f) => f.id === farmIdParam) ?? mockFarms[0] ?? null;

  if (!farm) {
    redirect("/farms");
  }

  const eligibility = mockCSPEligibility;
  const enhancements = mockCSPEnhancements;

  const activeEnhancements = enhancements.filter(
    (e) => e.status === "active" || e.status === "committed"
  );
  const consideringEnhancements = enhancements.filter(
    (e) => e.status === "considering"
  );

  const totalSelectedPayment = activeEnhancements.reduce(
    (sum, e) => sum + (e.estimated_payment ?? 0),
    0
  );

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
          <span className="text-foreground font-medium">Enhancements</span>
        </div>
        <h1 className="font-heading text-2xl font-bold text-foreground sm:text-3xl">
          Enhancement Activities
        </h1>
        <p className="text-sm text-muted-foreground">
          Additional conservation activities that increase your score and
          payment
        </p>
      </div>

      {/* Deadline alerts */}
      <CSPDeadlineBanners deadlines={eligibility.upcoming_deadlines} />

      {/* Summary bar */}
      {activeEnhancements.length > 0 && (
        <div className="rounded-xl border border-primary/30 bg-primary/5 px-4 py-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-foreground">
              {activeEnhancements.length} enhancement
              {activeEnhancements.length !== 1 ? "s" : ""} selected
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Codes:{" "}
              {activeEnhancements.map((e) => e.code).join(", ")}
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs text-muted-foreground">Added to payment</p>
            <p className="font-heading text-xl font-bold text-primary">
              +${totalSelectedPayment.toLocaleString()}/yr
            </p>
          </div>
        </div>
      )}

      {/* Selected enhancements */}
      {activeEnhancements.length > 0 && (
        <CSPEnhancementList
          enhancements={activeEnhancements}
          title="Your selected enhancements"
          showEmpty={false}
        />
      )}

      {activeEnhancements.length > 0 && consideringEnhancements.length > 0 && (
        <Separator />
      )}

      {/* Additional enhancements to consider */}
      {consideringEnhancements.length > 0 && (
        <CSPEnhancementList
          enhancements={consideringEnhancements}
          title="More enhancements to consider"
          showEmpty={false}
        />
      )}

      {enhancements.length === 0 && (
        <div className="rounded-xl border border-border bg-card p-8 text-center">
          <p className="text-sm font-medium text-foreground mb-1">
            No enhancements available yet
          </p>
          <p className="text-sm text-muted-foreground max-w-sm mx-auto">
            Complete your eligibility evaluation to see which enhancement
            activities are relevant for your operation.
          </p>
        </div>
      )}

      {/* Info note */}
      <div className="flex items-start gap-2 rounded-xl border border-border bg-muted/30 px-4 py-4">
        <Info
          className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
          aria-hidden="true"
        />
        <p className="text-xs text-muted-foreground leading-relaxed">
          Enhancement selection will be interactive once connected to the live
          API. Payment estimates shown are based on NRCS payment schedules and
          your enrolled acres. Bundle-eligible enhancements pay at 115% when
          applied together. Contact your NRCS office to confirm enhancement
          eligibility and finalize your selections.
        </p>
      </div>
    </div>
  );
}
