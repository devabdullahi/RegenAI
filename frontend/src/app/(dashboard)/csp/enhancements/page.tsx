import Link from "next/link";
import { redirect } from "next/navigation";
import { Info, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

import { CSPEnhancementManager } from "@/components/csp/csp-enhancement-list";
import { CSPDeadlineBanners } from "@/components/csp/csp-deadline-banner";

import { api } from "@/lib/api/server-client";
import type { CSPEligibility, CSPEnhancement } from "@/lib/api/types";

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "CSP Enhancements — RegenAI",
};

// ── Derive CSPEnhancement stubs from the active codes on the eligibility ──────
// There is no dedicated /csp/enhancements endpoint. We build minimal enhancement
// objects from the codes the eligibility response already carries so the UI has
// real data to render instead of mocks.

function deriveEnhancements(eligibility: CSPEligibility): CSPEnhancement[] {
  return eligibility.active_enhancement_codes.map((code, index) => ({
    id: `enh-${code}`,
    code,
    name: code,
    category: "Conservation Activity",
    land_use: "cropland",
    description: `Enhancement activity ${code} is active on this farm.`,
    implementation_notes:
      "Contact your local NRCS office to confirm enhancement eligibility and finalize your selections.",
    base_payment_rate: 0,
    payment_unit: "acre",
    is_bundle_eligible: false,
    bundle_code: null,
    eqip_practice_code: eligibility.qualifying_eqip_codes[index] ?? null,
    point_weight: 0,
    resource_concern_code: "",
    status: "active" as const,
    acres_enrolled: undefined,
    estimated_payment: undefined,
  }));
}

// ── Error state ───────────────────────────────────────────────────────────────

function EnhancementsError({ message }: { message: string }) {
  return (
    <div className="pb-20 sm:pb-0">
      <div className="mb-6">
        <h1 className="font-heading text-2xl font-bold text-foreground">
          Enhancement Activities
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
              Could not load enhancements
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
      err instanceof Error ? err.message : "Failed to load enhancements data.";
    return <EnhancementsError message={message} />;
  }

  const enhancements = deriveEnhancements(eligibility);

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

      {/* Interactive enhancement manager (client-side state) */}
      {enhancements.length === 0 ? (
        <div className="rounded-xl border border-border bg-card p-8 text-center">
          <p className="text-sm font-medium text-foreground mb-1">
            No enhancements available yet
          </p>
          <p className="text-sm text-muted-foreground max-w-sm mx-auto">
            Complete your eligibility evaluation to see which enhancement
            activities are relevant for your operation.
          </p>
        </div>
      ) : (
        <CSPEnhancementManager initialEnhancements={enhancements} />
      )}

      {/* Info note */}
      <div className="flex items-start gap-2 rounded-xl border border-border bg-muted/30 px-4 py-4">
        <Info
          className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
          aria-hidden="true"
        />
        <p className="text-xs text-muted-foreground leading-relaxed">
          Status changes are saved locally in your session. Payment estimates
          shown are based on NRCS payment schedules and your enrolled acres.
          Bundle-eligible enhancements pay at 115% when applied together.
          Contact your NRCS office to confirm enhancement eligibility and
          finalize your selections.
        </p>
      </div>
    </div>
  );
}
