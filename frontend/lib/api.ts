import type {
  User, Document, DocumentAnalysis, DashboardStats,
} from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("docai_token");
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.body && !(options.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers as Record<string, string> | undefined),
  };

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    let detail = "Something went wrong. Please try again.";
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // ignore parse failure, use default message
    }
    throw new Error(detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  async register(name: string, email: string, password: string) {
    return request<{ access_token: string; user: User }>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ name, email, password }),
    });
  },

  async login(email: string, password: string) {
    return request<{ access_token: string; user: User }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },

  async me() {
    return request<User>("/api/auth/me");
  },

  async uploadDocument(file: File) {
    const form = new FormData();
    form.append("file", file);
    return request<Document>("/api/documents/upload", { method: "POST", body: form });
  },

  async listDocuments() {
    return request<Document[]>("/api/documents");
  },

  async getDocument(id: number) {
    return request<Document>(`/api/documents/${id}`);
  },

  async getAnalysis(id: number) {
    return request<DocumentAnalysis>(`/api/documents/${id}/analysis`);
  },

  async reanalyze(id: number) {
    return request<{ detail: string }>(`/api/documents/${id}/analyze`, { method: "POST" });
  },

  async cancelDocument(id: number) {
    return request<{ detail: string; status: string }>(`/api/documents/${id}/cancel`, { method: "POST" });
  },

  async deleteDocument(id: number) {
    return request<{ detail: string }>(`/api/documents/${id}`, { method: "DELETE" });
  },

  async getDashboardStats() {
    return request<DashboardStats>("/api/dashboard/stats");
  },

  async chat(documentId: number, question: string) {
    return request<{ answer: string; evidence: { page_number: number; source_text: string } | null }>(
      `/api/documents/${documentId}/chat`,
      { method: "POST", body: JSON.stringify({ question }) }
    );
  },

  async getPage(documentId: number, pageNumber: number) {
    return request<{ page_number: number; raw_text: string; image_path: string }>(
      `/api/documents/${documentId}/pages/${pageNumber}`
    );
  },

  async getAIModelSettings() {
    return request<{
      ai_provider: string;
      default_model: string;
      fast_model: string;
      reasoning_model: string;
      api_key_configured: boolean;
    }>("/api/settings/ai-models");
  },

  async updateAIModelSettings(payload: {
    ai_provider?: string;
    default_model?: string;
    fast_model?: string;
    reasoning_model?: string;
    api_key?: string;
  }) {
    return request<{
      ai_provider: string;
      default_model: string;
      fast_model: string;
      reasoning_model: string;
      api_key_configured: boolean;
    }>("/api/settings/ai-models", { method: "PUT", body: JSON.stringify(payload) });
  },

  async removeApiKey() {
    return request<{
      ai_provider: string;
      default_model: string;
      fast_model: string;
      reasoning_model: string;
      api_key_configured: boolean;
    }>("/api/settings/ai-models/api-key", { method: "DELETE" });
  },
};

export function setToken(token: string) {
  window.localStorage.setItem("docai_token", token);
}

export function clearToken() {
  window.localStorage.removeItem("docai_token");
}
