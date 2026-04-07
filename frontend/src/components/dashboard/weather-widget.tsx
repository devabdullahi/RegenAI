import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Sun, CloudRain, Thermometer, Droplets } from "lucide-react";
import type { WeatherData } from "@/lib/api/types";

const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function getSoilTempNote(soilTemp: number): string {
  if (soilTemp >= 55) return "Great for planting most crops";
  if (soilTemp >= 50) return "Good for planting corn and soybeans";
  if (soilTemp >= 45) return "Getting close — hold off on planting a few more days";
  if (soilTemp >= 40) return "Too cold for corn — wait for warmer soil";
  return "Too cold for field work right now";
}

function DayCard({ day }: { day: WeatherData }) {
  const date = new Date(day.date + "T12:00:00");
  const dayName = DAY_NAMES[date.getUTCDay()];
  const hasRain = day.precip_mm > 0;

  return (
    <div className="flex min-w-[64px] flex-1 flex-col items-center gap-1 rounded-xl bg-muted/50 px-2 py-3">
      <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
        {dayName}
      </span>
      <div className="my-1">
        {hasRain ? (
          <CloudRain className="h-6 w-6 text-blue-500" aria-label="Rain expected" />
        ) : (
          <Sun className="h-6 w-6 text-amber-400" aria-label="Sunny" />
        )}
      </div>
      <span className="text-sm font-semibold text-foreground">
        {day.temp_high}&deg;
      </span>
      <span className="text-xs text-muted-foreground">{day.temp_low}&deg;</span>
      {hasRain && (
        <div className="mt-0.5 flex items-center gap-0.5">
          <Droplets className="h-3 w-3 text-blue-400" />
          <span className="text-[10px] text-blue-500 font-medium">
            {Math.round(day.precip_mm / 25.4 * 10) / 10}&quot;
          </span>
        </div>
      )}
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

  const todayData = weather[0];
  const soilTemp = todayData?.soil_temp;

  return (
    <Card>
      <CardHeader className="border-b pb-3">
        <CardTitle className="flex items-center gap-2 text-base font-semibold font-heading">
          <Sun className="h-5 w-5 text-amber-400" />
          5-Day Forecast
        </CardTitle>
      </CardHeader>

      <CardContent className="pt-3">
        {/* Day strip */}
        <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
          {weather.map((day) => (
            <DayCard key={day.id} day={day} />
          ))}
        </div>

        {/* Soil temp callout */}
        {soilTemp !== undefined && (
          <div className="mt-4 flex items-start gap-3 rounded-xl bg-primary/5 border border-primary/20 px-4 py-3">
            <Thermometer className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
            <div>
              <p className="text-sm font-semibold text-foreground">
                Soil temp: {soilTemp}&deg;F
              </p>
              <p className="mt-0.5 text-sm text-muted-foreground">
                {getSoilTempNote(soilTemp)}
              </p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function WeatherWidgetEmpty() {
  return (
    <Card>
      <CardHeader className="border-b pb-3">
        <CardTitle className="flex items-center gap-2 text-base font-semibold font-heading">
          <Sun className="h-5 w-5 text-amber-400" />
          5-Day Forecast
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-3">
        <div className="flex gap-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="flex flex-1 flex-col items-center gap-2 rounded-xl bg-muted/50 px-2 py-3"
            >
              <Skeleton className="h-3 w-8" />
              <Skeleton className="h-6 w-6 rounded-full" />
              <Skeleton className="h-4 w-6" />
              <Skeleton className="h-3 w-4" />
            </div>
          ))}
        </div>
        <div className="mt-4 rounded-xl bg-muted px-4 py-3">
          <Skeleton className="h-4 w-36" />
          <Skeleton className="mt-1.5 h-3 w-48" />
        </div>
        <p className="mt-3 text-center text-sm text-muted-foreground">
          Weather data loading...
        </p>
      </CardContent>
    </Card>
  );
}
