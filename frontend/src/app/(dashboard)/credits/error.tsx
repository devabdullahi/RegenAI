"use client";

import { useEffect } from "react";
import Link from "next/link";
import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function CreditsError({ error, reset }: ErrorProps) {
  useEffect(() => {
    // Log to an error reporting service when available
    console.error("[credits] page error:", error);
  }, [error]);

  return (
    <div className="pb-20 sm:pb-0 space-y-6">
      <h1 className="font-heading text-2xl font-bold text-foreground sm:text-3xl">
        Credits &amp; Programs
      </h1>

      <Card className="border-destructive/30 bg-destructive/5">
        <CardContent className="flex flex-col items-center px-6 py-12 text-center">
          <AlertCircle
            className="mb-4 h-10 w-10 text-destructive"
            aria-hidden="true"
          />
          <p className="font-heading text-lg font-semibold text-foreground">
            Could not load your credit information
          </p>
          <p className="mt-2 max-w-sm text-sm text-muted-foreground">
            Something went wrong while loading your EQIP eligibility and carbon
            credit data. This is usually a temporary problem.
          </p>

          <div className="mt-6 flex flex-col items-center gap-3 sm:flex-row">
            <Button
              onClick={reset}
              className="min-h-[48px] px-6"
              aria-label="Retry loading credits"
            >
              Try again
            </Button>
            <Button variant="outline" asChild className="min-h-[48px] px-6">
              <Link href="/farms">Back to my farms</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
