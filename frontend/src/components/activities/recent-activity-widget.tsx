import Link from "next/link";
import { Plus } from "lucide-react";
import { ButtonLink } from "@/components/shared/button-link";
import { getActivityTypeConfig } from "@/lib/activity-types";
import { formatAcres, formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { FieldActivity } from "@/lib/api/types";

interface RecentActivityWidgetProps {
  activities: FieldActivity[];
  fieldNames: Record<string, string>;
  /**
   * Farm to keep in the links. Defaults to the farm of the listed activities,
   * so pass it explicitly for the empty state.
   */
  farmId?: string;
}

/**
 * The last few lines of the field log. The page above supplies the section
 * head, so this renders the rows only.
 */
export function RecentActivityWidget({
  activities,
  fieldNames,
  farmId,
}: RecentActivityWidgetProps) {
  const resolvedFarmId = farmId ?? activities[0]?.farm_id;
  const farmQuery = resolvedFarmId ? `?farm_id=${encodeURIComponent(resolvedFarmId)}` : "";

  if (activities.length === 0) {
    return (
      <div className="border-y border-border py-6">
        <p className="text-sm text-muted-foreground">No activities logged yet.</p>
        <ButtonLink href={`/activities/new${farmQuery}`} className="mt-4">
          Log your first activity
        </ButtonLink>
      </div>
    );
  }

  return (
    <div>
      <ul className="border-t border-border" aria-label="Recent activities">
        {activities.map((activity) => {
          const config = getActivityTypeConfig(activity.activity_type);
          const Icon = config.icon;
          const fieldName = fieldNames[activity.field_id] ?? "Unknown field";

          return (
            <li
              key={activity.id}
              className="flex flex-wrap items-baseline gap-x-4 gap-y-1 border-b border-border py-3"
            >
              <time
                dateTime={activity.activity_date}
                className="w-24 shrink-0 font-mono text-xs tabular-nums text-muted-foreground"
              >
                {formatDate(activity.activity_date)}
              </time>

              <span className="flex min-w-0 flex-1 items-baseline gap-2">
                {/* The type mark aids recognition when scanning the log. */}
                <Icon
                  className={cn("size-4 shrink-0 translate-y-0.5", config.markerClasses)}
                  aria-hidden="true"
                />
                <span className="min-w-0">
                  <span className="text-sm font-medium text-foreground">
                    {config.label}
                  </span>
                  <span className="ml-2 text-sm text-muted-foreground">{fieldName}</span>
                </span>
              </span>

              <span className="w-20 shrink-0 text-right font-mono text-sm tabular-nums text-muted-foreground">
                {formatAcres(activity.acres, { short: true })}
              </span>
            </li>
          );
        })}
      </ul>

      <div className="mt-4 flex flex-wrap items-center gap-4">
        <ButtonLink href={`/activities/new${farmQuery}`} variant="outline">
          <Plus aria-hidden="true" />
          Log an activity
        </ButtonLink>
        <Link
          href={`/activities${farmQuery}`}
          className="inline-flex min-h-12 items-center text-sm font-medium text-primary hover:underline"
        >
          View the whole log<span className="sr-only"> of field activities</span>
        </Link>
      </div>
    </div>
  );
}
