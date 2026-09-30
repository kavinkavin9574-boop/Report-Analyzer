import clsx, { ClassValue } from "clsx";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function severityColor(severity: string) {
  switch (severity) {
    case "critical":
      return {
        text: "text-brick-600",
        bg: "bg-brick-100 dark:bg-brick-600/20",
        dot: "bg-brick-600",
      };
    case "high":
      return {
        text: "text-brick-600",
        bg: "bg-brick-100 dark:bg-brick-600/20",
        dot: "bg-brick-600",
      };
    case "medium":
      return {
        text: "text-amber-600",
        bg: "bg-amber-100 dark:bg-amber-600/20",
        dot: "bg-amber-600",
      };
    default:
      return {
        text: "text-slate-500 dark:text-slate-400",
        bg: "bg-paper-dim dark:bg-ink-800",
        dot: "bg-slate-500",
      };
  }
}

export function statusLabel(status: string) {
  const map: Record<string, string> = {
    uploaded: "Uploaded",
    processing: "Processing",
    extracting_text: "Extracting text",
    analyzing: "Analyzing",
    validating: "Validating",
    completed: "Completed",
    failed: "Failed",
    cancelling: "Stopping",
    cancelled: "Cancelled",
  };
  return map[status] || status;
}

export function documentTypeLabel(type: string) {
  const map: Record<string, string> = {
    invoice: "Invoice",
    contract: "Contract",
    financial_report: "Financial Report",
    compliance: "Compliance Document",
    purchase_order: "Purchase Order",
    other: "Other",
  };
  return map[type] || type;
}

export function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export function formatFieldName(name: string) {
  return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatCurrency(value: number, currency = "USD") {
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(value);
  } catch {
    return `${currency} ${value.toFixed(2)}`;
  }
}
