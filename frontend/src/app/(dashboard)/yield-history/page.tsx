"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Loader2, Plus, Wheat } from "lucide-react";
import { YieldSummaryCard } from "@/components/activities/yield-summary-card";
import { ButtonLink } from "@/components/shared/button-link";
import { RuleHead } from "@/components/shared/record";
import {
  EmptyState,
  ErrorState,
  NoFarmSelected,
} from "@/components/shared/page-states";
import { Button } from "@/components/ui/button";
import { api, ApiRequestError } from "@/lib/api/client";
import { aphToView, yieldRecordToView } from "@/lib/api/adapters";
import { yieldUnitForCrop, type YieldUnit } from "@/lib/crops";
import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";
import type {
  APHResult,
  Field,
  YieldHistoryRecord,
  YieldRecord,
} from "@/lib/api/types";

const APH_FACT_SHEET_URL =
  "https://www.rma.usda.gov/en/Fact-Sheets/National-Fact-Sheets/Actual-Production-History-APH";

/**
 * Bar fill per crop, from the chart tokens in globals.css. There are more
 * crops than tokens, so fills repeat; the crop is named under every bar.
 */
const CROP_BAR_CLASSES: Record<string, string> = {
  corn: "bg-chart-2",
  soybeans: "bg-chart-1",
  wheat: "bg-chart-3",
  sorghum: "bg-soil",
  cotton: "bg-chart-4",
  rice: "bg-chart-5",
  barley: "bg-chart-1",
  oats: "bg-chart-3",
  rye: "bg-chart-3",
  canola: "bg-chart-2",
  sunflower: "bg-chart-2",
  "dry beans": "bg-chart-1",
  peanuts: "bg-chart-4",
  sugarbeets: "bg-chart-5",
  "alfalfa / hay": "bg-chart-1",
};

/**
 * The unit every record shares, or null when a field's rotation mixes crops
 * that are not reported in the same unit (e.g. corn in bu/ac and hay in
 * ton/ac). Callers label each figure individually when this is null.
 */
function sharedYieldUnit(records: YieldRecord[]): YieldUnit | null {
  const units = new Set(records.map((r) => yieldUnitForCrop(r.crop_type)));
  const [onlyUnit] = [...units];
  return units.size === 1 && onlyUnit !== undefined ? onlyUnit : null;
}

// ── Yield trend ───────────────────────────────────────────────────────────────

function YieldBarChart({ records }: { records: YieldRecord[] }) {
  if (records.length === 0) return null;

  const sorted = [...records].sort((a, b) => a.crop_year - b.crop_year);
  const maxYield = Math.max(...sorted.map((r) => r.yield_bu_ac));
  const unit = sharedYieldUnit(sorted);

  return (
    <div>
      <RuleHead label={unit ? `Yield by year, ${unit}` : "Yield by year"} />
      {unit === null && (
        <p className="mt-2 text-sm text-muted-foreground">
          These years are not all reported in the same unit, so bar heights are
          not comparable. Each year&apos;s unit is listed in the table below.
        </p>
      )}
      <div className="mt-3 flex items-end gap-2 border-b border-border" style={{ height: "140px" }}>
        {sorted.map((record) => {
          const heightPct = (record.yield_bu_ac / maxYield) * 100;
          const barColor =
            CROP_BAR_CLASSES[record.crop_type.toLowerCase()] ?? "bg-primary";
          return (
            <div
              key={record.id}
              className="flex h-full flex-1 flex-col items-center justify-end gap-1"
            >
              <span className="font-mono text-xs tabular-nums text-foreground">
                {record.yield_bu_ac}
              </span>
              <div
                className={cn("w-full", barColor)}
                style={{ height: `${Math.max(heightPct, 8)}%` }}
                role="img"
                aria-label={`${record.crop_year}: ${record.yield_bu_ac} ${yieldUnitForCrop(record.crop_type)} ${record.crop_type}`}
              />
            </div>
          );
        })}
      </div>
      <div className="flex gap-2">
        {sorted.map((record) => (
          <div key={record.id} className="flex flex-1 flex-col items-center pt-1.5">
            <span className="font-mono text-xs tabular-nums text-foreground">
              {record.crop_year}
            </span>
            <span className="font-mono text-[0.6875rem] tracking-[0.08em] text-muted-foreground uppercase">
              {record.crop_type}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Yield table ───────────────────────────────────────────────────────────────

const HEAD_CELL =
  "py-2 font-mono text-[0.6875rem] font-medium tracking-[0.14em] text-muted-foreground uppercase";

function YieldTable({
  records,
  fieldName,
}: {
  records: YieldRecord[];
  fieldName: string;
}) {
  const sorted = [...records].sort((a, b) => b.crop_year - a.crop_year);
  const unit = sharedYieldUnit(sorted);

  if (sorted.length === 0) {
    return (
      <p className="border-y border-border py-6 text-sm text-muted-foreground">
        No yield records yet.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[34rem] text-sm">
        <thead>
          <tr className="border-y border-border">
            <th scope="col" className={cn(HEAD_CELL, "pr-4 text-left")}>
              Year
            </th>
            <th scope="col" className={cn(HEAD_CELL, "pr-4 text-left")}>
              Field
            </th>
            <th scope="col" className={cn(HEAD_CELL, "pr-4 text-left")}>
              Crop
            </th>
            <th scope="col" className={cn(HEAD_CELL, "pl-4 text-right")}>
              {unit ? `Yield ${unit}` : "Yield"}
            </th>
            <th scope="col" className={cn(HEAD_CELL, "pl-4 text-right")}>
              Moisture %
            </th>
            <th scope="col" className={cn(HEAD_CELL, "pl-4 text-right")}>
              Acres ac
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {sorted.map((record) => (
            <tr key={record.id}>
              <td className="py-2.5 pr-4 font-mono tabular-nums text-foreground">
                {record.crop_year}
              </td>
              <td className="py-2.5 pr-4 text-muted-foreground">{fieldName}</td>
              <td className="py-2.5 pr-4 text-foreground capitalize">
                {record.crop_type}
              </td>
              <td className="py-2.5 pl-4 text-right font-mono font-medium tabular-nums text-foreground">
                {record.yield_bu_ac}
                {unit === null && (
                  <span className="ml-1 font-normal text-muted-foreground">
                    {yieldUnitForCrop(record.crop_type)}
                  </span>
                )}
              </td>
              <td className="py-2.5 pl-4 text-right font-mono tabular-nums text-muted-foreground">
                {record.moisture_pct === null
                  ? "—"
                  : formatNumber(record.moisture_pct)}
              </td>
              <td className="py-2.5 pl-4 text-right font-mono tabular-nums text-muted-foreground">
                {formatNumber(record.acres)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

/** Masthead of the yield sheet. */
function YieldHeading({ action }: { action?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3 border-b-2 border-rule-strong pb-3">
      <div>
        <h1 className="font-heading text-2xl font-semibold text-foreground sm:text-3xl">
          Yield history
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Your actual yields by year and field, and the APH they add up to.
        </p>
      </div>
      {action}
    </div>
  );
}

export default function YieldHistoryPage() {
  const searchParams = useSearchParams();

  // FE-016: Read farm_id from searchParams
  const farmId =
    searchParams.get("farm_id") ?? searchParams.get("farm") ?? null;

  const [recordsByField, setRecordsByField] = useState<
    Record<string, YieldRecord[]>
  >({});
  const [aphByField, setAphByField] = useState<Record<string, APHResult>>({});
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

      const currentFarmId: string = farmId;

      try {
        // Yield history and APH are per field on the backend.
        const farmFields = await api.fields.list(currentFarmId);
        const perField = await Promise.all(
          farmFields.map(async (f) => {
            const [records, aph] = await Promise.all([
              api.activities.getYieldHistory(f.id),
              // APH returns 422 until a field has >= 4 years of yield data.
              // Any other failure hides only the APH card, but is logged.
              api.activities.getAPH(f.id).catch((err: unknown) => {
                if (!(err instanceof ApiRequestError && err.code === 422)) {
                  console.error(`YieldHistoryPage: APH failed for field ${f.id}`, err);
                }
                return null;
              }),
            ]);
            return {
              fieldId: f.id,
              records: (records as YieldHistoryRecord[]).map((r) =>
                yieldRecordToView(r, currentFarmId)
              ),
              aph: aph ? aphToView(aph, currentFarmId) : null,
            };
          })
        );

        if (!cancelled) {
          const nextRecords: Record<string, YieldRecord[]> = {};
          const nextAph: Record<string, APHResult> = {};
          for (const entry of perField) {
            nextRecords[entry.fieldId] = entry.records;
            if (entry.aph) nextAph[entry.fieldId] = entry.aph;
          }
          setRecordsByField(nextRecords);
          setAphByField(nextAph);
          setFields(farmFields);
          // Default to first field that has yield data, else first field
          const firstWithData = perField.find((p) => p.records.length > 0);
          setSelectedFieldId(
            firstWithData?.fieldId ?? farmFields[0]?.id ?? null
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
  const selectedAph = selectedFieldId
    ? (aphByField[selectedFieldId] ?? null)
    : null;
  const fieldRecords = selectedFieldId
    ? (recordsByField[selectedFieldId] ?? [])
    : [];

  // ── No farm selected ─────────────────────────────────────────────────────────

  if (!farmId && !loading) {
    return (
      <div className="pb-20 sm:pb-0">
        <YieldHeading />
        <NoFarmSelected description="Choose a farm to see its yield history and APH." />
      </div>
    );
  }

  // ── Loading ───────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="pb-20 sm:pb-0">
        <YieldHeading />
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
      <div className="pb-20 sm:pb-0">
        <YieldHeading />
        <ErrorState
          title="Couldn't load yield history"
          message={error}
          actions={[]}
        >
          <Button variant="outline" onClick={() => window.location.reload()}>
            Try again
          </Button>
        </ErrorState>
      </div>
    );
  }

  // ── Main content ──────────────────────────────────────────────────────────────

  const addYieldHref = `/activities/new?type=harvest${
    farmId ? `&farm_id=${encodeURIComponent(farmId)}` : ""
  }`;

  return (
    <div className="pb-20 sm:pb-0">
      <YieldHeading
        action={
          <ButtonLink href={addYieldHref}>
            <Plus aria-hidden="true" />
            Add yield record
          </ButtonLink>
        }
      />

      <div className="space-y-8">
        {/* Which field the sheet is about */}
        {fields.length > 1 && (
          <div>
            <RuleHead label="Viewing field" />
            <div className="mt-2 flex flex-wrap gap-2">
              {fields.map((field) => (
                <button
                  key={field.id}
                  type="button"
                  onClick={() => setSelectedFieldId(field.id)}
                  aria-pressed={selectedFieldId === field.id}
                  className={cn(
                    "flex min-h-12 items-center gap-2 rounded-sm border px-4 py-2 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                    selectedFieldId === field.id
                      ? "border-foreground bg-muted text-foreground"
                      : "border-border bg-card text-muted-foreground hover:text-foreground"
                  )}
                >
                  {field.name}
                  <span className="font-mono text-xs tabular-nums opacity-80">
                    {formatNumber(field.acres)} ac
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* APH summary */}
        {selectedField && selectedAph ? (
          <YieldSummaryCard
            aph={selectedAph}
            fieldName={selectedField.name}
            yieldUnit={yieldUnitForCrop(selectedField.crop_type)}
          />
        ) : selectedField ? (
          <div>
            <RuleHead label={`APH — ${selectedField.name}`} />
            <p className="mt-3 text-sm text-muted-foreground">
              No APH for {selectedField.name} yet. APH needs at least 4 years of
              harvest records.
            </p>
          </div>
        ) : null}

        {/* Yield trend */}
        <YieldBarChart records={fieldRecords} />

        {/* Year-by-year records */}
        <div>
          <RuleHead label="Year-by-year records" />
          <div className="mt-3">
            {selectedField ? (
              <YieldTable records={fieldRecords} fieldName={selectedField.name} />
            ) : (
              <EmptyState
                icon={Wheat}
                title="No fields yet"
                message="Add a field to this farm before recording yields."
              />
            )}
          </div>
        </div>

        {/* What APH is */}
        <div>
          <RuleHead label="What APH is and why it matters" />
          <div className="reading mt-3 max-w-[62ch] space-y-3 text-muted-foreground">
            <p>
              <strong className="text-foreground">
                APH (Actual Production History)
              </strong>{" "}
              is the average yield per acre calculated from your last 4&ndash;10
              years of harvest records. Your crop insurance company uses this
              number to set your coverage level.
            </p>
            <p>
              If you have a bad year and your actual yield drops below your
              guarantee, you file a claim. A higher APH means a higher guarantee
              per acre &mdash; which means a bigger payout if disaster strikes.
            </p>
            <p>
              <strong className="text-foreground">
                Every harvest you log here
              </strong>{" "}
              goes into your APH calculation. Accurate records protect you.
              Missing records can lower your APH and your coverage.
            </p>
          </div>
          <div className="mt-2">
            <ButtonLink
              href={APH_FACT_SHEET_URL}
              external
              variant="link"
              className="px-0"
              aria-label="Learn more about APH on the USDA RMA website"
            >
              Learn more at USDA RMA
            </ButtonLink>
          </div>
        </div>

        {/* Back to the log */}
        <div className="border-t border-border pt-4">
          <Link
            href={
              farmId
                ? `/activities?farm_id=${encodeURIComponent(farmId)}`
                : "/activities"
            }
            className="inline-flex min-h-12 items-center text-sm font-medium text-primary hover:underline"
          >
            Back to the field log
          </Link>
        </div>
      </div>
    </div>
  );
}
