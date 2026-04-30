import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { ActivityForm } from "@/components/activities/activity-form";
import { api } from "@/lib/api/client";
import type { Field } from "@/lib/api/types";
import type { Metadata } from "next";
import type { ActivityType } from "@/lib/api/types";

export const metadata: Metadata = {
  title: "Log Activity — RegenAI",
  description: "Record a field activity: planting, spraying, fertilizing, scouting, or harvest.",
};

interface NewActivityPageProps {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
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

  const validTypes: ActivityType[] = ["plant", "spray", "fertilize", "scout", "harvest"];
  const defaultType = validTypes.includes(typeParam as ActivityType)
    ? (typeParam as ActivityType)
    : undefined;

  // Resolve fields: prefer the explicit farm_id param, fall back to first farm
  let fields: Field[] = [];

  try {
    if (farmIdParam) {
      fields = await api.fields.list(farmIdParam);
    } else {
      // No farm specified — fetch the user's farms and use the first one
      const farms = await api.farms.list();
      if (farms.length > 0 && farms[0]) {
        fields = await api.fields.list(farms[0].id);
      }
    }
  } catch {
    // Gracefully degrade — the form will render with an empty field list
    fields = [];
  }

  return (
    <div className="pb-20 sm:pb-0 space-y-6">
      {/* Back link + header */}
      <div>
        <Link
          href={farmIdParam ? `/activities?farm_id=${farmIdParam}` : "/activities"}
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors mb-3"
        >
          <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          Back to Field Log
        </Link>
        <h1 className="font-heading text-2xl font-bold text-foreground sm:text-3xl">
          Log an Activity
        </h1>
        <p className="mt-1 text-sm text-muted-foreground max-w-prose">
          Record what happened on your farm today. The more you log, the better
          your crop insurance APH and program eligibility gets.
        </p>
      </div>

      <ActivityForm
        fields={fields}
        defaultFieldId={defaultFieldId}
        defaultActivityType={defaultType}
      />
    </div>
  );
}
