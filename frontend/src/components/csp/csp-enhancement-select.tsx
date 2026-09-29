"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/client";
import type { FarmEnhancementRecord, FarmEnhancementStatus } from "@/lib/api/types";

/**
 * Saves a farm's choice for one enhancement to csp_farm_enhancements, then
 * refreshes the route so the server component page shows the new status.
 */
export function CSPEnhancementSelect({
  farmId,
  enhancementCode,
  enhancementName,
  selection,
}: {
  farmId: string;
  enhancementCode: string;
  enhancementName: string;
  selection: FarmEnhancementRecord | null;
}) {
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const [refreshing, startRefresh] = useTransition();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const pending = saving || refreshing;

  async function run(action: () => Promise<unknown>) {
    setSaving(true);
    setErrorMessage(null);
    try {
      await action();
      startRefresh(() => router.refresh());
    } catch (err) {
      console.error(
        `CSP enhancement save failed farm=${farmId} code=${enhancementCode}`,
        err
      );
      setErrorMessage(
        err instanceof Error && err.message
          ? `We could not save this activity: ${err.message}`
          : "We could not save this activity. Please try again."
      );
    } finally {
      setSaving(false);
    }
  }

  const add = () =>
    run(() =>
      api.csp.createFarmEnhancement({
        farm_id: farmId,
        enhancement_code: enhancementCode,
        status: "considering",
      })
    );
  const setStatus = (status: FarmEnhancementStatus) =>
    run(() => api.csp.updateFarmEnhancement(selection!.id, { status }));
  const remove = () =>
    run(() => api.csp.deleteFarmEnhancement(selection!.id));

  const status = selection?.status;
  const buttonClass = "min-h-12 cursor-pointer";

  return (
    <div className="flex flex-col items-start gap-2">
      <div className="flex flex-wrap items-center gap-2">
        {(!selection || status === "removed") && (
          <Button
            type="button"
            variant="outline"
            className={buttonClass}
            onClick={selection ? () => setStatus("considering") : add}
            disabled={pending}
            aria-busy={pending}
          >
            Add to my plan
            <span className="sr-only">: {enhancementName}</span>
          </Button>
        )}
        {status === "considering" && (
          <Button
            type="button"
            className={buttonClass}
            onClick={() => setStatus("committed")}
            disabled={pending}
            aria-busy={pending}
          >
            Commit
            <span className="sr-only"> to {enhancementName}</span>
          </Button>
        )}
        {status === "committed" && (
          <Button
            type="button"
            variant="outline"
            className={buttonClass}
            onClick={() => setStatus("considering")}
            disabled={pending}
            aria-busy={pending}
          >
            Undo commit
            <span className="sr-only">: {enhancementName}</span>
          </Button>
        )}
        {selection && status !== "removed" && status !== "active" && (
          <Button
            type="button"
            variant="ghost"
            className={buttonClass}
            onClick={remove}
            disabled={pending}
            aria-busy={pending}
          >
            Remove
            <span className="sr-only"> {enhancementName} from my plan</span>
          </Button>
        )}
      </div>
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
