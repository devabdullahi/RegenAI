import Link from "next/link";
import { ChevronLeft, Tractor, Wheat } from "lucide-react";
import { ActivityForm } from "@/components/activities/activity-form";
import { EmptyState, ErrorState } from "@/components/shared/page-states";
import { api } from "@/lib/api/server-client";
import { ACTIVITY_TYPE_IDS } from "@/lib/activity-types";
import type { ActivityType, Field } from "@/lib/api/types";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Log Activity — RegenAI",
  description: "Record a field activity: planting, spraying, fertilizing, scouting, or harvest.",
};

interface NewActivityPageProps {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

function isActivityType(value: string | undefined): value is ActivityType {
  return (ACTIVITY_TYPE_IDS as readonly string[]).includes(value ?? "");
}

export default async function NewActivityPage({ searchParams }: NewActivityPageProps) {
  const params = await searchParams;

  const defaultFieldId =
    typeof params.field === "string" ? params.field : undefined;
  const typeParam =
    typeof params.type === "string" ? params.type : undefined;
  const farmIdParam =
    typeof params.farm_id === "string"
      ? params.farm_id
      : typeof params.farm === "string"
        ? params.farm
        : undefined;

  const defaultType = isActivityType(typeParam) ? typeParam : undefined;

  // Resolve the farm: prefer the explicit farm_id param, else the user's first farm.
  let farmId: string | undefined = farmIdParam;
  let fields: Field[] = [];
  let loadError: string | null = null;

  try {
    if (!farmId) {
      const farms = await api.farms.list();
      farmId = farms[0]?.id;
    }
    if (farmId) {
      fields = await api.fields.list(farmId);
    }
  } catch (err) {
    console.error(`NewActivityPage: failed to load fields for farm ${farmId ?? "(none)"}`, err);
    loadError = err instanceof Error ? err.message : "Failed to load your fields.";
  }

  const backHref = farmId
    ? `/activities?farm_id=${encodeURIComponent(farmId)}`
    : "/activities";

  return (
    <div className="pb-20 sm:pb-0">
      {/* Back link + masthead */}
      <Link
        href={backHref}
        className="inline-flex min-h-12 items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        Back to the field log
      </Link>
      <div className="mb-8 border-b-2 border-rule-strong pb-3">
        <h1 className="font-heading text-2xl font-semibold text-foreground sm:text-3xl">
          Log an activity
        </h1>
        <p className="mt-1 max-w-[62ch] text-sm text-muted-foreground">
          Record what happened on your farm today. The more you log, the better
          your crop insurance APH and program eligibility gets.
        </p>
      </div>

      {loadError ? (
        <ErrorState
          title="Couldn't load your fields"
          message={loadError}
          actions={[
            { label: "Try again", href: "/activities/new" },
            { label: "Back to farms", href: "/farms", variant: "outline" },
          ]}
        />
      ) : !farmId ? (
        <EmptyState
          icon={Tractor}
          title="No farm yet"
          message="Add a farm and its fields before logging field activities."
          actions={[{ label: "Add a farm", href: "/onboarding" }]}
        />
      ) : fields.length === 0 ? (
        <EmptyState
          icon={Wheat}
          title="No fields yet"
          message="This farm has no fields. Add a field before logging activities."
          actions={[
            { label: "View farm", href: `/farms/${encodeURIComponent(farmId)}` },
          ]}
        />
      ) : (
        <ActivityForm
          farmId={farmId}
          fields={fields}
          defaultFieldId={defaultFieldId}
          defaultActivityType={defaultType}
        />
      )}
    </div>
  );
}
