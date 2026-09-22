"use client";

import { useSyncExternalStore } from "react";
import { WifiOff } from "lucide-react";

function subscribe(callback: () => void) {
  window.addEventListener("online", callback);
  window.addEventListener("offline", callback);
  return () => {
    window.removeEventListener("online", callback);
    window.removeEventListener("offline", callback);
  };
}

function getSnapshot() {
  return navigator.onLine;
}

// Assume online during SSR to avoid a flash of the banner
function getServerSnapshot() {
  return true;
}

export function OfflineBanner() {
  const isOnline = useSyncExternalStore(
    subscribe,
    getSnapshot,
    getServerSnapshot
  );

  if (isOnline) return null;

  return (
    // A band across the top of the sheet, like a stamped notice on a form.
    <div
      role="status"
      aria-live="polite"
      className="flex items-center justify-center gap-2 bg-warning px-4 py-2 font-mono text-xs font-medium tracking-[0.08em] text-warning-foreground uppercase"
    >
      <WifiOff className="h-4 w-4 shrink-0" aria-hidden="true" />
      <span>Offline — changes may not save</span>
    </div>
  );
}
