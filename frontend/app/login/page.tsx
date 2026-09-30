"use client";

import { useState, FormEvent } from "react";
import { ScrollText } from "lucide-react";
import { useAuth } from "@/lib/auth-context";

export default function LoginPage() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { login, register } = useAuth();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await register(name, email, password);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex bg-paper dark:bg-ink-950">
      {/* Left: editorial panel, hidden on mobile */}
      <div className="hidden lg:flex lg:w-1/2 bg-ink-950 dark:bg-ink-900 text-paper flex-col justify-between p-12">
        <div className="flex items-center gap-2">
          <ScrollText size={22} strokeWidth={1.5} />
          <span className="font-serif text-xl">Ledger</span>
        </div>
        <div className="max-w-md">
          <p className="font-serif text-3xl leading-snug">
            Every figure your AI reports, traced back to the exact line it came from.
          </p>
          <p className="mt-4 text-sm text-slate-300 dark:text-slate-400 leading-relaxed">
            Upload invoices, contracts, and financial reports. Ledger extracts the
            numbers, flags what's inconsistent, and shows you the source page for
            every claim it makes.
          </p>
        </div>
        <p className="text-xs text-slate-400 dark:text-slate-500">Built for finance, legal, and compliance teams.</p>
      </div>

      {/* Right: form */}
      <div className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-2 mb-8">
            <ScrollText size={20} className="text-verdigris-600" strokeWidth={1.75} />
            <span className="font-serif text-lg">Ledger</span>
          </div>

          <h1 className="font-serif text-2xl mb-1 text-ink-900 dark:text-paper">
            {mode === "login" ? "Welcome back" : "Create your account"}
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mb-8">
            {mode === "login" ? "Sign in to continue to your documents." : "Start analyzing documents in minutes."}
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === "register" && (
              <div>
                <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1.5">Full name</label>
                <input
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full border border-slate-300 dark:border-ink-700 rounded px-3 py-2 text-sm bg-white dark:bg-ink-900 text-ink-900 dark:text-paper focus:outline-none focus:ring-2 focus:ring-verdigris-500/40 focus:border-verdigris-500"
                  placeholder="Kavin"
                />
              </div>
            )}
            <div>
              <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1.5">Email</label>
              <input
                required
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full border border-slate-300 dark:border-ink-700 rounded px-3 py-2 text-sm bg-white dark:bg-ink-900 text-ink-900 dark:text-paper focus:outline-none focus:ring-2 focus:ring-verdigris-500/40 focus:border-verdigris-500"
                placeholder="you@company.com"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1.5">Password</label>
              <input
                required
                type="password"
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full border border-slate-300 dark:border-ink-700 rounded px-3 py-2 text-sm bg-white dark:bg-ink-900 text-ink-900 dark:text-paper focus:outline-none focus:ring-2 focus:ring-verdigris-500/40 focus:border-verdigris-500"
                placeholder="••••••••"
              />
            </div>

            {error && (
              <p className="text-sm text-brick-600 bg-brick-100 dark:bg-brick-600/15 border border-brick-600/20 rounded px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full bg-ink-900 dark:bg-verdigris-600 text-paper rounded py-2.5 text-sm font-medium hover:bg-ink-800 dark:hover:bg-verdigris-500 transition-colors disabled:opacity-60"
            >
              {submitting ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
            </button>
          </form>

          <p className="mt-6 text-sm text-slate-500 dark:text-slate-400 text-center">
            {mode === "login" ? "New here?" : "Already have an account?"}{" "}
            <button
              onClick={() => setMode(mode === "login" ? "register" : "login")}
              className="text-verdigris-600 hover:underline"
            >
              {mode === "login" ? "Create an account" : "Sign in"}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
