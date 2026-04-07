import { Suspense } from "react";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { DashboardNav } from "@/components/shared/dashboard-nav";

// DashboardNav uses useSearchParams() so it must be wrapped in Suspense
// to allow static prerendering of dashboard pages per Next.js requirements.
function NavFallback() {
  return (
    <header className="sticky top-0 z-50 border-b bg-card">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
        <div className="h-9 w-32 animate-pulse rounded-lg bg-muted" />
        <div className="hidden h-8 w-64 animate-pulse rounded-lg bg-muted sm:block" />
        <div className="h-9 w-9 animate-pulse rounded-lg bg-muted" />
      </div>
    </header>
  );
}

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const devBypass = process.env.NEXT_PUBLIC_DEV_AUTH_BYPASS === "true";
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
      <Suspense fallback={<NavFallback />}>
        <DashboardNav userEmail={userEmail} />
      </Suspense>
      <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-5xl">{children}</div>
      </main>
    </div>
  );
}
