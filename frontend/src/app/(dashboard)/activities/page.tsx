"use client";

import { useState, useMemo, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { ClipboardList, Loader2, Plus } from "lucide-react";
import { ActivityRow } from "@/components/activities/activity-row";
import { ActivityFilters } from "@/components/activities/activity-filters";
import type { ActivityFiltersState } from "@/components/activities/activity-filters";
import { ButtonLink } from "@/components/shared/button-link";
import { RuleHead } from "@/components/shared/record";
import {
  EmptyState,
  ErrorState,
  NoFarmSelected,
} from "@/components/shared/page-states";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/client";
import { activityToView } from "@/lib/api/adapters";
import {
  emptyActivityTypeCounts,
  getActivityTypeConfig,
} from "@/lib/activity-types";
import { pluralize } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { FieldActivity, Field, ActivityType } from "@/lib/api/types";

/** Max rows per field (backend limit is 200). */
const ACTIVITIES_PER_FIELD = 200;

const EMPTY_FILTERS: ActivityFiltersState = {
  fieldId: null,
  activityType: null,
  dateFrom: null,
  dateTo: null,
};

/** Masthead of the log sheet: one title, one primary action. */
function LogHeading({
  subtitle,
  newActivityHref,
}: {
  subtitle?: string;
  newActivityHref?: string;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3 border-b-2 border-rule-strong pb-3">
      <div>
        <h1 className="font-heading text-2xl font-semibold text-foreground sm:text-3xl">
          Field log
        </h1>
        {subtitle && (
          <p className="mt-1 font-mono text-[0.6875rem] tracking-[0.12em] text-muted-foreground uppercase">
            {subtitle}
          </p>
        )}
      </div>
      {newActivityHref && (
        <ButtonLink href={newActivityHref}>
          <Plus aria-hidden="true" />
          Log activity
        </ButtonLink>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ActivitiesPage() {
  const [filters, setFilters] = useState<ActivityFiltersState>(EMPTY_FILTERS);
  const [showFilters, setShowFilters] = useState(false);

  const [activities, setActivities] = useState<FieldActivity[]>([]);
  const [fields, setFields] = useState<Field[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Determine farm_id from current URL searchParams
  const searchParams = useSearchParams();
  const farmId = searchParams.get("farm_id") ?? searchParams.get("farm");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);

      if (!farmId) {
        setLoading(false);
        return;
      }

      const currentFarmId: string = farmId;

      try {
        // The backend lists activities per field (GET /activities?field_id=),
        // so fetch the farm's fields first and then each field's activities.
        const farmFields = await api.fields.list(currentFarmId);
        const perField = await Promise.all(
          farmFields.map((f) =>
            api.activities
              .list(f.id, { limit: ACTIVITIES_PER_FIELD })
              .then((r) =>
                r.activities.map((a) => activityToView(a, currentFarmId, f.acres))
              )
          )
        );

        if (!cancelled) {
          // Sort newest first
          const sorted = perField.flat().sort(
            (a, b) =>
              new Date(b.activity_date).getTime() -
              new Date(a.activity_date).getTime()
          );
          setActivities(sorted);
          setFields(farmFields);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load activities. Please try again."
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, [farmId]);

  const fieldMap = useMemo(
    () => Object.fromEntries(fields.map((f) => [f.id, f])),
    [fields]
  );

  const filtered = useMemo(() => {
    return activities.filter((a) => {
      if (filters.fieldId && a.field_id !== filters.fieldId) return false;
      if (filters.activityType && a.activity_type !== filters.activityType)
        return false;
      if (filters.dateFrom && a.activity_date < filters.dateFrom) return false;
      if (filters.dateTo && a.activity_date > filters.dateTo) return false;
      return true;
    });
  }, [activities, filters]);

  // Count per type for the quick-stat row, seeded so every type has an entry.
  const typeCounts = useMemo(() => {
    const counts = emptyActivityTypeCounts();
    activities.forEach((a) => {
      counts[a.activity_type] = (counts[a.activity_type] ?? 0) + 1;
    });
    return counts;
  }, [activities]);

  const activeFilterCount = Object.values(filters).filter(Boolean).length;
  const newActivityHref = farmId
    ? `/activities/new?farm_id=${encodeURIComponent(farmId)}`
    : "/activities/new";

  // ── No farm selected ─────────────────────────────────────────────────────────

  if (!farmId && !loading) {
    return (
      <div className="pb-20 sm:pb-0">
        <LogHeading />
        <NoFarmSelected description="Choose a farm to see its field log." />
      </div>
    );
  }

  // ── Loading ───────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="pb-20 sm:pb-0">
        <LogHeading />
        <div className="flex items-center justify-center py-20">
          <Loader2
            className="h-8 w-8 animate-spin text-muted-foreground"
            aria-label="Loading activities"
          />
        </div>
      </div>
    );
  }

  // ── Error ─────────────────────────────────────────────────────────────────────

  if (error) {
    return (
      <div className="pb-20 sm:pb-0">
        <LogHeading />
        <ErrorState
          title="Couldn't load your field log"
          message={error}
          actions={[]}
        >
          <Button variant="outline" onClick={() => window.location.reload()}>
            Try again
          </Button>
        </ErrorState>
      </div>
    );
  }

  // ── Main content ──────────────────────────────────────────────────────────────

  const totalLabel = `${activities.length} ${pluralize(
    activities.length,
    "entry",
    "entries"
  )} on record`;

  return (
    <div className="pb-20 sm:pb-0">
      <LogHeading
        subtitle={activities.length > 0 ? totalLabel : undefined}
        newActivityHref={newActivityHref}
      />

      <div className="space-y-6">
        {/* Count strip — each column filters the log to that kind of work */}
        {activities.length > 0 && (
          <div>
            <RuleHead label="By kind of work" />
            <div className="mt-2 flex divide-x divide-border overflow-x-auto border-y border-border">
              {(Object.entries(typeCounts) as [ActivityType, number][]).map(
                ([type, count]) => {
                  const typeConfig = getActivityTypeConfig(type);
                  const Icon = typeConfig.icon;
                  const isActive = filters.activityType === type;
                  return (
                    <button
                      key={type}
                      type="button"
                      onClick={() =>
                        setFilters((f) => ({
                          ...f,
                          activityType: f.activityType === type ? null : type,
                        }))
                      }
                      aria-pressed={isActive}
                      className={cn(
                        "flex min-w-[76px] flex-1 flex-col items-center justify-center gap-1 px-2 py-3 text-center transition-colors",
                        isActive ? "bg-muted" : "hover:bg-muted/50"
                      )}
                    >
                      <Icon
                        className={cn("h-4 w-4", typeConfig.markerClasses)}
                        aria-hidden="true"
                      />
                      <span className="font-mono text-sm font-medium tabular-nums text-foreground">
                        {count}
                      </span>
                      <span className="font-mono text-[0.6875rem] leading-tight tracking-[0.08em] text-muted-foreground uppercase">
                        {typeConfig.label}
                      </span>
                    </button>
                  );
                }
              )}
            </div>
          </div>
        )}

        {/* Filters */}
        <div>
          <Button
            variant="outline"
            onClick={() => setShowFilters((v) => !v)}
            aria-expanded={showFilters}
          >
            {showFilters ? "Hide filters" : "Show filters"}
            {activeFilterCount > 0 && (
              <span className="font-mono tabular-nums">({activeFilterCount})</span>
            )}
          </Button>

          {showFilters && (
            <div className="mt-3">
              <ActivityFilters
                fields={fields}
                filters={filters}
                onChange={setFilters}
              />
            </div>
          )}
        </div>

        {/* Results count */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="font-mono text-xs tracking-[0.08em] text-muted-foreground uppercase">
            {filtered.length === activities.length
              ? `${filtered.length} shown`
              : `${filtered.length} of ${activities.length} shown`}
          </p>
          <Link
            href={
              farmId
                ? `/yield-history?farm_id=${encodeURIComponent(farmId)}`
                : "/yield-history"
            }
            className="inline-flex min-h-12 items-center text-sm font-medium text-primary hover:underline"
          >
            View yield history
          </Link>
        </div>

        {/* The log */}
        {filtered.length === 0 ? (
          <EmptyState
            icon={ClipboardList}
            title={
              activities.length === 0
                ? "Nothing logged yet"
                : "No entries match your filters"
            }
            message={
              activities.length === 0
                ? "Log what happens on the farm and it shows up here, newest first."
                : "Try adjusting or clearing your filters."
            }
          >
            {activities.length === 0 ? (
              <ButtonLink href={newActivityHref}>
                <Plus aria-hidden="true" />
                Log activity
              </ButtonLink>
            ) : (
              <Button variant="outline" onClick={() => setFilters(EMPTY_FILTERS)}>
                Clear filters
              </Button>
            )}
          </EmptyState>
        ) : (
          <div
            className="border-t border-border"
            role="list"
            aria-label="Field log entries"
          >
            {filtered.map((activity) => {
              const field = fieldMap[activity.field_id];
              return (
                <div key={activity.id} role="listitem">
                  <ActivityRow
                    activity={activity}
                    fieldName={field?.name ?? activity.field_id}
                  />
                </div>
              );
            })}
          </div>
        )}

        {/* Add another line to the log without scrolling back up */}
        {filtered.length > 0 && (
          <div className="border-t border-border pt-4">
            <ButtonLink href={newActivityHref} variant="outline">
              <Plus aria-hidden="true" />
              Log activity
            </ButtonLink>
          </div>
        )}
      </div>
    </div>
  );
}
