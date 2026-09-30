"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  FileStack, AlertOctagon, AlertTriangle, Clock, FileWarning, Wallet,
} from "lucide-react";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
  PieChart, Pie, Cell,
} from "recharts";
import { AppShell } from "@/components/app-shell";
import { StatCard } from "@/components/stat-card";
import { StatusBadge } from "@/components/status-badge";
import { useRequireAuth } from "@/lib/use-require-auth";
import { api } from "@/lib/api";
import type { DashboardStats, Document } from "@/types";
import { documentTypeLabel, formatBytes, formatCurrency, formatDate } from "@/lib/utils";

const SEVERITY_COLORS: Record<string, string> = {
  low: "#6B7280",
  medium: "#C77D2E",
  high: "#B23A2E",
  critical: "#7A1F17",
};

export default function DashboardPage() {
  const { user, loading } = useRequireAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [docs, setDocs] = useState<Document[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    let interval: ReturnType<typeof setInterval>;

    function refresh() {
      Promise.all([api.getDashboardStats(), api.listDocuments()])
        .then(([s, d]) => {
          setStats(s);
          setDocs(d.slice(0, 6));
          // Stop polling once nothing on the dashboard is still processing.
          const stillProcessing = d.some((doc) => !["completed", "failed", "cancelled"].includes(doc.status));
          if (!stillProcessing) clearInterval(interval);
        })
        .catch((e) => setError(e.message));
    }

    refresh();
    // Poll for live status updates while any recent document is still
    // processing, so counts/charts/status badges update without a reload.
    interval = setInterval(refresh, 3000);
    return () => clearInterval(interval);
  }, [user]);

  if (loading || !user) return null;

  const severityData = stats
    ? Object.entries(stats.findings_by_severity).map(([severity, count]) => ({ severity, count }))
    : [];

  const typeData = stats
    ? Object.entries(stats.documents_by_type).map(([type, count]) => ({ name: documentTypeLabel(type), value: count }))
    : [];

  return (
    <AppShell>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-serif text-2xl">Dashboard</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">An overview of everything you've uploaded.</p>
        </div>
        <Link
          href="/upload"
          className="bg-ink-900 text-paper text-sm px-4 py-2 rounded hover:bg-ink-800 transition-colors"
        >
          Upload document
        </Link>
      </div>

      {error && <p className="text-sm text-brick-600 mb-4">{error}</p>}

      {!stats ? (
        <DashboardSkeleton />
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
            <StatCard label="Documents analyzed" value={stats.documents_analyzed} icon={FileStack} />
            <StatCard label="Critical issues" value={stats.critical_issues} icon={AlertOctagon} tone="critical" />
            <StatCard label="Warnings" value={stats.warnings} icon={AlertTriangle} tone="warning" />
            <StatCard label="Upcoming deadlines" value={stats.upcoming_deadlines} icon={Clock} />
            <StatCard label="Missing data" value={stats.missing_data_count} icon={FileWarning} tone="warning" />
            <StatCard
              label="Total financial value"
              value={formatCurrency(stats.total_financial_value)}
              icon={Wallet}
              tone="positive"
            />
          </div>

          <div className="grid md:grid-cols-2 gap-4 mb-8">
            <div className="border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900 p-5">
              <h2 className="text-sm text-slate-500 dark:text-slate-400 mb-4">Findings by severity</h2>
              {severityData.every((d) => d.count === 0) ? (
                <EmptyChart label="No findings yet — upload a document to see this fill in." />
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={severityData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#D3D6DC" vertical={false} />
                    <XAxis dataKey="severity" tick={{ fontSize: 12, fill: "#6B7280" }} axisLine={false} tickLine={false} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: "#6B7280" }} axisLine={false} tickLine={false} />
                    <Tooltip cursor={{ fill: "#EFEDE6" }} />
                    <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                      {severityData.map((entry) => (
                        <Cell key={entry.severity} fill={SEVERITY_COLORS[entry.severity]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>

            <div className="border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900 p-5">
              <h2 className="text-sm text-slate-500 dark:text-slate-400 mb-4">Document type distribution</h2>
              {typeData.length === 0 ? (
                <EmptyChart label="Nothing uploaded yet." />
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie
                      data={typeData}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={50}
                      outerRadius={80}
                      paddingAngle={2}
                    >
                      {typeData.map((_, i) => (
                        <Cell key={i} fill={["#2F6F62", "#C77D2E", "#141A2E", "#6B7280", "#B23A2E"][i % 5]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </>
      )}

      <div className="border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900">
        <div className="px-5 py-4 border-b border-slate-300/70 dark:border-ink-700/60 flex items-center justify-between">
          <h2 className="text-sm font-medium">Recent documents</h2>
          <Link href="/documents" className="text-xs text-verdigris-600 hover:underline">
            View all
          </Link>
        </div>

        {docs.length === 0 ? (
          <div className="px-5 py-10 text-center">
            <p className="text-sm text-slate-500 dark:text-slate-400">No documents yet.</p>
            <Link href="/upload" className="text-sm text-verdigris-600 hover:underline">
              Upload your first document →
            </Link>
          </div>
        ) : (
          <>
            {/* Desktop table */}
            <table className="w-full text-sm hidden md:table">
              <thead>
                <tr className="text-left text-xs text-slate-500 dark:text-slate-400 border-b border-slate-300/70 dark:border-ink-700/60">
                  <th className="font-normal px-5 py-2.5">Document</th>
                  <th className="font-normal px-5 py-2.5">Type</th>
                  <th className="font-normal px-5 py-2.5">Status</th>
                  <th className="font-normal px-5 py-2.5">Uploaded</th>
                </tr>
              </thead>
              <tbody>
                {docs.map((d) => (
                  <tr key={d.id} className="border-b border-slate-300/40 last:border-0 hover:bg-paper-dim dark:hover:bg-ink-800/50">
                    <td className="px-5 py-3">
                      <Link href={`/documents/${d.id}`} className="hover:text-verdigris-600">
                        {d.filename}
                      </Link>
                    </td>
                    <td className="px-5 py-3 text-slate-500 dark:text-slate-400">{documentTypeLabel(d.document_type)}</td>
                    <td className="px-5 py-3"><StatusBadge status={d.status} /></td>
                    <td className="px-5 py-3 text-slate-500 dark:text-slate-400">{formatDate(d.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Mobile cards */}
            <div className="md:hidden divide-y divide-slate-300/40 dark:divide-ink-700/50">
              {docs.map((d) => (
                <Link key={d.id} href={`/documents/${d.id}`} className="block px-5 py-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium truncate pr-2">{d.filename}</span>
                    <StatusBadge status={d.status} />
                  </div>
                  <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                    {documentTypeLabel(d.document_type)} · {formatBytes(d.file_size)} · {formatDate(d.created_at)}
                  </div>
                </Link>
              ))}
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}

function EmptyChart({ label }: { label: string }) {
  return <div className="h-[220px] flex items-center justify-center text-sm text-slate-400 dark:text-slate-500">{label}</div>;
}

function DashboardSkeleton() {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900 px-5 py-4 h-[84px] animate-pulse" />
      ))}
    </div>
  );
}
