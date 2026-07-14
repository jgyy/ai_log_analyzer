export type ConnectorType = "manual" | "linux" | "docker" | "virtualbox" | "remote";
export type RemoteAuthMethod = "password" | "ssh_key";
export type Severity = "healthy" | "info" | "warning" | "critical";
export type ActionType = 
    "restart_docker_container"
    | "start_docker_container" 
    | "stop_docker_container" 
    | "restart_systemd_service"
    | "start_vm"
    | "stop_vm"
    | "restart_vm"
    | "restore_vm_snapshot"
    | "restart_gdm_service";

export type BusinessRiskLevel = "Low" | "Medium" | "High" | "Critical";

export interface MitigationStep { title: string; description: string; command_or_action: string }
export interface ImmediateMitigation { prepare: MitigationStep[], pre_validate: MitigationStep[], apply: MitigationStep[], post_validate: MitigationStep[] }

export interface AnalysisDiagrams {
  timeline_flowchart: string;
  root_cause_diagram: string;
  mitigation_flowchart: string;
}

export interface SourceSummary {
  source: ConnectorType;
  status: Severity;
  collected: boolean;
  message: string;
  item_count: number;
}

export interface AffectedComponent {
  name: string;
  source: ConnectorType;
  status: Severity;
  impact: string;
  evidence_refs: string[];
}

export interface CollectedEvidence {
  id: string;
  source: ConnectorType;
  component: string;
  severity: Severity;
  timestamp?: string | null;
  message: string;
  metadata: Array<{ key: string; value: string }>;
}

export interface VisualSummary {
  headline: string;
  likely_failure_path: string[];
  plain_english_summary: string;
  business_impact: string;
  fix_summary: string;
}

export interface BusinessSummary {
  incident_title: string;
  what_happened: string;
  business_impact: string;
  risk_level: BusinessRiskLevel;
  affected_service: string;
  recommended_next_step: string;
}

export interface ExecutableAction {
  id: string;
  label: string;
  action_type: ActionType;
  target: string;
  risk_level: string;
  preconditions: string[];
  source: ConnectorType;
}

export interface MessageResponse {
  message: string;
  evidence_ids: string[];
}

export interface AnalysisResult {
  investigation_timeline: { 
    start: MessageResponse; 
    symptom: MessageResponse; 
    observation: MessageResponse; 
    finding: MessageResponse; 
    root_cause: MessageResponse; 
  }
  root_cause: { investigation_summary: string; impact: string; root_causes: string[]; hypotheses: string[]; key_findings: string[]; investigation_gaps: string[] }
  mitigation_plan: { summary: string; immediate_mitigation: ImmediateMitigation; rollback_steps: string[]; agent_spec_ready: string[] }
  business_summary: BusinessSummary;
  diagrams?: AnalysisDiagrams
  source_summary: SourceSummary[];
  affected_components: AffectedComponent[];
  severity: Severity;
  confidence: number;
  evidence: CollectedEvidence[];
  visual_summary: VisualSummary;
  recommended_actions: ExecutableAction[];
}

export interface VMInfo {
  name: string;
  uuid: string;
  state: string;
  guest_additions_running: boolean;
  has_credentials: boolean;
  snapshot_count: number;
}

export interface RemoteTargetInfo {
  name: string;
  host: string;
  port: number;
  username: string;
  auth_method: RemoteAuthMethod;
  configured: boolean;
  created_at?: string | null;
}
