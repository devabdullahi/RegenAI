"use client"

import { Button as ButtonPrimitive } from "@base-ui/react/button"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

// Controls on equipment: a cut rectangle, a firm label, a real click. No lift,
// no glow. `accent` is reserved for actions with a deadline attached.
const buttonVariants = cva(
  "group/button inline-flex shrink-0 items-center justify-center rounded-sm border text-sm font-medium whitespace-nowrap transition-colors outline-none select-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background active:not-aria-[haspopup]:translate-y-px disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-destructive [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default:
          "border-primary bg-primary text-primary-foreground hover:bg-primary/90",
        accent:
          "border-accent bg-accent text-accent-foreground hover:bg-accent/90",
        outline:
          "border-border bg-card text-foreground hover:bg-muted aria-expanded:bg-muted",
        secondary:
          "border-border bg-secondary text-secondary-foreground hover:bg-muted",
        ghost:
          "border-transparent bg-transparent text-foreground hover:bg-muted aria-expanded:bg-muted",
        destructive:
          "border-destructive/40 bg-transparent text-destructive hover:bg-destructive/10",
        link: "border-transparent text-primary underline underline-offset-4 hover:text-accent",
      },
      size: {
        default: "h-11 gap-2 px-4",
        xs: "h-7 gap-1 px-2 text-xs",
        sm: "h-9 gap-1.5 px-3 text-[0.8rem]",
        lg: "h-12 gap-2 px-5 text-base",
        icon: "size-11",
        "icon-xs": "size-7 [&_svg:not([class*='size-'])]:size-3",
        "icon-sm": "size-9 [&_svg:not([class*='size-'])]:size-3.5",
        "icon-lg": "size-12",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  ...props
}: ButtonPrimitive.Props & VariantProps<typeof buttonVariants>) {
  return (
    <ButtonPrimitive
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
