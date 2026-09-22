import { Suspense } from "react";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { isDevAuthBypassEnabled } from "@/lib/supabase/dev-bypass";
import { DashboardNav } from "@/components/shared/dashboard-nav";
import { OfflineBanner } from "@/components/shared/offline-banner";

// DashboardNav uses useSearchParams() so it must be wrapped in Suspense
// to allow static prerendering of dashboard pages per Next.js requirements.
function NavFallback() {
  return (
    <header className="sticky top-0 z-50 border-b border-border bg-card">
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <div className="h-5 w-24 animate-pulse rounded-sm bg-muted" />
        <div className="hidden h-4 w-64 animate-pulse rounded-sm bg-muted sm:block" />
        <div className="size-6 animate-pulse rounded-sm bg-muted" />
      </div>
    </header>
  );
}

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const devBypass = isDevAuthBypassEnabled();
  let userEmail = "dev@farm.com";

  if (!devBypass) {
    const supabase = await createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (!user) {
      redirect("/login");
    }
    userEmail = user.email ?? "";
  }

  return (
    <div className="flex min-h-screen flex-col">
      <OfflineBanner />
      <Suspense fallback={<NavFallback />}>
        <DashboardNav userEmail={userEmail} />
      </Suspense>
      <main id="main-content" className="flex-1 px-4 py-8 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-5xl">{children}</div>
      </main>
    </div>
  );
}
