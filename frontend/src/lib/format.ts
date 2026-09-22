/**
 * Display formatters shared by server and client components.
 *
 * Locale is pinned to en-US so server-rendered and hydrated output match.
 * Every formatter accepts null/undefined/invalid input and returns `fallback`
 * (default "—") instead of "Invalid Date" or "NaN".
 */

const LOCALE = "en-US";
const DEFAULT_FALLBACK = "—";

const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

type Fallback = { fallback?: string };

function toDate(value: string | Date): { date: Date; dateOnly: boolean } {
  if (value instanceof Date) return { date: value, dateOnly: false };
  // "2026-09-25" parses as UTC midnight, which is the previous evening in US
  // time zones. Format date-only strings in UTC so the calendar day is kept.
  const dateOnly = DATE_ONLY.test(value);
  return { date: new Date(dateOnly ? `${value}T00:00:00Z` : value), dateOnly };
}

/**
 * Format a date for display, e.g. "Sep 25, 2026".
 * Date-only strings ("2026-09-25") never shift a day across time zones.
 */
export function formatDate(
  value: string | Date | null | undefined,
  opts: Intl.DateTimeFormatOptions & Fallback = {}
): string {
  const { fallback = DEFAULT_FALLBACK, ...intlOpts } = opts;
  if (value === null || value === undefined || value === "") return fallback;

  const { date, dateOnly } = toDate(value);
  if (Number.isNaN(date.getTime())) return fallback;

  const hasFields =
    intlOpts.year || intlOpts.month || intlOpts.day || intlOpts.weekday;
  return date.toLocaleDateString(LOCALE, {
    ...(hasFields ? {} : { year: "numeric", month: "short", day: "numeric" }),
    ...intlOpts,
    ...(dateOnly ? { timeZone: "UTC" } : {}),
  });
}

/** Format a timestamp with time, e.g. "Sep 25, 2026, 3:04 PM" (viewer's time zone). */
export function formatDateTime(
  value: string | Date | null | undefined,
  opts: Intl.DateTimeFormatOptions & Fallback = {}
): string {
  const { fallback = DEFAULT_FALLBACK, ...intlOpts } = opts;
  if (value === null || value === undefined || value === "") return fallback;

  const { date } = toDate(value);
  if (Number.isNaN(date.getTime())) return fallback;

  return date.toLocaleString(LOCALE, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    ...intlOpts,
  });
}

interface NumberOpts extends Fallback {
  maxFractionDigits?: number;
  minFractionDigits?: number;
}

function isFiniteNumber(n: number | null | undefined): n is number {
  return typeof n === "number" && Number.isFinite(n);
}

/** Format a number with thousands separators, e.g. 1234.5 -> "1,234.5". */
export function formatNumber(
  n: number | null | undefined,
  { maxFractionDigits = 1, minFractionDigits = 0, fallback = DEFAULT_FALLBACK }: NumberOpts = {}
): string {
  if (!isFiniteNumber(n)) return fallback;
  return n.toLocaleString(LOCALE, {
    maximumFractionDigits: maxFractionDigits,
    minimumFractionDigits: Math.min(minFractionDigits, maxFractionDigits),
  });
}

/** Format US dollars, e.g. 12500 -> "$12,500" (whole dollars by default). */
export function formatUsd(
  n: number | null | undefined,
  { maxFractionDigits = 0, minFractionDigits = 0, fallback = DEFAULT_FALLBACK }: NumberOpts = {}
): string {
  if (!isFiniteNumber(n)) return fallback;
  return n.toLocaleString(LOCALE, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: maxFractionDigits,
    minimumFractionDigits: Math.min(minFractionDigits, maxFractionDigits),
  });
}

/**
 * Pick the singular or plural word for a count.
 * pluralize(1, "field") -> "field"; pluralize(3, "field") -> "fields".
 */
export function pluralize(
  count: number,
  singular: string,
  plural: string = `${singular}s`
): string {
  return count === 1 ? singular : plural;
}

/** Format acres with unit, e.g. 1 -> "1 acre", 1234.5 -> "1,234.5 acres", short: "1,234.5 ac". */
export function formatAcres(
  n: number | null | undefined,
  { short = false, ...opts }: NumberOpts & { short?: boolean } = {}
): string {
  if (!isFiniteNumber(n)) return opts.fallback ?? DEFAULT_FALLBACK;
  const unit = short ? "ac" : pluralize(n, "acre");
  return `${formatNumber(n, opts)} ${unit}`;
}
