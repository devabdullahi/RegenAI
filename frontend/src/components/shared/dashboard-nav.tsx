"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  Sprout,
  LayoutDashboard,
  Tractor,
  FileText,
  ShieldCheck,
  LogOut,
  ClipboardList,
  MoreHorizontal,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";

const STATIC_NAV_ITEMS = [
  { href: "/farms", label: "My Farms", icon: Tractor },
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/activities", label: "Field Log", icon: ClipboardList },
] as const;

// The Earn Credits and Cost-Share links forward farm_id so those pages
// know which farm to display without the user needing to pick again.
const CREDITS_NAV_ITEM = { label: "Earn Credits", icon: FileText } as const;
const CSP_NAV_ITEM = { label: "Cost-Share", icon: ShieldCheck } as const;

export function DashboardNav({ userEmail }: { userEmail: string }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();
  const [programsOpen, setProgramsOpen] = useState(false);

  // Forward farm context (farm, farm_id) to farm-specific pages so they load
  // the correct farm without the user needing to pick again.
  const farmId =
    searchParams.get("farm_id") ??
    searchParams.get("farm") ??
    null;
  const creditsHref = farmId ? `/credits?farm_id=${farmId}` : "/credits";
  const cspHref = farmId ? `/csp?farm_id=${farmId}` : "/csp";

  // Full nav list (desktop + tablet)
  const allNavItems = [
    ...STATIC_NAV_ITEMS,
    { href: creditsHref, label: CREDITS_NAV_ITEM.label, icon: CREDITS_NAV_ITEM.icon },
    { href: cspHref, label: CSP_NAV_ITEM.label, icon: CSP_NAV_ITEM.icon },
  ];

  // Mobile shows max 4 items: 3 core items + a "Programs" overflow button
  const mobileMainItems = STATIC_NAV_ITEMS;
  const mobileProgramItems = [
    { href: creditsHref, label: CREDITS_NAV_ITEM.label, icon: CREDITS_NAV_ITEM.icon },
    { href: cspHref, label: CSP_NAV_ITEM.label, icon: CSP_NAV_ITEM.icon },
  ];
  const isProgramsActive =
    pathname.startsWith("/credits") || pathname.startsWith("/csp");

  async function handleSignOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
  }

  return (
    <header className="sticky top-0 z-50 border-b bg-card">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
        <Link href="/farms" className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary">
            <Sprout className="h-5 w-5 text-primary-foreground" />
          </div>
          <span className="font-heading text-lg font-bold text-foreground">
            RegenAI
          </span>
        </Link>

        <nav className="hidden items-center gap-1 sm:flex" aria-label="Main navigation">
          {allNavItems.map((item) => {
            // Match active state on the pathname segment only, not query params
            const basePath = item.href.split("?")[0];
            const isActive = pathname.startsWith(basePath);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:text-foreground"
                }`}
                aria-current={isActive ? "page" : undefined}
              >
                <item.icon className="h-4 w-4" aria-hidden="true" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-2">
          <span className="hidden text-sm text-muted-foreground sm:inline">
            {userEmail}
          </span>
          <Button
            variant="ghost"
            size="icon"
            onClick={handleSignOut}
            aria-label="Sign out"
            className="cursor-pointer"
          >
            <LogOut className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>
      </div>

      {/* Mobile bottom nav — max 4 items: 3 core + Programs overflow */}
      <nav
        className="fixed bottom-0 left-0 right-0 z-50 border-t bg-card sm:hidden"
        aria-label="Mobile navigation"
      >
        {/* Programs sub-menu drawer — slides up above the bottom nav */}
        {programsOpen && (
          <div className="border-t bg-card px-4 py-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Programs
              </span>
              <button
                onClick={() => setProgramsOpen(false)}
                aria-label="Close programs menu"
                className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
            {mobileProgramItems.map((item) => {
              const basePath = item.href.split("?")[0];
              const isActive = pathname.startsWith(basePath);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setProgramsOpen(false)}
                  className={`flex items-center gap-3 rounded-lg px-3 py-3 text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                  aria-current={isActive ? "page" : undefined}
                >
                  <item.icon className="h-5 w-5" aria-hidden="true" />
                  {item.label}
                </Link>
              );
            })}
          </div>
        )}
        <div className="flex items-center justify-around py-2">
          {mobileMainItems.map((item) => {
            const basePath = item.href.split("?")[0];
            const isActive = pathname.startsWith(basePath);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex min-h-[48px] flex-col items-center justify-center gap-1 px-3 py-1 text-xs font-medium ${
                  isActive ? "text-primary" : "text-muted-foreground"
                }`}
                aria-current={isActive ? "page" : undefined}
              >
                <item.icon className="h-5 w-5" aria-hidden="true" />
                {item.label}
              </Link>
            );
          })}
          {/* Programs overflow trigger — 4th mobile tab */}
          <button
            onClick={() => setProgramsOpen((prev) => !prev)}
            aria-expanded={programsOpen}
            aria-haspopup="true"
            aria-label="Open programs menu"
            className={`flex min-h-[48px] flex-col items-center justify-center gap-1 px-3 py-1 text-xs font-medium cursor-pointer transition-colors ${
              isProgramsActive || programsOpen ? "text-primary" : "text-muted-foreground"
            }`}
          >
            <MoreHorizontal className="h-5 w-5" aria-hidden="true" />
            Programs
          </button>
        </div>
      </nav>
    </header>
  );
}
