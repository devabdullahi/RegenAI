"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/shared/page-states";

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
    <ErrorState
      className="min-h-[60vh] justify-center"
      title="Something went wrong during setup"
      message="We hit a problem while setting up your farm. The answers you already entered are saved on this device, so you can try again without starting over."
      actions={[{ label: "Back to farms", href: "/farms", variant: "outline" }]}
    >
      <Button onClick={reset} className="min-h-12 w-full max-w-xs">
        Try again
      </Button>
    </ErrorState>
  );
}
