"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { ClipboardList, Plus, Sprout, Droplets, FlaskConical, Eye, Wheat } from "lucide-react";
import { ActivityCard } from "@/components/activities/activity-card";
import { ActivityFilters } from "@/components/activities/activity-filters";
import type { ActivityFiltersState } from "@/components/activities/activity-filters";
import { mockActivitiesSorted } from "@/lib/mocks/activities";
import { mockFields } from "@/lib/mocks/farms";
import type { ActivityType, SprayDetails } from "@/lib/api/types";

const TYPE_ICONS: Record<ActivityType, React.ElementType> = {
  plant: Sprout,
  spray: Droplets,
  fertilize: FlaskConical,
  scout: Eye,
  harvest: Wheat,
};

const TYPE_COUNTS: Record<ActivityType, string> = {
  plant: "bg-green-100 text-green-700",
  spray: "bg-blue-100 text-blue-700",
  fertilize: "bg-amber-100 text-amber-700",
  scout: "bg-purple-100 text-purple-700",
  harvest: "bg-orange-100 text-orange-700",
};

export default function ActivitiesPage() {
  const [filters, setFilters] = useState<ActivityFiltersState>({
    fieldId: null,
    activityType: null,
    dateFrom: null,
    dateTo: null,
  });
  const [showFilters, setShowFilters] = useState(false);

  const fieldMap = useMemo(
    () => Object.fromEntries(mockFields.map((f) => [f.id, f])),
    []
  );

  const filtered = useMemo(() => {
    return mockActivitiesSorted.filter((a) => {
      if (filters.fieldId && a.field_id !== filters.fieldId) return false;
      if (filters.activityType && a.activity_type !== filters.activityType) return false;
      if (filters.dateFrom && a.activity_date < filters.dateFrom) return false;
      if (filters.dateTo && a.activity_date > filters.dateTo) return false;
      return true;
    });
  }, [filters]);

  // Count per type for the quick-stat row
  const typeCounts = useMemo(() => {
    const counts: Partial<Record<ActivityType, number>> = {};
    mockActivitiesSorted.forEach((a) => {
      counts[a.activity_type] = (counts[a.activity_type] ?? 0) + 1;
    });
    return counts;
  }, []);

  const activeFilterCount = Object.values(filters).filter(Boolean).length;

  return (
    <div className="pb-20 sm:pb-0 space-y-6">
      {/* Page header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <ClipboardList className="h-5 w-5 text-primary" aria-hidden="true" />
            <h1 className="font-heading text-2xl font-bold text-foreground sm:text-3xl">
              Field Activity Log
            </h1>
          </div>
          <p className="text-sm text-muted-foreground max-w-prose">
            Everything that happens on your farm, in one place. Tap any record
            to see full details.
          </p>
        </div>

        <Link href="/activities/new">
          <button
            type="button"
            className="flex min-h-[52px] items-center gap-2 rounded-xl bg-accent px-5 py-3 text-base font-semibold text-accent-foreground transition-colors hover:bg-accent/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Plus className="h-5 w-5" aria-hidden="true" />
            Log Activity
          </button>
        </Link>
      </div>

      {/* Quick count strip */}
      <div className="grid grid-cols-5 gap-2">
        {(Object.entries(typeCounts) as [ActivityType, number][]).map(
          ([type, count]) => {
            const Icon = TYPE_ICONS[type];
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
                aria-pressed={filters.activityType === type}
                className={`flex flex-col items-center justify-center gap-1 rounded-xl border-2 py-3 px-2 text-center transition-all ${
                  filters.activityType === type
                    ? `${TYPE_COUNTS[type]} border-current`
                    : "border-border bg-card hover:bg-muted"
                }`}
              >
                <Icon className="h-5 w-5" aria-hidden="true" />
                <span className="text-sm font-bold">{count}</span>
                <span className="text-[10px] text-muted-foreground leading-none capitalize">
                  {type}
                </span>
              </button>
            );
          }
        )}
      </div>

      {/* Filter toggle */}
      <div>
        <button
          type="button"
          onClick={() => setShowFilters((v) => !v)}
          className="flex min-h-[48px] items-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
          aria-expanded={showFilters}
        >
          {showFilters ? "Hide filters" : "Show filters"}
          {activeFilterCount > 0 && (
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
              {activeFilterCount}
            </span>
          )}
        </button>

        {showFilters && (
          <div className="mt-3">
            <ActivityFilters
              fields={mockFields}
              filters={filters}
              onChange={setFilters}
            />
          </div>
        )}
      </div>

      {/* Results count */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {filtered.length === mockActivitiesSorted.length
            ? `${filtered.length} activities`
            : `${filtered.length} of ${mockActivitiesSorted.length} activities`}
        </p>
        <Link
          href="/yield-history"
          className="text-sm font-medium text-primary hover:underline"
        >
          View yield history
        </Link>
      </div>

      {/* Timeline */}
      {filtered.length === 0 ? (
        <div className="rounded-xl border border-border bg-card px-6 py-12 text-center">
          <ClipboardList className="mx-auto mb-3 h-10 w-10 text-muted-foreground" aria-hidden="true" />
          <p className="font-heading text-base font-semibold text-foreground">
            No activities match your filters
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            Try adjusting or clearing your filters.
          </p>
          <button
            type="button"
            onClick={() =>
              setFilters({
                fieldId: null,
                activityType: null,
                dateFrom: null,
                dateTo: null,
              })
            }
            className="mt-4 min-h-[48px] rounded-lg border border-border px-5 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
          >
            Clear filters
          </button>
        </div>
      ) : (
        <div className="space-y-4" role="list" aria-label="Activity timeline">
          {filtered.map((activity) => {
            const field = fieldMap[activity.field_id];
            return (
              <div key={activity.id} role="listitem">
                <ActivityCard
                  activity={activity}
                  fieldName={field?.name ?? activity.field_id}
                />
              </div>
            );
          })}
        </div>
      )}

      {/* Log activity CTA at bottom */}
      <div className="rounded-xl border border-dashed border-primary/30 bg-primary/5 px-4 py-6 text-center">
        <p className="text-sm font-medium text-foreground mb-3">
          Something happen today on the farm?
        </p>
        <Link href="/activities/new">
          <button
            type="button"
            className="min-h-[52px] rounded-xl bg-primary px-8 py-3 text-base font-semibold text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Plus className="mr-2 inline-block h-5 w-5 align-middle" aria-hidden="true" />
            Log an Activity
          </button>
        </Link>
      </div>
    </div>
  );
}
