"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import {
  LayoutDashboard,
  Tractor,
  FileText,
  ShieldCheck,
  LogOut,
  ClipboardList,
  MoreHorizontal,
  X,
  type LucideIcon,
} from "lucide-react";
import { createClient } from "@/lib/supabase/client";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

const FARM_DETAIL_PATH = /^\/farms\/([^/]+)/;

/**
 * Link to a farm-specific page, forwarding the current farm. Pages read
 * different param names: /dashboard reads `farm`, the rest read `farm_id`.
 */
function farmHref(path: string, param: "farm" | "farm_id", farmId: string | null) {
  return farmId ? `${path}?${param}=${encodeURIComponent(farmId)}` : path;
}

export function DashboardNav({ userEmail }: { userEmail: string }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();
  const [programsOpen, setProgramsOpen] = useState(false);

  // Farm context comes from the query string, or from the path on /farms/[id].
  const farmId =
    searchParams.get("farm_id") ??
    searchParams.get("farm") ??
    pathname.match(FARM_DETAIL_PATH)?.[1] ??
    null;

  const coreItems: NavItem[] = [
    { href: "/farms", label: "My Farms", icon: Tractor },
    { href: farmHref("/dashboard", "farm", farmId), label: "Dashboard", icon: LayoutDashboard },
    { href: farmHref("/activities", "farm_id", farmId), label: "Field Log", icon: ClipboardList },
  ];
  const programItems: NavItem[] = [
    { href: farmHref("/credits", "farm_id", farmId), label: "Earn Credits", icon: FileText },
    { href: farmHref("/csp", "farm_id", farmId), label: "CSP", icon: ShieldCheck },
  ];
  const allNavItems = [...coreItems, ...programItems];

  // Match active state on the path only, not query params. /farms must not
  // light up for every path that merely starts with "/farms".
  function isActive(href: string) {
    const basePath = href.split("?")[0] ?? href;
    return pathname === basePath || pathname.startsWith(`${basePath}/`);
  }
  const isProgramsActive = programItems.some((item) => isActive(item.href));

  async function handleSignOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
  }

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-card">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-1 sm:px-6 lg:px-8">
        {/* Masthead: the name on the record, set as type, not as a logo tile. */}
        <Link href="/farms" className="flex min-h-12 items-center">
          <span className="font-heading text-lg font-semibold tracking-[-0.02em] text-foreground">
            RegenAI
          </span>
        </Link>

        <nav className="hidden items-center gap-5 sm:flex" aria-label="Main navigation">
          {allNavItems.map((item) => {
            const active = isActive(item.href);
            return (
              <Link
                key={item.label}
                href={item.href}
                className={cn(
                  // Active is a 2px rule under the word, the way a form marks
                  // the part being filled in.
                  "flex min-h-12 items-center gap-2 border-b-2 px-0.5 text-sm font-medium transition-colors",
                  active
                    ? "border-primary text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                )}
                aria-current={active ? "page" : undefined}
              >
                <item.icon className="h-4 w-4" aria-hidden="true" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-3">
          <span className="hidden font-mono text-xs text-muted-foreground sm:inline">
            {userEmail}
          </span>
          <Button
            variant="ghost"
            size="icon"
            onClick={handleSignOut}
            aria-label="Sign out"
            className="size-12 cursor-pointer"
          >
            <LogOut className="h-5 w-5" aria-hidden="true" />
          </Button>
        </div>
      </div>

      {/* Mobile bottom nav — max 4 items: 3 core + Programs overflow */}
      <nav
        className="fixed right-0 bottom-0 left-0 z-50 border-t border-border bg-card sm:hidden"
        aria-label="Mobile navigation"
      >
        {/* Programs sub-menu drawer — opens above the bottom nav */}
        {programsOpen && (
          <div id="mobile-programs-menu" className="border-t border-border bg-card px-4 py-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="font-mono text-[0.6875rem] font-medium tracking-[0.14em] text-muted-foreground uppercase">
                Programs
              </span>
              <button
                type="button"
                onClick={() => setProgramsOpen(false)}
                aria-label="Close programs menu"
                className="flex size-12 cursor-pointer items-center justify-center text-muted-foreground transition-colors hover:text-foreground"
              >
                <X className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>
            {programItems.map((item) => {
              const active = isActive(item.href);
              return (
                <Link
                  key={item.label}
                  href={item.href}
                  onClick={() => setProgramsOpen(false)}
                  className={cn(
                    "flex min-h-12 items-center gap-3 border-l-2 px-3 py-3 text-sm font-medium transition-colors",
                    active
                      ? "border-primary text-foreground"
                      : "border-transparent text-muted-foreground hover:text-foreground"
                  )}
                  aria-current={active ? "page" : undefined}
                >
                  <item.icon className="h-5 w-5" aria-hidden="true" />
                  {item.label}
                </Link>
              );
            })}
          </div>
        )}
        <div className="flex items-stretch justify-around">
          {coreItems.map((item) => {
            const active = isActive(item.href);
            return (
              <Link
                key={item.label}
                href={item.href}
                className={cn(
                  "flex min-h-12 min-w-12 flex-col items-center justify-center gap-0.5 border-t-2 px-3 py-2 text-xs font-medium transition-colors",
                  active
                    ? "border-primary text-foreground"
                    : "border-transparent text-muted-foreground"
                )}
                aria-current={active ? "page" : undefined}
              >
                <item.icon className="h-6 w-6 shrink-0" aria-hidden="true" />
                {/* Label hidden below 480px (icon-only tab bar), visible above */}
                <span className="hidden leading-tight min-[480px]:inline">{item.label}</span>
                {/* Screen-reader label always present so icon-only mode stays accessible */}
                <span className="sr-only min-[480px]:hidden">{item.label}</span>
              </Link>
            );
          })}
          {/* Programs overflow trigger — 4th mobile tab */}
          <button
            type="button"
            onClick={() => setProgramsOpen((prev) => !prev)}
            aria-expanded={programsOpen}
            aria-controls="mobile-programs-menu"
            className={cn(
              "flex min-h-12 min-w-12 cursor-pointer flex-col items-center justify-center gap-0.5 border-t-2 px-3 py-2 text-xs font-medium transition-colors",
              isProgramsActive || programsOpen
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground"
            )}
          >
            <MoreHorizontal className="h-6 w-6 shrink-0" aria-hidden="true" />
            <span className="hidden leading-tight min-[480px]:inline">Programs</span>
            <span className="sr-only min-[480px]:hidden">Programs</span>
          </button>
        </div>
      </nav>
    </header>
  );
}
