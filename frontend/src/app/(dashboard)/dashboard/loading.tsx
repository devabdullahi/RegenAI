import { Skeleton } from "@/components/ui/skeleton";

export default function DashboardPageLoading() {
  return (
    <div className="space-y-6 pb-20 sm:pb-0">
      {/* Field selector skeleton */}
      <Skeleton className="h-10 w-full max-w-xs rounded-lg" />

      {/* Recommendation cards skeleton */}
      <div className="space-y-2">
        <Skeleton className="h-5 w-56" />
        <div className="space-y-3">
          <Skeleton className="h-28 w-full rounded-xl" />
          <Skeleton className="h-28 w-full rounded-xl" />
        </div>
      </div>

      {/* Widgets skeleton */}
      <div className="grid gap-4 sm:grid-cols-2">
        <Skeleton className="h-40 w-full rounded-xl" />
        <Skeleton className="h-40 w-full rounded-xl" />
      </div>

      {/* Programs skeleton */}
      <div className="space-y-3">
        <Skeleton className="h-5 w-44" />
        <div className="grid gap-4 sm:grid-cols-2">
          <Skeleton className="h-24 w-full rounded-xl" />
          <Skeleton className="h-24 w-full rounded-xl" />
        </div>
      </div>
    </div>
  );
}
