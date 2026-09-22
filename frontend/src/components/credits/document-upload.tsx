"use client";

import { useState, useRef, useCallback } from "react";
import { toast } from "sonner";
import { Upload, Trash2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { RuleHead, Stamp } from "@/components/shared/record";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import type { Document } from "@/lib/api/types";

// ── Constants ─────────────────────────────────────────────────────────────────

const MAX_BYTES = 10 * 1024 * 1024; // 10 MB
const ACCEPTED_TYPES = ["application/pdf", "image/jpeg", "image/png"];
const ACCEPTED_EXTENSIONS = ".pdf,.jpg,.jpeg,.png";
const ACCEPTED_LABEL = "PDF, JPG, or PNG";

const DOC_TYPE_OPTIONS: Array<{
  value: Document["doc_type"];
  label: string;
}> = [
  { value: "soil_report", label: "Soil Report" },
  { value: "field_photo", label: "Field Photo" },
  { value: "compliance", label: "Compliance Document" },
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDocType(docType: Document["doc_type"]): string {
  return (
    DOC_TYPE_OPTIONS.find((o) => o.value === docType)?.label ?? "Document"
  );
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ── Props ─────────────────────────────────────────────────────────────────────

interface DocumentUploadProps {
  /** Server-fetched documents passed in as initial state. */
  initialDocuments: Document[];
  farmId: string;
}

// ── Component ─────────────────────────────────────────────────────────────────

export function DocumentUpload({
  initialDocuments,
  farmId,
}: DocumentUploadProps) {
  const [docs, setDocs] = useState<Document[]>(initialDocuments);
  const [isDragging, setIsDragging] = useState(false);
  const [stagedFile, setStagedFile] = useState<File | null>(null);
  const [docType, setDocType] = useState<Document["doc_type"]>("soil_report");
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // ── Validation ──────────────────────────────────────────────────────────────

  const validateFile = useCallback((file: File): boolean => {
    if (!ACCEPTED_TYPES.includes(file.type)) {
      toast.error("Unsupported file type", {
        description: `Please upload a ${ACCEPTED_LABEL} file.`,
      });
      return false;
    }
    if (file.size > MAX_BYTES) {
      toast.error("File too large", {
        description: "Maximum file size is 10 MB.",
      });
      return false;
    }
    return true;
  }, []);

  const stageFile = useCallback(
    (file: File) => {
      if (validateFile(file)) {
        setStagedFile(file);
      }
    },
    [validateFile]
  );

  // ── Drag-and-drop ───────────────────────────────────────────────────────────

  function handleDragOver(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsDragging(true);
  }

  function handleDragLeave(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsDragging(false);
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) stageFile(file);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) stageFile(file);
    // Reset so the same file can be re-selected after clearing
    e.target.value = "";
  }

  // ── Upload ──────────────────────────────────────────────────────────────────

  async function handleUpload() {
    if (!stagedFile) {
      toast.info("No file selected", {
        description: "Drag a file into the box above or click to choose one.",
      });
      return;
    }

    setUploading(true);
    try {
      const uploaded = await api.documents.upload(farmId, stagedFile, docType);
      setDocs((prev) => [uploaded, ...prev]);
      setStagedFile(null);
      toast.success("Document uploaded", {
        description: `${stagedFile.name} was saved successfully.`,
      });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Upload failed. Please try again.";
      toast.error("Upload failed", { description: message });
    } finally {
      setUploading(false);
    }
  }

  // ── Delete ──────────────────────────────────────────────────────────────────

  async function handleDelete(doc: Document) {
    const fileName = doc.file_name;
    const confirmed = window.confirm(
      `Delete "${fileName}"? This cannot be undone.`
    );
    if (!confirmed) return;

    setDeletingId(doc.id);
    try {
      await api.documents.delete(doc.id);
      setDocs((prev) => prev.filter((d) => d.id !== doc.id));
      toast.success("Document deleted", { description: fileName });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Delete failed. Please try again.";
      toast.error("Delete failed", { description: message });
    } finally {
      setDeletingId(null);
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <section aria-labelledby="docs-heading">
      <h2
        id="docs-heading"
        className="font-heading text-xl font-semibold text-foreground"
      >
        Supporting documents
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Upload soil reports, field photos, or compliance records
      </p>

      {/* Upload */}
      <div className="mt-6">
        <RuleHead label="Upload a document" />

        <div className="mt-3 space-y-4">
          {/* Drop zone */}
          <div
            role="button"
            tabIndex={0}
            aria-label="Drop zone: drag and drop a file here, or press Enter to choose a file"
            onClick={() => !uploading && inputRef.current?.click()}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                if (!uploading) inputRef.current?.click();
              }
            }}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={cn(
              "flex min-h-[132px] cursor-pointer flex-col items-center justify-center gap-2 rounded-sm border border-dashed px-6 py-8 text-center transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
              uploading
                ? "pointer-events-none border-border bg-muted/30 opacity-60"
                : isDragging
                  ? "border-primary bg-muted/60"
                  : "border-border bg-card hover:border-primary/60 hover:bg-muted/40"
            )}
          >
            <Upload
              className={cn(
                "h-5 w-5 transition-colors",
                isDragging ? "text-primary" : "text-muted-foreground"
              )}
              aria-hidden="true"
            />
            <p className="text-sm font-medium text-foreground">
              {isDragging ? "Release to upload" : "Drag and drop a file here"}
            </p>
            <p className="text-xs text-muted-foreground">
              or tap to browse &middot; {ACCEPTED_LABEL} &middot; max 10 MB
            </p>
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPTED_EXTENSIONS}
              onChange={handleFileChange}
              className="sr-only"
              aria-hidden="true"
              tabIndex={-1}
              disabled={uploading}
            />
          </div>

          {/* Staged file */}
          {stagedFile && (
            <div className="flex items-center gap-3 border border-border bg-card px-3 py-2.5">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-foreground">
                  {stagedFile.name}
                </p>
                <p className="font-mono text-xs tabular-nums text-muted-foreground">
                  {formatBytes(stagedFile.size)} &mdash; ready to upload
                </p>
              </div>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setStagedFile(null);
                }}
                disabled={uploading}
                className="flex size-12 shrink-0 items-center justify-center text-muted-foreground transition-colors hover:text-destructive disabled:opacity-40"
                aria-label={`Remove ${stagedFile.name}`}
              >
                &times;
              </button>
            </div>
          )}

          {/* Document type */}
          <div className="space-y-1.5">
            <Label htmlFor="doc-type-select">Document type</Label>
            <Select
              value={docType}
              onValueChange={(v) => setDocType(v as Document["doc_type"])}
              disabled={uploading}
            >
              <SelectTrigger id="doc-type-select" className="min-h-12 w-full text-base">
                <SelectValue placeholder="Select type" />
              </SelectTrigger>
              <SelectContent>
                {DOC_TYPE_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <Button
            onClick={handleUpload}
            disabled={!stagedFile || uploading}
            className="min-h-12 cursor-pointer"
          >
            {uploading ? (
              <>
                <Loader2 className="animate-spin" aria-hidden="true" />
                Uploading...
              </>
            ) : (
              <>
                <Upload aria-hidden="true" />
                Upload document
              </>
            )}
          </Button>
        </div>
      </div>

      {/* On file */}
      <div className="mt-8">
        <RuleHead
          label={docs.length > 0 ? `On file · ${docs.length}` : "On file"}
        />

        {docs.length === 0 ? (
          <div className="mt-3 border-y border-border py-6">
            <p className="text-sm font-medium text-foreground">
              No documents uploaded yet
            </p>
            <p className="mt-1 max-w-[56ch] text-sm leading-relaxed text-muted-foreground">
              Uploading soil reports and compliance records strengthens your
              EQIP and VCM applications.
            </p>
          </div>
        ) : (
          <ul aria-label="Uploaded documents" className="mt-3 border-t border-border">
            {docs.map((doc) => {
              const fileName = doc.file_name;
              const isDeleting = deletingId === doc.id;
              return (
                <li
                  key={doc.id}
                  className="flex items-center gap-3 border-b border-border py-3"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-foreground">
                      {fileName}
                    </p>
                    <p className="mt-1 flex flex-wrap items-center gap-2">
                      <Stamp>{formatDocType(doc.doc_type)}</Stamp>
                      <span className="font-mono text-xs tabular-nums text-muted-foreground">
                        {formatDate(doc.created_at)}
                      </span>
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDelete(doc)}
                    disabled={isDeleting || uploading}
                    className="flex size-12 shrink-0 items-center justify-center text-muted-foreground transition-colors hover:text-destructive disabled:opacity-40"
                    aria-label={`Delete ${fileName}`}
                  >
                    {isDeleting ? (
                      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                    ) : (
                      <Trash2 className="h-4 w-4" aria-hidden="true" />
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
