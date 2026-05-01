import { Skeleton } from "@/components/ui/skeleton";

export default function ActivitiesPageLoading() {
  return (
    <div className="space-y-6 pb-20 sm:pb-0">
      {/* Page heading + Log Activity button */}
      <div className="flex items-start justify-between gap-4">
        <Skeleton className="h-8 w-52 rounded-lg" />
        <Skeleton className="h-12 w-36 rounded-xl" />
      </div>

      {/* Type-count strip (8 squares) */}
      <div className="grid grid-cols-4 gap-2 lg:grid-cols-8">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-20 w-full rounded-xl" />
        ))}
      </div>

      {/* Filter toggle */}
      <Skeleton className="h-12 w-36 rounded-lg" />

      {/* Results count */}
      <Skeleton className="h-4 w-32" />

      {/* Activity cards */}
      <div className="space-y-4">
        <Skeleton className="h-28 w-full rounded-xl" />
        <Skeleton className="h-28 w-full rounded-xl" />
        <Skeleton className="h-28 w-full rounded-xl" />
      </div>
    </div>
  );
}
