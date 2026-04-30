"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";

export default function OnboardingError({
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
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 px-4 text-center">
      <h2 className="font-heading text-xl font-bold">
        Something went wrong during setup
      </h2>
      <p className="max-w-sm text-sm text-muted-foreground">
        We hit an error while setting up your farm. Your progress has been saved
        locally.
      </p>
      <Button onClick={reset} className="min-h-[48px]">
        Try again
      </Button>
    </div>
  );
}
