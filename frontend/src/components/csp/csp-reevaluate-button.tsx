"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/client";

/**
 * Re-runs POST /csp/evaluate, then refreshes the route so the server component
 * page refetches and shows the new result.
 */
export function CSPReevaluateButton({ farmId }: { farmId: string }) {
  const router = useRouter();
  const [evaluating, setEvaluating] = useState(false);
  const [refreshing, startRefresh] = useTransition();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const pending = evaluating || refreshing;

  async function handleReevaluate() {
    setEvaluating(true);
    setErrorMessage(null);
    try {
      await api.csp.evaluate(farmId);
      startRefresh(() => router.refresh());
    } catch (err) {
      console.error(`CSP re-evaluate failed farm=${farmId}`, err);
      setErrorMessage(
        err instanceof Error && err.message
          ? `We could not re-evaluate your farm: ${err.message}`
          : "We could not re-evaluate your farm. Please try again."
      );
    } finally {
      setEvaluating(false);
    }
  }

  return (
    <div className="flex flex-col items-start gap-2 sm:items-end">
      <Button
        type="button"
        variant="outline"
        className="min-h-12 cursor-pointer"
        onClick={handleReevaluate}
        disabled={pending}
        aria-busy={pending}
      >
        {pending ? "Re-evaluating..." : "Re-evaluate"}
        <span className="sr-only"> CSP eligibility</span>
      </Button>
      {errorMessage && (
        <p
          role="alert"
          className="border-l-[3px] border-l-destructive py-2 pl-3 text-sm text-destructive"
        >
          {errorMessage}
        </p>
      )}
    </div>
  );
}
