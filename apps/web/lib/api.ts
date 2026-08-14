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
  scan_status: string;
  processing_provider?: string;
  extracted_data: Record<string, string | null>;
  patient_summary: Record<string, string>;
  evidence: Array<{ evidence_id: string; page: number; text: string; bbox?: number[] }>;
  quality_warnings: string[];
  error?: string;
};

export type FieldAssertion = {
  id: string;
  field_name: string;
  raw_value?: string;
  normalized_value?: string;
  original_normalized_value?: string;
  document_id: string;
  page?: number;
  evidence_ids: string[];
  bounding_boxes: number[][];
  extraction_provider: string;
  support_status: "SUPPORTED" | "UNSUPPORTED" | "CONFLICTING" | "STAFF_CORRECTED";
  validation_errors: string[];
  correction?: { id: string; reason: string; actor_user_id: string; created_at: string };
};

export type Finding = {
  id: string;
  code: string;
  status: "PASS" | "FAIL" | "REVIEW";
  critical: boolean;
  explanation: string;
  evidence_assertion_ids: string[];
  reference_record_ids: string[];
  override?: { reason: string; actor_role: string; created_at: string };
};

export type Evaluation = {
  id: string;
  ruleset_version: string;
  reference_data_version: string;
  input_hash: string;
  evaluated_at: string;
  outcome: "PROVISIONALLY_ELIGIBLE" | "REVIEW_REQUIRED" | "BLOCKED";
  stale: boolean;
  findings: Finding[];
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
  requested_services: string[];
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
  assertions?: FieldAssertion[];
  evaluation?: Evaluation;
  profile?: Record<string, unknown>;
  questionnaires?: Array<{ type: string; definition_version: string; responses: Record<string, unknown>; confirmed_prefill_fields: string[] }>;
  attestations?: Array<{ type: string; actor_user_id: string; attested_at: string }>;
  access_url?: string;
  bootstrap_code?: string;
};

function csrfToken() {
  if (typeof document === "undefined") return undefined;
  const value = document.cookie.split("; ").find((item) => item.startsWith("cp_csrf="));
  return value ? decodeURIComponent(value.split("=", 2)[1]) : undefined;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const csrf = csrfToken();
  const headers = new Headers(init?.headers);
  if (!(init?.body instanceof FormData)) headers.set("content-type", "application/json");
  if (csrf && init?.method && !["GET", "HEAD"].includes(init.method.toUpperCase())) headers.set("x-csrf-token", csrf);
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    credentials: "include",
    headers,
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
