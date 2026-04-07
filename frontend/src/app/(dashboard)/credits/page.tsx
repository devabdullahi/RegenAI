import Link from "next/link";
import { Tractor, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { EqipDetail } from "@/components/credits/eqip-detail";
import { VcmDetail } from "@/components/credits/vcm-detail";
import { DocumentUpload } from "@/components/credits/document-upload";
import { mockFarms, mockFields, mockCredits } from "@/lib/mocks/farms";
import type { Metadata } from "next";
import type { Document } from "@/lib/api/types";

export const metadata: Metadata = {
  title: "Credits & Programs — RegenAI",
  description:
    "Track your EQIP eligibility and voluntary carbon market credits for your farm.",
};

interface CreditsPageProps {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

export default async function CreditsPage({ searchParams }: CreditsPageProps) {
  const params = await searchParams;
  const farmIdParam =
    typeof params.farm_id === "string" ? params.farm_id : undefined;

  // Default to first farm when no farm_id provided
  const farm =
    mockFarms.find((f) => f.id === farmIdParam) ?? mockFarms[0] ?? null;

  if (!farm) {
    return <NoFarmState />;
  }

  const farmFields = mockFields.filter((f) => f.farm_id === farm.id);
  const credits = mockCredits.filter((c) => c.farm_id === farm.id);
  const eqipCredit = credits.find((c) => c.program === "EQIP");
  const vcmCredit = credits.find((c) => c.program === "VCM");

  // Empty document list — Supabase Storage integration TBD
  const documents: Document[] = [];

  return (
    <div className="pb-20 sm:pb-0 space-y-10">
      {/* Page header */}
      <div className="space-y-1">
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <Link
            href="/farms"
            className="hover:text-foreground transition-colors"
          >
            {farm.name}
          </Link>
          <span aria-hidden="true">&rsaquo;</span>
          <span className="text-foreground font-medium">Credits &amp; Programs</span>
        </div>
        <h1 className="font-heading text-2xl font-bold text-foreground sm:text-3xl">
          Credits &amp; Programs
        </h1>
        <p className="text-muted-foreground text-sm">
          {farm.state} &middot; {farm.total_acres.toLocaleString()} total
          acres &middot; EQIP and carbon credit tracking
        </p>
      </div>

      {/* EQIP Section */}
      {eqipCredit ? (
        <EqipDetail credit={eqipCredit} />
      ) : (
        <NoProgramData program="EQIP" />
      )}

      <Separator />

      {/* VCM Section */}
      {vcmCredit ? (
        <VcmDetail credit={vcmCredit} fields={farmFields} />
      ) : (
        <NoProgramData program="VCM" />
      )}

      <Separator />

      {/* Document upload */}
      <DocumentUpload documents={documents} farmId={farm.id} />
    </div>
  );
}

// ── Empty states ──────────────────────────────────────────────

function NoProgramData({ program }: { program: string }) {
  return (
    <div className="rounded-xl border border-border bg-card p-6 text-center space-y-2">
      <FileText
        className="mx-auto h-8 w-8 text-muted-foreground"
        aria-hidden="true"
      />
      <p className="text-sm font-medium text-foreground">
        No {program} data yet
      </p>
      <p className="text-sm text-muted-foreground max-w-sm mx-auto leading-relaxed">
        {program === "EQIP"
          ? "Your EQIP eligibility assessment is pending. RegenAI will notify you when results are ready."
          : "Your VCM credit estimate will appear here once your practices are documented."}
      </p>
    </div>
  );
}

function NoFarmState() {
  return (
    <div className="pb-20 sm:pb-0">
      <div className="mb-6">
        <h1 className="font-heading text-2xl font-bold text-foreground">
          Credits &amp; Programs
        </h1>
        <p className="mt-1 text-muted-foreground">
          Select a farm to see your program eligibility.
        </p>
      </div>
      <Card className="py-12 text-center">
        <CardContent className="flex flex-col items-center gap-5">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
            <Tractor className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
          </div>
          <div className="max-w-sm">
            <h2 className="font-heading text-lg font-semibold text-foreground">
              No farm found
            </h2>
            <p className="mt-1.5 text-sm text-muted-foreground leading-relaxed">
              Add a farm first to start tracking EQIP eligibility and carbon
              credits.
            </p>
          </div>
          <Link href="/farms">
            <Button className="min-h-[48px] bg-primary text-primary-foreground hover:bg-primary/90 cursor-pointer">
              <Tractor className="mr-2 h-4 w-4" aria-hidden="true" />
              Go to My Farms
            </Button>
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
