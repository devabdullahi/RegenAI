import { ButtonLink } from "@/components/shared/button-link";
import { Stamp } from "@/components/shared/record";
import { Skeleton } from "@/components/ui/skeleton";
import { type Tone } from "@/lib/status-styles";
import type { CreditEligibility, CreditStatus } from "@/lib/api/types";

const STATUS_STAMP: Record<CreditStatus, { label: string; tone: Tone }> = {
  eligible: { label: "Eligible", tone: "success" },
  pending_review: { label: "Pending review", tone: "warning" },
  not_eligible: { label: "Not eligible", tone: "destructive" },
};

function creditsHref(farmId?: string): string {
  return farmId ? `/credits?farm_id=${encodeURIComponent(farmId)}` : "/credits";
}

/** One program, printed as a row on the sheet: name, status, notes, next step. */
function ProgramRow({
  name,
  description,
  credit,
  action,
  farmId,
}: {
  name: string;
  description: string;
  credit: CreditEligibility;
  action: string;
  farmId?: string;
}) {
  const status = STATUS_STAMP[credit.status];

  return (
    <div className="py-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-heading text-base font-semibold text-foreground">
            {name}
          </p>
          <p className="text-xs text-muted-foreground">{description}</p>
        </div>
        <Stamp tone={status.tone}>{status.label}</Stamp>
      </div>

      {credit.practices_documented.length > 0 && (
        <div className="mt-3">
          <p className="font-mono text-[0.6875rem] font-medium tracking-[0.14em] text-muted-foreground uppercase">
            Documented practices
          </p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {credit.practices_documented.map((code) => (
              <Stamp key={code}>Practice {code}</Stamp>
            ))}
          </div>
        </div>
      )}

      {credit.notes && (
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          {credit.notes}
        </p>
      )}

      <ButtonLink
        href={creditsHref(farmId)}
        variant="outline"
        size="sm"
        className="mt-3"
      >
        {action}
      </ButtonLink>
    </div>
  );
}

interface CreditPanelProps {
  credits: CreditEligibility[] | null | undefined;
  farmId?: string;
}

export function CreditPanel({ credits, farmId }: CreditPanelProps) {
  if (!credits || credits.length === 0) {
    return <CreditPanelEmpty />;
  }

  const eqip = credits.find((c) => c.program === "EQIP");
  const vcm = credits.find((c) => c.program === "VCM");

  if (!eqip && !vcm) {
    return (
      <p className="py-4 text-sm text-muted-foreground">
        No program data available for this farm yet.
      </p>
    );
  }

  return (
    <div className="divide-y divide-border">
      {eqip && (
        <ProgramRow
          name="EQIP"
          description="Environmental Quality Incentives (cost-share program)"
          credit={eqip}
          action="View EQIP details"
          farmId={farmId}
        />
      )}
      {vcm && (
        <ProgramRow
          name="Voluntary Carbon Markets"
          description="VCM credits"
          credit={vcm}
          action="Learn more"
          farmId={farmId}
        />
      )}
    </div>
  );
}

export function CreditPanelEmpty() {
  return (
    <div className="divide-y divide-border">
      {["EQIP", "VCM"].map((label) => (
        <div key={label} className="space-y-2 py-4">
          <Skeleton className="h-4 w-24 rounded-sm" />
          <Skeleton className="h-3 w-56 rounded-sm" />
          <Skeleton className="h-3 w-4/5 rounded-sm" />
          <Skeleton className="h-9 w-40 rounded-sm" />
        </div>
      ))}
    </div>
  );
}
