"use client";

import { useEffect, useState } from "react";
import { Sun, Moon, Check } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { useRequireAuth } from "@/lib/use-require-auth";
import { useTheme } from "@/lib/theme-context";
import { api } from "@/lib/api";

const MODEL_SUGGESTIONS: Record<string, string[]> = {
  openai: ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano", "o4-mini", "o3"],
  nvidia: ["nvidia/nemotron-3.5-lightning-30b-a3b", "deepseek-ai/deepseek-v4-pro-0813", "moonshotai/kimi-k3"],
  openrouter: ["openai/gpt-4o-mini", "anthropic/claude-3.7-sonnet", "google/gemini-2.5-flash"],
};

interface AIModelSettings {
  ai_provider: string;
  default_model: string;
  fast_model: string;
  reasoning_model: string;
  api_key_configured: boolean;
}

export default function SettingsPage() {
  const { user, loading } = useRequireAuth();
  const { theme, setTheme } = useTheme();

  const [aiSettings, setAiSettings] = useState<AIModelSettings | null>(null);
  const [form, setForm] = useState({ ai_provider: "openai", default_model: "", fast_model: "", reasoning_model: "" });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [saveError, setSaveError] = useState("");
  const [ocrEnabled, setOcrEnabled] = useState(true);
  const [autoAnalyze, setAutoAnalyze] = useState(true);

  useEffect(() => {
    if (!user) return;
    api
      .getAIModelSettings()
      .then((data) => {
        setAiSettings(data);
        setForm({
          ai_provider: data.ai_provider,
          default_model: data.default_model,
          fast_model: data.fast_model,
          reasoning_model: data.reasoning_model,
        });
      })
      .catch(() => {});
  }, [user]);

  async function saveAiSettings() {
    setSaving(true);
    setSaved(false);
    setSaveError("");
    try {
      const key = apiKey.trim();
      const data = await api.updateAIModelSettings({
        ...form,
        ...(key ? { api_key: key } : {}),
      });
      setAiSettings(data);
      if (key) setApiKey("");
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : "Unable to save AI settings.");
    } finally {
      setSaving(false);
    }
  }

  async function removeApiKey() {
    setSaving(true);
    setSaved(false);
    setSaveError("");
    try {
      const data = await api.removeApiKey();
      setAiSettings(data);
      setApiKey("");
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : "Unable to remove the API key.");
    } finally {
      setSaving(false);
    }
  }

  function selectProvider(provider: string) {
    const model = provider === "nvidia"
      ? "nvidia/nemotron-3.5-lightning-30b-a3b"
      : provider === "openrouter"
        ? "openai/gpt-4o-mini"
        : "gpt-4o-mini";
    setForm((current) => ({
      ...current,
      ai_provider: provider,
      default_model: model,
      fast_model: model,
      reasoning_model: model,
    }));
  }

  if (loading || !user) return null;

  return (
    <AppShell>
      <h1 className="font-serif text-2xl mb-1">Settings</h1>
      <p className="text-sm text-slate-500 dark:text-slate-400 mb-8">
        Manage your account, appearance, and how documents are processed.
      </p>

      <div className="space-y-6 max-w-xl">
        <section className="border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900 p-5">
          <h2 className="text-sm font-medium mb-4">Account</h2>
          <div className="space-y-3 text-sm">
            <Row label="Name" value={user.name} />
            <Row label="Email" value={user.email} />
            <Row label="Role" value={user.role} />
          </div>
        </section>

        <section className="border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900 p-5">
          <h2 className="text-sm font-medium mb-4">Appearance</h2>
          <div className="flex gap-2">
            <ThemeOption icon={Sun} label="Light" active={theme === "light"} onClick={() => setTheme("light")} />
            <ThemeOption icon={Moon} label="Dark" active={theme === "dark"} onClick={() => setTheme("dark")} />
          </div>
        </section>

        <section className="border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900 p-5">
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-sm font-medium">AI model</h2>
            {aiSettings && (
              <span
                className={`text-xs px-2 py-0.5 rounded ${
                  aiSettings.api_key_configured
                    ? "bg-verdigris-100 dark:bg-verdigris-600/20 text-verdigris-600 dark:text-verdigris-500"
                    : "bg-amber-100 dark:bg-amber-600/20 text-amber-600"
                }`}
              >
                {aiSettings.api_key_configured ? "API key configured" : "No API key set"}
              </span>
            )}
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
            Select the provider that issued your key. Switching providers clears the current key; the replacement
            stays in backend memory and is never stored in the database or returned to the browser.
            {aiSettings && !aiSettings.api_key_configured && (
              <>
                {" "}Document analysis needs a key for the selected provider.
              </>
            )}
          </p>

          <div className="space-y-4">
            <div>
              <label htmlFor="ai-provider" className="block text-xs text-slate-500 dark:text-slate-400 mb-1.5">
                Provider
              </label>
              <select
                id="ai-provider"
                value={form.ai_provider}
                onChange={(event) => selectProvider(event.target.value)}
                className="w-full border border-slate-300 dark:border-ink-700 rounded px-3 py-2 text-sm bg-white dark:bg-ink-900 text-ink-900 dark:text-paper focus:outline-none focus:ring-2 focus:ring-verdigris-500/40 focus:border-verdigris-500"
              >
                <option value="openai">OpenAI</option>
                <option value="nvidia">NVIDIA</option>
                <option value="openrouter">OpenRouter</option>
              </select>
            </div>
            <div>
              <label htmlFor="provider-api-key" className="block text-xs text-slate-500 dark:text-slate-400 mb-1.5">
                {form.ai_provider === "nvidia"
                  ? "NVIDIA API key"
                  : form.ai_provider === "openrouter"
                    ? "OpenRouter API key"
                    : "OpenAI API key"}
              </label>
              <input
                id="provider-api-key"
                type="password"
                autoComplete="new-password"
                spellCheck={false}
                value={apiKey}
                onChange={(event) => {
                  const value = event.target.value;
                  setApiKey(value);
                  if (value.startsWith("nvapi-") && form.ai_provider !== "nvidia") selectProvider("nvidia");
                  if (value.startsWith("sk-or-v1-") && form.ai_provider !== "openrouter") {
                    selectProvider("openrouter");
                  } else if (value.startsWith("sk-") && form.ai_provider !== "openai") {
                    selectProvider("openai");
                  }
                }}
                className="w-full border border-slate-300 dark:border-ink-700 rounded px-3 py-2 text-sm bg-white dark:bg-ink-900 text-ink-900 dark:text-paper focus:outline-none focus:ring-2 focus:ring-verdigris-500/40 focus:border-verdigris-500"
              />
              <button
                type="button"
                onClick={removeApiKey}
                disabled={saving || !aiSettings?.api_key_configured}
                className="mt-2 text-xs text-slate-500 dark:text-slate-400 underline underline-offset-2 hover:text-ink-900 dark:hover:text-paper disabled:opacity-60"
              >
                Remove API key
              </button>
            </div>
            <ModelField
              label="Default model"
              hint="Used for extraction and summarization"
              value={form.default_model}
              suggestions={MODEL_SUGGESTIONS[form.ai_provider] || MODEL_SUGGESTIONS.openai}
              onChange={(v) => setForm((f) => ({ ...f, default_model: v }))}
            />
            <ModelField
              label="Fast model"
              hint="Used for classification"
              value={form.fast_model}
              suggestions={MODEL_SUGGESTIONS[form.ai_provider] || MODEL_SUGGESTIONS.openai}
              onChange={(v) => setForm((f) => ({ ...f, fast_model: v }))}
            />
            <ModelField
              label="Reasoning model"
              hint="Used for anomaly detection and complex analysis"
              value={form.reasoning_model}
              suggestions={MODEL_SUGGESTIONS[form.ai_provider] || MODEL_SUGGESTIONS.openai}
              onChange={(v) => setForm((f) => ({ ...f, reasoning_model: v }))}
            />

            <div className="flex items-center gap-3 pt-1">
              <button
                onClick={saveAiSettings}
                disabled={saving}
                className="bg-ink-900 dark:bg-verdigris-600 text-paper text-sm px-4 py-2 rounded hover:bg-ink-800 dark:hover:bg-verdigris-500 transition-colors disabled:opacity-60"
              >
                {saving ? "Saving…" : "Save AI settings"}
              </button>
              {saved && (
                <span className="flex items-center gap-1 text-xs text-verdigris-600 dark:text-verdigris-500">
                  <Check size={14} /> Saved
                </span>
              )}
            </div>
            {saveError && <p role="alert" className="text-xs text-brick-600">{saveError}</p>}
          </div>
        </section>

        <section className="border border-slate-300/70 dark:border-ink-700/60 rounded bg-white dark:bg-ink-900 p-5">
          <h2 className="text-sm font-medium mb-4">Processing</h2>
          <ToggleRow label="OCR for scanned documents" checked={ocrEnabled} onChange={setOcrEnabled} />
          <ToggleRow label="Automatically analyze on upload" checked={autoAnalyze} onChange={setAutoAnalyze} />
        </section>
      </div>
    </AppShell>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-slate-500 dark:text-slate-400">{label}</span>
      <span>{value}</span>
    </div>
  );
}

function ThemeOption({
  icon: Icon, label, active, onClick,
}: { icon: typeof Sun; label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`flex-1 flex flex-col items-center gap-1.5 py-3 rounded border text-xs transition-colors ${
        active
          ? "border-verdigris-600 bg-verdigris-100 dark:bg-verdigris-600/20 text-verdigris-600 dark:text-verdigris-500"
          : "border-slate-300 dark:border-ink-700 text-slate-500 dark:text-slate-400 hover:bg-paper-dim dark:hover:bg-ink-800"
      }`}
    >
      <Icon size={16} strokeWidth={1.75} />
      {label}
    </button>
  );
}

function ModelField({
  label, hint, value, suggestions, onChange,
}: { label: string; hint: string; value: string; suggestions: string[]; onChange: (v: string) => void }) {
  const listId = `${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-models`;
  return (
    <div>
      <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1.5">
        {label} <span className="text-slate-400 dark:text-slate-500">— {hint}</span>
      </label>
      <input
        list={listId}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full border border-slate-300 dark:border-ink-700 rounded px-3 py-2 text-sm bg-white dark:bg-ink-900 text-ink-900 dark:text-paper focus:outline-none focus:ring-2 focus:ring-verdigris-500/40 focus:border-verdigris-500"
      />
      <datalist id={listId}>
        {suggestions.map((m) => (
          <option key={m} value={m} />
        ))}
      </datalist>
    </div>
  );
}

function ToggleRow({
  label, checked, onChange,
}: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-center justify-between py-2">
      <span className="text-sm">{label}</span>
      <button
        onClick={() => onChange(!checked)}
        className={`w-10 h-6 rounded-full transition-colors relative ${
          checked ? "bg-verdigris-600" : "bg-slate-300 dark:bg-ink-700"
        }`}
      >
        <span
          className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
            checked ? "translate-x-4" : "translate-x-0.5"
          }`}
        />
      </button>
    </div>
  );
}
