import Link from "next/link";
import { EqipDetail } from "@/components/credits/eqip-detail";
import { VcmDetail } from "@/components/credits/vcm-detail";
import { DocumentUpload } from "@/components/credits/document-upload";
import { ErrorState, NoFarmSelected } from "@/components/shared/page-states";
import { api } from "@/lib/api/server-client";
import type { Metadata } from "next";
import { creditsToList, vcmEstimateFromReport } from "@/lib/api/adapters";
import { formatAcres } from "@/lib/format";
import type {
  CreditEligibility,
  CreditEligibilityGetResponse,
  CreditReportResponse,
  Document,
  Farm,
} from "@/lib/api/types";

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
  const farmId =
    typeof params.farm_id === "string"
      ? params.farm_id
      : typeof params.farm === "string"
        ? params.farm
        : undefined;

  if (!farmId) {
    return (
      <div className="pb-20 sm:pb-0">
        <PageHeading />
        <NoFarmSelected description="Choose a farm to see its EQIP eligibility and carbon credits." />
      </div>
    );
  }

  let farm: Farm;
  let credits: CreditEligibility[];
  let documents: Document[];
  let report: CreditReportResponse | null;

  let creditsResp: CreditEligibilityGetResponse;

  try {
    [farm, creditsResp, documents, report] = await Promise.all([
      api.farms.get(farmId),
      api.credits.get(farmId),
      api.documents.list(farmId),
      // The VCM estimate is one widget: on failure it falls back, the page still loads.
      api.credits.getReport(farmId).catch((err: unknown) => {
        console.error(`CreditsPage: credits report failed for farm ${farmId}`, err);
        return null;
      }),
    ]);
    credits = creditsToList(creditsResp);
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Failed to load credits data.";
    return (
      <div className="pb-20 sm:pb-0">
        <PageHeading />
        <ErrorState title="Couldn't load credits" message={message} />
      </div>
    );
  }

  const eqipCredit = credits.find((c) => c.program === "EQIP");
  const vcmCredit = credits.find((c) => c.program === "VCM");

  return (
    <div className="pb-20 sm:pb-0">
      {/* Masthead of the record */}
      <div className="border-b-2 border-rule-strong pb-3">
        <nav
          aria-label="Breadcrumb"
          className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground"
        >
          <Link href="/farms" className="transition-colors hover:text-foreground">
            {farm.name}
          </Link>
          <span aria-hidden="true">&rsaquo;</span>
          <span className="font-medium text-foreground" aria-current="page">
            Credits and programs
          </span>
        </nav>
        <h1 className="font-heading mt-1 text-2xl font-semibold text-foreground sm:text-3xl">
          Credits and programs
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {farm.state} &middot;{" "}
          <span className="font-mono tabular-nums">
            {formatAcres(farm.total_acres, { short: true })}
          </span>{" "}
          total &middot; EQIP and carbon credit tracking
        </p>
      </div>

      <div className="mt-10 space-y-12">
        {eqipCredit ? (
          <EqipDetail credit={eqipCredit} />
        ) : (
          <NoProgramData program="EQIP" />
        )}

        {vcmCredit ? (
          <VcmDetail
            credit={vcmCredit}
            estimate={report ? vcmEstimateFromReport(report.vcm) : undefined}
          />
        ) : (
          <NoProgramData program="VCM" />
        )}

        <DocumentUpload initialDocuments={documents} farmId={farm.id} />
      </div>
    </div>
  );
}

// ── Shared pieces ─────────────────────────────────────────────────────────────

/** Title block for the states that load before the farm is known. */
function PageHeading() {
  return (
    <div className="mb-6 border-b-2 border-rule-strong pb-3">
      <h1 className="font-heading text-2xl font-semibold text-foreground sm:text-3xl">
        Credits and programs
      </h1>
    </div>
  );
}

function NoProgramData({ program }: { program: string }) {
  return (
    <section aria-label={`${program} status`}>
      <h2 className="font-heading text-xl font-semibold text-foreground">
        No {program} data yet
      </h2>
      <p className="mt-2 max-w-[62ch] text-sm leading-relaxed text-muted-foreground">
        {program === "EQIP"
          ? "Your EQIP eligibility assessment is pending. RegenAI will notify you when results are ready."
          : "Your VCM credit estimate will appear here once your practices are documented."}
      </p>
    </section>
  );
}
