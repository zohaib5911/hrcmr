"use client";

import { FileText, LoaderCircle, Upload, X } from "lucide-react";
import { useId, useState, type DragEvent } from "react";

import { formatBytes, validateFile } from "@/lib/ui/files";
import { cn } from "@/lib/utils";

import { IconButton } from "./button";
import { Icon } from "./icon";
import { ProgressBar } from "./progress";
import { StatusChip } from "./status-chip";

export interface UploadItem {
  id: string;
  name: string;
  size: number;
  /** 0 to 100, while uploading. */
  progress?: number;
  /** Every file is scanned for malware before anyone can open it (plan 4.5). */
  status: "uploading" | "scanning" | "safe" | "rejected";
  /** Why it was rejected, in words. */
  message?: string;
}

interface FileDropProps {
  label: string;
  description?: string;
  /** Extensions (".pdf") or types ("image/*"). */
  accept?: readonly string[];
  maxBytes?: number;
  multiple?: boolean;
  items: readonly UploadItem[];
  /** Called with the files that passed the checks. */
  onFiles: (files: File[]) => void;
  onRemove?: (id: string) => void;
  disabled?: boolean;
  className?: string;
}

/** A drop area and a file picker in one, with each file's progress and scan result listed below. */
export function FileDrop({
  label,
  description,
  accept,
  maxBytes = 10 * 1024 * 1024,
  multiple = false,
  items,
  onFiles,
  onRemove,
  disabled = false,
  className,
}: FileDropProps) {
  const id = useId();
  const [dragging, setDragging] = useState(false);
  const [refused, setRefused] = useState<{ name: string; reason: string }[]>([]);

  function take(list: FileList | null) {
    if (!list || disabled) return;
    const accepted: File[] = [];
    const rejected: { name: string; reason: string }[] = [];
    for (const file of Array.from(list).slice(0, multiple ? undefined : 1)) {
      const reason = validateFile(file, { accept, maxBytes });
      if (reason) rejected.push({ name: file.name, reason });
      else accepted.push(file);
    }
    setRefused(rejected);
    if (accepted.length > 0) onFiles(accepted);
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    take(event.dataTransfer.files);
  }

  return (
    <div className={className}>
      <label
        htmlFor={id}
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "rounded-card flex cursor-pointer flex-col items-center gap-2 border-[1.5px] border-dashed px-6 py-8 text-center transition-colors motion-small",
          "has-[:focus-visible]:outline-accent has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2",
          dragging
            ? "border-accent bg-accent-tint"
            : "border-label-tertiary bg-elevated hover:border-accent",
          disabled && "cursor-not-allowed opacity-50",
        )}
      >
        <Icon icon={Upload} size={24} className="text-label-secondary" />
        <span className="text-headline text-label">{label}</span>
        <span className="text-callout text-label">
          Drag files here, or{" "}
          <span className="text-accent-text font-medium underline">
            choose {multiple ? "files" : "a file"}
          </span>
        </span>
        {description ? <span className="text-footnote text-label">{description}</span> : null}
        <input
          id={id}
          type="file"
          className="sr-only"
          multiple={multiple}
          accept={accept?.join(",")}
          disabled={disabled}
          onChange={(event) => {
            take(event.target.files);
            // Lets the same file be chosen again after it was removed.
            event.target.value = "";
          }}
        />
      </label>

      {refused.length > 0 ? (
        <ul role="alert" className="mt-3 flex flex-col gap-1">
          {refused.map((file) => (
            <li key={file.name} className="text-footnote text-danger">
              <span className="font-medium">{file.name}:</span> {file.reason}
            </li>
          ))}
        </ul>
      ) : null}

      {/* Announced politely, so "Scanning…" turning into "Safe" is heard. */}
      <ul aria-live="polite" aria-label="Files" className="mt-3 flex flex-col gap-2">
        {items.map((item) => (
          <li
            key={item.id}
            className="bg-elevated rounded-card shadow-e1 flex items-center gap-3 p-3"
          >
            <Icon icon={FileText} size={20} className="text-label-secondary" />
            <div className="min-w-0 flex-1">
              <p className="text-callout text-label truncate">{item.name}</p>
              <p className="text-footnote text-label-secondary">{formatBytes(item.size)}</p>
              {item.status === "uploading" ? (
                <ProgressBar
                  label={`Uploading ${item.name}`}
                  value={item.progress}
                  className="mt-1.5"
                />
              ) : null}
              {item.status === "rejected" && item.message ? (
                <p className="text-footnote text-danger mt-1">{item.message}</p>
              ) : null}
            </div>
            {item.status === "scanning" ? (
              <StatusChip tone="info">
                <Icon
                  icon={LoaderCircle}
                  size={16}
                  className="animate-spin motion-reduce:animate-pulse"
                />
                Scanning…
              </StatusChip>
            ) : null}
            {item.status === "safe" ? <StatusChip tone="success">Safe</StatusChip> : null}
            {item.status === "rejected" ? <StatusChip tone="danger">Rejected</StatusChip> : null}
            {onRemove ? (
              <IconButton label={`Remove ${item.name}`} size="sm" onClick={() => onRemove(item.id)}>
                <Icon icon={X} size={16} />
              </IconButton>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
