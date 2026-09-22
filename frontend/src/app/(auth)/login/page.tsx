"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RuleHead } from "@/components/shared/record";
import { Loader2 } from "lucide-react";

/** Messages for the ?error= values set by /auth/callback. */
const CALLBACK_ERROR_MESSAGES: Record<string, string> = {
  auth: "That sign-in link didn't work. It may have expired or already been used. Enter your email to get a new link.",
};

const SEND_FAILED_MESSAGE =
  "We couldn't send your sign-in link. Check your internet connection and try again.";

export default function LoginPage() {
  // useSearchParams needs a Suspense boundary so the page can still prerender.
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const searchParams = useSearchParams();
  const callbackError = searchParams.get("error");
  const callbackErrorMessage = callbackError
    ? (CALLBACK_ERROR_MESSAGES[callbackError] ??
      "We couldn't sign you in. Enter your email to get a new link.")
    : null;

  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSubmitted, setHasSubmitted] = useState(false);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setHasSubmitted(true);

    try {
      const supabase = createClient();
      const { error: otpError } = await supabase.auth.signInWithOtp({
        email,
        options: {
          emailRedirectTo: `${window.location.origin}/auth/callback`,
        },
      });
      if (otpError) {
        console.error("Login: signInWithOtp failed", otpError.message);
        setError(SEND_FAILED_MESSAGE);
        return;
      }
      setSent(true);
    } catch (err) {
      // Network failures throw instead of returning { error }.
      console.error("Login: signInWithOtp threw", err);
      setError(SEND_FAILED_MESSAGE);
    } finally {
      setLoading(false);
    }
  }

  // Show the callback error until the user tries again.
  const visibleError = error ?? (hasSubmitted ? null : callbackErrorMessage);

  return (
    <main
      id="main-content"
      className="mx-auto flex min-h-screen w-full max-w-md flex-col justify-center px-4 py-10"
    >
      {/* Masthead: wordmark over a heavy rule, the way a bulletin opens. */}
      <div className="border-b-2 border-rule-strong pb-3">
        <h1 className="font-heading text-4xl font-bold tracking-tight">
          RegenAI
        </h1>
        <p className="mt-1 font-mono text-[0.6875rem] tracking-[0.14em] text-muted-foreground uppercase">
          Conservation record · US row-crop farms
        </p>
      </div>

      {sent ? (
        <div className="mt-8 flex flex-col gap-4">
          <RuleHead label="Link sent" />
          <p className="reading text-foreground">
            We sent a sign-in link to{" "}
            <span className="font-mono text-base">{email}</span>. Open it on this
            device and you will be signed in — there is no password to remember.
          </p>
          <Button
            variant="outline"
            size="lg"
            className="self-start"
            onClick={() => {
              setSent(false);
              setEmail("");
            }}
          >
            Use a different email
          </Button>
        </div>
      ) : (
        <form onSubmit={handleLogin} className="mt-8 flex flex-col gap-5">
          <RuleHead label="Sign in" />
          <div className="flex flex-col gap-2">
            <Label htmlFor="email">Email address</Label>
            <Input
              id="email"
              type="email"
              placeholder="you@farm.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              className="font-mono"
            />
            <p className="text-xs text-muted-foreground">
              No password needed. We send a link that signs you in.
            </p>
          </div>

          {visibleError && (
            <p
              className="border-l-[3px] border-l-destructive py-2 pl-3 text-sm text-destructive"
              role="alert"
            >
              {visibleError}
            </p>
          )}

          <Button type="submit" size="lg" disabled={loading || !email}>
            {loading ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
                Sending link
              </>
            ) : (
              "Email me a sign-in link"
            )}
          </Button>
        </form>
      )}
    </main>
  );
}
