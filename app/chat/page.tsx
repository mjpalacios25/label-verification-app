"use client";

import { useCallback, useRef, useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8080";

export function isVerificationResult(v: unknown): v is VerificationResult {
  return (
    typeof v === "object" &&
    v !== null &&
    "brand_match" in v &&
    "alcohol_match" in v &&
    "warning_match" in v
  );
}

type VerificationResult = {
  brand_match: "yes" | "no";
  alcohol_match: "yes" | "no";
  warning_match: "yes" | "no";
};

type ResultRow = {
  key: keyof VerificationResult;
  label: string;
};

const RESULT_ROWS: ResultRow[] = [
  { key: "brand_match", label: "Brand Name Match" },
  { key: "alcohol_match", label: "Alcohol Content Match" },
  { key: "warning_match", label: "Warning Label Match" },
];

const IMAGE_ACCEPT = ".jpeg,.jpg,image/jpeg";
const FORM_ACCEPT = ".pdf,application/pdf";

/**
 * Deduplicate File objects by name + size so the same file selected twice does
 * not appear as two list entries.
 */
export function dedupeFiles(existing: File[], incoming: File[]): File[] {
  const seen = new Set(existing.map((f) => `${f.name}:${f.size}`));
  const additions = incoming.filter((f) => {
    const id = `${f.name}:${f.size}`;
    if (seen.has(id)) return false;
    seen.add(id);
    return true;
  });
  return additions.length > 0 ? [...existing, ...additions] : existing;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ChatLandingPage() {
  const [images, setImages] = useState<File[]>([]);
  const [form, setForm] = useState<File | null>(null);
  const [draggingZone, setDraggingZone] = useState<"images" | "form" | null>(
    null,
  );
  const [isVerifying, setIsVerifying] = useState(false);
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const imageInputRef = useRef<HTMLInputElement>(null);
  const formInputRef = useRef<HTMLInputElement>(null);

  const canVerify = images.length > 0 && form !== null && !isVerifying;

  const addImages = useCallback((fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;
    const incoming = Array.from(fileList).filter(
      (f) => f.type === "image/jpeg" || /\.jpe?g$/i.test(f.name),
    );
    if (incoming.length === 0) return;
    setImages((prev) => dedupeFiles(prev, incoming));
  }, []);

  const setFormFile = useCallback((fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;
    const pdf = Array.from(fileList).find(
      (f) => f.type === "application/pdf" || /\.pdf$/i.test(f.name),
    );
    if (pdf) setForm(pdf);
  }, []);

  const handleImageInput = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      addImages(event.target.files);
      event.target.value = "";
    },
    [addImages],
  );

  const handleFormInput = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      setFormFile(event.target.files);
      event.target.value = "";
    },
    [setFormFile],
  );

  const handleImageDrop = useCallback(
    (event: React.DragEvent<HTMLButtonElement>) => {
      event.preventDefault();
      setDraggingZone(null);
      addImages(event.dataTransfer.files);
    },
    [addImages],
  );

  const handleFormDrop = useCallback(
    (event: React.DragEvent<HTMLButtonElement>) => {
      event.preventDefault();
      setDraggingZone(null);
      setFormFile(event.dataTransfer.files);
    },
    [setFormFile],
  );

  const removeImage = useCallback((target: File) => {
    setImages((prev) =>
      prev.filter((f) => !(f.name === target.name && f.size === target.size)),
    );
  }, []);

  const clearImages = useCallback(() => setImages([]), []);
  const removeForm = useCallback(() => setForm(null), []);

  const handleVerify = useCallback(async () => {
    if (images.length === 0 || !form) return;

    setIsVerifying(true);
    setError(null);
    setResult(null);

    try {
      const body = new FormData();
      for (const image of images) {
        body.append("images", image);
      }
      body.append("form", form);

      const response = await fetch(`${API_BASE_URL}/verify`, {
        method: "POST",
        body,
      });

      if (!response.ok) {
        throw new Error(
          `Verification request failed (HTTP ${response.status}).`,
        );
      }

      const data = await response.json();
      if (!isVerificationResult(data)) {
        throw new Error("Unexpected response format from the verification service.");
      }
      setResult(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? `${err.message} Make sure the verification service is running at ${API_BASE_URL}.`
          : "An unexpected error occurred while verifying the labels.",
      );
    } finally {
      setIsVerifying(false);
    }
  }, [images, form]);

  const handleDownloadCsv = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/export`);
      if (!response.ok) throw new Error(`Export failed (HTTP ${response.status}).`);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "verification_runs.csv";
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download CSV.");
    }
  }, []);

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-8 px-6 py-12 pb-32 sm:py-16">
      <header className="flex flex-col gap-4">
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          Alcohol Label Verification
        </h1>
        <p className="text-base text-foreground/70 sm:text-lg">
          Upload images of your beverage labels and the matching government
          approval form. Our AI checks each label against the approval for
          compliance.
        </p>
        <ol className="flex flex-col gap-1 text-sm text-foreground/60">
          <li>1. Upload one or more JPEG label images.</li>
          <li>2. Upload the government approval form (PDF).</li>
          <li>3. Click Verify to run the AI compliance check.</li>
        </ol>
      </header>

      {/* Label images upload zone */}
      <section className="flex flex-col gap-4">
        <h2 className="text-lg font-semibold">Label Images</h2>
        <button
          type="button"
          aria-label="Upload label images by dragging and dropping or clicking to browse"
          onClick={() => imageInputRef.current?.click()}
          onDragOver={(event) => {
            event.preventDefault();
            setDraggingZone("images");
          }}
          onDragLeave={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget as Node)) {
              setDraggingZone(null);
            }
          }}
          onDrop={handleImageDrop}
          className={`flex w-full cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-foreground/40 ${
            draggingZone === "images"
              ? "border-foreground/60 bg-foreground/5"
              : "border-foreground/25 hover:border-foreground/40 hover:bg-foreground/[0.03]"
          }`}
        >
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.5}
            strokeLinecap="round"
            strokeLinejoin="round"
            className="h-10 w-10 text-foreground/50"
          >
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <circle cx="9" cy="9" r="1.5" />
            <path d="m3 16 5-5 4 4 3-3 6 6" />
          </svg>
          <p className="text-base font-medium">Drag and drop label images</p>
          <p className="text-sm text-foreground/60">
            or click to browse — JPEG files, multiple allowed
          </p>
        </button>
        <input
          ref={imageInputRef}
          type="file"
          accept={IMAGE_ACCEPT}
          multiple
          onChange={handleImageInput}
          className="hidden"
        />

        {images.length > 0 && (
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-foreground/70">
                {images.length} {images.length === 1 ? "image" : "images"}{" "}
                selected
              </span>
              <button
                type="button"
                onClick={clearImages}
                className="text-sm text-foreground/60 underline-offset-4 transition-colors hover:text-foreground hover:underline"
              >
                Clear all
              </button>
            </div>
            <ul className="flex flex-col gap-2">
              {images.map((image) => (
                <li
                  key={`${image.name}:${image.size}`}
                  className="flex items-center justify-between gap-3 rounded-lg border border-foreground/15 bg-foreground/[0.02] px-4 py-3"
                >
                  <div className="flex min-w-0 flex-col">
                    <span className="truncate font-medium">{image.name}</span>
                    <span className="text-sm text-foreground/60">
                      {formatBytes(image.size)}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => removeImage(image)}
                    aria-label={`Remove image ${image.name}`}
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-lg text-foreground/50 transition-colors hover:bg-foreground/10 hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-foreground/40"
                  >
                    &times;
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      {/* Approval form upload zone */}
      <section className="flex flex-col gap-4">
        <h2 className="text-lg font-semibold">Government Approval Form</h2>
        <button
          type="button"
          aria-label="Upload the approval form PDF by dragging and dropping or clicking to browse"
          onClick={() => formInputRef.current?.click()}
          onDragOver={(event) => {
            event.preventDefault();
            setDraggingZone("form");
          }}
          onDragLeave={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget as Node)) {
              setDraggingZone(null);
            }
          }}
          onDrop={handleFormDrop}
          className={`flex w-full cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-foreground/40 ${
            draggingZone === "form"
              ? "border-foreground/60 bg-foreground/5"
              : "border-foreground/25 hover:border-foreground/40 hover:bg-foreground/[0.03]"
          }`}
        >
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.5}
            strokeLinecap="round"
            strokeLinejoin="round"
            className="h-10 w-10 text-foreground/50"
          >
            <path d="M14 3v4a1 1 0 0 0 1 1h4" />
            <path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2Z" />
            <path d="M9 13h6M9 17h6" />
          </svg>
          <p className="text-base font-medium">Drag and drop the approval PDF</p>
          <p className="text-sm text-foreground/60">
            or click to browse — single PDF file
          </p>
        </button>
        <input
          ref={formInputRef}
          type="file"
          accept={FORM_ACCEPT}
          onChange={handleFormInput}
          className="hidden"
        />

        {form && (
          <ul className="flex flex-col gap-2">
            <li className="flex items-center justify-between gap-3 rounded-lg border border-foreground/15 bg-foreground/[0.02] px-4 py-3">
              <div className="flex min-w-0 flex-col">
                <span className="truncate font-medium">{form.name}</span>
                <span className="text-sm text-foreground/60">
                  {formatBytes(form.size)}
                </span>
              </div>
              <button
                type="button"
                onClick={removeForm}
                aria-label={`Remove form ${form.name}`}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-lg text-foreground/50 transition-colors hover:bg-foreground/10 hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-foreground/40"
              >
                &times;
              </button>
            </li>
          </ul>
        )}
      </section>

      {/* Error message */}
      {error && (
        <p
          role="alert"
          className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-600 dark:text-red-400"
        >
          {error}
        </p>
      )}

      {/* Results */}
      {result && (
        <section
          aria-live="polite"
          className="flex flex-col gap-4 rounded-xl border border-foreground/15 bg-foreground/[0.02] p-6"
        >
          <h2 className="text-lg font-semibold">Verification Results</h2>
          <ul className="flex flex-col divide-y divide-foreground/10">
            {RESULT_ROWS.map(({ key, label }) => {
              const isMatch = result[key] === "yes";
              return (
                <li
                  key={key}
                  className="flex items-center justify-between gap-3 py-3"
                >
                  <span className="font-medium">{label}</span>
                  <span
                    className={`flex items-center gap-2 text-sm font-semibold ${
                      isMatch
                        ? "text-green-600 dark:text-green-400"
                        : "text-red-600 dark:text-red-400"
                    }`}
                  >
                    <svg
                      aria-hidden="true"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth={2}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      className="h-5 w-5"
                    >
                      {isMatch ? (
                        <path d="M20 6 9 17l-5-5" />
                      ) : (
                        <path d="M18 6 6 18M6 6l12 12" />
                      )}
                    </svg>
                    {isMatch ? "Match" : "No match"}
                  </span>
                </li>
              );
            })}
          </ul>

          <button
            type="button"
            onClick={handleDownloadCsv}
            className="self-start rounded-lg border border-foreground/25 px-4 py-2 text-sm font-medium transition-colors hover:border-foreground/40 hover:bg-foreground/[0.05] focus:outline-none focus-visible:ring-2 focus-visible:ring-foreground/40"
          >
            Download CSV
          </button>
        </section>
      )}

      {/* Sticky verify footer */}
      <div className="fixed bottom-0 left-0 right-0 border-t border-foreground/10 bg-background/90 px-6 py-4 backdrop-blur-sm">
        <div className="mx-auto max-w-3xl">
          <button
            type="button"
            onClick={handleVerify}
            disabled={!canVerify}
            aria-busy={isVerifying}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-foreground px-6 py-3 text-base font-semibold text-background transition-opacity hover:opacity-80 focus:outline-none focus-visible:ring-2 focus-visible:ring-foreground/40 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {isVerifying && (
              <svg
                aria-hidden="true"
                viewBox="0 0 24 24"
                fill="none"
                className="h-5 w-5 animate-spin"
              >
                <circle
                  cx="12"
                  cy="12"
                  r="9"
                  stroke="currentColor"
                  strokeWidth={3}
                  className="opacity-25"
                />
                <path
                  d="M21 12a9 9 0 0 0-9-9"
                  stroke="currentColor"
                  strokeWidth={3}
                  strokeLinecap="round"
                />
              </svg>
            )}
            {isVerifying ? "Verifying…" : "Start Verifying Labels"}
          </button>
        </div>
      </div>
    </main>
  );
}
