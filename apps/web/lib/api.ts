export type Rule = {
  code: string;
  label: string;
  status: "PASS" | "FAIL" | "REVIEW";
  explanation: string;
  evidence_document_ids: string[];
};

export type DocumentRecord = {
  id: string;
  expected_category: string;
  category: string | null;
  filename: string;
  media_type: string;
  page_count: number;
  sha256?: string;
  status: string;
  processing_provider?: string;
  extracted_data: Record<string, string | null>;
  patient_summary: Record<string, string>;
  evidence: Array<{ evidence_id: string; page: number; text: string; bbox?: number[] }>;
  quality_warnings: string[];
  error?: string;
};

export type CaseRecord = {
  id: string;
  reference: string;
  patient_name: string;
  patient_email: string;
  id_last4: string;
  appointment_type: string;
  appointment_date?: string;
  visit_reason: string;
  document_requirement: "yes" | "no" | "unsure";
  identity_source: "manual" | "singpass_demo";
  clinic_id: string;
  status: string;
  rules: Rule[];
  ai_provider?: string;
  check_in_confirmations: Record<string, boolean>;
  queue_number?: string;
  queue_status: string;
  room_assignment?: string;
  queue_updated_at?: string;
  created_at: string;
  updated_at: string;
  documents?: DocumentRecord[];
  access_url?: string;
};

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    credentials: "include",
    headers: init?.body instanceof FormData ? init.headers : { "content-type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const problem = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof problem.detail === "string" ? problem.detail : JSON.stringify(problem.detail));
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export function prettyStatus(status: string) {
  return status.toLowerCase().split("_").map((part) => part[0].toUpperCase() + part.slice(1)).join(" ");
}

const VISIT_REASON_LABELS: Record<string, string> = {
  gp_consultation: "GP consultation",
  corporate_insurer_screening: "Corporate or insurer health screening",
  occupational_health_screening: "Occupational health screening",
  employer_insurer_medical_exam: "Employer or insurer medical examination",
  healthier_sg_periodic_checkup: "Healthier SG or periodic check-up",
  other_unsure: "Other or not sure",
};

export function visitReasonLabel(reason: string) {
  return VISIT_REASON_LABELS[reason] || prettyStatus(reason);
}

export function documentRequirementLabel(requirement: string) {
  if (requirement === "yes") return "Yes, I have relevant documents";
  if (requirement === "no") return "No documents needed";
  return "Not sure - clinic to confirm";
}

export function documentCategoryLabel(category?: string | null) {
  return category && category !== "unknown" ? prettyStatus(category) : "Identifying document";
}

export function queueStatusLabel(status: string) {
  const labels: Record<string, string> = {
    NOT_ISSUED: "Not issued",
    WAITING_FOR_REVIEW: "Waiting for clinic review",
    PROCEED_TO_REGISTRATION: "Proceed now",
    CALLED_TO_ROOM: "You are being called",
  };
  return labels[status] || prettyStatus(status);
}
