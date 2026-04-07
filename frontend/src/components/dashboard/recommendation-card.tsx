"use client";

import { useState } from "react";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { CheckCircle2, X } from "lucide-react";
import type { Recommendation } from "@/lib/api/types";

function PriorityBadge({ priority }: { priority: Recommendation["priority"] }) {
  if (priority === "high") {
    return (
      <span className="inline-flex items-center rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-semibold text-red-700">
        High Priority
      </span>
    );
  }
  if (priority === "medium") {
    return (
      <span className="inline-flex items-center rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-700">
        Medium Priority
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-semibold text-green-700">
      Low Priority
    </span>
  );
}

interface RecommendationCardProps {
  recommendation: Recommendation;
  onMarkDone?: (id: string) => void;
  onDismiss?: (id: string) => void;
}

export function RecommendationCard({
  recommendation,
  onMarkDone,
  onDismiss,
}: RecommendationCardProps) {
  const [done, setDone] = useState(
    recommendation.status === "acted"
  );
  const [dismissed, setDismissed] = useState(
    recommendation.status === "dismissed"
  );

  if (dismissed) return null;

  function handleMarkDone() {
    setDone(true);
    onMarkDone?.(recommendation.id);
  }

  function handleDismiss() {
    setDismissed(true);
    onDismiss?.(recommendation.id);
  }

  return (
    <Card className={done ? "opacity-75" : ""}>
      <CardHeader className="border-b">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <CardTitle className="text-base font-semibold leading-snug font-heading">
            {recommendation.title}
          </CardTitle>
          <PriorityBadge priority={recommendation.priority} />
        </div>
        <p className="mt-0.5 text-xs text-muted-foreground font-mono tracking-wide uppercase">
          EQIP Practice {recommendation.practice_code}
        </p>
      </CardHeader>

      <CardContent className="pt-3">
        {done ? (
          <div className="flex items-center gap-3 rounded-lg bg-green-50 p-3 text-green-700">
            <CheckCircle2 className="h-5 w-5 shrink-0 text-green-600" />
            <span className="text-sm font-medium">
              Marked as done — great work!
            </span>
          </div>
        ) : (
          <p className="text-[1.0625rem] leading-relaxed text-foreground">
            {recommendation.rationale}
          </p>
        )}
      </CardContent>

      {!done && (
        <CardContent className="pt-0">
          <div className="flex flex-wrap gap-2">
            <Button
              onClick={handleMarkDone}
              className="min-h-[48px] flex-1 bg-primary text-primary-foreground hover:bg-primary/90 cursor-pointer"
            >
              <CheckCircle2 className="mr-2 h-4 w-4" />
              Mark as Done
            </Button>
            <Button
              variant="ghost"
              onClick={handleDismiss}
              className="min-h-[48px] cursor-pointer text-muted-foreground hover:text-foreground"
              aria-label="Dismiss recommendation"
            >
              <X className="mr-1 h-4 w-4" />
              Dismiss
            </Button>
          </div>
        </CardContent>
      )}

      <CardFooter className="mt-0">
        <p className="text-xs text-muted-foreground leading-relaxed">
          This is not professional agronomic advice. Consult your local
          agronomist before making changes to your farming practices.
        </p>
      </CardFooter>
    </Card>
  );
}

export function RecommendationCardSkeleton() {
  return (
    <Card>
      <CardHeader className="border-b">
        <div className="flex items-start justify-between gap-2">
          <Skeleton className="h-5 w-3/4" />
          <Skeleton className="h-5 w-20 rounded-full" />
        </div>
        <Skeleton className="mt-1 h-3 w-24" />
      </CardHeader>
      <CardContent className="pt-3">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="mt-2 h-4 w-5/6" />
        <Skeleton className="mt-2 h-4 w-4/6" />
      </CardContent>
      <CardContent className="pt-0">
        <div className="flex gap-2">
          <Skeleton className="h-12 flex-1 rounded-lg" />
          <Skeleton className="h-12 w-24 rounded-lg" />
        </div>
      </CardContent>
      <CardFooter>
        <Skeleton className="h-3 w-full" />
      </CardFooter>
    </Card>
  );
}

export function RecommendationsEmpty() {
  return (
    <Card className="py-10 text-center">
      <CardContent className="flex flex-col items-center gap-3">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-muted">
          <div className="h-8 w-8 animate-pulse rounded-full bg-muted-foreground/20" />
        </div>
        <div>
          <p className="font-heading text-base font-semibold">
            Your analysis is running
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            Check back soon — recommendations will appear here.
          </p>
        </div>
        <div className="mt-2 flex w-full max-w-xs flex-col gap-2">
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-4/5 self-center" />
          <Skeleton className="h-3 w-3/5 self-center" />
        </div>
      </CardContent>
    </Card>
  );
}
