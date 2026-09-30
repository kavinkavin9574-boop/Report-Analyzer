import { cn, statusLabel } from "@/lib/utils";

export function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    completed: "bg-verdigris-100 text-verdigris-600 dark:bg-verdigris-600/20 dark:text-verdigris-500",
    failed: "bg-brick-100 text-brick-600 dark:bg-brick-600/20 dark:text-brick-600",
    uploaded: "bg-paper-dim text-slate-500 dark:bg-ink-800 dark:text-slate-400",
    cancelled: "bg-paper-dim text-slate-500 dark:bg-ink-800 dark:text-slate-400",
  };
  const style = styles[status] || "bg-amber-100 text-amber-600 dark:bg-amber-600/20 dark:text-amber-600";

  return (
    <span className={cn("inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs", style)}>
      {!["completed", "failed", "cancelled"].includes(status) && (
        <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
      )}
      {statusLabel(status)}
    </span>
  );
}
