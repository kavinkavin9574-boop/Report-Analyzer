import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

export function StatCard({
  label, value, icon: Icon, tone = "neutral",
}: {
  label: string;
  value: string | number;
  icon: LucideIcon;
  tone?: "neutral" | "warning" | "critical" | "positive";
}) {
  const toneClasses: Record<string, string> = {
    neutral: "text-ink-900 dark:text-paper",
    positive: "text-verdigris-600 dark:text-verdigris-500",
    warning: "text-amber-600",
    critical: "text-brick-600",
  };

  return (
    <div className="border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900 px-5 py-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-slate-500 dark:text-slate-400">{label}</span>
        <Icon size={15} strokeWidth={1.75} className="text-slate-400 dark:text-slate-500" />
      </div>
      <div className={cn("font-serif text-2xl", toneClasses[tone])}>{value}</div>
    </div>
  );
}
