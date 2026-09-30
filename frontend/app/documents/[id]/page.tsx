"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  FileText, Clock, ListChecks, Wallet, AlertTriangle, FileWarning,
  ShieldCheck, MessageSquare, X, RefreshCw, Send, Square,
} from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { StatusBadge } from "@/components/status-badge";
import { PageImage } from "@/components/page-image";
import { useRequireAuth } from "@/lib/use-require-auth";
import { api } from "@/lib/api";
import type { DocumentAnalysis, Evidence } from "@/types";
import { cn, documentTypeLabel, formatFieldName, severityColor } from "@/lib/utils";

type TabKey = "overview" | "deadlines" | "obligations" | "financial" | "anomalies" | "missing" | "chat";

const TABS: { key: TabKey; label: string; icon: typeof FileText }[] = [
  { key: "overview", label: "Overview", icon: FileText },
  { key: "deadlines", label: "Deadlines", icon: Clock },
  { key: "obligations", label: "Obligations", icon: ListChecks },
  { key: "financial", label: "Financial", icon: Wallet },
  { key: "anomalies", label: "Anomalies", icon: AlertTriangle },
  { key: "missing", label: "Missing Data", icon: FileWarning },
  { key: "chat", label: "Ask this document", icon: MessageSquare },
];

export default function DocumentDetailPage() {
  const { user, loading } = useRequireAuth();
  const params = useParams();
  const documentId = Number(params.id);

  const [analysis, setAnalysis] = useState<DocumentAnalysis | null>(null);
  const [tab, setTab] = useState<TabKey>("overview");
  const [activeEvidence, setActiveEvidence] = useState<Evidence | null>(null);
  const [polling, setPolling] = useState(true);
  const [reanalyzeError, setReanalyzeError] = useState<string | null>(null);
  const [reanalyzing, setReanalyzing] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const [canceling, setCanceling] = useState(false);

  useEffect(() => {
    if (!user || !documentId || !polling) return;
    let interval: ReturnType<typeof setInterval>;

    async function fetchAnalysis() {
      try {
        const data = await api.getAnalysis(documentId);
        setAnalysis(data);
        if (["completed", "failed", "cancelled"].includes(data.document.status)) {
          setPolling(false);
          clearInterval(interval);
        }
      } catch {
        // ignore transient errors while processing
      }
    }

    fetchAnalysis();
    interval = setInterval(fetchAnalysis, 2000);
    return () => clearInterval(interval);
  }, [user, documentId, polling]);

  if (loading || !user) return null;

  if (!analysis) {
    return (
      <AppShell>
        <div className="h-64 animate-pulse bg-white dark:bg-ink-900 border border-slate-300/70 rounded" />
      </AppShell>
    );
  }

  const { document } = analysis;
  const isProcessing = !["completed", "failed", "cancelled"].includes(document.status);

  return (
    <AppShell>
      <div className="flex items-start justify-between mb-1 gap-4">
        <div className="min-w-0">
          <h1 className="font-serif text-2xl truncate">{document.filename}</h1>
          <div className="flex items-center gap-2 mt-1.5 text-sm text-slate-500 dark:text-slate-400">
            <span>{documentTypeLabel(document.document_type)}</span>
            <span>·</span>
            <StatusBadge status={document.status} />
          </div>
        </div>
        <div className="shrink-0 flex items-center gap-2">
          {isProcessing && (
            <button
              disabled={canceling || document.status === "cancelling"}
              onClick={async () => {
                setCanceling(true);
                setCancelError(null);
                try {
                  const result = await api.cancelDocument(documentId);
                  setAnalysis((current) => current ? {
                    ...current,
                    document: { ...current.document, status: result.status },
                  } : current);
                } catch (error) {
                  setCancelError(error instanceof Error ? error.message : "Analysis could not be stopped.");
                } finally {
                  setCanceling(false);
                }
              }}
              className="flex items-center gap-1.5 text-xs border border-amber-600/40 text-amber-700 dark:text-amber-500 rounded px-3 py-1.5 hover:bg-amber-100 dark:hover:bg-amber-600/10 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Square size={13} /> {canceling || document.status === "cancelling" ? "Stopping…" : "Stop analysis"}
            </button>
          )}
          <button
            disabled={isProcessing || reanalyzing}
            onClick={async () => {
              setReanalyzing(true);
              setReanalyzeError(null);
              try {
                await api.reanalyze(documentId);
                setPolling(true);
              } catch (error) {
                setReanalyzeError(error instanceof Error ? error.message : "Re-analysis could not be started.");
              } finally {
                setReanalyzing(false);
              }
            }}
            className="flex items-center gap-1.5 text-xs border border-slate-300 dark:border-ink-700 rounded px-3 py-1.5 hover:bg-paper-dim dark:hover:bg-ink-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw size={13} className={reanalyzing ? "animate-spin" : undefined} /> {reanalyzing ? "Starting…" : "Re-analyze"}
          </button>
        </div>
      </div>

      {cancelError && (
        <div role="alert" className="mt-3 text-sm text-brick-600 bg-brick-100 border border-brick-600/20 rounded px-4 py-2.5">
          {cancelError}
        </div>
      )}
      {reanalyzeError && (
        <div role="alert" className="mt-3 text-sm text-brick-600 bg-brick-100 border border-brick-600/20 rounded px-4 py-2.5">
          {reanalyzeError}
        </div>
      )}

      {isProcessing && (
        <div className="mt-4 mb-6 flex items-center gap-2 text-sm text-amber-600 bg-amber-100 border border-amber-600/20 rounded px-4 py-2.5">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-600 animate-pulse" />
          {document.status === "extracting_text" && "Extracting text from the document…"}
          {document.status === "processing" && "Preparing document…"}
          {document.status === "analyzing" && "Running AI analysis…"}
          {document.status === "validating" && "Validating findings…"}
          {document.status === "uploaded" && "Queued for processing…"}
        </div>
      )}

      {document.status === "failed" && (
        <div className="mt-4 mb-6 text-sm text-brick-600 bg-brick-100 border border-brick-600/20 rounded px-4 py-2.5">
          Analysis failed. {document.error_message || "Try re-analyzing, or upload the document again if the problem persists."}
        </div>
      )}

      {document.status === "cancelling" && (
        <div className="mt-4 mb-6 text-sm text-amber-700 dark:text-amber-500 bg-amber-100 dark:bg-amber-600/10 border border-amber-600/20 rounded px-4 py-2.5">
          Stop requested. The current OCR or AI request will finish before processing stops.
        </div>
      )}
      {document.status === "cancelled" && (
        <div className="mt-4 mb-6 text-sm text-slate-600 dark:text-slate-300 bg-paper-dim dark:bg-ink-800 border border-slate-300/70 dark:border-ink-700/60 rounded px-4 py-2.5">
          Analysis stopped. You can start it again with Re-analyze.
        </div>
      )}

      {/* Tabs */}
      <div className="mt-6 border-b border-slate-300/70 dark:border-ink-700/60 flex gap-1 overflow-x-auto no-scrollbar">
        {TABS.map((t) => {
          const Icon = t.icon;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={cn(
                "flex items-center gap-1.5 px-3.5 py-2.5 text-sm whitespace-nowrap border-b-2 -mb-px transition-colors",
                tab === t.key ? "border-ink-900 text-ink-900 dark:text-paper" : "border-transparent text-slate-500 dark:text-slate-400 hover:text-ink-700"
              )}
            >
              <Icon size={14} strokeWidth={1.75} />
              {t.label}
            </button>
          );
        })}
      </div>

      <div className={cn("mt-6 grid gap-6", activeEvidence ? "lg:grid-cols-2" : "grid-cols-1")}>
        <div className="min-w-0">
          {tab === "overview" && <OverviewTab analysis={analysis} onEvidence={setActiveEvidence} />}
          {tab === "deadlines" && <DeadlinesTab analysis={analysis} onEvidence={setActiveEvidence} />}
          {tab === "obligations" && <ObligationsTab analysis={analysis} onEvidence={setActiveEvidence} />}
          {tab === "financial" && <FinancialTab analysis={analysis} onEvidence={setActiveEvidence} />}
          {tab === "anomalies" && <AnomaliesTab analysis={analysis} />}
          {tab === "missing" && <MissingTab analysis={analysis} />}
          {tab === "chat" && <ChatTab documentId={documentId} disabled={isProcessing} />}
        </div>

        {activeEvidence && (
          <div className="border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900 lg:sticky lg:top-6 lg:max-h-[calc(100vh-3rem)] lg:overflow-y-auto">
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-300/70 dark:border-ink-700/60">
              <span className="text-xs text-slate-500 dark:text-slate-400">
                Page {activeEvidence.page_number}
                {activeEvidence.section ? ` · ${activeEvidence.section}` : ""}
              </span>
              <button onClick={() => setActiveEvidence(null)} className="text-slate-400 dark:text-slate-500 hover:text-slate-600">
                <X size={16} />
              </button>
            </div>
            <div className="p-2">
              <PageImage
                documentId={documentId}
                pageNumber={activeEvidence.page_number}
                highlightText={activeEvidence.source_text}
              />
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}

function EvidenceButton({ evidence, onClick }: { evidence: Evidence | null; onClick: (e: Evidence) => void }) {
  if (!evidence) return null;
  return (
    <button
      onClick={() => onClick(evidence)}
      className="text-xs text-verdigris-600 hover:underline whitespace-nowrap"
    >
      View source — p.{evidence.page_number}
    </button>
  );
}

function OverviewTab({
  analysis, onEvidence,
}: { analysis: DocumentAnalysis; onEvidence: (e: Evidence) => void }) {
  return (
    <div className="space-y-6">
      {analysis.summary && (
        <div className="border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900 p-5">
          <h2 className="text-sm font-medium mb-2">Summary</h2>
          <p className="text-sm text-ink-700 leading-relaxed">{analysis.summary}</p>
          {analysis.model_used && <p className="text-xs text-slate-400 dark:text-slate-500 mt-3">Analyzed with {analysis.model_used}</p>}
        </div>
      )}

      <div className="border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900">
        <div className="px-5 py-3 border-b border-slate-300/70 dark:border-ink-700/60">
          <h2 className="text-sm font-medium">Extracted fields</h2>
        </div>
        {analysis.findings.length === 0 ? (
          <p className="px-5 py-8 text-sm text-slate-500 dark:text-slate-400 text-center">No fields extracted yet.</p>
        ) : (
          <div className="divide-y divide-slate-300/40 dark:divide-ink-700/50">
            {analysis.findings.map((f) => (
              <div key={f.id} className="flex items-center justify-between gap-4 px-5 py-3">
                <div className="min-w-0">
                  <p className="text-xs text-slate-500 dark:text-slate-400">{formatFieldName(f.field_name)}</p>
                  <p className="text-sm truncate">{f.field_value}</p>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className="text-xs text-slate-400 dark:text-slate-500">{Math.round(f.confidence * 100)}%</span>
                  <EvidenceButton evidence={f.evidence} onClick={onEvidence} />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function DeadlinesTab({ analysis, onEvidence }: { analysis: DocumentAnalysis; onEvidence: (e: Evidence) => void }) {
  if (analysis.deadlines.length === 0) return <EmptyState label="No deadlines detected in this document." />;
  return (
    <div className="border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900 divide-y divide-slate-300/40 dark:divide-ink-700/50">
      {analysis.deadlines.map((d) => (
        <div key={d.id} className="flex items-center justify-between gap-4 px-5 py-3.5">
          <div>
            <p className="text-sm">{d.event}</p>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{d.value || (d.absolute_date && new Date(d.absolute_date).toLocaleDateString())}</p>
          </div>
          <EvidenceButton evidence={d.evidence} onClick={onEvidence} />
        </div>
      ))}
    </div>
  );
}

function ObligationsTab({ analysis, onEvidence }: { analysis: DocumentAnalysis; onEvidence: (e: Evidence) => void }) {
  if (analysis.obligations.length === 0) return <EmptyState label="No obligations detected in this document." />;
  return (
    <div className="border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900 divide-y divide-slate-300/40 dark:divide-ink-700/50">
      {analysis.obligations.map((o) => (
        <div key={o.id} className="px-5 py-3.5">
          <div className="flex items-start justify-between gap-4">
            <p className="text-sm">{o.action}</p>
            <EvidenceButton evidence={o.evidence} onClick={onEvidence} />
          </div>
          <div className="flex flex-wrap gap-3 mt-1.5 text-xs text-slate-500 dark:text-slate-400">
            {o.responsible_party && <span>Party: {o.responsible_party}</span>}
            {o.frequency && <span>Frequency: {o.frequency}</span>}
            {o.deadline && <span>Deadline: {o.deadline}</span>}
          </div>
        </div>
      ))}
    </div>
  );
}

function FinancialTab({ analysis, onEvidence }: { analysis: DocumentAnalysis; onEvidence: (e: Evidence) => void }) {
  if (analysis.financial_values.length === 0) return <EmptyState label="No financial values extracted." />;
  return (
    <div className="border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900 divide-y divide-slate-300/40 dark:divide-ink-700/50">
      {analysis.financial_values.map((v) => (
        <div key={v.id} className="flex items-center justify-between gap-4 px-5 py-3.5">
          <div>
            <p className="text-sm">{formatFieldName(v.label)}</p>
            {v.is_calculated && <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">Calculated deterministically</p>}
          </div>
          <div className="flex items-center gap-3">
            <span className="font-mono text-sm">
              {v.value?.toLocaleString(undefined, { style: "currency", currency: v.currency || "USD" })}
            </span>
            <EvidenceButton evidence={v.evidence} onClick={onEvidence} />
          </div>
        </div>
      ))}
    </div>
  );
}

function AnomaliesTab({ analysis }: { analysis: DocumentAnalysis }) {
  if (analysis.anomalies.length === 0) {
    return (
      <div className="border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900 py-12 text-center">
        <ShieldCheck size={22} className="mx-auto mb-2 text-verdigris-600" strokeWidth={1.5} />
        <p className="text-sm text-slate-500 dark:text-slate-400">No anomalies detected.</p>
      </div>
    );
  }
  return (
    <div className="space-y-2">
      {analysis.anomalies.map((a) => {
        const colors = severityColor(a.severity);
        return (
          <div key={a.id} className="border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900 p-4">
            <div className="flex items-start justify-between gap-3">
              <p className="text-sm font-medium">{a.title}</p>
              <span className={cn("text-xs px-2 py-0.5 rounded shrink-0", colors.bg, colors.text)}>
                {a.severity}
              </span>
            </div>
            {a.description && <p className="text-sm text-slate-500 dark:text-slate-400 mt-1.5 leading-relaxed">{a.description}</p>}
            <div className="flex items-center gap-3 mt-2 text-xs text-slate-400 dark:text-slate-500">
              <span>{a.detection_type === "ai" ? "AI-detected" : "Rule-based"}</span>
              {a.pages && a.pages.length > 0 && <span>Pages: {a.pages.join(", ")}</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function MissingTab({ analysis }: { analysis: DocumentAnalysis }) {
  if (analysis.missing_data.length === 0) {
    return (
      <div className="border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900 py-12 text-center">
        <ShieldCheck size={22} className="mx-auto mb-2 text-verdigris-600" strokeWidth={1.5} />
        <p className="text-sm text-slate-500 dark:text-slate-400">Nothing required appears to be missing.</p>
      </div>
    );
  }
  return (
    <div className="border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900 divide-y divide-slate-300/40 dark:divide-ink-700/50">
      {analysis.missing_data.map((m) => (
        <div key={m.id} className="flex items-center gap-3 px-5 py-3.5">
          <FileWarning size={15} className="text-amber-600 shrink-0" strokeWidth={1.75} />
          <div>
            <p className="text-sm">{m.field_name}</p>
            {m.description && <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{m.description}</p>}
          </div>
        </div>
      ))}
    </div>
  );
}

function ChatTab({ documentId, disabled }: { documentId: number; disabled: boolean }) {
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; content: string; page?: number }[]>([]);
  const [question, setQuestion] = useState("");
  const [sending, setSending] = useState(false);

  async function send() {
    if (!question.trim() || sending) return;
    const q = question.trim();
    setMessages((m) => [...m, { role: "user", content: q }]);
    setQuestion("");
    setSending(true);
    try {
      const res = await api.chat(documentId, q);
      setMessages((m) => [...m, { role: "assistant", content: res.answer, page: res.evidence?.page_number }]);
    } catch (err) {
      setMessages((m) => [...m, { role: "assistant", content: err instanceof Error ? err.message : "Something went wrong." }]);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900 flex flex-col h-[500px]">
      <div className="flex-1 overflow-y-auto p-5 space-y-3">
        {messages.length === 0 && (
          <p className="text-sm text-slate-400 dark:text-slate-500 text-center mt-16">
            Ask a question about this document — answers are grounded only in its content.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={cn("max-w-[85%]", m.role === "user" ? "ml-auto text-right" : "")}>
            <div
              className={cn(
                "inline-block rounded px-3.5 py-2 text-sm text-left",
                m.role === "user" ? "bg-ink-900 text-paper" : "bg-paper-dim text-ink-900 dark:text-paper"
              )}
            >
              {m.content}
            </div>
            {m.page && <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">Source: page {m.page}</p>}
          </div>
        ))}
      </div>
      <div className="border-t border-slate-300/70 dark:border-ink-700/60 p-3 flex gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          disabled={disabled}
          placeholder={disabled ? "Wait for analysis to complete…" : "What is the payment deadline?"}
          className="flex-1 border border-slate-300 dark:border-ink-700 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-verdigris-500/40 focus:border-verdigris-500 disabled:bg-paper-dim"
        />
        <button
          onClick={send}
          disabled={disabled || sending}
          className="bg-ink-900 text-paper rounded px-3.5 disabled:opacity-50"
        >
          <Send size={15} />
        </button>
      </div>
    </div>
  );
}

function EmptyState({ label }: { label: string }) {
  return (
    <div className="border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900 py-12 text-center">
      <p className="text-sm text-slate-500 dark:text-slate-400">{label}</p>
    </div>
  );
}
