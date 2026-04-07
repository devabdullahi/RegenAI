import { ShieldAlert } from "lucide-react";
import { cn } from "@/lib/utils";

interface RestrictedUseBadgeProps {
  className?: string;
  size?: "sm" | "default";
}

export function RestrictedUseBadge({
  className,
  size = "default",
}: RestrictedUseBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full font-semibold",
        size === "sm"
          ? "px-2 py-0.5 text-xs"
          : "px-2.5 py-1 text-xs",
        "bg-red-100 text-red-700 border border-red-200",
        className
      )}
      aria-label="Restricted use pesticide — certified applicator required"
    >
      <ShieldAlert className="h-3 w-3 shrink-0" aria-hidden="true" />
      Restricted Use
    </span>
  );
}
