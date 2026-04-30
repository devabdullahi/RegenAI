import Link from "next/link";
import { Sprout, Droplets, FlaskConical, Eye, Wheat, Shovel, Leaf, ClipboardList, ChevronRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { ActivityType, FieldActivity } from "@/lib/api/types";

const TYPE_CONFIG: Record<
  ActivityType,
  { icon: React.ElementType; bg: string; iconColor: string; label: string }
> = {
  plant: { icon: Sprout, bg: "bg-green-100", iconColor: "text-green-600", label: "Planting" },
  spray: { icon: Droplets, bg: "bg-blue-100", iconColor: "text-blue-600", label: "Spray" },
  fertilize: { icon: FlaskConical, bg: "bg-amber-100", iconColor: "text-amber-600", label: "Fertilize" },
  scout: { icon: Eye, bg: "bg-purple-100", iconColor: "text-purple-600", label: "Scouting" },
  harvest: { icon: Wheat, bg: "bg-orange-100", iconColor: "text-orange-600", label: "Harvest" },
  tillage: { icon: Shovel, bg: "bg-stone-100", iconColor: "text-stone-600", label: "Tillage" },
  cover_crop: { icon: Leaf, bg: "bg-teal-100", iconColor: "text-teal-600", label: "Cover Crop" },
  other: { icon: ClipboardList, bg: "bg-gray-100", iconColor: "text-gray-600", label: "Other" },
};

interface RecentActivityWidgetProps {
  activities: FieldActivity[];
  fieldNames: Record<string, string>;
}

export function RecentActivityWidget({
  activities,
  fieldNames,
}: RecentActivityWidgetProps) {
  if (activities.length === 0) {
    return (
      <Card>
        <CardHeader className="border-b">
          <CardTitle className="text-base font-semibold">Recent Field Activity</CardTitle>
        </CardHeader>
        <CardContent className="pt-4 pb-4 text-center">
          <p className="text-sm text-muted-foreground">No activities logged yet.</p>
          <Link href="/activities/new">
            <button
              type="button"
              className="mt-3 min-h-[48px] rounded-lg bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
            >
              Log your first activity
            </button>
          </Link>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="border-b">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-semibold">Recent Field Activity</CardTitle>
          <Link
            href="/activities"
            className="flex items-center gap-0.5 text-sm font-medium text-primary hover:underline"
            aria-label="View all field activities"
          >
            View all
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </div>
      </CardHeader>

      <CardContent className="pt-3 pb-0">
        <ul className="divide-y divide-border/50" aria-label="Recent activities">
          {activities.map((activity) => {
            const config = TYPE_CONFIG[activity.activity_type];
            const Icon = config.icon;
            const fieldName = fieldNames[activity.field_id] ?? activity.field_id;
            const dateObj = new Date(activity.activity_date + "T12:00:00");
            const dateStr = dateObj.toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
            });

            return (
              <li key={activity.id} className="flex items-center gap-3 py-3">
                <div
                  className={cn(
                    "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
                    config.bg
                  )}
                >
                  <Icon className={cn("h-5 w-5", config.iconColor)} aria-hidden="true" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-foreground leading-snug">
                    {config.label}
                    <span className="ml-1.5 font-normal text-muted-foreground">
                      — {fieldName}
                    </span>
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {dateStr} &middot; {activity.acres} acres
                  </p>
                </div>
              </li>
            );
          })}
        </ul>

        <div className="py-3 border-t border-border/50 mt-0">
          <Link href="/activities/new">
            <button
              type="button"
              className="w-full min-h-[48px] rounded-lg border border-accent bg-accent/10 px-4 py-2 text-sm font-semibold text-accent transition-colors hover:bg-accent/20"
            >
              + Log an Activity
            </button>
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
