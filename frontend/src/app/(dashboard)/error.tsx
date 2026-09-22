"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/shared/page-states";

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
    <ErrorState actions={[{ label: "Back to farms", href: "/farms", variant: "outline" }]}>
      <Button onClick={reset} className="min-h-12 cursor-pointer">
        Try again
      </Button>
    </ErrorState>
  );
}
