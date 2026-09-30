"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ShieldCheck } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { useRequireAuth } from "@/lib/use-require-auth";
import { api } from "@/lib/api";
import type { Document, Anomaly } from "@/types";
import { cn, severityColor } from "@/lib/utils";

interface AlertItem extends Anomaly {
  document: Document;
}

export default function AlertsPage() {
  const { user, loading } = useRequireAuth();
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [fetching, setFetching] = useState(true);

  useEffect(() => {
    if (!user) return;
    (async () => {
      const docs = await api.listDocuments();
      const completed = docs.filter((d) => d.status === "completed");
      const results = await Promise.all(
        completed.map(async (d) => {
          const analysis = await api.getAnalysis(d.id);
          return analysis.anomalies.map((a) => ({ ...a, document: d }));
        })
      );
      const flat = results.flat().sort((a, b) => severityRank(b.severity) - severityRank(a.severity));
      setAlerts(flat);
      setFetching(false);
    })();
  }, [user]);

  if (loading || !user) return null;

  return (
    <AppShell>
      <h1 className="font-serif text-2xl mb-1">Alerts</h1>
      <p className="text-sm text-slate-500 dark:text-slate-400 mb-8">Anomalies detected across all of your documents.</p>

      {fetching ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-16 border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900 animate-pulse" />
          ))}
        </div>
      ) : alerts.length === 0 ? (
        <div className="border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900 py-16 text-center">
          <ShieldCheck size={22} className="mx-auto mb-2 text-verdigris-600" strokeWidth={1.5} />
          <p className="text-sm text-slate-500 dark:text-slate-400">No anomalies across any of your documents.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {alerts.map((a) => {
            const colors = severityColor(a.severity);
            return (
              <Link
                key={`${a.document.id}-${a.id}`}
                href={`/documents/${a.document.id}`}
                className="block border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900 p-4 hover:bg-paper-dim dark:hover:bg-ink-800/50"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-2.5">
                    <AlertTriangle size={15} className={cn("mt-0.5 shrink-0", colors.text)} strokeWidth={1.75} />
                    <div>
                      <p className="text-sm font-medium">{a.title}</p>
                      <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{a.document.filename}</p>
                    </div>
                  </div>
                  <span className={cn("text-xs px-2 py-0.5 rounded shrink-0", colors.bg, colors.text)}>
                    {a.severity}
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </AppShell>
  );
}

function severityRank(s: string) {
  return { critical: 3, high: 2, medium: 1, low: 0 }[s] ?? 0;
}
