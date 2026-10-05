"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutGrid, FileStack, AlertTriangle, Settings as SettingsIcon,
  LogOut, ScrollText, Sun, Moon,
} from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { useTheme } from "@/lib/theme-context";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutGrid },
  { href: "/documents", label: "Documents", icon: FileStack },
  { href: "/alerts", label: "Alerts", icon: AlertTriangle },
  { href: "/settings", label: "Settings", icon: SettingsIcon },
];

function ThemeToggle({ className }: { className?: string }) {
  const { theme, toggleTheme } = useTheme();
  return (
    <button
      onClick={toggleTheme}
      aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
      className={className}
    >
      {theme === "dark" ? <Sun size={16} strokeWidth={1.75} /> : <Moon size={16} strokeWidth={1.75} />}
    </button>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen bg-paper dark:bg-ink-950 text-ink-900 dark:text-paper">
      {/* Desktop left rail */}
      <aside className="hidden md:flex fixed inset-y-0 left-0 w-60 flex-col border-r border-slate-300/60 dark:border-ink-700/60 bg-paper dark:bg-ink-950">
        <div className="px-6 py-6 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ScrollText size={20} className="text-verdigris-600 dark:text-verdigris-500" strokeWidth={1.75} />
            <span className="font-serif text-sm tracking-tight">AI Report Analyzer</span>
          </div>
          <ThemeToggle className="text-slate-400 hover:text-ink-700 dark:hover:text-paper transition-colors" />
        </div>
        <nav className="flex-1 px-3 space-y-0.5">
          {NAV_ITEMS.map((item) => {
            const active = pathname?.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 px-3 py-2 rounded text-sm transition-colors",
                  active
                    ? "bg-ink-900 text-paper dark:bg-paper dark:text-ink-950"
                    : "text-ink-700 dark:text-slate-300 hover:bg-paper-dim dark:hover:bg-ink-800"
                )}
              >
                <Icon size={16} strokeWidth={1.75} />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="px-3 py-4 border-t border-slate-300/60 dark:border-ink-700/60">
          <div className="px-3 py-2 text-xs text-slate-500 dark:text-slate-400 truncate">{user?.email}</div>
          <button
            onClick={logout}
            className="w-full flex items-center gap-3 px-3 py-2 rounded text-sm text-ink-700 dark:text-slate-300 hover:bg-paper-dim dark:hover:bg-ink-800 transition-colors"
          >
            <LogOut size={16} strokeWidth={1.75} />
            Sign out
          </button>
        </div>
      </aside>

      {/* Mobile top bar */}
      <header className="md:hidden sticky top-0 z-20 flex items-center justify-between px-4 py-3 bg-paper dark:bg-ink-950 border-b border-slate-300/60 dark:border-ink-700/60">
        <div className="flex items-center gap-2">
          <ScrollText size={18} className="text-verdigris-600 dark:text-verdigris-500" strokeWidth={1.75} />
          <span className="font-serif text-sm">AI Report Analyzer</span>
        </div>
        <div className="flex items-center gap-3">
          <ThemeToggle className="text-slate-500 dark:text-slate-400" />
          <button onClick={logout} className="text-slate-500 dark:text-slate-400">
            <LogOut size={18} strokeWidth={1.75} />
          </button>
        </div>
      </header>

      <main className="md:pl-60 pb-20 md:pb-0">
        <div className="max-w-6xl mx-auto px-4 md:px-8 py-6 md:py-10">{children}</div>
      </main>

      {/* Mobile bottom nav */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 z-20 bg-paper dark:bg-ink-950 border-t border-slate-300/60 dark:border-ink-700/60 flex justify-around py-2">
        {NAV_ITEMS.map((item) => {
          const active = pathname?.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex flex-col items-center gap-1 px-3 py-1 text-[11px]",
                active ? "text-ink-900 dark:text-paper" : "text-slate-500 dark:text-slate-400"
              )}
            >
              <Icon size={19} strokeWidth={1.75} />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
