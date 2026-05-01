import { Skeleton } from "@/components/ui/skeleton";

export default function CreditsPageLoading() {
  return (
    <div className="space-y-6 pb-20 sm:pb-0">
      {/* Page heading skeleton */}
      <Skeleton className="h-8 w-52 rounded-lg" />

      {/* Farm header / status banner */}
      <Skeleton className="h-20 w-full rounded-xl" />

      {/* Two program cards */}
      <div className="space-y-3">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-36 w-full rounded-xl" />
        <Skeleton className="h-36 w-full rounded-xl" />
      </div>

      {/* Document upload area */}
      <div className="space-y-2">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-28 w-full rounded-xl" />
      </div>
    </div>
  );
}
