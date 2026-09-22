"use client";

import { useRouter, useSearchParams } from "next/navigation";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatAcres } from "@/lib/format";
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
    <Select value={selectedFieldId} onValueChange={handleFieldChange}>
      <SelectTrigger
        aria-label="Field"
        className="h-auto min-h-12 w-full py-2 text-sm sm:w-auto sm:min-w-[260px]"
      >
        <SelectValue placeholder="Select a field">
          {selectedField ? (
            <span>
              <span className="font-medium">{selectedField.name}</span>
              <span className="ml-2 text-muted-foreground">
                <span className="font-mono">
                  {formatAcres(selectedField.acres, { short: true })}
                </span>{" "}
                &middot; {selectedField.crop_type}
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
            <span className="ml-2 text-xs text-muted-foreground">
              <span className="font-mono">
                {formatAcres(field.acres, { short: true })}
              </span>{" "}
              &middot; {field.crop_type}
            </span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
