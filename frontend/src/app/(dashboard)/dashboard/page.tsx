import Link from "next/link";
import { Suspense } from "react";
import { Plus, Tractor, Wheat } from "lucide-react";
import { FieldSelector } from "@/components/dashboard/field-selector";
import {
  RecommendationCard,
  RecommendationsEmpty,
} from "@/components/dashboard/recommendation-card";
import { WeatherWidget } from "@/components/dashboard/weather-widget";
import { SoilWidget } from "@/components/dashboard/soil-widget";
import { CreditPanel } from "@/components/dashboard/credit-panel";
import { CspStatusWidget } from "@/components/csp/csp-status-widget";
import { RecentActivityWidget } from "@/components/activities/recent-activity-widget";
import { UpcomingDeadlines } from "@/components/shared/deadline-alerts";
import { RuleHead } from "@/components/shared/record";
import {
  EmptyState,
  ErrorState,
  NoFarmSelected,
} from "@/components/shared/page-states";
import { api, ApiRequestError } from "@/lib/api/server-client";
import {
  activityToView,
  adaptDeadlines,
  adaptEligibility,
  creditsToList,
} from "@/lib/api/adapters";
import { formatAcres, pluralize } from "@/lib/format";
import type {
  CreditEligibility,
  CSPEligibilityResponse,
  Farm,
  Field,
  FieldActivity,
  Recommendation,
  SoilProfile,
  WeatherData,
} from "@/lib/api/types";

const RECENT_ACTIVITY_LIMIT = 5;

interface DashboardPageProps {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

function recentActivityCopy(count: number): string {
  if (count === 0) return "No field activities logged yet";
  if (count === 1) return "Your most recent logged field activity";
  return `Your last ${count} logged field ${pluralize(count, "activity", "activities")}`;
}

export default async function DashboardPage({
  searchParams,
}: DashboardPageProps) {
  const params = await searchParams;

  const farmIdParam =
    typeof params.farm === "string" ? params.farm : undefined;
  const fieldIdParam =
    typeof params.field === "string" ? params.field : undefined;

  if (!farmIdParam) {
    return (
      <div className="pb-20 sm:pb-0">
        <NoFarmSelected
          actions={[
            { label: "Go to My Farms", href: "/farms", icon: Tractor },
            { label: "Add a New Farm", href: "/onboarding", variant: "outline", icon: Plus },
          ]}
        />
      </div>
    );
  }
  const farmId: string = farmIdParam;
  const dashboardHref = `/dashboard?farm=${encodeURIComponent(farmId)}`;

  let farm: Farm;
  try {
    farm = await api.farms.get(farmId);
  } catch (err) {
    // Only a 404 means the farm is gone or not yours; other failures are errors.
    if (err instanceof ApiRequestError && err.code === 404) {
      return (
        <div className="pb-20 sm:pb-0">
          <NoFarmSelected
            title="Farm not found"
            description="This farm does not exist or you do not have access to it. Choose one of your farms."
          />
        </div>
      );
    }
    return (
      <div className="pb-20 sm:pb-0">
        <ErrorState
          card
          title="Couldn't load dashboard"
          message={err instanceof Error ? err.message : undefined}
          actions={[
            { label: "Try again", href: dashboardHref },
            { label: "Back to farms", href: "/farms", variant: "outline" },
          ]}
        />
      </div>
    );
  }

  // Farm-level data. Fields are required; credits and CSP degrade gracefully.
  let farmFields: Field[];
  let credits: CreditEligibility[];
  let cspResp: CSPEligibilityResponse | null;

  try {
    const [fieldsResp, creditsResp, cspEligibilityResp] = await Promise.all([
      api.fields.list(farmId),
      api.credits.get(farmId).catch(() => null),
      api.csp.getEligibility(farmId).catch(() => null),
    ]);
    farmFields = fieldsResp;
    credits = creditsToList(creditsResp);
    cspResp = cspEligibilityResp;
  } catch (err) {
    return (
      <div className="pb-20 sm:pb-0">
        <ErrorState
          card
          title="Couldn't load dashboard"
          message={err instanceof Error ? err.message : undefined}
          actions={[
            { label: "Try again", href: dashboardHref },
            { label: "Back to farms", href: "/farms", variant: "outline" },
          ]}
        />
      </div>
    );
  }

  // Default to first field if no field param
  const selectedField =
    farmFields.find((f) => f.id === fieldIdParam) ?? farmFields[0];

  if (!selectedField) {
    return (
      <div className="pb-20 sm:pb-0">
        <EmptyState
          card
          icon={Wheat}
          title="No fields yet"
          message={`${farm.name} has no fields. Add a field to see recommendations, weather, and soil data.`}
          actions={[
            { label: "View farm", href: `/farms/${encodeURIComponent(farmId)}` },
            { label: "Back to farms", href: "/farms", variant: "outline" },
          ]}
        />
      </div>
    );
  }

  // Field-level data for the selected field, plus recent activity across all
  // fields. Every call tolerates failure so one bad widget can't break the page.
  const [recommendations, weather, soil, cspPayments, activityLists, deadlinesResp] =
    await Promise.all([
      api.recommendations
        .list(selectedField.id)
        .catch((): Recommendation[] => []),
      api.fields.getWeather(selectedField.id).catch((): WeatherData[] => []),
      api.fields.getSoil(selectedField.id).catch((): SoilProfile | null => null),
      cspResp
        ? api.csp.getPayments(farmId).catch(() => null)
        : Promise.resolve(null),
      Promise.all(
        farmFields.map((f) =>
          api.activities
            .list(f.id, { limit: RECENT_ACTIVITY_LIMIT })
            .then((r) => r.activities.map((a) => activityToView(a, farmId, f.acres)))
            .catch((): FieldActivity[] => [])
        )
      ),
      api.csp.getDeadlines(farm.state).catch(() => null),
    ]);

  const upcomingDeadlines = adaptDeadlines(deadlinesResp);

  const recentActivities = activityLists
    .flat()
    .sort((a, b) => b.activity_date.localeCompare(a.activity_date))
    .slice(0, RECENT_ACTIVITY_LIMIT);

  const cspEligibility = cspResp
    ? adaptEligibility(cspResp, { payments: cspPayments })
    : null;

  const fieldNameMap = Object.fromEntries(
    farmFields.map((f) => [f.id, f.name])
  );

  return (
    <div className="space-y-10 pb-20 sm:pb-0">
      {/* Masthead of the record: whose farm, which sheet, how big */}
      <div className="border-b-2 border-rule-strong pb-3">
        <nav
          aria-label="Breadcrumb"
          className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground"
        >
          <Link
            href={`/farms/${encodeURIComponent(farmId)}`}
            className="transition-colors hover:text-foreground"
          >
            {farm.name}
          </Link>
          <span aria-hidden="true">&rsaquo;</span>
          <span className="font-medium text-foreground" aria-current="page">
            Dashboard
          </span>
        </nav>
        <h1 className="font-heading mt-1 text-[1.75rem] font-semibold text-foreground sm:text-3xl">
          Farm dashboard
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {farm.state} &middot;{" "}
          <span className="font-mono">
            {formatAcres(farm.total_acres, { short: true })}
          </span>{" "}
          total
        </p>
      </div>

      {/* Which field the sheet is about */}
      <div>
        <RuleHead label="Viewing field" />
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1">
          <Suspense
            fallback={
              <div className="h-12 w-full max-w-xs animate-pulse rounded-sm bg-muted" />
            }
          >
            <FieldSelector
              fields={farmFields}
              selectedFieldId={selectedField.id}
              farmId={farmId}
            />
          </Suspense>
          {selectedField.boundary_description && (
            <p className="text-xs text-muted-foreground">
              {selectedField.boundary_description}
            </p>
          )}
        </div>
      </div>

      {/* ── The decision: what to do this week ── */}
      <section aria-labelledby="recommendations-heading">
        <h2
          id="recommendations-heading"
          className="font-heading text-2xl font-semibold text-foreground"
        >
          What should I do this week?
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          For {selectedField.name}
        </p>

        <div className="mt-5 space-y-5">
          {recommendations.length === 0 ? (
            <RecommendationsEmpty farmId={farmId} />
          ) : (
            recommendations.map((rec) => (
              <RecommendationCard key={rec.id} recommendation={rec} />
            ))
          )}
        </div>
      </section>

      {/* ── The record: field conditions ── */}
      <section aria-label="Field conditions">
        <RuleHead label="Field conditions" />
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          <WeatherWidget weather={weather} />
          <SoilWidget soil={soil} />
        </div>
      </section>

      {/* ── The record: program eligibility ── */}
      <section aria-label="Program eligibility">
        <RuleHead label="Program eligibility" />
        <p className="mt-1.5 text-xs text-muted-foreground">
          Cost-share and carbon credit programs for {farm.name}
        </p>

        {/* CSP Navigator widget — only render when data is available */}
        {cspEligibility && (
          <div className="mt-3">
            <CspStatusWidget eligibility={cspEligibility} farmId={farmId} />
          </div>
        )}

        <div className="mt-1">
          <CreditPanel credits={credits} farmId={farmId} />
        </div>

        {/* Next few program deadlines for this state — hidden on error */}
        <UpcomingDeadlines deadlines={upcomingDeadlines} className="mt-6" />
      </section>

      {/* ── The record: what happened recently ── */}
      <section aria-label="Recent activity">
        <RuleHead label="Recent activity" />
        <p className="mt-1.5 text-xs text-muted-foreground">
          {recentActivityCopy(recentActivities.length)}
        </p>
        <div className="mt-3">
          <RecentActivityWidget
            activities={recentActivities}
            fieldNames={fieldNameMap}
          />
        </div>
      </section>
    </div>
  );
}
