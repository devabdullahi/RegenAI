"use client";

import { useRouter, useSearchParams } from "next/navigation";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { MapPin } from "lucide-react";
import type { Field } from "@/lib/api/types";

interface FieldSelectorProps {
  fields: Field[];
  selectedFieldId: string;
  farmId: string;
}

export function FieldSelector({
  fields,
  selectedFieldId,
  farmId,
}: FieldSelectorProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  function handleFieldChange(fieldId: string | null) {
    if (!fieldId) return;
    const params = new URLSearchParams(searchParams.toString());
    params.set("farm", farmId);
    params.set("field", fieldId);
    router.push(`/dashboard?${params.toString()}`);
  }

  const selectedField = fields.find((f) => f.id === selectedFieldId);

  return (
    <div className="flex items-center gap-2">
      <MapPin className="h-4 w-4 shrink-0 text-muted-foreground" />
      <Select value={selectedFieldId} onValueChange={handleFieldChange}>
        <SelectTrigger className="min-h-[48px] h-auto py-2 w-full sm:w-auto sm:min-w-[220px] text-sm">
          <SelectValue placeholder="Select a field">
            {selectedField ? (
              <span>
                {selectedField.name}
                <span className="ml-1.5 text-muted-foreground">
                  &middot; {selectedField.acres} ac &middot;{" "}
                  {selectedField.crop_type}
                </span>
              </span>
            ) : (
              "Select a field"
            )}
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          {fields.map((field) => (
            <SelectItem key={field.id} value={field.id}>
              <span className="font-medium">{field.name}</span>
              <span className="ml-1.5 text-muted-foreground text-xs">
                {field.acres} ac &middot; {field.crop_type}
              </span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
