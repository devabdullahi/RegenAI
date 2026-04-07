import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Sprout, Clock, Brain, DollarSign } from "lucide-react";

export default function OnboardingWelcome() {
  return (
    <div className="flex flex-col items-center gap-8">
      <div className="text-center">
        <div className="mx-auto mb-4 flex h-20 w-20 items-center justify-center rounded-3xl bg-primary">
          <Sprout className="h-10 w-10 text-primary-foreground" />
        </div>
        <h1 className="font-heading text-3xl font-bold">
          Welcome to RegenAI
        </h1>
        <p className="mt-2 text-lg text-muted-foreground">
          Let&apos;s set up your farm in about 5 minutes
        </p>
      </div>

      <div className="grid w-full gap-4">
        <Card>
          <CardContent className="flex items-start gap-4 pt-6">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10">
              <Brain className="h-5 w-5 text-primary" />
            </div>
            <div>
              <CardTitle className="text-base font-heading">
                AI-powered recommendations
              </CardTitle>
              <CardDescription className="text-base">
                Get personalized advice for your soil, weather, and crops —
                written in plain English
              </CardDescription>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex items-start gap-4 pt-6">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent/10">
              <DollarSign className="h-5 w-5 text-accent" />
            </div>
            <div>
              <CardTitle className="text-base font-heading">
                Find cost-share programs
              </CardTitle>
              <CardDescription className="text-base">
                Discover EQIP eligibility and carbon credit opportunities you
                might be missing
              </CardDescription>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex items-start gap-4 pt-6">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-secondary/10">
              <Clock className="h-5 w-5 text-secondary" />
            </div>
            <div>
              <CardTitle className="text-base font-heading">
                Quick setup
              </CardTitle>
              <CardDescription className="text-base">
                We&apos;ll ask about your farm, fields, and current practices.
                Takes about 5 minutes.
              </CardDescription>
            </div>
          </CardContent>
        </Card>
      </div>

      <Link href="/onboarding/farm" className="w-full">
        <Button className="w-full bg-accent text-accent-foreground hover:bg-accent/90 text-lg font-semibold py-6 cursor-pointer">
          Get Started
        </Button>
      </Link>
    </div>
  );
}
