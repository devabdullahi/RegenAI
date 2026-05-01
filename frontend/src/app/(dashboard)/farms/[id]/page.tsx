import Link from "next/link";
import { ArrowLeft, MapPin, Wheat, Tractor, AlertCircle, LayoutDashboard, Leaf, ClipboardList } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { api, ApiRequestError } from "@/lib/api/server-client";
import type { Farm, Field } from "@/lib/api/types";
import type { Metadata } from "next";

// ── Metadata ──────────────────────────────────────────────────────────────────

export const metadata: Metadata = {
  title: "Farm Detail — RegenAI",
  description: "View farm summary, fields, and quick links to programs.",
};

// ── Goals label map ───────────────────────────────────────────────────────────

const GOALS_LABEL: Record<NonNullable<Farm["goals"]>, string> = {
  cost_savings: "Cost Savings",
  carbon_credits: "Carbon Credits",
  both: "Cost Savings & Carbon Credits",
};

// ── Page ──────────────────────────────────────────────────────────────────────

export default async function FarmDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  // Attempt to fetch the farm — treat 404 specially, re-throw everything else
  let farm: Farm;
  try {
    farm = await api.farms.get(id);
  } catch (err) {
    if (err instanceof ApiRequestError && err.code === 404) {
      return <FarmNotFound />;
    }
    const message =
      err instanceof Error ? err.message : "Failed to load farm.";
    return <FarmLoadError message={message} />;
  }

  // Fetch fields concurrently — missing fields is non-fatal
  let fields: Field[] = [];
  try {
    fields = await api.fields.list(id);
  } catch {
    // Render the page without fields rather than blocking the whole view
  }

  return (
    <div className="pb-20 sm:pb-0 space-y-8">
      {/* Back link */}
      <div>
        <Link
          href="/farms"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          All farms
        </Link>
      </div>

      {/* Farm summary card */}
      <section aria-labelledby="farm-summary-heading">
        <Card>
          <CardHeader className="pb-3">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-primary/10">
                  <Tractor className="h-6 w-6 text-primary" aria-hidden="true" />
                </div>
                <div>
                  <CardTitle
                    id="farm-summary-heading"
                    className="font-heading text-xl leading-tight"
                  >
                    {farm.name}
                  </CardTitle>
                  <CardDescription className="flex items-center gap-1 mt-0.5">
                    <MapPin className="h-3.5 w-3.5" aria-hidden="true" />
                    {farm.state}
                    {farm.county_fips && (
                      <span className="text-muted-foreground/60">
                        &nbsp;&middot; FIPS {farm.county_fips}
                      </span>
                    )}
                  </CardDescription>
                </div>
              </div>
              {farm.goals && (
                <Badge variant="secondary" className="shrink-0 self-start">
                  {GOALS_LABEL[farm.goals]}
                </Badge>
              )}
            </div>
          </CardHeader>

          <CardContent className="space-y-4">
            {/* Key stats row */}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <StatTile label="Total acres" value={farm.total_acres.toLocaleString()} />
              <StatTile label="Fields" value={String(fields.length)} />
              <StatTile
                label="Added"
                value={new Date(farm.created_at).toLocaleDateString("en-US", {
                  month: "short",
                  year: "numeric",
                })}
                className="col-span-2 sm:col-span-1"
              />
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Quick-link action buttons */}
      <section aria-labelledby="quick-links-heading">
        <h2
          id="quick-links-heading"
          className="font-heading text-lg font-semibold text-foreground mb-3"
        >
          Jump to
        </h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <QuickLink
            href={`/credits?farm_id=${farm.id}`}
            icon={<Leaf className="h-5 w-5" aria-hidden="true" />}
            label="Credits & Programs"
            description="EQIP and carbon market eligibility"
          />
          <QuickLink
            href={`/csp?farm_id=${farm.id}`}
            icon={<LayoutDashboard className="h-5 w-5" aria-hidden="true" />}
            label="CSP Navigator"
            description="Conservation Stewardship Program"
          />
          <QuickLink
            href={`/activities?farm_id=${farm.id}`}
            icon={<ClipboardList className="h-5 w-5" aria-hidden="true" />}
            label="Field Activities"
            description="Log and review field work"
          />
        </div>
      </section>

      {/* Fields list */}
      <section aria-labelledby="fields-heading">
        <div className="mb-4 flex items-center justify-between">
          <h2
            id="fields-heading"
            className="font-heading text-lg font-semibold text-foreground"
          >
            Fields
            {fields.length > 0 && (
              <span className="ml-2 text-base font-normal text-muted-foreground">
                ({fields.length})
              </span>
            )}
          </h2>
        </div>

        {fields.length === 0 ? (
          <Card className="py-10 text-center">
            <CardContent className="flex flex-col items-center gap-4">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-muted">
                <Wheat className="h-7 w-7 text-muted-foreground" aria-hidden="true" />
              </div>
              <div>
                <p className="font-medium text-foreground">No fields yet</p>
                <p className="mt-1 text-sm text-muted-foreground max-w-xs mx-auto leading-relaxed">
                  Fields will appear here once they are added to this farm.
                </p>
              </div>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {fields.map((field) => (
              <FieldCard key={field.id} field={field} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatTile({
  label,
  value,
  className,
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div
      className={[
        "rounded-xl border border-border bg-muted/40 px-4 py-3",
        className ?? "",
      ]
        .join(" ")
        .trim()}
    >
      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
        {label}
      </p>
      <p className="mt-1 text-xl font-bold text-foreground leading-tight">
        {value}
      </p>
    </div>
  );
}

function QuickLink({
  href,
  icon,
  label,
  description,
}: {
  href: string;
  icon: React.ReactNode;
  label: string;
  description: string;
}) {
  return (
    <Link href={href} className="group block">
      <div className="flex min-h-[72px] items-center gap-4 rounded-xl border border-border bg-card px-4 py-4 transition-shadow group-hover:shadow-md">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
          {icon}
        </div>
        <div className="min-w-0">
          <p className="font-medium text-foreground leading-snug">
            {label}
          </p>
          <p className="text-xs text-muted-foreground mt-0.5 leading-snug">
            {description}
          </p>
        </div>
        <ArrowLeft
          className="ml-auto h-4 w-4 shrink-0 rotate-180 text-muted-foreground/50 transition-transform group-hover:translate-x-0.5"
          aria-hidden="true"
        />
      </div>
    </Link>
  );
}

function FieldCard({ field }: { field: Field }) {
  // Derive a soil texture hint from practices if a direct soil type isn't stored
  const practices = field.practices ?? [];

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base font-semibold font-heading">
          <Wheat className="h-4 w-4 text-primary shrink-0" aria-hidden="true" />
          {field.name}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Primary field stats */}
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline">{field.acres.toLocaleString()} ac</Badge>
          <Badge variant="secondary">{field.crop_type}</Badge>
        </div>

        {/* Boundary description (acts as human-readable soil/location info) */}
        {field.boundary_description && (
          <p className="text-xs text-muted-foreground leading-relaxed">
            {field.boundary_description}
          </p>
        )}

        {/* Practices */}
        {practices.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {practices.map((practice) => (
              <Badge key={practice} variant="outline" className="text-xs">
                {practice}
              </Badge>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── Error / not-found states ──────────────────────────────────────────────────

function FarmNotFound() {
  return (
    <div className="pb-20 sm:pb-0">
      <div className="mb-4">
        <Link
          href="/farms"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          All farms
        </Link>
      </div>
      <Card className="py-12 text-center">
        <CardContent className="flex flex-col items-center gap-5">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
            <Tractor className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
          </div>
          <div className="max-w-sm">
            <h1 className="font-heading text-lg font-semibold text-foreground">
              Farm not found
            </h1>
            <p className="mt-1.5 text-sm text-muted-foreground leading-relaxed">
              This farm does not exist or you do not have access to it. Head
              back to your farms list to find the right one.
            </p>
          </div>
          <Link href="/farms">
            <Button className="min-h-[48px] bg-primary text-primary-foreground hover:bg-primary/90 cursor-pointer">
              <Tractor className="mr-2 h-4 w-4" aria-hidden="true" />
              Back to My Farms
            </Button>
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}

function FarmLoadError({ message }: { message: string }) {
  return (
    <div className="pb-20 sm:pb-0">
      <div className="mb-4">
        <Link
          href="/farms"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          All farms
        </Link>
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
            <h1 className="font-heading text-lg font-semibold text-foreground">
              Could not load farm
            </h1>
            <p className="mt-1.5 text-sm text-muted-foreground leading-relaxed">
              {message}
            </p>
          </div>
          <div className="flex flex-col gap-2 w-full max-w-xs">
            <Link href="/farms">
              <Button
                variant="outline"
                className="w-full min-h-[48px] cursor-pointer"
              >
                Back to farms
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
