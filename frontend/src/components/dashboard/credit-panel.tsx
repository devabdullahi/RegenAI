import Link from "next/link";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { FileText, Leaf, CheckCircle2, Clock, XCircle, ChevronRight } from "lucide-react";
import type { CreditEligibility } from "@/lib/api/types";

function StatusBadge({ status }: { status: CreditEligibility["status"] }) {
  if (status === "eligible") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-semibold text-green-700">
        <CheckCircle2 className="h-3 w-3" />
        Eligible
      </span>
    );
  }
  if (status === "pending_review") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-700">
        <Clock className="h-3 w-3" />
        Pending Review
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-semibold text-red-700">
      <XCircle className="h-3 w-3" />
      Not Eligible
    </span>
  );
}

function EqipCard({
  credit,
  farmId,
}: {
  credit: CreditEligibility;
  farmId?: string;
}) {
  const creditsHref = farmId ? `/credits?farm_id=${farmId}` : "/credits";

  return (
    <div className="rounded-xl border border-border bg-card p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
            <FileText className="h-4 w-4 text-primary" />
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">EQIP</p>
            <p className="text-xs text-muted-foreground">
              Environmental Quality Incentives
            </p>
          </div>
        </div>
        <StatusBadge status={credit.status} />
      </div>

      {credit.practices_documented.length > 0 && (
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-1.5">
            Documented practices
          </p>
          <div className="flex flex-wrap gap-1.5">
            {credit.practices_documented.map((code) => (
              <span
                key={code}
                className="inline-flex items-center rounded-md bg-muted px-2 py-0.5 text-xs font-mono font-medium text-foreground"
              >
                Practice {code}
              </span>
            ))}
          </div>
        </div>
      )}

      {credit.notes && (
        <p className="text-sm text-muted-foreground leading-relaxed">
          {credit.notes}
        </p>
      )}

      <Link href={creditsHref}>
        <Button
          variant="outline"
          className="w-full min-h-[48px] cursor-pointer text-primary border-primary/30 hover:bg-primary/5 hover:border-primary"
        >
          View EQIP Details
          <ChevronRight className="ml-1 h-4 w-4" />
        </Button>
      </Link>
    </div>
  );
}

function VcmCard({
  credit,
  farmId,
}: {
  credit: CreditEligibility;
  farmId?: string;
}) {
  const creditsHref = farmId ? `/credits?farm_id=${farmId}` : "/credits";

  // Parse estimated credits from notes (e.g., "Estimated 1.2 carbon credits per acre")
  const creditMatch = credit.notes.match(/(\d+\.?\d*)\s+carbon credits? per acre/i);
  const creditsPerAcre = creditMatch ? creditMatch[1] : null;

  return (
    <div className="rounded-xl border border-border bg-card p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/10">
            <Leaf className="h-4 w-4 text-accent" />
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">
              Voluntary Carbon Markets
            </p>
            <p className="text-xs text-muted-foreground">VCM credits</p>
          </div>
        </div>
        <StatusBadge status={credit.status} />
      </div>

      {creditsPerAcre && (
        <div className="rounded-lg bg-accent/5 border border-accent/20 px-3 py-2.5">
          <p className="text-xs text-muted-foreground">Estimated yield</p>
          <p className="text-lg font-bold text-foreground leading-tight">
            {creditsPerAcre}{" "}
            <span className="text-sm font-medium text-muted-foreground">
              carbon credits / acre
            </span>
          </p>
        </div>
      )}

      {credit.notes && (
        <p className="text-sm text-muted-foreground leading-relaxed">
          {credit.notes}
        </p>
      )}

      <Link href={creditsHref}>
        <Button
          className="w-full min-h-[48px] bg-accent text-accent-foreground hover:bg-accent/90 cursor-pointer"
        >
          Learn More
          <ChevronRight className="ml-1 h-4 w-4" />
        </Button>
      </Link>
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

  return (
    <div className="space-y-3">
      {eqip && <EqipCard credit={eqip} farmId={farmId} />}
      {vcm && <VcmCard credit={vcm} farmId={farmId} />}
      {!eqip && !vcm && (
        <p className="text-sm text-muted-foreground text-center py-4">
          No program data available for this farm yet.
        </p>
      )}
    </div>
  );
}

export function CreditPanelEmpty() {
  return (
    <div className="space-y-3">
      {["EQIP", "VCM"].map((label) => (
        <div
          key={label}
          className="rounded-xl border border-border bg-card p-4 space-y-3"
        >
          <div className="flex items-center gap-2">
            <Skeleton className="h-8 w-8 rounded-lg" />
            <div className="space-y-1">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-3 w-36" />
            </div>
          </div>
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-4/5" />
          <Skeleton className="h-12 w-full rounded-lg" />
        </div>
      ))}
    </div>
  );
}
