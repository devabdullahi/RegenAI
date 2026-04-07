import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { Sprout } from "lucide-react";
import Link from "next/link";

export default async function OnboardingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const devBypass = process.env.NEXT_PUBLIC_DEV_AUTH_BYPASS === "true";

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
      <header className="border-b bg-card px-4 py-3">
        <div className="mx-auto flex max-w-2xl items-center gap-2">
          <Link href="/farms" className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
              <Sprout className="h-4 w-4 text-primary-foreground" />
            </div>
            <span className="font-heading text-lg font-bold">RegenAI</span>
          </Link>
          <span className="text-sm text-muted-foreground">
            &middot; Farm Setup
          </span>
        </div>
      </header>
      <main className="flex-1 px-4 py-8">
        <div className="mx-auto max-w-2xl">{children}</div>
      </main>
    </div>
  );
}
