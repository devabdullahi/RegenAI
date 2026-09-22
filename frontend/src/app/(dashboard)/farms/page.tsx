import { Tractor, Plus } from "lucide-react";
import { ButtonLink } from "@/components/shared/button-link";
import { EmptyState, ErrorState } from "@/components/shared/page-states";
import { api } from "@/lib/api/server-client";
import { formatAcres } from "@/lib/format";
import type { Farm } from "@/lib/api/types";

export default async function FarmsPage() {
  let farms: Farm[];
  try {
    farms = await api.farms.list();
  } catch (err) {
    // Never fall through to "No farms yet": that invites duplicate farms.
    return (
      <div className="pb-20 sm:pb-0">
        <ErrorState
          title="Couldn't load your farms"
          message={
            err instanceof Error
              ? err.message
              : "Check your connection and try again."
          }
          actions={[{ label: "Try again", href: "/farms" }]}
        />
      </div>
    );
  }

  const sortedFarms = [...farms].sort((a, b) =>
    b.created_at.localeCompare(a.created_at)
  );
  const totalAcres = sortedFarms.reduce(
    (sum, farm) => sum + (farm.total_acres ?? 0),
    0
  );

  return (
    <div className="pb-20 sm:pb-0">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3 border-b-2 border-rule-strong pb-3">
        <div>
          <h1 className="font-heading text-2xl font-bold">Farms</h1>
          {sortedFarms.length > 0 && (
            <p className="mt-1 font-mono text-[0.6875rem] tracking-[0.12em] text-muted-foreground uppercase">
              {sortedFarms.length} on record · {formatAcres(totalAcres)} total
            </p>
          )}
        </div>
        <ButtonLink href="/onboarding">
          <Plus aria-hidden="true" />
          Add farm
        </ButtonLink>
      </div>

      {sortedFarms.length === 0 ? (
        <EmptyState
          icon={Tractor}
          title="No farms yet"
          message="Add your first farm to get recommendations, program eligibility and a field log."
          actions={[
            { label: "Add your first farm", href: "/onboarding", icon: Plus },
          ]}
        />
      ) : (
        /* A register: one line per farm, acres in the figures column. */
        <ul className="border-t border-border">
          {sortedFarms.map((farm) => (
            <li
              key={farm.id}
              className="flex flex-wrap items-baseline gap-x-4 gap-y-2 border-b border-border py-4"
            >
              <div className="min-w-0 flex-1">
                <h2 className="font-heading text-lg font-semibold">
                  {farm.name}
                </h2>
                <p className="mt-0.5 font-mono text-xs tracking-[0.08em] text-muted-foreground uppercase">
                  {farm.state}
                </p>
              </div>

              <p className="font-mono text-base tabular-nums">
                {formatAcres(farm.total_acres)}
              </p>

              <div className="flex w-full gap-4 sm:w-auto sm:pl-4">
                <ButtonLink
                  href={`/dashboard?farm=${encodeURIComponent(farm.id)}`}
                  variant="link"
                  className="px-0"
                  aria-label={`Open dashboard for ${farm.name}`}
                >
                  Dashboard
                </ButtonLink>
                <ButtonLink
                  href={`/farms/${encodeURIComponent(farm.id)}`}
                  variant="link"
                  className="px-0"
                  aria-label={`Farm details for ${farm.name}`}
                >
                  Details
                </ButtonLink>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
