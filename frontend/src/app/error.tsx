"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/shared/page-states";

export default function GlobalError({
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
    <ErrorState
      className="min-h-[60vh] justify-center"
      title="Something went wrong"
      message="This page hit an unexpected problem. Try again, or go back to your farms. If it keeps happening, check your internet connection."
    >
      <Button onClick={reset} className="min-h-12 w-full max-w-xs">
        Try again
      </Button>
    </ErrorState>
  );
}
