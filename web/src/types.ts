import type { Thresholds } from "./rules";

export type Route = "APPROVE" | "SEND_TO_LEGAL" | "ESCALATE";
export type Tier = "ACCEPT" | "FLAG" | "REJECT";

export interface ClauseAssessment {
  rule_id: string;
  title: string;
  tier: Tier;
  score: number;
  score_parts: { base: number; adjustment: number };
  evidence: string[];
  present: boolean;
  spans: string[];
  redline: string;
  fallback: string;
}

export interface RedlineItem {
  rule_id: string;
  title: string;
  tier: Tier;
  score: number;
  evidence: string[];
  redline: string;
  fallback: string;
}

export interface ContractRow {
  contract_id: string;
  title: string;
  document_name: string | null;
  parties: string | null;
  agreement_date: string | null;
  effective_date: string | null;
  overall_score: number;
  route: Route;
  flag_count: number;
  reject_count: number;
  clauses: ClauseAssessment[];
  action: string;
  redline_draft: RedlineItem[];
  pending_approval: boolean;
}

export interface RuleTableRow {
  present: number;
  present_pct: number;
  accept: number;
  flag: number;
  reject: number;
  flag_rate: number;
}

export interface Summary {
  findings: {
    contract_count: number;
    routes: Record<string, number>;
    approve_pct: number;
    needs_legal_pct: number;
    rule_table: Record<string, RuleTableRow>;
    most_flagged_rule: string;
    most_flagged_count: number;
    uncapped_liability_contracts: number;
    uncapped_liability_pct: number;
    no_audit_rights_contracts: number;
    non_ontario_governing_law_contracts: number;
    low_or_unquantified_cap_contracts: number;
    total_clause_spans: number;
    assessed_playbook_spans: number;
    exception_spans: number;
    mean_overall_score: number;
    effort_minutes: number;
    effort_hours: number;
  };
  eval: {
    n: number;
    tier_accuracy: number;
    precision: number;
    recall: number;
  };
  eval_misses: { contract_id: string; rule_id: string; expected: string; got: string }[];
  config: {
    thresholds: Thresholds;
    route_bars: { escalate_score: number; legal_score: number };
    contract_score_weights: { max_clause: number; mean_clause: number };
    effort_minutes: Record<string, number>;
    replay_date: string;
    tuning_note?: string;
  };
  company: { name: string; profile: string; fictional: boolean };
  queue_meta: {
    source: string;
    source_url: string;
    license: string;
    citation: string;
    slice: string;
    clause_note: string;
    fetched_at: string;
    replay_date: string;
    count: number;
    span_count: number;
  };
  data_note: string;
}

export interface PlaybookRule {
  id: string;
  cuad_category: string;
  title: string;
  stance: string;
  redline: string;
  fallback: string;
  seeded: boolean;
}

export interface Playbook {
  rules: PlaybookRule[];
  categories: Record<string, string>;
}

export interface TestVector {
  contract_id: string;
  rule_id: string;
  term_spans: string[];
  notice_spans: string[];
  has_exception: boolean;
  expected_tier: Tier;
  expected_score: number;
}

export interface Stamp {
  repo: string;
  git_sha: string;
  built_utc: string;
  pipeline: string;
}

export interface RedlineDeskData {
  summary: Summary;
  contracts: ContractRow[];
  playbook: Playbook;
  vectors: { vectors: TestVector[] };
  stamp: Stamp | null;
}
