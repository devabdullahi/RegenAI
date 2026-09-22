/**
 * Full-page / section states: error, empty, and "no farm selected".
 *
 * Set like a note written on the sheet itself: a small marker, a title, a line
 * of explanation, then what to do next. No illustration, no tinted tile.
 *
 * Works in Server and Client Components (no "use client"; actions render via
 * ButtonLink). For a client-only action such as an error boundary's reset(),
 * pass a <Button onClick=...> as `children` instead of `actions`.
 *
 *   <ErrorState title="Unable to load checklist" message={message} />
 *   <NoFarmSelected description="Choose a farm to view your CSP application checklist." />
 *   <EmptyState icon={ClipboardList} title="No activities yet"
 *     actions={[{ label: "Log an activity", href: "/activities/new" }]} />
 */

import type { ReactNode } from "react";
import { AlertCircle, Tractor, type LucideIcon } from "lucide-react";
import { ButtonLink } from "@/components/shared/button-link";
import { cn } from "@/lib/utils";

export interface PageStateAction {
  label: string;
  href: string;
  variant?: "default" | "outline" | "secondary" | "ghost";
  icon?: LucideIcon;
}

interface PageStateBaseProps {
  title: string;
  /** Plain-language explanation. */
  message?: ReactNode;
  /** Link buttons, rendered in order (first is the primary action). */
  actions?: PageStateAction[];
  /** Custom content rendered with the actions (e.g. a client-side retry Button). */
  children?: ReactNode;
  /** Wrap in a bordered record sheet. */
  card?: boolean;
  className?: string;
}

interface StateShellProps extends PageStateBaseProps {
  icon: LucideIcon;
  /** Color of the state marker — a severity cue, never decoration. */
  iconClasses: string;
  /** 3px left edge bar, the way a problem is marked in a margin. */
  edgeClasses?: string;
  /** role="alert" for errors so screen readers announce them. */
  role?: "alert" | "status";
}

function StateShell({
  icon: Icon,
  iconClasses,
  edgeClasses,
  title,
  message,
  actions = [],
  children,
  card = false,
  className,
  role,
}: StateShellProps) {
  return (
    <div
      role={role}
      className={cn(
        "py-12",
        card && "border border-border bg-card px-5 py-10",
        edgeClasses && cn("border-l-[3px] pl-5", edgeClasses),
        className
      )}
    >
      <div className="flex items-center gap-2">
        <Icon className={cn("size-4 shrink-0", iconClasses)} aria-hidden="true" />
        <h2 className="font-heading text-xl font-semibold text-foreground">
          {title}
        </h2>
      </div>
      {message && (
        <p className="reading mt-2 max-w-[56ch] text-muted-foreground">
          {message}
        </p>
      )}
      {(children || actions.length > 0) && (
        <div className="mt-6 flex flex-wrap items-center gap-3">
          {children}
          {actions.map(({ label, href, variant, icon: ActionIcon }, index) => (
            <ButtonLink
              key={`${href}-${label}`}
              href={href}
              variant={variant ?? (index === 0 ? "default" : "outline")}
            >
              {ActionIcon && <ActionIcon aria-hidden="true" />}
              {label}
            </ButtonLink>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Error ─────────────────────────────────────────────────────────────────────

export interface ErrorStateProps extends Partial<PageStateBaseProps> {
  icon?: LucideIcon;
}

/**
 * Something failed to load. Defaults: title "Something went wrong", a generic
 * connection message, and an outline "Back to farms" action.
 */
export function ErrorState({
  title = "Something went wrong",
  message = "We had trouble loading your farm data. Check your connection and try again.",
  actions = [{ label: "Back to farms", href: "/farms", variant: "outline" }],
  icon = AlertCircle,
  ...rest
}: ErrorStateProps) {
  return (
    <StateShell
      role="alert"
      icon={icon}
      iconClasses="text-destructive"
      edgeClasses="border-l-destructive"
      title={title}
      message={message}
      actions={actions}
      {...rest}
    />
  );
}

// ── Empty ─────────────────────────────────────────────────────────────────────

export interface EmptyStateProps extends PageStateBaseProps {
  icon: LucideIcon;
}

/** Nothing to show yet (no records, no results). Neutral styling. */
export function EmptyState({ icon, ...rest }: EmptyStateProps) {
  return (
    <StateShell
      role="status"
      icon={icon}
      iconClasses="text-muted-foreground"
      {...rest}
    />
  );
}

// ── No farm selected ─────────────────────────────────────────────────────────

export interface NoFarmSelectedProps extends Partial<PageStateBaseProps> {
  /** What the page shows once a farm is chosen. */
  description?: ReactNode;
  icon?: LucideIcon;
}

/**
 * Page opened without a farm_id. Defaults: "Select a farm first" with a
 * "Go to My Farms" primary action.
 */
export function NoFarmSelected({
  title = "Select a farm first",
  description = "Choose a farm to see its recommendations, field data, and program eligibility.",
  message,
  actions = [{ label: "Go to My Farms", href: "/farms", icon: Tractor }],
  icon = Tractor,
  ...rest
}: NoFarmSelectedProps) {
  return (
    <StateShell
      icon={icon}
      iconClasses="text-muted-foreground"
      title={title}
      message={message ?? description}
      actions={actions}
      {...rest}
    />
  );
}
