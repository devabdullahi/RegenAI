"use client";

import { Sprout, Droplets, FlaskConical, Eye, Wheat, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ActivityType } from "@/lib/api/types";
import type { Field } from "@/lib/api/types";

const TYPE_OPTIONS: { value: ActivityType; label: string; icon: React.ElementType }[] = [
  { value: "plant", label: "Planting", icon: Sprout },
  { value: "spray", label: "Spray", icon: Droplets },
  { value: "fertilize", label: "Fertilize", icon: FlaskConical },
  { value: "scout", label: "Scouting", icon: Eye },
  { value: "harvest", label: "Harvest", icon: Wheat },
];

export interface ActivityFiltersState {
  fieldId: string | null;
  activityType: ActivityType | null;
  dateFrom: string | null;
  dateTo: string | null;
}

interface ActivityFiltersProps {
  fields: Field[];
  filters: ActivityFiltersState;
  onChange: (filters: ActivityFiltersState) => void;
}

export function ActivityFilters({ fields, filters, onChange }: ActivityFiltersProps) {
  const hasActiveFilters =
    filters.fieldId !== null ||
    filters.activityType !== null ||
    filters.dateFrom !== null ||
    filters.dateTo !== null;

  function clearAll() {
    onChange({ fieldId: null, activityType: null, dateFrom: null, dateTo: null });
  }

  return (
    <div className="space-y-4 rounded-xl border border-border bg-card px-4 py-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-foreground">Filter activities</p>
        {hasActiveFilters && (
          <button
            type="button"
            onClick={clearAll}
            className="flex min-h-[44px] items-center gap-1 rounded-lg px-2 py-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
          >
            <X className="h-3.5 w-3.5" aria-hidden="true" />
            Clear all
          </button>
        )}
      </div>

      {/* Field filter */}
      <div className="space-y-1.5">
        <label
          htmlFor="filter-field"
          className="block text-xs font-medium text-muted-foreground uppercase tracking-wide"
        >
          Field
        </label>
        <select
          id="filter-field"
          value={filters.fieldId ?? ""}
          onChange={(e) =>
            onChange({ ...filters, fieldId: e.target.value || null })
          }
          className="h-12 w-full rounded-lg border border-input bg-background px-3 text-base text-foreground focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/50"
        >
          <option value="">All fields</option>
          {fields.map((f) => (
            <option key={f.id} value={f.id}>
              {f.name} ({f.acres} ac)
            </option>
          ))}
        </select>
      </div>

      {/* Activity type filter — pill buttons */}
      <div className="space-y-1.5">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Activity type
        </p>
        <div className="flex flex-wrap gap-2">
          {TYPE_OPTIONS.map((opt) => {
            const isActive = filters.activityType === opt.value;
            const Icon = opt.icon;
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() =>
                  onChange({
                    ...filters,
                    activityType: isActive ? null : opt.value,
                  })
                }
                aria-pressed={isActive}
                className={cn(
                  "flex min-h-[44px] items-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border bg-background text-muted-foreground hover:text-foreground"
                )}
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                {opt.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Date range */}
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <label
            htmlFor="filter-date-from"
            className="block text-xs font-medium text-muted-foreground uppercase tracking-wide"
          >
            From date
          </label>
          <input
            id="filter-date-from"
            type="date"
            value={filters.dateFrom ?? ""}
            onChange={(e) =>
              onChange({ ...filters, dateFrom: e.target.value || null })
            }
            className="h-12 w-full rounded-lg border border-input bg-background px-3 text-base text-foreground focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/50"
          />
        </div>
        <div className="space-y-1.5">
          <label
            htmlFor="filter-date-to"
            className="block text-xs font-medium text-muted-foreground uppercase tracking-wide"
          >
            To date
          </label>
          <input
            id="filter-date-to"
            type="date"
            value={filters.dateTo ?? ""}
            onChange={(e) =>
              onChange({ ...filters, dateTo: e.target.value || null })
            }
            className="h-12 w-full rounded-lg border border-input bg-background px-3 text-base text-foreground focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/50"
          />
        </div>
      </div>
    </div>
  );
}
