"use client";

/**
 * A link styled as a Button. Use this instead of <Link><Button/></Link>, which
 * nests a <button> inside an <a> (invalid HTML, double tab stop).
 *
 *   <ButtonLink href="/farms">Go to My Farms</ButtonLink>
 *   <ButtonLink href="/farms" variant="outline" className="w-full">Back</ButtonLink>
 *   <ButtonLink href={NRCS_SERVICE_CENTER_LOCATOR_URL} external>Find office</ButtonLink>
 *
 * "use client" is required because buttonVariants comes from a client module and
 * cannot be called in a Server Component; ButtonLink itself is still safe to
 * render from Server Components (all props are serializable).
 *
 * For base-ui triggers (DialogTrigger etc.), keep using the `render` prop:
 *   <DialogTrigger render={<Button variant="outline" />}>...</DialogTrigger>
 */

import Link from "next/link";
import type { ComponentProps } from "react";
import type { VariantProps } from "class-variance-authority";
import { ExternalLink } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type ButtonLinkProps = Omit<ComponentProps<typeof Link>, "className"> &
  VariantProps<typeof buttonVariants> & {
    className?: string;
    /**
     * Open in a new tab with rel="noopener noreferrer", show an external-link
     * icon, and add "(opens in new tab)" for screen readers.
     */
    external?: boolean;
  };

export function ButtonLink({
  href,
  variant = "default",
  size = "default",
  className,
  external = false,
  children,
  ...props
}: ButtonLinkProps) {
  const classes = cn(
    buttonVariants({ variant, size }),
    // 48px minimum touch target (CLAUDE.md §3), with room for longer labels.
    "min-h-12 px-4",
    className
  );

  if (external) {
    return (
      <a
        href={typeof href === "string" ? href : String(href)}
        target="_blank"
        rel="noopener noreferrer"
        className={classes}
        {...(props as ComponentProps<"a">)}
      >
        {children}
        <ExternalLink aria-hidden="true" />
        <span className="sr-only">(opens in new tab)</span>
      </a>
    );
  }

  return (
    <Link href={href} className={classes} {...props}>
      {children}
    </Link>
  );
}
