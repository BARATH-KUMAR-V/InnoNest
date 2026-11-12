export type Role = "applicant" | "underwriter" | "policy_admin" | "auditor";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  phone: string | null;
}

export interface Applicant {
  id: number;
  role: string;
  full_name: string;
  dob: string;
  pan: string;
  phone: string;
  email: string;
  address: string;
  city: string;
  employment_type: string;
  employer: string;
  years_in_job: number;
  monthly_income: number;
  other_income: number;
  existing_emi: number;
  business_type: string | null;
  annual_turnover: number | null;
  annual_itr_income: number | null;
}

export interface Application {
  id: number;
  reference: string;
  product: "HOME_LOAN" | "LAP";
  status: string;
  pending_stage: string | null;
  loan_amount: number;
  interest_rate: number;
  tenure_months: number;
  purpose: string;
  end_use: string | null;
  policy_key: string;
  property_type: string;
  property_city: string;
  property_address: string;
  property_pincode: string;
  property_area_sqft: number;
  survey_no: string;
  declared_value: number;
  seller_name: string | null;
  owner_name: string | null;
  existing_mortgage_amount: number;
  consents: Record<string, boolean>;
  submitted_at: string | null;
  decided_at: string | null;
  expires_at: string | null;
  created_at: string;
  applicants: Applicant[];
}

export interface ApplicationRow {
  id: number;
  reference: string;
  product: string;
  status: string;
  loan_amount: number;
  property_city: string;
  policy_key: string;
  submitted_at: string | null;
  decided_at: string | null;
  created_at: string;
  applicant_name: string | null;
  employment_type: string | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface ChecklistItem {
  key: string;
  kind: string;
  status: string;
  title: string;
  message: string;
  doc_type: string | null;
  applicant_id: number | null;
  applicant_name: string | null;
  document_id: number | null;
  evidence?: Record<string, unknown>;
}

export interface Checklist {
  complete: boolean;
  open_count: number;
  total: number;
  items: ChecklistItem[];
}

export interface DocRequest {
  id: number;
  kind: string;
  item_key: string;
  title: string;
  message: string;
  status: string;
  response: string | null;
  due_at: string | null;
  reminders_sent: number;
  last_reminded_at: string | null;
  created_at: string;
  fulfilled_at: string | null;
}

export interface Finding {
  id: string;
  severity: string;
  text: string;
  evidence: unknown;
}

export interface DocumentRecord {
  id: number;
  applicant_id: number | null;
  doc_type: string;
  detected_type: string | null;
  original_name: string;
  size_bytes: number;
  sha256: string;
  status: string;
  extraction_status: string;
  confidence: number | null;
  findings: Finding[];
  page_count: number;
  ocr_used: boolean;
  uploaded_at: string;
}

export interface FieldRecord {
  id: number;
  name: string;
  value: string;
  numeric_value: number | null;
  confidence: number;
  corrected_value: string | null;
  effective_value: string;
}

export interface NotificationRecord {
  id: number;
  application_id: number | null;
  channel: string;
  kind: string;
  subject: string;
  body: string;
  delivery_status: string;
  simulated: boolean;
  recipient: string | null;
  read_at: string | null;
  created_at: string;
}

export interface Check {
  id: number;
  applicant_id: number | null;
  category: string;
  code: string;
  title: string;
  status: string;
  detail: string;
  evidence: Record<string, any>;
  disposition: string | null;
  disposition_note: string | null;
}

export interface ProviderCall {
  id: number;
  applicant_id: number | null;
  provider: string;
  provider_name: string;
  mode: string;
  integration_status: string;
  response_status: string;
  consent_ref: string | null;
  source_ref: string | null;
  verification_result: string;
  response: Record<string, any>;
  requested_at: string;
}

export interface ReasonCode {
  code: string;
  name: string;
  outcome: string;
  message: string;
  values: Record<string, unknown>;
}

export interface Decision {
  id: number;
  outcome: string;
  kind: string;
  decided_by: string;
  policy_key: string;
  policy_name: string;
  policy_version: number;
  ruleset_version: string;
  inputs: Record<string, any>;
  outputs: Record<string, any>;
  reason_codes: ReasonCode[];
  explanation: string;
  evidence_refs: { type: string; id: number }[];
  result_hash: string;
  review_note: string | null;
  created_at: string;
}

export interface Policy {
  id: number;
  key: string;
  name: string;
  version: number;
  status: string;
  description: string;
  params: Record<string, any>;
  change_note: string | null;
  created_by: string;
  created_at: string;
}

export interface AuditEvent {
  id: number;
  application_id: number | null;
  actor: string;
  actor_role: string;
  action: string;
  entity: string | null;
  details: Record<string, unknown>;
  hash: string;
  created_at: string;
}
