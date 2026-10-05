export interface User {
  id: number;
  name: string;
  email: string;
  role: string;
}

export interface Document {
  id: number;
  filename: string;
  mime_type: string;
  document_type: string;
  status: string;
  page_count: number;
  file_size: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface Evidence {
  id: number;
  page_number: number;
  section: string | null;
  source_text: string;
  bbox: number[] | null;
}

export interface Finding {
  id: number;
  category: string;
  field_name: string;
  field_value: string | null;
  confidence: number;
  source: string;
  evidence: Evidence | null;
}

export interface Deadline {
  id: number;
  event: string;
  value: string | null;
  absolute_date: string | null;
  confidence: number;
  evidence: Evidence | null;
}

export interface Obligation {
  id: number;
  responsible_party: string | null;
  action: string;
  frequency: string | null;
  deadline: string | null;
  condition: string | null;
  consequence: string | null;
  confidence: number;
  evidence: Evidence | null;
}

export interface FinancialValue {
  id: number;
  label: string;
  value: number | null;
  currency: string | null;
  is_calculated: boolean;
  evidence: Evidence | null;
}

export interface Anomaly {
  id: number;
  title: string;
  severity: "low" | "medium" | "high" | "critical";
  description: string | null;
  detection_type: "rule" | "ai";
  pages: number[] | null;
  confidence: number;
}

export interface MissingData {
  id: number;
  field_name: string;
  description: string | null;
}

export interface StructuredSummary {
  text: string;
  key_points: string[];
}

export interface DocumentAnalysis {
  document: Document;
  summary: StructuredSummary | string | null;
  extracted_fields: Record<string, string | number | boolean | null>;
  report_text: string;
  model_used: string | null;
  findings: Finding[];
  deadlines: Deadline[];
  obligations: Obligation[];
  financial_values: FinancialValue[];
  anomalies: Anomaly[];
  missing_data: MissingData[];
}

export interface DashboardStats {
  documents_analyzed: number;
  critical_issues: number;
  warnings: number;
  upcoming_deadlines: number;
  missing_data_count: number;
  total_financial_value: number;
  documents_by_type: Record<string, number>;
  findings_by_severity: Record<string, number>;
}
