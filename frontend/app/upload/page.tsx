"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { UploadCloud, File as FileIcon, X, Loader2 } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { useRequireAuth } from "@/lib/use-require-auth";
import { api } from "@/lib/api";
import { formatBytes } from "@/lib/utils";

const ACCEPTED_TYPES = ["application/pdf", "image/png", "image/jpeg"];
const MAX_SIZE = 25 * 1024 * 1024;

interface QueueItem {
  file: File;
  status: "pending" | "uploading" | "done" | "error";
  error?: string;
  documentId?: number;
}

export default function UploadPage() {
  const { user, loading } = useRequireAuth();
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  const addFiles = useCallback((files: FileList | null) => {
    if (!files) return;
    const items: QueueItem[] = Array.from(files).map((file) => {
      if (!ACCEPTED_TYPES.includes(file.type)) {
        return { file, status: "error", error: "Unsupported file type" };
      }
      if (file.size > MAX_SIZE) {
        return { file, status: "error", error: "File exceeds 25MB limit" };
      }
      return { file, status: "pending" };
    });
    setQueue((q) => [...q, ...items]);
  }, []);

  async function startUpload(index: number) {
    setQueue((q) => q.map((item, i) => (i === index ? { ...item, status: "uploading" } : item)));
    try {
      const doc = await api.uploadDocument(queue[index].file);
      setQueue((q) => q.map((item, i) => (i === index ? { ...item, status: "done", documentId: doc.id } : item)));
    } catch (err) {
      setQueue((q) =>
        q.map((item, i) =>
          i === index ? { ...item, status: "error", error: err instanceof Error ? err.message : "Upload failed" } : item
        )
      );
    }
  }

  function retry(index: number) {
    startUpload(index);
  }

  function remove(index: number) {
    setQueue((q) => q.filter((_, i) => i !== index));
  }

  if (loading || !user) return null;

  return (
    <AppShell>
      <h1 className="font-serif text-2xl mb-1">Upload documents</h1>
      <p className="text-sm text-slate-500 dark:text-slate-400 mb-8">
        PDF, PNG, or JPG — up to 25MB. We'll classify, extract, and validate automatically.
      </p>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragActive(false);
          addFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className={`border-2 border-dashed rounded-lg py-14 px-6 text-center cursor-pointer transition-colors ${
          dragActive ? "border-verdigris-500 bg-verdigris-100/40 dark:bg-verdigris-600/10" : "border-slate-300 dark:border-ink-700 bg-white dark:bg-ink-900 hover:border-slate-400 dark:hover:border-ink-600"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".pdf,.png,.jpg,.jpeg"
          className="hidden"
          onChange={(e) => addFiles(e.target.files)}
        />
        <UploadCloud size={28} className="mx-auto mb-3 text-slate-400 dark:text-slate-500" strokeWidth={1.5} />
        <p className="text-sm">
          <span className="text-verdigris-600 font-medium">Click to upload</span> or drag and drop
        </p>
        <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">PDF, PNG, JPG up to 25MB</p>
      </div>

      {queue.length > 0 && (
        <div className="mt-6 space-y-2">
          {queue.map((item, i) => (
            <div key={i} className="flex items-center gap-3 border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900 px-4 py-3">
              <FileIcon size={18} className="text-slate-400 dark:text-slate-500 shrink-0" strokeWidth={1.75} />
              <div className="flex-1 min-w-0">
                <p className="text-sm truncate">{item.file.name}</p>
                <p className="text-xs text-slate-400 dark:text-slate-500">{formatBytes(item.file.size)}</p>
              </div>

              {item.status === "pending" && (
                <button
                  onClick={() => startUpload(i)}
                  className="text-xs bg-ink-900 text-paper px-3 py-1.5 rounded hover:bg-ink-800"
                >
                  Upload
                </button>
              )}
              {item.status === "uploading" && (
                <Loader2 size={16} className="animate-spin text-slate-400 dark:text-slate-500" />
              )}
              {item.status === "done" && item.documentId && (
                <button
                  onClick={() => router.push(`/documents/${item.documentId}`)}
                  className="text-xs text-verdigris-600 hover:underline"
                >
                  View analysis →
                </button>
              )}
              {item.status === "error" && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-brick-600">{item.error}</span>
                  <button onClick={() => retry(i)} className="text-xs text-verdigris-600 hover:underline">
                    Retry
                  </button>
                </div>
              )}

              <button onClick={() => remove(i)} className="text-slate-400 dark:text-slate-500 hover:text-slate-600">
                <X size={15} />
              </button>
            </div>
          ))}
        </div>
      )}
    </AppShell>
  );
}
