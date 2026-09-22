"use client";

import { ACTIVITY_TYPES } from "@/lib/activity-types";
import { cn } from "@/lib/utils";
import type { ActivityType } from "@/lib/api/types";

const DESCRIPTIONS: Record<ActivityType, string> = {
  plant: "Record what you put in the ground",
  spray: "Herbicide, insecticide, or fungicide",
  fertilize: "Nitrogen, phosphorus, potassium",
  scout: "Pest, disease, or weed check",
  harvest: "Yield, moisture, and ticket info",
  tillage: "Chisel, disk, strip-till, or other passes",
  cover_crop: "Seeding a cover crop",
  other: "Anything else worth recording",
};

interface ActivityTypePickerProps {
  value: ActivityType | null;
  onChange: (type: ActivityType) => void;
}

export function ActivityTypePicker({ value, onChange }: ActivityTypePickerProps) {
  return (
    <fieldset>
      <legend className="sr-only">Select activity type</legend>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {ACTIVITY_TYPES.map((config) => {
          const isSelected = value === config.id;
          const Icon = config.icon;
          return (
            <button
              key={config.id}
              type="button"
              onClick={() => onChange(config.id)}
              aria-pressed={isSelected}
              className={cn(
                "flex min-h-[64px] items-start gap-3 rounded-sm border px-4 py-3 text-left transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                isSelected
                  ? "border-foreground bg-muted"
                  : "border-border bg-card hover:bg-muted/50"
              )}
            >
              {/* The mark helps a farmer find the right kind of work quickly. */}
              <Icon
                className={cn("mt-0.5 size-5 shrink-0", config.markerClasses)}
                aria-hidden="true"
              />
              <span className="min-w-0">
                <span className="block text-base font-semibold text-foreground">
                  {config.label}
                </span>
                <span className="mt-0.5 block text-sm leading-snug text-muted-foreground">
                  {DESCRIPTIONS[config.id]}
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}
