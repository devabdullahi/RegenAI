import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  Wheat,
  Tractor,
  LayoutDashboard,
  Leaf,
  ClipboardList,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { LedgerRow, RuleHead, Stamp } from "@/components/shared/record";
import { EmptyState, ErrorState } from "@/components/shared/page-states";
import { api, ApiRequestError } from "@/lib/api/server-client";
import { formatAcres, formatDate, formatNumber } from "@/lib/format";
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

  // 404 means missing or hidden by RLS; anything else is a load failure.
  let farm: Farm;
  try {
    farm = await api.farms.get(id);
  } catch (err) {
    if (err instanceof ApiRequestError && err.code === 404) {
      return (
        <PageShell>
          <EmptyState
            icon={Tractor}
            title="Farm not found"
            message="This farm does not exist or you do not have access to it."
            actions={[{ label: "Back to My Farms", href: "/farms", icon: Tractor }]}
          />
        </PageShell>
      );
    }
    return (
      <PageShell>
        <ErrorState
          title="Couldn't load farm"
          message={err instanceof Error ? err.message : undefined}
          actions={[
            { label: "Try again", href: `/farms/${encodeURIComponent(id)}` },
            { label: "Back to farms", href: "/farms", variant: "outline" },
          ]}
        />
      </PageShell>
    );
  }

  // Fetched after the farm so a 404 short-circuits. A failure shows an error
  // in the fields section instead of a misleading "No fields yet".
  let fields: Field[] | null = null;
  let fieldsError: string | null = null;
  try {
    fields = await api.fields.list(id);
  } catch (err) {
    fieldsError = err instanceof Error ? err.message : "Failed to load fields.";
  }

  const encodedFarmId = encodeURIComponent(farm.id);

  return (
    <PageShell>
      {/* Masthead of the record: whose farm, where, how big */}
      <div className="border-b-2 border-rule-strong pb-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h1 className="font-heading text-2xl font-semibold text-foreground sm:text-3xl">
            {farm.name}
          </h1>
          {farm.goals && (
            <Badge variant="secondary" className="shrink-0">
              {GOALS_LABEL[farm.goals]}
            </Badge>
          )}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-muted-foreground">
          <span>{farm.state}</span>
          {farm.county_fips && <Stamp>FIPS {farm.county_fips}</Stamp>}
          <span className="font-mono tabular-nums">
            {formatAcres(farm.total_acres, { short: true })}
          </span>
        </div>
      </div>

      <div className="mt-8 space-y-8">
        {/* Summary figures */}
        <section aria-label="Farm summary">
          <RuleHead label="Summary" />
          <div className="mt-2 divide-y divide-border">
            <LedgerRow
              label="Total acres"
              value={`${formatNumber(farm.total_acres)} ac`}
            />
            <LedgerRow
              label="Fields"
              value={fields ? String(fields.length) : "—"}
            />
            <LedgerRow
              label="Added"
              value={formatDate(farm.created_at, {
                month: "short",
                year: "numeric",
              })}
            />
          </div>
        </section>

        {/* Quick links */}
        <section aria-label="Jump to">
          <RuleHead label="Jump to" />
          <div className="mt-1 border-t border-border">
            <QuickLink
              href={`/dashboard?farm=${encodedFarmId}`}
              icon={LayoutDashboard}
              label="Farm dashboard"
              description="Recommendations, weather, and soil"
            />
            <QuickLink
              href={`/credits?farm_id=${encodedFarmId}`}
              icon={Leaf}
              label="Credits and programs"
              description="EQIP and carbon market eligibility"
            />
            <QuickLink
              href={`/csp?farm_id=${encodedFarmId}`}
              icon={ShieldCheck}
              label="CSP Navigator"
              description="Conservation Stewardship Program"
            />
            <QuickLink
              href={`/activities?farm_id=${encodedFarmId}`}
              icon={ClipboardList}
              label="Field log"
              description="Log and review field work"
            />
          </div>
        </section>

        {/* Fields list */}
        <section aria-label="Fields">
          <RuleHead
            label={
              fields && fields.length > 0
                ? `Fields · ${fields.length}`
                : "Fields"
            }
          />

          <div className="mt-1">
            {fields === null ? (
              <ErrorState
                title="Couldn't load fields"
                message={fieldsError ?? undefined}
                actions={[{ label: "Try again", href: `/farms/${encodedFarmId}` }]}
              />
            ) : fields.length === 0 ? (
              <EmptyState
                icon={Wheat}
                title="No fields yet"
                message="Fields will appear here once they are added to this farm."
              />
            ) : (
              <ul className="border-t border-border">
                {fields.map((field) => (
                  <FieldRecord key={field.id} field={field} />
                ))}
              </ul>
            )}
          </div>
        </section>
      </div>
    </PageShell>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function PageShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="pb-20 sm:pb-0">
      <Link
        href="/farms"
        className="inline-flex min-h-12 items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        All farms
      </Link>
      {children}
    </div>
  );
}

function QuickLink({
  href,
  icon: Icon,
  label,
  description,
}: {
  href: string;
  icon: LucideIcon;
  label: string;
  description: string;
}) {
  return (
    <Link
      href={href}
      className="group flex min-h-14 items-center gap-3 border-b border-border py-3 transition-colors hover:bg-muted/40"
    >
      {/* The icon names the destination, the way a tab on a file does. */}
      <Icon className="size-4 shrink-0 text-primary" aria-hidden="true" />
      <span className="min-w-0 flex-1">
        <span className="block font-medium text-foreground">{label}</span>
        <span className="block text-xs text-muted-foreground">{description}</span>
      </span>
      <ArrowRight
        className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5"
        aria-hidden="true"
      />
    </Link>
  );
}

/** One field as a line of the plat book: name, acres, crop, practices. */
function FieldRecord({ field }: { field: Field }) {
  const practices = field.practices ?? [];

  return (
    <li className="flex flex-wrap items-baseline gap-x-4 gap-y-2 border-b border-border py-4">
      <div className="min-w-0 flex-1">
        <h3 className="font-heading text-base font-semibold text-foreground">
          {field.name}
        </h3>
        <p className="mt-0.5 font-mono text-xs tracking-[0.08em] text-muted-foreground uppercase">
          {field.crop_type}
        </p>
        {/* Legal land description (section / township / range) */}
        {field.boundary_description && (
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            {field.boundary_description}
          </p>
        )}
        {practices.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {practices.map((practice) => (
              <Stamp key={practice}>{practice}</Stamp>
            ))}
          </div>
        )}
      </div>

      <p className="font-mono text-base tabular-nums text-foreground">
        {formatAcres(field.acres, { short: true })}
      </p>
    </li>
  );
}
