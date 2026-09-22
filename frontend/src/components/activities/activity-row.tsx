"use client";

import { useId, useState, type ReactNode } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { LedgerRow } from "@/components/shared/record";
import { RestrictedUseBadge } from "./restricted-use-badge";
import { getActivityTypeConfig } from "@/lib/activity-types";
import { formatAcres, formatDate, formatNumber, formatUsd } from "@/lib/format";
import { severityLabel, severityTextClasses } from "@/lib/status-styles";
import { cn } from "@/lib/utils";
import type {
  CoverCropDetails,
  FertilizeDetails,
  FieldActivity,
  HarvestDetails,
  PlantingDetails,
  ScoutDetails,
  SprayDetails,
  TillageDetails,
} from "@/lib/api/types";

/** [label, value]; rows whose value is undefined were not recorded and are hidden. */
type DetailRow = [label: string, value: ReactNode];

function amount(n: number | undefined, suffix: string): string | undefined {
  return n === undefined ? undefined : `${formatNumber(n, { maxFractionDigits: 2 })}${suffix}`;
}

function rate(n: number | undefined, unit: string | undefined): string | undefined {
  return amount(n, ` ${unit ?? "per acre"}`);
}

// ── Type-specific values ──────────────────────────────────────────────────────

function SeverityText({ severity, suffix = "" }: { severity: ScoutDetails["severity"]; suffix?: string }) {
  if (!severity) return null;
  return (
    <span className={severityTextClasses[severity]}>
      {severityLabel[severity]}
      {suffix}
    </span>
  );
}

/**
 * What the row says in words: the variety, product or pest. Figures are kept
 * out of this so they can be set in the column on the right.
 */
function rowDescription(activity: FieldActivity): ReactNode {
  switch (activity.activity_type) {
    case "plant":
      return (activity.details as PlantingDetails).variety;
    case "spray": {
      const d = activity.details as SprayDetails;
      return [d.product_name, d.target_pest && `targeting ${d.target_pest}`]
        .filter(Boolean)
        .join(" · ");
    }
    case "fertilize":
      return (activity.details as FertilizeDetails).product_name;
    case "scout": {
      const d = activity.details as ScoutDetails;
      if (!d.pest_name) return d.severity ? <SeverityText severity={d.severity} suffix=" pressure" /> : null;
      return (
        <>
          {d.pest_name}
          {d.severity && (
            <>
              {" · "}
              <SeverityText severity={d.severity} suffix=" pressure" />
            </>
          )}
        </>
      );
    }
    case "harvest": {
      const d = activity.details as HarvestDetails;
      return amount(d.moisture_pct, "% moisture");
    }
    case "cover_crop":
      return (activity.details as CoverCropDetails).species;
    default:
      return null;
  }
}

/** The one figure that leads this row: rate, yield or depth, always with a unit. */
function rowFigure(activity: FieldActivity): string | undefined {
  switch (activity.activity_type) {
    case "plant":
      return amount((activity.details as PlantingDetails).seeding_rate_kac, "K seeds/ac");
    case "spray": {
      const d = activity.details as SprayDetails;
      return rate(d.rate, d.rate_unit);
    }
    case "fertilize": {
      const d = activity.details as FertilizeDetails;
      return rate(d.rate, d.rate_unit);
    }
    case "harvest":
      return amount((activity.details as HarvestDetails).yield_bu_ac, " bu/ac");
    case "tillage":
      return amount((activity.details as TillageDetails).depth_in, " in deep");
    default:
      return undefined;
  }
}

function detailRows(activity: FieldActivity): DetailRow[] {
  switch (activity.activity_type) {
    case "plant": {
      const d = activity.details as PlantingDetails;
      return [
        ["Variety", d.variety],
        ["Seeding rate", amount(d.seeding_rate_kac, "K seeds/acre")],
        ["Seed treatment", d.seed_treatment],
      ];
    }
    case "spray": {
      const d = activity.details as SprayDetails;
      return [
        ["Product", d.product_name],
        ["Rate", rate(d.rate, d.rate_unit)],
        ["Target pest", d.target_pest],
        ["Applicator", d.applicator_name],
        ["Applicator cert #", d.applicator_cert_number],
      ];
    }
    case "fertilize": {
      const d = activity.details as FertilizeDetails;
      return [
        ["Product", d.product_name],
        ["Rate", rate(d.rate, d.rate_unit)],
      ];
    }
    case "scout": {
      const d = activity.details as ScoutDetails;
      return [
        ["Pest or problem", d.pest_name],
        ["Pressure level", d.severity && <SeverityText severity={d.severity} />],
      ];
    }
    case "harvest": {
      const d = activity.details as HarvestDetails;
      return [
        ["Yield", amount(d.yield_bu_ac, " bu/acre")],
        ["Moisture", amount(d.moisture_pct, "%")],
        ["Crop year", d.crop_year?.toString()],
      ];
    }
    case "tillage": {
      const d = activity.details as TillageDetails;
      return [["Depth", amount(d.depth_in, " inches")]];
    }
    case "cover_crop": {
      const d = activity.details as CoverCropDetails;
      return [["Species", d.species]];
    }
    default:
      return [];
  }
}

function hasValue(row: DetailRow): boolean {
  const value = row[1];
  return value !== undefined && value !== null && value !== "";
}

function ActivityExpandedDetails({ activity }: { activity: FieldActivity }) {
  const rows: DetailRow[] = [
    ...detailRows(activity),
    ["Operator", activity.operator],
    ["Equipment", activity.equipment],
    [
      "Cost",
      activity.cost_per_acre === undefined
        ? undefined
        : `${formatUsd(activity.cost_per_acre, { maxFractionDigits: 2 })}/acre`,
    ],
  ].filter((row): row is DetailRow => hasValue(row as DetailRow));

  if (rows.length === 0 && !activity.notes) {
    return (
      <p className="py-2 text-sm text-muted-foreground">
        No other details were recorded for this activity.
      </p>
    );
  }

  return (
    <div className="border-t border-border pt-1">
      {rows.length > 0 && (
        <div className="divide-y divide-border/60">
          {rows.map(([label, value]) => (
            <LedgerRow key={label} label={label} value={value} />
          ))}
        </div>
      )}
      {activity.notes && (
        <div className="pt-3">
          <p className="font-mono text-[0.6875rem] font-medium tracking-[0.14em] text-muted-foreground uppercase">
            Notes
          </p>
          <p className="mt-1 text-sm leading-relaxed whitespace-pre-line text-foreground">
            {activity.notes}
          </p>
        </div>
      )}
    </div>
  );
}

// ── Logbook row ───────────────────────────────────────────────────────────────

interface ActivityRowProps {
  activity: FieldActivity;
  fieldName: string;
  defaultExpanded?: boolean;
}

/**
 * One line of the field log: date, what was done, where, and the figures. The
 * whole line opens the full record, so a season of work scans as a column of
 * dates rather than a stack of cards.
 */
export function ActivityRow({ activity, fieldName, defaultExpanded = false }: ActivityRowProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const panelId = `${useId()}-details`;

  const config = getActivityTypeConfig(activity.activity_type);
  const Icon = config.icon;
  const description = rowDescription(activity);
  const figure = rowFigure(activity);
  const isRestrictedUse =
    activity.activity_type === "spray" && (activity.details as SprayDetails).restricted_use;

  return (
    <div className="border-b border-border">
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
        aria-controls={panelId}
        className="flex w-full flex-wrap items-baseline gap-x-4 gap-y-1 py-3 text-left transition-colors hover:bg-muted/40 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        <time
          dateTime={activity.activity_date}
          className="w-24 shrink-0 font-mono text-xs tabular-nums text-muted-foreground"
        >
          {formatDate(activity.activity_date)}
        </time>

        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
            {/* The type mark aids recognition when scanning a long season. */}
            <Icon
              className={cn("size-4 shrink-0 translate-y-0.5", config.markerClasses)}
              aria-hidden="true"
            />
            <span className="font-medium text-foreground">{config.label}</span>
            <span className="text-muted-foreground">{fieldName}</span>
            {isRestrictedUse && <RestrictedUseBadge />}
          </span>
          {description && (
            <span className="mt-0.5 block text-sm text-muted-foreground">
              {description}
            </span>
          )}
        </span>

        <span className="flex shrink-0 items-baseline gap-4 font-mono text-sm tabular-nums">
          {figure && <span className="text-foreground">{figure}</span>}
          <span className="w-20 text-right text-muted-foreground">
            {formatAcres(activity.acres, { short: true })}
          </span>
          {expanded ? (
            <ChevronUp className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          ) : (
            <ChevronDown className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          )}
          <span className="sr-only">
            {expanded ? "Hide full details" : "Show full details"}
          </span>
        </span>
      </button>

      <div id={panelId} hidden={!expanded} className="pb-3 sm:pl-28">
        {expanded && <ActivityExpandedDetails activity={activity} />}
      </div>
    </div>
  );
}
