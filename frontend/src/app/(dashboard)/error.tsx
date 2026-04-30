"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex flex-col items-center gap-4 py-16 text-center">
      <h2 className="font-heading text-xl font-bold">Something went wrong</h2>
      <p className="max-w-sm text-sm text-muted-foreground">
        We had trouble loading your farm data. Check your connection and try
        again.
      </p>
      <Button onClick={reset} className="min-h-[48px]">
        Try again
      </Button>
    </div>
  );
}
