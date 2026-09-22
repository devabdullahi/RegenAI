/**
 * Record primitives — the house style in five parts.
 *
 * The app stands in for paperwork a farmer already keeps: plan sheets, scale
 * tickets, seed tags. These render that vocabulary. Prefer them to a Card with
 * a title: a sheet holds a whole section, a rule head divides it, a ledger row
 * states one figure, a stamp prints a program code, an edge note flags what
 * needs attention.
 */
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import { type Tone, toneEdgeClasses, toneTextClasses } from "@/lib/status-styles";

/** The paper a section is printed on: hairline border, cut corners, no lift. */
export function Sheet({
  className,
  children,
  ...props
}: React.ComponentProps<"section">) {
  return (
    <section
      className={cn("border border-border bg-card", className)}
      {...props}
    >
      {children}
    </section>
  );
}

/**
 * Section head: small-caps label, then a hairline to the end of the measure.
 * `action` sits past the rule, right-aligned, the way a form numbers its parts.
 */
export function RuleHead({
  label,
  action,
  className,
}: {
  label: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <h2 className="font-mono text-[0.6875rem] font-medium tracking-[0.14em] text-muted-foreground uppercase">
        {label}
      </h2>
      <span aria-hidden="true" className="h-px flex-1 bg-rule" />
      {action}
    </div>
  );
}

/**
 * One figure on a ticket: what it is, a dotted leader, what it reads.
 * `value` is set in mono with tabular figures so stacked rows align.
 */
export function LedgerRow({
  label,
  value,
  note,
  className,
}: {
  label: ReactNode;
  value: ReactNode;
  /** Optional second line under the label — a source, a date, a caveat. */
  note?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("ledger-row text-sm", className)}>
      <span className="text-muted-foreground">
        {label}
        {note ? (
          <span className="mt-0.5 block text-xs text-muted-foreground/80">
            {note}
          </span>
        ) : null}
      </span>
      <span className="font-medium text-foreground">{value}</span>
    </div>
  );
}

/** A program code as printed on a plan sheet: CPS 340, FY2026, 19169. */
export function Stamp({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <span className={cn("stamp", toneTextClasses[tone], className)}>
      {children}
    </span>
  );
}

/**
 * Edge note: a marked-up margin. A colored bar down the left edge carries the
 * status, so the note stays on the same paper instead of floating in a tinted
 * rounded box.
 */
export function EdgeNote({
  tone = "neutral",
  title,
  children,
  action,
  className,
}: {
  tone?: Tone;
  title?: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "border-l-[3px] bg-card py-3 pr-3 pl-4",
        toneEdgeClasses[tone],
        className
      )}
    >
      {title ? (
        <p className={cn("text-sm font-semibold", toneTextClasses[tone])}>
          {title}
        </p>
      ) : null}
      {children ? (
        <div className="text-sm text-muted-foreground">{children}</div>
      ) : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
