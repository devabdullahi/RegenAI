import { Cloud, CloudRain } from "lucide-react";
import { LedgerRow, RuleHead, Sheet } from "@/components/shared/record";
import { formatDate, formatNumber } from "@/lib/format";
import type { WeatherData } from "@/lib/api/types";

const MM_PER_INCH = 25.4;

/** The backend stores Open-Meteo temperatures in °C; farmers read °F. */
function celsiusToFahrenheit(celsius: number | null): number | null {
  return celsius === null ? null : (celsius * 9) / 5 + 32;
}

function getSoilTempNote(soilTemp: number): string {
  if (soilTemp >= 55) return "Great for planting most crops";
  if (soilTemp >= 50) return "Good for planting corn and soybeans";
  if (soilTemp >= 45) return "Getting close — hold off on planting a few more days";
  if (soilTemp >= 40) return "Too cold for corn — wait for warmer soil";
  return "Too cold for field work right now";
}

function formatDegrees(celsius: number | null): string {
  const fahrenheit = celsiusToFahrenheit(celsius);
  const formatted = formatNumber(fahrenheit, { maxFractionDigits: 0 });
  return fahrenheit === null ? formatted : `${formatted}°F`;
}

/** Rain in inches with its unit, e.g. "0.4 in". */
function formatInches(precipMm: number): string {
  return `${formatNumber(precipMm / MM_PER_INCH, { maxFractionDigits: 1 })} in`;
}

/** Today's calendar date as YYYY-MM-DD in the viewer's (or server's) time zone. */
function todayIsoDate(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

/**
 * Split stored forecast rows into "today" and the days shown in the strip.
 * Rows are kept from the last enrichment, so they can be stale: today is the
 * row dated today, else the most recent past row, else the first future row.
 */
function selectForecast(weather: WeatherData[]) {
  const byDate = [...weather].sort((a, b) => a.date.localeCompare(b.date));
  const today = todayIsoDate();
  const pastOrToday = byDate.filter((d) => d.date <= today);
  const current = pastOrToday[pastOrToday.length - 1] ?? byDate[0];
  const days = byDate.filter((d) => d.date >= (current?.date ?? today));
  return { current, days, isToday: current?.date === today };
}

/** The one icon that earns its place here: what the sky is doing. */
function RainIcon({ precipMm }: { precipMm: number | null }) {
  if (precipMm === null) {
    return <Cloud className="h-5 w-5 text-muted-foreground" aria-label="Rain unknown" />;
  }
  if (precipMm > 0) {
    return <CloudRain className="h-5 w-5 text-weather" aria-label="Rain expected" />;
  }
  return <Cloud className="h-5 w-5 text-muted-foreground" aria-label="No rain" />;
}

/** One column of the forecast strip: day, sky, high, low, rain. */
function DayColumn({ day, label }: { day: WeatherData; label: string }) {
  const hasRain = day.precip_mm !== null && day.precip_mm > 0;

  return (
    <div className="flex min-w-[68px] flex-1 flex-col items-center gap-1.5 px-2 py-3">
      <span className="font-mono text-[0.6875rem] font-medium tracking-[0.08em] text-muted-foreground uppercase">
        {label}
      </span>
      <RainIcon precipMm={day.precip_mm} />
      <span className="font-mono text-sm font-medium text-foreground">
        <span className="sr-only">High </span>
        {formatDegrees(day.temp_high)}
      </span>
      <span className="font-mono text-xs text-muted-foreground">
        <span className="sr-only">Low </span>
        {formatDegrees(day.temp_low)}
      </span>
      <span className="font-mono text-xs text-weather">
        {hasRain && day.precip_mm !== null ? (
          <>
            <span className="sr-only">Rain </span>
            {formatInches(day.precip_mm)}
          </>
        ) : (
          <span aria-hidden="true">&nbsp;</span>
        )}
      </span>
    </div>
  );
}

interface WeatherWidgetProps {
  weather: WeatherData[] | null | undefined;
}

export function WeatherWidget({ weather }: WeatherWidgetProps) {
  if (!weather || weather.length === 0) {
    return <WeatherWidgetEmpty />;
  }

  const { current, days, isToday } = selectForecast(weather);
  const soilTemp = celsiusToFahrenheit(current?.soil_temp ?? null);
  const title = days.length === 1 ? "Weather" : `${days.length}-day forecast`;

  return (
    <Sheet className="p-4">
      <RuleHead label={title} />

      {!isToday && current && (
        <p className="mt-3 text-xs text-muted-foreground">
          Latest forecast starts {formatDate(current.date)}.
        </p>
      )}

      {/* Day strip — columns divided by hairlines, figures in one column each */}
      <div className="mt-3 flex divide-x divide-border overflow-x-auto border-y border-border">
        {days.map((day, index) => (
          <DayColumn
            key={day.id}
            day={day}
            label={
              index === 0 && isToday
                ? "Today"
                : formatDate(day.date, { weekday: "short" })
            }
          />
        ))}
      </div>

      <LedgerRow
        className="mt-1"
        label="Soil temp"
        note={
          soilTemp === null
            ? "No soil temperature reading for this day."
            : getSoilTempNote(soilTemp)
        }
        value={soilTemp === null ? "—" : `${formatNumber(soilTemp)}°F`}
      />
    </Sheet>
  );
}

export function WeatherWidgetEmpty() {
  return (
    <Sheet className="p-4">
      <RuleHead label="Weather" />
      <p className="mt-3 text-sm text-muted-foreground">
        No weather data for this field yet. It is added when the field&apos;s
        location is looked up.
      </p>
    </Sheet>
  );
}
