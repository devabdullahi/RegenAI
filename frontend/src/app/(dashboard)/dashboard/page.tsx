import Link from "next/link";
import { Suspense } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tractor, LayoutDashboard } from "lucide-react";
import { FieldSelector } from "@/components/dashboard/field-selector";
import {
  RecommendationCard,
  RecommendationCardSkeleton,
  RecommendationsEmpty,
} from "@/components/dashboard/recommendation-card";
import { WeatherWidget } from "@/components/dashboard/weather-widget";
import { SoilWidget } from "@/components/dashboard/soil-widget";
import { CreditPanel } from "@/components/dashboard/credit-panel";
import { CspStatusWidget } from "@/components/csp/csp-status-widget";
import { RecentActivityWidget } from "@/components/activities/recent-activity-widget";

import {
  mockFarms,
  mockFields,
  mockRecommendations,
  mockSoilProfile,
  mockWeather,
  mockCredits,
} from "@/lib/mocks/farms";
import { mockCSPEligibility } from "@/lib/mocks/csp";
import { getActivitySummary } from "@/lib/mocks/activities";

interface DashboardPageProps {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

export default async function DashboardPage({
  searchParams,
}: DashboardPageProps) {
  const params = await searchParams;

  const farmId =
    typeof params.farm === "string" ? params.farm : undefined;
  const fieldIdParam =
    typeof params.field === "string" ? params.field : undefined;

  // No farm selected — prompt the user
  if (!farmId) {
    return <NoFarmSelected />;
  }

  // Look up farm
  const farm = mockFarms.find((f) => f.id === farmId);
  if (!farm) {
    return <NoFarmSelected />;
  }

  // Fields for this farm
  const farmFields = mockFields.filter((f) => f.farm_id === farmId);

  // Default to first field if no field param
  const selectedField =
    farmFields.find((f) => f.id === fieldIdParam) ?? farmFields[0];

  if (!selectedField) {
    return (
      <div className="pb-20 sm:pb-0">
        <p className="text-muted-foreground text-sm">
          No fields found for this farm.{" "}
          <Link href="/farms" className="text-primary underline">
            Back to farms
          </Link>
        </p>
      </div>
    );
  }

  // Filter mock data by selected field
  const recommendations = mockRecommendations.filter(
    (r) => r.field_id === selectedField.id
  );
  const soilProfile =
    mockSoilProfile.field_id === selectedField.id ? mockSoilProfile : null;
  const weather = mockWeather.filter(
    (w) => w.field_id === selectedField.id
  );
  const credits = mockCredits.filter((c) => c.farm_id === farmId);
  const activitySummary = getActivitySummary(farmId);
  const fieldNameMap = Object.fromEntries(
    mockFields.map((f) => [f.id, f.name])
  );

  return (
    <div className="pb-20 sm:pb-0 space-y-8">
      {/* Page header */}
      <div className="space-y-1">
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <Link href="/farms" className="hover:text-foreground transition-colors">
            {farm.name}
          </Link>
          <span>&rsaquo;</span>
          <span className="text-foreground font-medium">Dashboard</span>
        </div>
        <h1 className="font-heading text-2xl font-bold text-foreground sm:text-3xl">
          Farm Dashboard
        </h1>
        <p className="text-muted-foreground text-sm">
          {farm.state} &middot; {farm.total_acres.toLocaleString()} total acres
        </p>
      </div>

      {/* Field selector */}
      {farmFields.length > 0 && (
        <div className="rounded-xl border border-border bg-card px-4 py-3">
          <p className="mb-2 text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Viewing field
          </p>
          <Suspense
            fallback={
              <div className="h-12 w-full rounded-lg bg-muted animate-pulse" />
            }
          >
            <FieldSelector
              fields={farmFields}
              selectedFieldId={selectedField.id}
              farmId={farmId}
            />
          </Suspense>
          {selectedField.boundary_description && (
            <p className="mt-1.5 text-xs text-muted-foreground">
              {selectedField.boundary_description}
            </p>
          )}
        </div>
      )}

      {/* ── Section 1: What should I do this week? ── */}
      <section aria-labelledby="recommendations-heading">
        <div className="mb-4">
          <h2
            id="recommendations-heading"
            className="font-heading text-lg font-semibold text-foreground"
          >
            What should I do this week?
          </h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            Personalized actions for {selectedField.name}
          </p>
        </div>

        {recommendations.length === 0 ? (
          <RecommendationsEmpty />
        ) : (
          <div className="space-y-4">
            {recommendations.map((rec) => (
              <RecommendationCard key={rec.id} recommendation={rec} />
            ))}
          </div>
        )}
      </section>

      {/* ── Section 2: How's my field doing? ── */}
      <section aria-labelledby="field-status-heading">
        <div className="mb-4">
          <h2
            id="field-status-heading"
            className="font-heading text-lg font-semibold text-foreground"
          >
            How&apos;s my field doing?
          </h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            Current conditions for {selectedField.name}
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <WeatherWidget weather={weather} />
          <SoilWidget soil={soilProfile} />
        </div>
      </section>

      {/* ── Section 3: Am I eligible for programs? ── */}
      <section aria-labelledby="credits-heading">
        <div className="mb-4">
          <h2
            id="credits-heading"
            className="font-heading text-lg font-semibold text-foreground"
          >
            Am I eligible for programs?
          </h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            Cost-share and carbon credit programs for {farm.name}
          </p>
        </div>

        {/* CSP Navigator widget */}
        <div className="mb-3">
          <CspStatusWidget eligibility={mockCSPEligibility} farmId={farmId} />
        </div>

        <CreditPanel credits={credits} farmId={farmId} />
      </section>

      {/* ── Section 4: What happened recently? ── */}
      <section aria-labelledby="activity-heading">
        <div className="mb-4">
          <h2
            id="activity-heading"
            className="font-heading text-lg font-semibold text-foreground"
          >
            What happened recently?
          </h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            Your last {activitySummary.recent.length} logged field activities
          </p>
        </div>
        <RecentActivityWidget
          activities={activitySummary.recent}
          fieldNames={fieldNameMap}
        />
      </section>
    </div>
  );
}

function NoFarmSelected() {
  return (
    <div className="pb-20 sm:pb-0">
      <div className="mb-6">
        <h1 className="font-heading text-2xl font-bold text-foreground">
          Dashboard
        </h1>
        <p className="mt-1 text-muted-foreground">
          Select a farm to see your recommendations and field data.
        </p>
      </div>

      <Card className="py-12 text-center">
        <CardContent className="flex flex-col items-center gap-5">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
            <LayoutDashboard className="h-8 w-8 text-muted-foreground" />
          </div>
          <div className="max-w-sm">
            <h2 className="font-heading text-lg font-semibold text-foreground">
              No farm selected
            </h2>
            <p className="mt-1.5 text-sm text-muted-foreground leading-relaxed">
              Head to your farms list and tap a farm to open its dashboard with
              recommendations, weather, and program eligibility.
            </p>
          </div>
          <div className="flex flex-col gap-3 w-full max-w-xs">
            <Link href="/farms">
              <Button className="w-full min-h-[48px] bg-primary text-primary-foreground hover:bg-primary/90 cursor-pointer">
                <Tractor className="mr-2 h-4 w-4" />
                Go to My Farms
              </Button>
            </Link>
            <Link href="/onboarding">
              <Button
                variant="outline"
                className="w-full min-h-[48px] cursor-pointer"
              >
                Add a New Farm
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
