"use client";

import { useState, useMemo, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  ClipboardList,
  Plus,
  Sprout,
  Droplets,
  FlaskConical,
  Eye,
  Wheat,
  Shovel,
  Leaf,
  AlertCircle,
  Loader2,
} from "lucide-react";
import { ActivityCard } from "@/components/activities/activity-card";
import { ActivityFilters } from "@/components/activities/activity-filters";
import type { ActivityFiltersState } from "@/components/activities/activity-filters";
import { api } from "@/lib/api/client";
import type { FieldActivity, Field, ActivityType } from "@/lib/api/types";

// ── FE-011: All activity types including tillage and cover_crop ───────────────

const TYPE_ICONS: Record<ActivityType, React.ElementType> = {
  plant: Sprout,
  spray: Droplets,
  fertilize: FlaskConical,
  scout: Eye,
  harvest: Wheat,
  tillage: Shovel,
  cover_crop: Leaf,
  other: ClipboardList,
};

/** Default zero-count seed for all known activity types. */
const TYPE_COUNTS: Record<ActivityType, number> = {
  plant: 0,
  spray: 0,
  fertilize: 0,
  scout: 0,
  harvest: 0,
  tillage: 0,
  cover_crop: 0,
  other: 0,
};

const TYPE_COLORS: Record<ActivityType, string> = {
  plant: "bg-green-100 text-green-700",
  spray: "bg-blue-100 text-blue-700",
  fertilize: "bg-amber-100 text-amber-700",
  scout: "bg-purple-100 text-purple-700",
  harvest: "bg-orange-100 text-orange-700",
  tillage: "bg-stone-100 text-stone-700",
  cover_crop: "bg-teal-100 text-teal-700",
  other: "bg-gray-100 text-gray-700",
};

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ActivitiesPage() {
  const [filters, setFilters] = useState<ActivityFiltersState>({
    fieldId: null,
    activityType: null,
    dateFrom: null,
    dateTo: null,
  });
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

      try {
        const [summary, farmFields] = await Promise.all([
          api.activities.list(farmId),
          api.fields.list(farmId),
        ]);

        if (!cancelled) {
          // Sort newest first
          const sorted = [...summary.recent].sort(
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

  // Count per type for the quick-stat row — seeded from TYPE_COUNTS so every
  // type (including tillage and cover_crop) always has an entry.
  const typeCounts = useMemo(() => {
    const counts: Record<ActivityType, number> = { ...TYPE_COUNTS };
    activities.forEach((a) => {
      counts[a.activity_type] = (counts[a.activity_type] ?? 0) + 1;
    });
    return counts;
  }, [activities]);

  const activeFilterCount = Object.values(filters).filter(Boolean).length;

  // ── No farm selected ─────────────────────────────────────────────────────────

  if (!farmId && !loading) {
    return (
      <div className="pb-20 sm:pb-0 space-y-6">
        <div className="flex items-center gap-2 mb-1">
          <ClipboardList className="h-5 w-5 text-primary" aria-hidden="true" />
          <h1 className="font-heading text-2xl font-bold text-foreground sm:text-3xl">
            Field Activity Log
          </h1>
        </div>
        <div className="rounded-xl border border-border bg-card px-6 py-12 text-center">
          <ClipboardList
            className="mx-auto mb-3 h-10 w-10 text-muted-foreground"
            aria-hidden="true"
          />
          <p className="font-heading text-base font-semibold text-foreground">
            Select a farm to view activities
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            Choose a farm to see its field activity log.
          </p>
          <Link href="/farms">
            <button
              type="button"
              className="mt-4 min-h-[48px] rounded-lg bg-primary px-6 py-2 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
            >
              Go to My Farms
            </button>
          </Link>
        </div>
      </div>
    );
  }

  // ── Loading ───────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="pb-20 sm:pb-0 space-y-6">
        <div className="flex items-center gap-2">
          <ClipboardList className="h-5 w-5 text-primary" aria-hidden="true" />
          <h1 className="font-heading text-2xl font-bold text-foreground sm:text-3xl">
            Field Activity Log
          </h1>
        </div>
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
      <div className="pb-20 sm:pb-0 space-y-6">
        <div className="flex items-center gap-2">
          <ClipboardList className="h-5 w-5 text-primary" aria-hidden="true" />
          <h1 className="font-heading text-2xl font-bold text-foreground sm:text-3xl">
            Field Activity Log
          </h1>
        </div>
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 px-6 py-10 text-center">
          <AlertCircle
            className="mx-auto mb-3 h-9 w-9 text-destructive"
            aria-hidden="true"
          />
          <p className="font-heading text-base font-semibold text-foreground">
            Could not load activities
          </p>
          <p className="mt-1 text-sm text-muted-foreground">{error}</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-4 min-h-[48px] rounded-lg border border-border px-5 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  // ── Main content ──────────────────────────────────────────────────────────────

  return (
    <div className="pb-20 sm:pb-0 space-y-6">
      {/* Page header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <ClipboardList
              className="h-5 w-5 text-primary"
              aria-hidden="true"
            />
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

      {/* Quick count strip — only shown when there are activities */}
      {activities.length > 0 && (
        <div className="grid grid-cols-4 lg:grid-cols-8 gap-2">
          {(Object.entries(typeCounts) as [ActivityType, number][]).map(
            ([type, count]) => {
              const Icon = TYPE_ICONS[type] ?? ClipboardList;
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
                      ? `${TYPE_COLORS[type] ?? "bg-gray-100 text-gray-700"} border-current`
                      : "border-border bg-card hover:bg-muted"
                  }`}
                >
                  <Icon className="h-5 w-5" aria-hidden="true" />
                  <span className="text-sm font-bold">{count}</span>
                  <span className="text-[10px] text-muted-foreground leading-none capitalize">
                    {type.replace("_", " ")}
                  </span>
                </button>
              );
            }
          )}
        </div>
      )}

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
              fields={fields}
              filters={filters}
              onChange={setFilters}
            />
          </div>
        )}
      </div>

      {/* Results count */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {filtered.length === activities.length
            ? `${filtered.length} activities`
            : `${filtered.length} of ${activities.length} activities`}
        </p>
        <Link
          href={farmId ? `/yield-history?farm_id=${farmId}` : "/yield-history"}
          className="text-sm font-medium text-primary hover:underline"
        >
          View yield history
        </Link>
      </div>

      {/* Timeline */}
      {filtered.length === 0 ? (
        <div className="rounded-xl border border-border bg-card px-6 py-12 text-center">
          <ClipboardList
            className="mx-auto mb-3 h-10 w-10 text-muted-foreground"
            aria-hidden="true"
          />
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
