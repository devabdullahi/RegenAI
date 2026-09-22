"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ButtonLink } from "@/components/shared/button-link";
import { EdgeNote, Sheet, Stamp } from "@/components/shared/record";
import { api } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { type Tone } from "@/lib/status-styles";
import type {
  Recommendation,
  RecommendationPriority,
  RecommendationStatus,
} from "@/lib/api/types";

const PRIORITY_STAMP: Record<RecommendationPriority, { label: string; tone: Tone }> = {
  high: { label: "High priority", tone: "destructive" },
  medium: { label: "Medium priority", tone: "warning" },
  low: { label: "Low priority", tone: "success" },
};

interface RecommendationCardProps {
  recommendation: Recommendation;
}

export function RecommendationCard({ recommendation }: RecommendationCardProps) {
  const [status, setStatus] = useState<RecommendationStatus>(recommendation.status);
  const [saving, setSaving] = useState(false);

  if (status === "dismissed") return null;
  const done = status === "acted";
  const priority = PRIORITY_STAMP[recommendation.priority];

  // Optimistic: show the new status immediately, roll back if the save fails.
  async function updateStatus(next: RecommendationStatus) {
    const previous = status;
    setStatus(next);
    setSaving(true);
    try {
      await api.recommendations.updateStatus(recommendation.id, next);
    } catch (err) {
      setStatus(previous);
      toast.error(
        next === "acted"
          ? "We couldn't mark this as done."
          : "We couldn't dismiss this recommendation.",
        { description: err instanceof Error ? err.message : "Please try again." }
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <Sheet className={cn("p-5 sm:p-6", done && "opacity-75")}>
      {/* Codes first, the way a plan sheet heads an item. */}
      <div className="flex flex-wrap items-center gap-2">
        <Stamp>EQIP Practice {recommendation.practice_code}</Stamp>
        <Stamp tone={priority.tone}>{priority.label}</Stamp>
      </div>

      <h3 className="mt-3 font-heading text-xl leading-snug font-semibold text-foreground">
        {recommendation.title}
      </h3>

      {done ? (
        <div role="status" className="mt-3">
          <EdgeNote tone="success" title="Marked as done" />
        </div>
      ) : (
        <p className="reading mt-2 max-w-[62ch] text-foreground">
          {recommendation.rationale}
        </p>
      )}

      {!done && (
        <div className="mt-5 flex flex-wrap gap-3">
          <Button
            onClick={() => updateStatus("acted")}
            disabled={saving}
            size="lg"
            className="min-h-12 cursor-pointer"
          >
            Mark as done
          </Button>
          <Button
            variant="ghost"
            onClick={() => updateStatus("dismissed")}
            disabled={saving}
            className="min-h-12 cursor-pointer text-muted-foreground hover:text-foreground"
            aria-label="Dismiss recommendation"
          >
            Dismiss
          </Button>
        </div>
      )}

      <p className="mt-5 border-t border-border pt-3 text-xs leading-relaxed text-muted-foreground">
        This is not professional agronomic advice. Consult your local
        agronomist before making changes to your farming practices.
      </p>
    </Sheet>
  );
}

export function RecommendationsEmpty({ farmId }: { farmId: string }) {
  return (
    <div className="border-y border-border py-8">
      <p className="font-heading text-lg font-semibold text-foreground">
        Nothing to do this week
      </p>
      <p className="reading mt-1 max-w-[56ch] text-muted-foreground">
        Log a field activity and we will work out what to do next.
      </p>
      <ButtonLink
        href={`/activities/new?farm_id=${encodeURIComponent(farmId)}`}
        className="mt-5"
      >
        Add field activity
      </ButtonLink>
    </div>
  );
}
