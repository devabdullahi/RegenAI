"use client";

import { Sprout, Droplets, FlaskConical, Eye, Wheat } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ActivityType } from "@/lib/api/types";

const ACTIVITY_TYPES: {
  type: ActivityType;
  label: string;
  description: string;
  icon: React.ElementType;
  bg: string;
  selectedBg: string;
  selectedBorder: string;
  iconColor: string;
}[] = [
  {
    type: "plant",
    label: "Planting",
    description: "Record what you put in the ground",
    icon: Sprout,
    bg: "hover:bg-green-50",
    selectedBg: "bg-green-50",
    selectedBorder: "border-green-400",
    iconColor: "text-green-600",
  },
  {
    type: "spray",
    label: "Spray",
    description: "Herbicide, insecticide, or fungicide",
    icon: Droplets,
    bg: "hover:bg-blue-50",
    selectedBg: "bg-blue-50",
    selectedBorder: "border-blue-400",
    iconColor: "text-blue-600",
  },
  {
    type: "fertilize",
    label: "Fertilize",
    description: "Nitrogen, phosphorus, potassium",
    icon: FlaskConical,
    bg: "hover:bg-amber-50",
    selectedBg: "bg-amber-50",
    selectedBorder: "border-amber-400",
    iconColor: "text-amber-600",
  },
  {
    type: "scout",
    label: "Scouting",
    description: "Pest, disease, or weed check",
    icon: Eye,
    bg: "hover:bg-purple-50",
    selectedBg: "bg-purple-50",
    selectedBorder: "border-purple-400",
    iconColor: "text-purple-600",
  },
  {
    type: "harvest",
    label: "Harvest",
    description: "Yield, moisture, and ticket info",
    icon: Wheat,
    bg: "hover:bg-orange-50",
    selectedBg: "bg-orange-50",
    selectedBorder: "border-orange-400",
    iconColor: "text-orange-600",
  },
];

interface ActivityTypePickerProps {
  value: ActivityType | null;
  onChange: (type: ActivityType) => void;
}

export function ActivityTypePicker({ value, onChange }: ActivityTypePickerProps) {
  return (
    <fieldset>
      <legend className="sr-only">Select activity type</legend>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {ACTIVITY_TYPES.map((item) => {
          const isSelected = value === item.type;
          const Icon = item.icon;
          return (
            <button
              key={item.type}
              type="button"
              onClick={() => onChange(item.type)}
              aria-pressed={isSelected}
              className={cn(
                "flex min-h-[72px] items-center gap-4 rounded-xl border-2 px-4 py-4 text-left transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                isSelected
                  ? `${item.selectedBg} ${item.selectedBorder}`
                  : `border-border bg-card ${item.bg}`
              )}
            >
              <div
                className={cn(
                  "flex h-11 w-11 shrink-0 items-center justify-center rounded-xl",
                  isSelected ? "bg-white/70" : "bg-muted"
                )}
              >
                <Icon className={cn("h-6 w-6", item.iconColor)} aria-hidden="true" />
              </div>
              <div>
                <p className="text-base font-semibold text-foreground">
                  {item.label}
                </p>
                <p className="text-sm text-muted-foreground leading-snug mt-0.5">
                  {item.description}
                </p>
              </div>
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}
