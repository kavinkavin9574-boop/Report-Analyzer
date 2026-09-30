"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Search, Square, Trash2 } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { StatusBadge } from "@/components/status-badge";
import { useRequireAuth } from "@/lib/use-require-auth";
import { api } from "@/lib/api";
import type { Document } from "@/types";
import { documentTypeLabel, formatBytes, formatDate } from "@/lib/utils";

export default function DocumentsPage() {
  const { user, loading } = useRequireAuth();
  const [docs, setDocs] = useState<Document[]>([]);
  const [query, setQuery] = useState("");
  const [fetching, setFetching] = useState(true);
  const [cancelingId, setCancelingId] = useState<number | null>(null);
  const [actionError, setActionError] = useState("");

  useEffect(() => {
    if (!user) return;
    let interval: ReturnType<typeof setInterval>;

    function refresh() {
      api
        .listDocuments()
        .then((next) => {
          setDocs(next);
          // Stop polling once every document has finished processing.
          const stillProcessing = next.some((d) => !["completed", "failed", "cancelled"].includes(d.status));
          if (!stillProcessing) clearInterval(interval);
        })
        .finally(() => setFetching(false));
    }

    refresh();
    // Poll for live status updates (e.g. uploaded -> extracting -> analyzing
    // -> completed) while any document is still processing.
    interval = setInterval(refresh, 3000);
    return () => clearInterval(interval);
  }, [user]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return docs;
    return docs.filter(
      (d) => d.filename.toLowerCase().includes(q) || documentTypeLabel(d.document_type).toLowerCase().includes(q)
    );
  }, [docs, query]);

  async function handleDelete(id: number) {
    if (!confirm("Delete this document and all of its analysis? This can't be undone.")) return;
    await api.deleteDocument(id);
    setDocs((d) => d.filter((doc) => doc.id !== id));
  }

  async function handleCancel(id: number) {
    setCancelingId(id);
    setActionError("");
    try {
      await api.cancelDocument(id);
      setDocs((current) => current.map((doc) => doc.id === id ? { ...doc, status: "cancelling" } : doc));
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Unable to stop document analysis.");
    } finally {
      setCancelingId(null);
    }
  }

  if (loading || !user) return null;

  return (
    <AppShell>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-serif text-2xl">Documents</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">{docs.length} uploaded</p>
        </div>
        <Link href="/upload" className="bg-ink-900 text-paper text-sm px-4 py-2 rounded hover:bg-ink-800">
          Upload document
        </Link>
      </div>

      <div className="relative mb-4">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by filename or document type…"
          className="w-full border border-slate-300 dark:border-ink-700 rounded pl-9 pr-3 py-2 text-sm bg-white dark:bg-ink-900 focus:outline-none focus:ring-2 focus:ring-verdigris-500/40 focus:border-verdigris-500"
        />
      </div>

      {actionError && <p role="alert" className="mb-3 text-sm text-brick-600">{actionError}</p>}

      {fetching ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-14 border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900 animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900 py-16 text-center">
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {docs.length === 0 ? "No documents yet." : "No documents match your search."}
          </p>
        </div>
      ) : (
        <div className="border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900 divide-y divide-slate-300/40 dark:divide-ink-700/50">
          {filtered.map((d) => (
            <div key={d.id} className="flex items-center gap-4 px-5 py-3.5 hover:bg-paper-dim dark:hover:bg-ink-800/50">
              <Link href={`/documents/${d.id}`} className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{d.filename}</p>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  {documentTypeLabel(d.document_type)} · {formatBytes(d.file_size)} · {formatDate(d.created_at)}
                </p>
              </Link>
              <StatusBadge status={d.status} />
              {!(["completed", "failed", "cancelled"].includes(d.status)) && (
                <button
                  onClick={() => handleCancel(d.id)}
                  disabled={cancelingId === d.id || d.status === "cancelling"}
                  aria-label={d.status === "cancelling" ? "Stopping analysis" : "Stop analysis"}
                  title={d.status === "cancelling" ? "Stopping analysis" : "Stop analysis"}
                  className="inline-flex items-center gap-1.5 text-xs text-amber-700 dark:text-amber-500 hover:text-brick-600 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Square size={13} /> {d.status === "cancelling" || cancelingId === d.id ? "Stopping…" : "Stop"}
                </button>
              )}
              <button onClick={() => handleDelete(d.id)} className="text-slate-400 dark:text-slate-500 hover:text-brick-600">
                <Trash2 size={16} strokeWidth={1.75} />
              </button>
            </div>
          ))}
        </div>
      )}
    </AppShell>
  );
}
