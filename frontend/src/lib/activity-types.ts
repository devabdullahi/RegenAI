/**
 * Single source for field activity types shown in the UI.
 *
 * Must match the CHECK list on field_activities.activity_type in
 * supabase/migrations/20260406000005_field_activity_log.sql and the
 * ActivityType union in lib/api/types.ts (Record<ActivityType, ...> makes
 * TypeScript fail if a type is missing here).
 */

import {
  ClipboardList,
  Droplets,
  Eye,
  FlaskConical,
  Leaf,
  Shovel,
  Sprout,
  Wheat,
  type LucideIcon,
} from "lucide-react";
import type { ActivityType } from "@/lib/api/types";

export interface ActivityTypeConfig {
  id: ActivityType;
  /** Plain-language label, e.g. "Cover Crop". */
  label: string;
  /** lucide-react icon component. Used only where it helps recognition. */
  icon: LucideIcon;
  /**
   * Ink for the type marker. Structural, never a tinted tile: the label always
   * sits next to the mark, so color alone never carries the meaning.
   */
  markerClasses: string;
}

function config(
  id: ActivityType,
  label: string,
  icon: LucideIcon,
  // Literal class strings (not template-built) so Tailwind's scanner sees them.
  markerClasses: string
): ActivityTypeConfig {
  return { id, label, icon, markerClasses };
}

/** Display order for filters, pickers and summaries. */
export const ACTIVITY_TYPES: readonly ActivityTypeConfig[] = [
  config("plant", "Planting", Sprout, "text-success"),
  config("spray", "Spray", Droplets, "text-info"),
  config("fertilize", "Fertilize", FlaskConical, "text-accent"),
  config("scout", "Scouting", Eye, "text-chart-4"),
  config("harvest", "Harvest", Wheat, "text-warning-foreground"),
  config("tillage", "Tillage", Shovel, "text-soil"),
  config("cover_crop", "Cover Crop", Leaf, "text-primary"),
  config("other", "Other", ClipboardList, "text-muted-foreground"),
];

export const ACTIVITY_TYPE_CONFIG = Object.fromEntries(
  ACTIVITY_TYPES.map((t) => [t.id, t])
) as Record<ActivityType, ActivityTypeConfig>;

export const ACTIVITY_TYPE_IDS: readonly ActivityType[] = ACTIVITY_TYPES.map(
  (t) => t.id
);

/** Config for a type; unknown values (e.g. from an older API) fall back to "other". */
export function getActivityTypeConfig(
  type: string | null | undefined
): ActivityTypeConfig {
  return (
    ACTIVITY_TYPE_CONFIG[type as ActivityType] ?? ACTIVITY_TYPE_CONFIG.other
  );
}

/** Zero count for every type, for building per-type summaries. */
export function emptyActivityTypeCounts(): Record<ActivityType, number> {
  return Object.fromEntries(ACTIVITY_TYPE_IDS.map((id) => [id, 0])) as Record<
    ActivityType,
    number
  >;
}
