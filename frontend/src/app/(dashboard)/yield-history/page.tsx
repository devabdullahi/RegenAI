"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Plus,
  Info,
  Loader2,
  AlertCircle,
  Tractor,
} from "lucide-react";
import { YieldSummaryCard } from "@/components/activities/yield-summary-card";
import { api } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import type { APHResult, Field, YieldRecord } from "@/lib/api/types";

// ── Simple bar chart ───────────────────────────────────────────────────────────

function YieldBarChart({ records }: { records: YieldRecord[] }) {
  if (records.length === 0) return null;

  const sorted = [...records].sort((a, b) => a.crop_year - b.crop_year);
  const maxYield = Math.max(...sorted.map((r) => r.yield_bu_ac));

  const CROP_COLORS: Record<string, string> = {
    corn: "bg-amber-400",
    soybeans: "bg-green-500",
    wheat: "bg-yellow-500",
    sorghum: "bg-orange-400",
  };

  return (
    <div className="rounded-xl border border-border bg-card px-4 py-4">
      <p className="text-sm font-semibold text-foreground mb-4">
        Yield trend by year
      </p>
      <div className="flex items-end gap-2" style={{ height: "120px" }}>
        {sorted.map((record) => {
          const heightPct = (record.yield_bu_ac / maxYield) * 100;
          const barColor =
            CROP_COLORS[record.crop_type.toLowerCase()] ?? "bg-primary";
          return (
            <div
              key={record.id}
              className="flex flex-1 flex-col items-center gap-1"
            >
              <span className="text-sm font-bold text-foreground">
                {record.yield_bu_ac}
              </span>
              <div
                className={cn("w-full rounded-t-md transition-all", barColor)}
                style={{ height: `${Math.max(heightPct, 8)}%` }}
                role="img"
                aria-label={`${record.crop_year}: ${record.yield_bu_ac} bu/ac ${record.crop_type}`}
              />
              <span className="text-sm text-foreground">
                {record.crop_year}
              </span>
              <span
                className={cn(
                  "text-xs rounded px-1",
                  record.crop_type.toLowerCase() === "corn"
                    ? "bg-amber-100 text-amber-700"
                    : "bg-green-100 text-green-700"
                )}
              >
                {record.crop_type === "soybeans" ? "SB" : "C"}
              </span>
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div className="mt-3 flex flex-wrap gap-3">
        {Object.entries(CROP_COLORS)
          .filter(([crop]) =>
            sorted.some((r) => r.crop_type.toLowerCase() === crop)
          )
          .map(([crop, color]) => (
            <div key={crop} className="flex items-center gap-1.5">
              <div
                className={cn("h-3 w-3 rounded-sm", color)}
                aria-hidden="true"
              />
              <span className="text-xs text-muted-foreground capitalize">
                {crop}
              </span>
            </div>
          ))}
      </div>
    </div>
  );
}

// ── Yield table ───────────────────────────────────────────────────────────────

function YieldTable({ records }: { records: YieldRecord[] }) {
  const sorted = [...records].sort((a, b) => b.crop_year - a.crop_year);

  if (sorted.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-card px-4 py-8 text-center">
        <p className="text-sm text-muted-foreground">No yield records yet.</p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/30">
              <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Year
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Crop
              </th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Yield (bu/ac)
              </th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Moisture
              </th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Acres
              </th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((record, i) => (
              <tr
                key={record.id}
                className={cn(
                  "border-b border-border/50 last:border-0",
                  i % 2 === 0 ? "bg-card" : "bg-muted/10"
                )}
              >
                <td className="px-4 py-3.5 font-semibold text-foreground">
                  {record.crop_year}
                </td>
                <td className="px-4 py-3.5">
                  <span
                    className={cn(
                      "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                      record.crop_type.toLowerCase() === "corn"
                        ? "bg-amber-100 text-amber-700"
                        : "bg-green-100 text-green-700"
                    )}
                  >
                    {record.crop_type}
                  </span>
                </td>
                <td className="px-4 py-3.5 text-right font-semibold text-foreground">
                  {record.yield_bu_ac}
                </td>
                <td className="px-4 py-3.5 text-right text-muted-foreground">
                  {record.moisture_pct}%
                </td>
                <td className="px-4 py-3.5 text-right text-muted-foreground">
                  {record.acres.toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function YieldHistoryPage() {
  const searchParams = useSearchParams();

  // FE-016: Read farm_id from searchParams
  const farmId =
    searchParams.get("farm_id") ?? searchParams.get("farm") ?? null;

  const [aphResults, setAphResults] = useState<APHResult[]>([]);
  const [fields, setFields] = useState<Field[]>([]);
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);

      if (!farmId) {
        setLoading(false);
        return;
      }

      try {
        const [aphData, farmFields] = await Promise.all([
          api.activities.getYieldHistory(farmId),
          api.fields.list(farmId),
        ]);

        if (!cancelled) {
          setAphResults(aphData);
          setFields(farmFields);
          // Default to first field that has APH data, else first field
          const firstWithData = farmFields.find((f) =>
            aphData.some((a) => a.field_id === f.id)
          );
          setSelectedFieldId(
            firstWithData?.id ?? farmFields[0]?.id ?? null
          );
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load yield history. Please try again."
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, [farmId]);

  // Derive data for the selected field
  const selectedField = fields.find((f) => f.id === selectedFieldId) ?? null;
  const selectedAph =
    aphResults.find((a) => a.field_id === selectedFieldId) ?? null;
  const fieldRecords = selectedAph?.records ?? [];

  // ── No farm selected ─────────────────────────────────────────────────────────

  if (!farmId && !loading) {
    return (
      <div className="pb-20 sm:pb-0 space-y-6">
        <h1 className="font-heading text-2xl font-bold text-foreground sm:text-3xl">
          Yield History
        </h1>
        <div className="rounded-xl border border-border bg-card px-6 py-12 text-center">
          <Tractor
            className="mx-auto mb-3 h-10 w-10 text-muted-foreground"
            aria-hidden="true"
          />
          <p className="font-heading text-base font-semibold text-foreground">
            Select a farm to view data
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            Choose a farm to see its yield history and APH calculations.
          </p>
          <Link href="/farms">
            <button
              type="button"
              className="mt-4 min-h-[48px] rounded-lg bg-primary px-6 py-2 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
            >
              Go to My Farms
            </button>
          </Link>
        </div>
      </div>
    );
  }

  // ── Loading ───────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="pb-20 sm:pb-0 space-y-6">
        <h1 className="font-heading text-2xl font-bold text-foreground sm:text-3xl">
          Yield History
        </h1>
        <div className="flex items-center justify-center py-20">
          <Loader2
            className="h-8 w-8 animate-spin text-muted-foreground"
            aria-label="Loading yield history"
          />
        </div>
      </div>
    );
  }

  // ── Error ─────────────────────────────────────────────────────────────────────

  if (error) {
    return (
      <div className="pb-20 sm:pb-0 space-y-6">
        <h1 className="font-heading text-2xl font-bold text-foreground sm:text-3xl">
          Yield History
        </h1>
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 px-6 py-10 text-center">
          <AlertCircle
            className="mx-auto mb-3 h-9 w-9 text-destructive"
            aria-hidden="true"
          />
          <p className="font-heading text-base font-semibold text-foreground">
            Could not load yield history
          </p>
          <p className="mt-1 text-sm text-muted-foreground">{error}</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-4 min-h-[48px] rounded-lg border border-border px-5 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  // ── Main content ──────────────────────────────────────────────────────────────

  return (
    <div className="pb-20 sm:pb-0 space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold text-foreground sm:text-3xl">
            Yield History
          </h1>
          <p className="mt-1 text-sm text-muted-foreground max-w-prose">
            Your actual yields by year and field. Used to calculate your APH
            for crop insurance.
          </p>
        </div>

        <Link
          href={`/activities/new?type=harvest${farmId ? `&farm_id=${farmId}` : ""}`}
          className="flex min-h-[52px] items-center gap-2 rounded-xl bg-accent px-5 py-3 text-base font-semibold text-accent-foreground transition-colors hover:bg-accent/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Plus className="h-5 w-5" aria-hidden="true" />
          Add Yield Record
        </Link>
      </div>

      {/* Field selector */}
      {fields.length > 1 && (
        <div className="space-y-1.5">
          <label
            htmlFor="field-select"
            className="block text-sm font-medium text-muted-foreground uppercase tracking-wide"
          >
            View field
          </label>
          <div className="flex flex-wrap gap-2">
            {fields.map((field) => (
              <button
                key={field.id}
                type="button"
                onClick={() => setSelectedFieldId(field.id)}
                aria-pressed={selectedFieldId === field.id}
                className={cn(
                  "min-h-[48px] rounded-xl border-2 px-4 py-2 text-sm font-semibold transition-all",
                  selectedFieldId === field.id
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border bg-card text-muted-foreground hover:text-foreground"
                )}
              >
                {field.name}
                <span className="ml-1.5 text-xs font-normal opacity-70">
                  {field.acres} ac
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* APH summary */}
      {selectedField && selectedAph ? (
        <YieldSummaryCard aph={selectedAph} fieldName={selectedField.name} />
      ) : selectedField ? (
        <div className="rounded-xl border border-border bg-card px-4 py-8 text-center">
          <p className="text-sm text-muted-foreground">
            No APH data available for {selectedField.name} yet.
          </p>
        </div>
      ) : null}

      {/* Bar chart */}
      <YieldBarChart records={fieldRecords} />

      {/* Year-by-year table */}
      <div className="space-y-3">
        <h2 className="font-heading text-lg font-semibold text-foreground">
          Year-by-year records
        </h2>
        <YieldTable records={fieldRecords} />
      </div>

      {/* APH explanation */}
      <div className="rounded-xl border border-border bg-card px-4 py-5 space-y-3">
        <div className="flex items-center gap-2">
          <Info
            className="h-4 w-4 text-primary shrink-0"
            aria-hidden="true"
          />
          <h3 className="font-heading text-sm font-semibold text-foreground">
            What is APH and why does it matter?
          </h3>
        </div>
        <div className="space-y-2 text-sm text-muted-foreground leading-relaxed">
          <p>
            <strong className="text-foreground">
              APH (Actual Production History)
            </strong>{" "}
            is the average yield per acre calculated from your last 4–10 years
            of harvest records. Your crop insurance company uses this number to
            set your coverage level.
          </p>
          <p>
            If you have a bad year and your actual yield drops below your
            guarantee, you file a claim. A higher APH means a higher guarantee
            per acre — which means a bigger payout if disaster strikes.
          </p>
          <p>
            <strong className="text-foreground">
              Every harvest you log here
            </strong>{" "}
            goes into your APH calculation. Accurate records protect you.
            Missing records can lower your APH and your coverage.
          </p>
        </div>
        <div className="pt-1">
          <a
            href="https://www.rma.usda.gov/en/Fact-Sheets/National-Fact-Sheets/Actual-Production-History-APH"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
            aria-label="Learn more about APH on USDA RMA website (opens in new tab)"
          >
            Learn more at USDA RMA
          </a>
        </div>
      </div>

      {/* Quick link back */}
      <div className="text-center">
        <Link
          href={farmId ? `/activities?farm_id=${farmId}` : "/activities"}
          className="text-sm font-medium text-primary hover:underline"
        >
          Back to Field Activity Log
        </Link>
      </div>
    </div>
  );
}
