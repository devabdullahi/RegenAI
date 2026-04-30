"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { RestrictedUseBadge } from "./restricted-use-badge";
import { ChevronDown, ChevronUp, Sprout, Droplets, FlaskConical, Eye, Wheat, Shovel, Leaf, ClipboardList } from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  FieldActivity,
  ActivityType,
  SprayDetails,
  PlantingDetails,
  FertilizeDetails,
  ScoutDetails,
  HarvestDetails,
  ScoutingSeverity,
} from "@/lib/api/types";

// ── Type badge config ──────────────────────────────────────────────────────────

const TYPE_CONFIG: Record<
  ActivityType,
  { label: string; icon: React.ElementType; bg: string; text: string; border: string }
> = {
  plant: {
    label: "Planting",
    icon: Sprout,
    bg: "bg-green-100",
    text: "text-green-700",
    border: "border-green-200",
  },
  spray: {
    label: "Spray",
    icon: Droplets,
    bg: "bg-blue-100",
    text: "text-blue-700",
    border: "border-blue-200",
  },
  fertilize: {
    label: "Fertilize",
    icon: FlaskConical,
    bg: "bg-amber-100",
    text: "text-amber-700",
    border: "border-amber-200",
  },
  scout: {
    label: "Scouting",
    icon: Eye,
    bg: "bg-purple-100",
    text: "text-purple-700",
    border: "border-purple-200",
  },
  harvest: {
    label: "Harvest",
    icon: Wheat,
    bg: "bg-orange-100",
    text: "text-orange-700",
    border: "border-orange-200",
  },
  tillage: {
    label: "Tillage",
    icon: Shovel,
    bg: "bg-stone-100",
    text: "text-stone-700",
    border: "border-stone-200",
  },
  cover_crop: {
    label: "Cover Crop",
    icon: Leaf,
    bg: "bg-teal-100",
    text: "text-teal-700",
    border: "border-teal-200",
  },
  other: {
    label: "Other",
    icon: ClipboardList,
    bg: "bg-gray-100",
    text: "text-gray-700",
    border: "border-gray-200",
  },
};

const SEVERITY_CONFIG: Record<ScoutingSeverity, { label: string; color: string }> = {
  none: { label: "None", color: "text-muted-foreground" },
  low: { label: "Low", color: "text-green-600" },
  moderate: { label: "Moderate", color: "text-amber-600" },
  high: { label: "High", color: "text-red-600" },
  critical: { label: "Critical", color: "text-red-800 font-bold" },
};

// ── Type badge ─────────────────────────────────────────────────────────────────

export function ActivityTypeBadge({ type }: { type: ActivityType }) {
  const config = TYPE_CONFIG[type];
  const Icon = config.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold",
        config.bg,
        config.text,
        config.border
      )}
    >
      <Icon className="h-3 w-3 shrink-0" aria-hidden="true" />
      {config.label}
    </span>
  );
}

// ── Key detail preview per type ────────────────────────────────────────────────

function ActivityPreview({ activity }: { activity: FieldActivity }) {
  const { activity_type, details } = activity;

  if (activity_type === "plant") {
    const d = details as PlantingDetails;
    return (
      <p className="text-sm text-foreground">
        <span className="font-medium">{d.variety}</span>
        {" — "}
        {d.seeding_rate_kac}K seeds/ac at {d.row_spacing_in}" rows
      </p>
    );
  }

  if (activity_type === "spray") {
    const d = details as SprayDetails;
    return (
      <p className="text-sm text-foreground">
        <span className="font-medium">{d.product_name}</span>
        {" — "}
        {d.rate_oz_ac} oz/ac targeting {d.target_pest}
      </p>
    );
  }

  if (activity_type === "fertilize") {
    const d = details as FertilizeDetails;
    return (
      <p className="text-sm text-foreground">
        <span className="font-medium">{d.product_name}</span>
        {" — "}
        {d.n_lbs_ac}-{d.p_lbs_ac}-{d.k_lbs_ac} lbs N-P-K/ac ({d.method})
      </p>
    );
  }

  if (activity_type === "scout") {
    const d = details as ScoutDetails;
    const sev = SEVERITY_CONFIG[d.severity];
    return (
      <p className="text-sm text-foreground">
        <span className="font-medium">{d.pest_name}</span>
        {" — "}
        <span className={sev.color}>{sev.label} pressure</span>
        {d.threshold_exceeded && (
          <span className="ml-1.5 rounded-full bg-red-100 px-1.5 py-0.5 text-xs font-semibold text-red-700">
            Threshold exceeded
          </span>
        )}
      </p>
    );
  }

  if (activity_type === "harvest") {
    const d = details as HarvestDetails;
    return (
      <p className="text-sm text-foreground">
        <span className="font-medium">{d.yield_bu_ac} bu/ac</span>
        {" — "}
        {d.moisture_pct}% moisture, {d.test_weight_lbs_bu} lbs/bu test weight
      </p>
    );
  }

  return null;
}

// ── Expanded detail section ────────────────────────────────────────────────────

function ActivityExpandedDetails({ activity }: { activity: FieldActivity }) {
  const { activity_type, details } = activity;

  function Row({ label, value }: { label: string; value: React.ReactNode }) {
    return (
      <div className="flex justify-between gap-4 py-1.5 border-b border-border/50 last:border-0">
        <span className="text-xs text-muted-foreground shrink-0">{label}</span>
        <span className="text-xs text-foreground text-right">{value}</span>
      </div>
    );
  }

  return (
    <div className="mt-3 rounded-lg bg-muted/40 px-3 py-2 space-y-0">
      {activity_type === "plant" && (() => {
        const d = details as PlantingDetails;
        return (
          <>
            <Row label="Variety" value={d.variety} />
            <Row label="Seeding Rate" value={`${d.seeding_rate_kac}K seeds/acre`} />
            <Row label="Row Spacing" value={`${d.row_spacing_in} inches`} />
            <Row label="Planting Depth" value={`${d.depth_in} inches`} />
          </>
        );
      })()}

      {activity_type === "spray" && (() => {
        const d = details as SprayDetails;
        return (
          <>
            <Row label="Product" value={d.product_name} />
            <Row label="EPA Reg #" value={d.epa_reg_number} />
            <Row label="Rate" value={`${d.rate_oz_ac} oz/ac`} />
            <Row label="Target Pest" value={d.target_pest} />
            <Row label="Wind Speed" value={`${d.wind_mph} mph`} />
            <Row label="Temperature" value={`${d.temp_f}°F`} />
            {d.restricted_use && d.applicator_name && (
              <Row label="Applicator" value={d.applicator_name} />
            )}
            {d.restricted_use && d.applicator_cert_number && (
              <Row label="Cert #" value={d.applicator_cert_number} />
            )}
          </>
        );
      })()}

      {activity_type === "fertilize" && (() => {
        const d = details as FertilizeDetails;
        return (
          <>
            <Row label="Product" value={d.product_name} />
            <Row label="Nitrogen (N)" value={`${d.n_lbs_ac} lbs/ac`} />
            <Row label="Phosphorus (P)" value={`${d.p_lbs_ac} lbs/ac`} />
            <Row label="Potassium (K)" value={`${d.k_lbs_ac} lbs/ac`} />
            <Row label="Method" value={d.method.charAt(0).toUpperCase() + d.method.slice(1)} />
          </>
        );
      })()}

      {activity_type === "scout" && (() => {
        const d = details as ScoutDetails;
        return (
          <>
            <Row label="Pest Type" value={d.pest_type.charAt(0).toUpperCase() + d.pest_type.slice(1)} />
            <Row label="Pest Name" value={d.pest_name} />
            <Row label="Pressure Level" value={d.severity.charAt(0).toUpperCase() + d.severity.slice(1)} />
            <Row label="At Threshold" value={d.threshold_exceeded ? "Yes — action needed" : "No — monitor only"} />
            {d.action_taken && <Row label="Action Taken" value={d.action_taken} />}
          </>
        );
      })()}

      {activity_type === "harvest" && (() => {
        const d = details as HarvestDetails;
        return (
          <>
            <Row label="Yield" value={`${d.yield_bu_ac} bu/acre`} />
            <Row label="Moisture" value={`${d.moisture_pct}%`} />
            <Row label="Test Weight" value={`${d.test_weight_lbs_bu} lbs/bu`} />
            {d.elevator_ticket && <Row label="Elevator Ticket" value={d.elevator_ticket} />}
          </>
        );
      })()}

      {activity.operator && <Row label="Operator" value={activity.operator} />}
      {activity.equipment && <Row label="Equipment" value={activity.equipment} />}
      {activity.cost_per_acre != null && (
        <Row label="Cost" value={`$${activity.cost_per_acre}/acre`} />
      )}
      {activity.notes && (
        <div className="pt-2">
          <p className="text-xs text-muted-foreground mb-0.5">Notes</p>
          <p className="text-xs text-foreground leading-relaxed">{activity.notes}</p>
        </div>
      )}
    </div>
  );
}

// ── Main card ──────────────────────────────────────────────────────────────────

interface ActivityCardProps {
  activity: FieldActivity;
  fieldName: string;
  defaultExpanded?: boolean;
}

export function ActivityCard({
  activity,
  fieldName,
  defaultExpanded = false,
}: ActivityCardProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const dateObj = new Date(activity.activity_date + "T12:00:00");
  const dateFormatted = dateObj.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  const isRestrictedUse =
    activity.activity_type === "spray" &&
    (activity.details as SprayDetails).restricted_use;

  return (
    <Card>
      <CardHeader className="border-b">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <ActivityTypeBadge type={activity.activity_type} />
            {isRestrictedUse && <RestrictedUseBadge size="sm" />}
          </div>
          <time
            dateTime={activity.activity_date}
            className="text-sm font-medium text-muted-foreground shrink-0"
          >
            {dateFormatted}
          </time>
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          {fieldName} &middot; {activity.acres.toLocaleString()} acres
        </p>
      </CardHeader>

      <CardContent className="pt-3">
        <ActivityPreview activity={activity} />

        {expanded && <ActivityExpandedDetails activity={activity} />}

        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="mt-3 flex min-h-[44px] w-full items-center justify-center gap-1.5 rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          aria-expanded={expanded}
        >
          {expanded ? (
            <>
              <ChevronUp className="h-3.5 w-3.5" aria-hidden="true" />
              Show less
            </>
          ) : (
            <>
              <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
              Show full details
            </>
          )}
        </button>
      </CardContent>
    </Card>
  );
}
