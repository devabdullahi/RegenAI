import { createClient } from "@/lib/supabase/server";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tractor, Plus, MapPin } from "lucide-react";

export default async function FarmsPage() {
  const supabase = await createClient();
  const { data: farms } = await supabase
    .from("farms")
    .select("*")
    .order("created_at", { ascending: false });

  const hasFarms = farms && farms.length > 0;

  return (
    <div className="pb-20 sm:pb-0">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="font-heading text-2xl font-bold">My Farms</h1>
          <p className="text-muted-foreground">
            Manage your farms and fields
          </p>
        </div>
        <Link href="/onboarding">
          <Button className="bg-accent text-accent-foreground hover:bg-accent/90 cursor-pointer">
            <Plus className="mr-2 h-4 w-4" />
            Add Farm
          </Button>
        </Link>
      </div>

      {hasFarms ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {farms.map((farm) => (
            <Link key={farm.id} href={`/dashboard?farm=${farm.id}`}>
              <Card className="cursor-pointer transition-shadow hover:shadow-lg">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 font-heading">
                    <Tractor className="h-5 w-5 text-primary" />
                    {farm.name}
                  </CardTitle>
                  <CardDescription className="flex items-center gap-1">
                    <MapPin className="h-3 w-3" />
                    {farm.state} &middot; {farm.total_acres} acres
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    View dashboard and recommendations
                  </p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      ) : (
        <Card className="py-12 text-center">
          <CardContent className="flex flex-col items-center gap-4">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
              <Tractor className="h-8 w-8 text-muted-foreground" />
            </div>
            <div>
              <h2 className="font-heading text-lg font-semibold">
                No farms yet
              </h2>
              <p className="mt-1 text-muted-foreground">
                Add your first farm to get AI-powered recommendations
              </p>
            </div>
            <Link href="/onboarding">
              <Button className="bg-accent text-accent-foreground hover:bg-accent/90 cursor-pointer">
                <Plus className="mr-2 h-4 w-4" />
                Add Your First Farm
              </Button>
            </Link>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
