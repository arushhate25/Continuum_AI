// Mirrors the backend JSON (backend/app/core/permissions.py, handover.py, service.py).

export type Role = "admin" | "reviewer" | "leaver" | "successor";

export const ROLES: { value: Role; label: string; blurb: string }[] = [
  { value: "reviewer", label: "Reviewer", blurb: "Reviews claims and approves the handover. Can read restricted evidence." },
  { value: "admin", label: "Admin", blurb: "Loads sources and runs extraction. Can read restricted evidence." },
  { value: "leaver", label: "Leaver", blurb: "The person leaving. Sees claims, but restricted evidence is hidden." },
  { value: "successor", label: "Successor", blurb: "The incoming person. Sees only the approved handover, with redactions." },
];

export const STAFF: Role[] = ["admin", "reviewer"];
export const isStaff = (r: Role): boolean => STAFF.includes(r);
export const isRole = (v: unknown): v is Role =>
  v === "admin" || v === "reviewer" || v === "leaver" || v === "successor";

export type ClaimStatus = "Verified" | "Inferred" | "Conflicting" | "Missing";
export type ReviewState = "draft" | "approved" | "rejected";

export interface EvidenceView {
  source_id: string | null;
  quote: string | null;
  timestamp: string | null;
  match_kind: string | null;
  redacted: boolean;
}

export interface ClaimView {
  id: string;
  type: string;
  statement: string | null;
  status: ClaimStatus;
  confidence: number;
  evidence: EvidenceView[];
  review_state: ReviewState;
  version: number;
  conflicts_with: string[];
  redacted: boolean;
  placeholder: string | null;
  notes: string[];
}

export interface Source {
  id: string;
  kind: string;
  title: string | null;
  author: string;
  timestamp: string;
  text: string;
  access_label: "public" | "internal" | "restricted";
  url: string | null;
}

export interface Readiness {
  total: number;
  approved: number;
  verified: number;
  unresolved?: number;
  score: number;
}

export interface Handover {
  role: Role;
  decisions: ClaimView[];
  ownership: ClaimView[];
  risks: ClaimView[];
  dependencies: ClaimView[];
  unfinished_work: ClaimView[];
  open_questions: ClaimView[];
  day1: string[];
  week1: string[];
  readiness: Readiness;
}

export interface StatusInfo {
  project: string | null;
  sources: number;
  claims: number;
  approved: number;
  rejected: number;
  by_status: Record<string, number>;
  extraction_provider: string | null;
  extracted_at: string | null;
}

export interface ClaimDetail {
  claim: ClaimView;
  versions: { version?: number; statement?: string; review_state?: string; snapshot_at?: string }[];
}

export interface AuditEntry {
  ts: string;
  action: string;
  role: string;
  detail: Record<string, unknown>;
}

export interface Metrics {
  citation_precision: number;
  claims: number;
  restricted_sources: number;
  restricted_leaks_by_role: Record<string, string[]>;
  note: string;
}
