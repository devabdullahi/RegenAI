import { ShieldAlert } from "lucide-react";
import { Stamp } from "@/components/shared/record";

interface RestrictedUseBadgeProps {
  className?: string;
}

/**
 * Restricted-use pesticide flag. Stamped in the destructive ink, but the words
 * carry the meaning: the mark must still read as restricted in grayscale, and
 * the certified-applicator requirement is announced to screen readers.
 */
export function RestrictedUseBadge({ className }: RestrictedUseBadgeProps) {
  return (
    <Stamp tone="destructive" className={className}>
      <ShieldAlert className="h-3 w-3 shrink-0" aria-hidden="true" />
      Restricted use
      <span className="sr-only"> pesticide, certified applicator required</span>
    </Stamp>
  );
}
