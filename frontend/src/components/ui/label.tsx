"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

// Field captions on a printed form: small caps, letter-spaced, sitting quietly
// above the blank they name.
function Label({ className, ...props }: React.ComponentProps<"label">) {
  return (
    <label
      data-slot="label"
      className={cn(
        "flex items-center gap-2 font-mono text-xs font-medium tracking-[0.1em] text-muted-foreground uppercase select-none group-data-[disabled=true]:pointer-events-none group-data-[disabled=true]:opacity-50 peer-disabled:cursor-not-allowed peer-disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
}

export { Label }
