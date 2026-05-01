"use client";

import { useState, useRef, useCallback } from "react";
import { toast } from "sonner";
import {
  Upload,
  FileText,
  ImageIcon,
  File,
  FolderOpen,
  Trash2,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api/client";
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
  { value: "other", label: "Other" },
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function fileIcon(name: string) {
  const ext = name.split(".").pop()?.toLowerCase();
  if (ext === "pdf") return FileText;
  if (ext === "jpg" || ext === "jpeg" || ext === "png") return ImageIcon;
  return File;
}

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
    const fileName = doc.storage_path.split("/").pop() ?? doc.storage_path;
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
    <section aria-labelledby="docs-heading" className="space-y-4">
      {/* Section header */}
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-muted">
          <FolderOpen
            className="h-5 w-5 text-muted-foreground"
            aria-hidden="true"
          />
        </div>
        <div>
          <h2
            id="docs-heading"
            className="font-heading text-lg font-semibold text-foreground"
          >
            Supporting Documents
          </h2>
          <p className="text-sm text-muted-foreground">
            Upload soil reports, field photos, or compliance records
          </p>
        </div>
      </div>

      {/* Upload card */}
      <Card>
        <CardHeader className="border-b">
          <CardTitle className="text-base">Upload a document</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 pt-4">
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
            className={[
              "flex min-h-[140px] cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-8 text-center transition-colors",
              uploading
                ? "pointer-events-none opacity-60 border-border bg-muted/30"
                : isDragging
                  ? "border-primary bg-primary/5"
                  : "border-border bg-muted/30 hover:border-primary/50 hover:bg-muted/50",
            ].join(" ")}
          >
            <div
              className={`flex h-12 w-12 items-center justify-center rounded-full transition-colors ${
                isDragging ? "bg-primary/10" : "bg-muted"
              }`}
            >
              <Upload
                className={`h-6 w-6 transition-colors ${
                  isDragging ? "text-primary" : "text-muted-foreground"
                }`}
                aria-hidden="true"
              />
            </div>
            <div>
              <p className="text-sm font-medium text-foreground">
                {isDragging ? "Release to upload" : "Drag and drop a file here"}
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                or tap to browse &middot; {ACCEPTED_LABEL} &middot; max 10 MB
              </p>
            </div>
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

          {/* Staged file preview */}
          {stagedFile && (
            <div className="flex items-center gap-3 rounded-lg border border-border bg-muted/30 px-3 py-2.5">
              {(() => {
                const Icon = fileIcon(stagedFile.name);
                return (
                  <Icon
                    className="h-5 w-5 shrink-0 text-muted-foreground"
                    aria-hidden="true"
                  />
                );
              })()}
              <div className="flex-1 min-w-0">
                <p className="truncate text-sm font-medium text-foreground">
                  {stagedFile.name}
                </p>
                <p className="text-xs text-muted-foreground">
                  {formatBytes(stagedFile.size)} &mdash; ready to upload
                </p>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setStagedFile(null);
                }}
                disabled={uploading}
                className="shrink-0 rounded p-1 text-muted-foreground hover:text-destructive transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center disabled:opacity-40"
                aria-label={`Remove ${stagedFile.name}`}
              >
                &times;
              </button>
            </div>
          )}

          {/* Document type selector */}
          <div className="space-y-1.5">
            <label
              htmlFor="doc-type-select"
              className="text-sm font-medium text-foreground"
            >
              Document type
            </label>
            <Select
              value={docType}
              onValueChange={(v) => setDocType(v as Document["doc_type"])}
              disabled={uploading}
            >
              <SelectTrigger id="doc-type-select" className="w-full">
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

          {/* Upload button */}
          <Button
            onClick={handleUpload}
            disabled={!stagedFile || uploading}
            className="w-full min-h-[48px] bg-accent text-accent-foreground hover:bg-accent/90 disabled:opacity-50 cursor-pointer font-semibold"
          >
            {uploading ? (
              <>
                <Loader2
                  className="mr-2 h-4 w-4 animate-spin"
                  aria-hidden="true"
                />
                Uploading...
              </>
            ) : (
              <>
                <Upload className="mr-2 h-4 w-4" aria-hidden="true" />
                Upload Document
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Uploaded documents list */}
      <Card>
        <CardHeader className="border-b">
          <CardTitle className="text-base">
            Uploaded documents
            {docs.length > 0 && (
              <span className="ml-2 inline-flex h-5 w-5 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                {docs.length}
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {docs.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-8 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
                <FolderOpen
                  className="h-6 w-6 text-muted-foreground"
                  aria-hidden="true"
                />
              </div>
              <p className="text-sm font-medium text-foreground">
                No documents uploaded yet
              </p>
              <p className="text-sm text-muted-foreground max-w-xs leading-relaxed">
                Uploading soil reports and compliance records strengthens your
                EQIP and VCM applications.
              </p>
            </div>
          ) : (
            <ul aria-label="Uploaded documents" className="divide-y divide-border">
              {docs.map((doc) => {
                const fileName =
                  doc.storage_path.split("/").pop() ?? doc.storage_path;
                const Icon = fileIcon(fileName);
                const isDeleting = deletingId === doc.id;
                return (
                  <li
                    key={doc.id}
                    className="flex items-center gap-3 py-3 first:pt-0 last:pb-0"
                  >
                    <Icon
                      className="h-5 w-5 shrink-0 text-muted-foreground"
                      aria-hidden="true"
                    />
                    <div className="flex-1 min-w-0">
                      <p className="truncate text-sm font-medium text-foreground">
                        {fileName}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {formatDocType(doc.doc_type)} &middot;{" "}
                        {formatDate(doc.uploaded_at)}
                      </p>
                    </div>
                    <button
                      onClick={() => handleDelete(doc)}
                      disabled={isDeleting || uploading}
                      className="shrink-0 rounded p-1.5 text-muted-foreground hover:text-destructive transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center disabled:opacity-40"
                      aria-label={`Delete ${fileName}`}
                    >
                      {isDeleting ? (
                        <Loader2
                          className="h-4 w-4 animate-spin"
                          aria-hidden="true"
                        />
                      ) : (
                        <Trash2 className="h-4 w-4" aria-hidden="true" />
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>
    </section>
  );
}
