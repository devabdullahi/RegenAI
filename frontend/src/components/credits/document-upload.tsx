"use client";

import { useState, useRef, useCallback } from "react";
import { toast } from "sonner";
import { Upload, FileText, ImageIcon, File, FolderOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Document } from "@/lib/api/types";

const ACCEPTED_TYPES = ["application/pdf", "image/jpeg", "image/png"];
const ACCEPTED_EXTENSIONS = ".pdf,.jpg,.jpeg,.png";
const ACCEPTED_LABEL = "PDF, JPG, or PNG";

function fileIcon(name: string) {
  const ext = name.split(".").pop()?.toLowerCase();
  if (ext === "pdf") return FileText;
  if (ext === "jpg" || ext === "jpeg" || ext === "png") return ImageIcon;
  return File;
}

function formatDocType(docType: Document["doc_type"]): string {
  const map: Record<Document["doc_type"], string> = {
    soil_report: "Soil Report",
    field_photo: "Field Photo",
    compliance: "Compliance Document",
    other: "Other",
  };
  return map[docType] ?? "Document";
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

interface DocumentUploadProps {
  documents: Document[];
  farmId: string;
}

export function DocumentUpload({ documents, farmId }: DocumentUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [stagedFile, setStagedFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateFile = useCallback((file: File): boolean => {
    if (!ACCEPTED_TYPES.includes(file.type)) {
      toast.error("Unsupported file type", {
        description: `Please upload a ${ACCEPTED_LABEL} file.`,
      });
      return false;
    }
    if (file.size > 10 * 1024 * 1024) {
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
    // Reset input so the same file can be re-selected if cleared
    e.target.value = "";
  }

  function handleUpload() {
    if (!stagedFile) {
      toast.info("No file selected", {
        description: "Drag a file into the box above or click to choose one.",
      });
      return;
    }
    toast.info("Document upload coming soon", {
      description:
        "Supabase Storage integration is in progress. Your documents will sync automatically once enabled.",
    });
    setStagedFile(null);
  }

  function handleClearStaged() {
    setStagedFile(null);
  }

  return (
    <section aria-labelledby="docs-heading" className="space-y-4">
      {/* Section header */}
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-muted">
          <FolderOpen className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
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
            onClick={() => inputRef.current?.click()}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                inputRef.current?.click();
              }
            }}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={[
              "flex min-h-[140px] cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-8 text-center transition-colors",
              isDragging
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
                  {(stagedFile.size / 1024).toFixed(0)} KB — ready to upload
                </p>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleClearStaged();
                }}
                className="shrink-0 rounded p-1 text-muted-foreground hover:text-destructive transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
                aria-label={`Remove ${stagedFile.name}`}
              >
                &times;
              </button>
            </div>
          )}

          {/* Upload button */}
          <Button
            onClick={handleUpload}
            disabled={!stagedFile}
            className="w-full min-h-[48px] bg-accent text-accent-foreground hover:bg-accent/90 disabled:opacity-50 cursor-pointer font-semibold"
          >
            <Upload className="mr-2 h-4 w-4" aria-hidden="true" />
            Upload Document
          </Button>
        </CardContent>
      </Card>

      {/* Uploaded documents list */}
      <Card>
        <CardHeader className="border-b">
          <CardTitle className="text-base">
            Uploaded documents
            {documents.length > 0 && (
              <span className="ml-2 inline-flex h-5 w-5 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                {documents.length}
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {documents.length === 0 ? (
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
            <ul
              aria-label="Uploaded documents"
              className="divide-y divide-border"
            >
              {documents.map((doc) => {
                const fileName = doc.storage_path.split("/").pop() ?? doc.storage_path;
                const Icon = fileIcon(fileName);
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
