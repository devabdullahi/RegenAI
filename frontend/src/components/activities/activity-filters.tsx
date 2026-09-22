"use client";

import { X } from "lucide-react";
import { RuleHead, Sheet } from "@/components/shared/record";
import { Label } from "@/components/ui/label";
import { ACTIVITY_TYPES } from "@/lib/activity-types";
import { formatAcres } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ActivityType, Field } from "@/lib/api/types";

export interface ActivityFiltersState {
  fieldId: string | null;
  activityType: ActivityType | null;
  dateFrom: string | null;
  dateTo: string | null;
}

export const EMPTY_ACTIVITY_FILTERS: ActivityFiltersState = {
  fieldId: null,
  activityType: null,
  dateFrom: null,
  dateTo: null,
};

interface ActivityFiltersProps {
  fields: Field[];
  filters: ActivityFiltersState;
  onChange: (filters: ActivityFiltersState) => void;
}

/** A blank on the sheet: ruled box, cut corners, figures in mono. */
const fieldInputClasses =
  "h-12 w-full rounded-sm border border-input bg-card px-3 text-base text-foreground transition-colors outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40";

export function ActivityFilters({ fields, filters, onChange }: ActivityFiltersProps) {
  const hasActiveFilters = Object.values(filters).some((v) => v !== null);

  return (
    <Sheet className="space-y-4 px-4 py-4">
      <RuleHead
        label="Filter activities"
        action={
          hasActiveFilters ? (
            <button
              type="button"
              onClick={() => onChange(EMPTY_ACTIVITY_FILTERS)}
              className="flex min-h-12 items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              <X className="h-4 w-4" aria-hidden="true" />
              Clear all
            </button>
          ) : undefined
        }
      />

      <div className="space-y-1.5">
        <Label htmlFor="filter-field">Field</Label>
        <select
          id="filter-field"
          value={filters.fieldId ?? ""}
          onChange={(e) => onChange({ ...filters, fieldId: e.target.value || null })}
          className={fieldInputClasses}
        >
          <option value="">All fields</option>
          {fields.map((f) => (
            <option key={f.id} value={f.id}>
              {f.name} ({formatAcres(f.acres, { short: true })})
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-1.5">
        <p
          id="filter-type-label"
          className="font-mono text-xs font-medium tracking-[0.1em] text-muted-foreground uppercase"
        >
          Activity type
        </p>
        <div role="group" aria-labelledby="filter-type-label" className="flex flex-wrap gap-2">
          {ACTIVITY_TYPES.map((config) => {
            const isActive = filters.activityType === config.id;
            const Icon = config.icon;
            return (
              <button
                key={config.id}
                type="button"
                onClick={() =>
                  onChange({ ...filters, activityType: isActive ? null : config.id })
                }
                aria-pressed={isActive}
                className={cn(
                  "flex min-h-12 items-center gap-1.5 rounded-sm border px-3 py-2 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                  isActive
                    ? "border-foreground bg-muted text-foreground"
                    : "border-border bg-card text-muted-foreground hover:text-foreground"
                )}
              >
                <Icon
                  className={cn("h-4 w-4 shrink-0", config.markerClasses)}
                  aria-hidden="true"
                />
                {config.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="filter-date-from">From date</Label>
          <input
            id="filter-date-from"
            type="date"
            value={filters.dateFrom ?? ""}
            onChange={(e) => onChange({ ...filters, dateFrom: e.target.value || null })}
            className={cn(fieldInputClasses, "font-mono")}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="filter-date-to">To date</Label>
          <input
            id="filter-date-to"
            type="date"
            value={filters.dateTo ?? ""}
            onChange={(e) => onChange({ ...filters, dateTo: e.target.value || null })}
            className={cn(fieldInputClasses, "font-mono")}
          />
        </div>
      </div>
    </Sheet>
  );
}
