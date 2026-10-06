"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  FileText, Clock, ListChecks, Wallet, AlertTriangle, FileWarning,
  ShieldCheck, MessageSquare, X, RefreshCw, Send, Square, Eye,
} from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { StatusBadge } from "@/components/status-badge";
import { PageImage } from "@/components/page-image";
import { useRequireAuth } from "@/lib/use-require-auth";
import { api } from "@/lib/api";
import type { DocumentAnalysis, Evidence, SummarySection } from "@/types";
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
          {document.status === "analyzing" && "Reviewing document details and cross-checking findings…"}
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
  const findingByName = new Map(analysis.findings.map((finding) => [finding.field_name, finding]));
  const summary = analysis.summary;
  const summaryText = typeof summary === "string" ? summary.trim() : summary?.text.trim();
  const overviewSection = findReportSection(analysis, "Overview");
  const hasStructuredReport = typeof summary !== "string" && (summary?.sections.length ?? 0) > 0;
  const keyPoints = typeof summary === "string" || hasStructuredReport ? [] : summary?.key_points ?? [];
  const rows = hasStructuredReport ? [] : Object.entries(analysis.extracted_fields ?? {});
  const hasExtractedDetails = summaryText || keyPoints.length > 0 || (overviewSection?.items.length ?? 0) > 0 || rows.length > 0;
  const [isOriginalOpen, setIsOriginalOpen] = useState(false);
  const reportPages = analysis.report_text
    .split(/(?=\[PAGE \d+\]\n)/)
    .map((page) => {
      const match = page.match(/^\[PAGE (\d+)\]\n/);
      return {
        pageNumber: match ? Number(match[1]) : null,
        text: page.replace(/^\[PAGE \d+\]\n/, "").trim(),
      };
    })
    .filter((page) => page.text);

  return (
    <div className="space-y-6">
      <div className="border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900">
        <div className="flex items-center justify-between gap-3 px-5 py-3 border-b border-slate-300/70 dark:border-ink-700/60">
          <h2 className="text-sm font-medium">Report details</h2>
          <button
            type="button"
            onClick={() => setIsOriginalOpen((open) => !open)}
            aria-expanded={isOriginalOpen}
            className="inline-flex shrink-0 items-center gap-1.5 rounded border border-slate-300 dark:border-ink-700 px-3 py-1.5 text-xs text-ink-700 dark:text-slate-200 hover:bg-paper-dim dark:hover:bg-ink-800"
          >
            {isOriginalOpen ? <X size={14} /> : <Eye size={14} />}
            {isOriginalOpen ? "Close original" : "View original"}
          </button>
        </div>
        {isOriginalOpen && <OriginalDocumentViewer document={analysis.document} />}
        {summaryText && (
          <p className="px-5 py-4 text-sm leading-6 text-ink-700 dark:text-slate-200 border-b border-slate-300/70 dark:border-ink-700/60">
            {summaryText}
          </p>
        )}
        {keyPoints.length > 0 && (
          <ul className="divide-y divide-slate-300/40 dark:divide-ink-700/50">
            {keyPoints.map((point, index) => (
              <li key={`${index}-${point}`} className="px-5 py-3 text-sm leading-6 text-ink-700 dark:text-slate-200">
                {point}
              </li>
            ))}
          </ul>
        )}
        {overviewSection && <StructuredReportSection section={overviewSection} />}
        {rows.length === 0 ? (
          <p className="px-5 py-6 text-sm text-slate-500 dark:text-slate-400">
            {hasExtractedDetails
              ? "The report details are shown above."
              : analysis.report_text
                ? "Key facts were not extracted. Showing the text recognized from your report instead."
                : "No readable text was extracted from this report. If it is scanned, check OCR setup and re-analyze."}
          </p>
        ) : (
          <div className="divide-y divide-slate-300/40 dark:divide-ink-700/50">
            {rows.map(([key, value]) => (
              <article key={key} className="px-5 py-4">
                <div className="flex items-start justify-between gap-4">
                  <h3 className="text-sm font-medium text-ink-800 dark:text-paper">
                    {formatFieldName(key)}
                  </h3>
                  <EvidenceButton
                    evidence={findingByName.get(key)?.evidence ?? null}
                    onClick={onEvidence}
                  />
                </div>
                <p className="mt-1.5 text-sm leading-6 text-ink-700 dark:text-slate-200 whitespace-pre-wrap break-words">
                  {formatFindingValue(value)}
                </p>
              </article>
            ))}
          </div>
        )}
        {!hasExtractedDetails && analysis.report_text && (
          <div className="space-y-4 px-5 pb-5">
            {reportPages.map(({ pageNumber, text }, index) => (
              <article
                key={`${pageNumber ?? "page"}-${index}`}
                className="rounded border border-slate-200 dark:border-ink-700 bg-paper-dim/40 dark:bg-ink-800/50"
              >
                {pageNumber !== null && (
                  <h3 className="border-b border-slate-200 dark:border-ink-700 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                    Page {pageNumber}
                  </h3>
                )}
                <p className="px-4 py-4 text-sm leading-7 text-ink-700 dark:text-slate-200 whitespace-pre-line break-words">
                  {text}
                </p>
              </article>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function OriginalDocumentViewer({ document }: { document: DocumentAnalysis["document"] }) {
  const [source, setSource] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    async function loadOriginal() {
      setError(null);
      try {
        const token = window.localStorage.getItem("docai_token");
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/documents/${document.id}/original`,
          { headers: token ? { Authorization: `Bearer ${token}` } : {} },
        );
        if (!response.ok) {
          throw new Error(response.status === 404
            ? "The original file could not be found."
            : "Could not load the original document.");
        }
        objectUrl = URL.createObjectURL(await response.blob());
        if (!cancelled) setSource(objectUrl);
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Could not load the original document.");
        }
      }
    }

    loadOriginal();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [document.id]);

  return (
    <section className="border-b border-slate-300/70 dark:border-ink-700/60 bg-paper-dim/40 dark:bg-ink-800/40 p-3">
      <h3 className="mb-2 text-xs font-medium text-slate-600 dark:text-slate-300">{document.filename}</h3>
      {error ? (
        <p role="alert" className="rounded border border-brick-600/20 bg-brick-100 px-4 py-3 text-sm text-brick-600">
          {error}
        </p>
      ) : !source ? (
        <p className="py-8 text-center text-sm text-slate-500 dark:text-slate-400">Loading original document…</p>
      ) : document.mime_type === "application/pdf" ? (
        <iframe
          title={`Original document: ${document.filename}`}
          src={source}
          className="h-[70vh] min-h-96 w-full rounded border border-slate-300 dark:border-ink-700 bg-white"
        />
      ) : (
        <div className="flex max-h-[70vh] justify-center overflow-auto rounded border border-slate-300 dark:border-ink-700 bg-white p-2">
          <img src={source} alt={`Original document: ${document.filename}`} className="h-auto max-w-full object-contain" />
        </div>
      )}
    </section>
  );
}

function formatFindingValue(value: unknown): string {
  if (typeof value === "string") {
    try {
      return formatFindingValue(JSON.parse(value) as unknown);
    } catch {
      return value;
    }
  }
  if (value == null) return "—";
  if (Array.isArray(value)) {
    return value.map((item) => `• ${formatFindingValue(item)}`).join("\n");
  }
  if (typeof value === "object") {
    return Object.entries(value).map(([key, item]) =>
      `${formatFieldName(key)}: ${formatFindingValue(item)}`
    ).join("\n");
  }
  return String(value);
}

function DeadlinesTab({ analysis, onEvidence }: { analysis: DocumentAnalysis; onEvidence: (e: Evidence) => void }) {
  const reportSection = findReportSection(analysis, "Deadlines");
  if (reportSection) return <StructuredReportSection section={reportSection} />;
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
  const reportSection = findReportSection(analysis, "Obligations / Action Items");
  if (reportSection) return <StructuredReportSection section={reportSection} />;
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
  const reportSection = findReportSection(analysis, "Financial Information");
  if (reportSection) return <StructuredReportSection section={reportSection} table />;
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
  const reportSection = findReportSection(analysis, "Anomalies / Inconsistencies / Missing Information");
  if (reportSection) {
    return (
      <div className="space-y-4">
        <StructuredReportSection section={reportSection} />
        {analysis.anomalies.length > 0 && (
          <section>
            <h3 className="mb-2 text-sm font-semibold text-ink-800 dark:text-paper">Detected checks</h3>
            <AnomalyFindings anomalies={analysis.anomalies} />
          </section>
        )}
      </div>
    );
  }
  return <AnomalyFindings anomalies={analysis.anomalies} />;
}

function AnomalyFindings({ anomalies }: { anomalies: DocumentAnalysis["anomalies"] }) {
  if (anomalies.length === 0) {
    return (
      <div className="border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900 py-12 text-center">
        <ShieldCheck size={22} className="mx-auto mb-2 text-verdigris-600" strokeWidth={1.5} />
        <p className="text-sm text-slate-500 dark:text-slate-400">No anomalies detected.</p>
      </div>
    );
  }
  return (
    <div className="space-y-2">
      {anomalies.map((a) => {
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

function findReportSection(analysis: DocumentAnalysis, heading: string): SummarySection | undefined {
  if (typeof analysis.summary === "string" || !analysis.summary) return undefined;
  const expectedHeading = heading.toLowerCase();
  return analysis.summary.sections.find((section) =>
    section.heading.replace(/^\d+\.\s*/, "").trim().toLowerCase() === expectedHeading
  );
}

function StructuredReportSection({
  section,
  table = false,
}: {
  section: SummarySection;
  table?: boolean;
}) {
  return (
    <section className="border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900">
      <h2 className="px-5 py-3 text-sm font-semibold text-ink-800 dark:text-paper border-b border-slate-300/70 dark:border-ink-700/60">
        {section.heading.replace(/^\d+\.\s*/, "")}
      </h2>
      {section.items.length === 0 ? (
        <p className="px-5 py-4 text-sm text-slate-500 dark:text-slate-400">
          No information was extracted for this section.
        </p>
      ) : table ? (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-paper-dim/60 dark:bg-ink-800/60 text-xs text-slate-500 dark:text-slate-400">
              <tr>
                <th className="px-5 py-2 font-medium">Item</th>
                <th className="px-5 py-2 font-medium">Document-stated value</th>
                <th className="px-5 py-2 font-medium">Source / classification</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-300/40 dark:divide-ink-700/50">
              {section.items.map((item, index) => (
                <tr key={`${item.label}-${index}`} className="align-top">
                  <td className="px-5 py-3 font-medium text-ink-800 dark:text-paper">{item.label}</td>
                  <td className="px-5 py-3 whitespace-pre-wrap text-ink-700 dark:text-slate-200">{item.value}</td>
                  <td className="px-5 py-3 text-xs text-slate-500 dark:text-slate-400">
                    <span className="font-medium">{item.source_type.replace("_", " ")}</span>
                    {item.source_location && <p className="mt-1">{item.source_location}</p>}
                    {item.evidence && <p className="mt-1 italic">“{item.evidence}”</p>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="divide-y divide-slate-300/40 dark:divide-ink-700/50">
          {section.items.map((item, index) => (
            <article key={`${item.label}-${index}`} className="px-5 py-3">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <h3 className="text-sm font-medium text-ink-800 dark:text-paper">{item.label}</h3>
                <span className="text-xs text-slate-500 dark:text-slate-400">
                  {item.source_type.replace("_", " ")}
                  {item.source_location ? ` · ${item.source_location}` : ""}
                </span>
              </div>
              <p className="mt-1 text-sm leading-6 text-ink-700 dark:text-slate-200 whitespace-pre-wrap break-words">
                {item.value}
              </p>
              {item.evidence && (
                <blockquote className="mt-2 border-l-2 border-verdigris-500/50 pl-3 text-xs leading-5 text-slate-500 dark:text-slate-400">
                  “{item.evidence}”
                </blockquote>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
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
                m.role === "user"
                  ? "bg-ink-900 text-paper"
                  : "bg-paper-dim text-ink-900 dark:bg-ink-800 dark:text-paper"
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
          className="flex-1 border border-slate-300 dark:border-ink-700 rounded bg-white dark:bg-ink-800 px-3 py-2 text-sm text-ink-900 dark:text-paper placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-verdigris-500/40 focus:border-verdigris-500 disabled:bg-paper-dim dark:disabled:bg-ink-800"
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
