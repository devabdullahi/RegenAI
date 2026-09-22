import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { isDevAuthBypassEnabled } from "@/lib/supabase/dev-bypass";
import Link from "next/link";

export default async function OnboardingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const devBypass = isDevAuthBypassEnabled();

  if (!devBypass) {
    const supabase = await createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (!user) {
      redirect("/login");
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-border bg-card">
        <div className="mx-auto flex max-w-2xl items-baseline justify-between gap-3 px-4 py-3">
          <Link
            href="/farms"
            className="flex items-baseline font-heading text-lg font-bold tracking-tight"
          >
            RegenAI
          </Link>
          <span className="font-mono text-[0.6875rem] tracking-[0.14em] text-muted-foreground uppercase">
            Farm setup
          </span>
        </div>
      </header>
      <main id="main-content" className="flex-1 px-4 py-8">
        <div className="mx-auto max-w-2xl">{children}</div>
      </main>
    </div>
  );
}
