import { Skeleton } from "@/components/ui/skeleton";

export default function CspPageLoading() {
  return (
    <div className="space-y-6 pb-20 sm:pb-0">
      {/* Page heading */}
      <Skeleton className="h-8 w-48 rounded-lg" />

      {/* Eligibility score gauge */}
      <Skeleton className="h-44 w-full rounded-xl" />

      {/* Checklist / enhancement items */}
      <div className="space-y-3">
        <Skeleton className="h-5 w-56" />
        <Skeleton className="h-20 w-full rounded-xl" />
        <Skeleton className="h-20 w-full rounded-xl" />
        <Skeleton className="h-20 w-full rounded-xl" />
      </div>

      {/* Payment estimate card */}
      <Skeleton className="h-32 w-full rounded-xl" />
    </div>
  );
}
