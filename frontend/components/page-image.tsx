"use client";

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function PageImage({
  documentId, pageNumber, highlightText,
}: {
  documentId: number;
  pageNumber: number;
  highlightText?: string | null;
}) {
  const [src, setSrc] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    async function load() {
      setError(false);
      setSrc(null);
      try {
        const token = window.localStorage.getItem("docai_token");
        const res = await fetch(`${API_URL}/api/documents/${documentId}/pages/${pageNumber}/image`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (!res.ok) throw new Error("failed");
        const blob = await res.blob();
        objectUrl = URL.createObjectURL(blob);
        if (!cancelled) setSrc(objectUrl);
      } catch {
        if (!cancelled) setError(true);
      }
    }

    load();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [documentId, pageNumber]);

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-slate-400 dark:text-slate-500">
        Unable to load this page.
      </div>
    );
  }

  if (!src) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-slate-400 dark:text-slate-500">
        Loading page…
      </div>
    );
  }

  return (
    <div className="relative">
      <img src={src} alt={`Page ${pageNumber}`} className="w-full h-auto shadow-sm" />
      {highlightText && (
        <div className="mt-3 mx-2 p-3 bg-amber-100 dark:bg-amber-600/15 border border-amber-600/30 rounded text-xs text-ink-900 dark:text-paper leading-relaxed">
          <span className="text-amber-600 font-medium">Evidence on this page: </span>
          "{highlightText}"
        </div>
      )}
    </div>
  );
}
