import "server-only";

import { createServerClient } from "@supabase/ssr";
import { createClient as createSupabaseClient } from "@supabase/supabase-js";
import { cookies } from "next/headers";

// Production guard: never allow auth bypass in production
if (
  process.env.DEV_AUTH_BYPASS === "true" &&
  process.env.NODE_ENV === "production"
) {
  throw new Error(
    "DEV_AUTH_BYPASS cannot be enabled in production. Remove it from your environment."
  );
}

export async function createClient() {
  // DEV ONLY: bypass auth with anon key (no service role key exposure)
  if (process.env.DEV_AUTH_BYPASS === "true") {
    return createSupabaseClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
    );
  }

  const cookieStore = await cookies();

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options)
            );
          } catch {
            // The `setAll` method is called from Server Components where
            // cookies cannot be set. This is safe to ignore.
          }
        },
      },
    }
  );
}
