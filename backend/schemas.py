from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    SRE = "sre"
    VIEWER = "viewer"

class ConnectorType(str, Enum):
    MANUAL = "manual"
    LINUX = "linux"
    DOCKER = "docker"

class Severity(str, Enum):
    HEALTHY = "healthy"
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

class ActionType(str, Enum):
    RESTART_DOCKER_CONTAINER = "restart_docker_container"
    START_DOCKER_CONTAINER = "start_docker_container"
    STOP_DOCKER_CONTAINER = "stop_docker_container"
    RESTART_SYSTEMD_SERVICE = "restart_systemd_service"

# Auth Schemas
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: UserRole = UserRole.VIEWER
    organization_id: Optional[str] = None

class UserRoleUpdate(BaseModel):
    role: UserRole

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: "UserResponse"

class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: UserRole
    organization_id: str
    organization_name: str
    is_active: bool = True
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Organization Schemas
class OrganizationCreate(BaseModel):
    name: str
    slug: str

class OrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    created_at: datetime
    is_active: bool
    
    class Config:
        from_attributes = True

# Log Analysis Schemas (existing, adding org_id)
class InvestigationTimeline(BaseModel):
    start: str
    symptom: str
    observation: str
    finding: str
    root_cause: str

class RootCauseSection(BaseModel):
    investigation_summary: str
    impact: str
    root_causes: List[str]
    hypotheses: List[str]
    key_findings: List[str]
    investigation_gaps: List[str]

class MitigationStep(BaseModel):
    title: str
    description: str
    command_or_action: str

class ImmediateMitigation(BaseModel):
    prepare: List[MitigationStep]
    pre_validate: List[MitigationStep]
    apply: List[MitigationStep]
    post_validate: List[MitigationStep]

class MitigationPlan(BaseModel):
    summary: str
    immediate_mitigation: ImmediateMitigation
    rollback_steps: List[str]
    agent_spec_ready: List[str]

class AnalysisDiagrams(BaseModel):
    timeline_flowchart: str
    root_cause_diagram: str
    mitigation_flowchart: str
    
class SourceSummary(BaseModel):
    source: ConnectorType
    status: Severity = Severity.INFO
    collected: bool = True
    message: str = ""
    item_count: int = 0

class AffectedComponent(BaseModel):
    name: str
    source: ConnectorType
    status: Severity = Severity.INFO
    impact: str = ""
    evidence_refs: List[str] = Field(default_factory=list)

class EvidenceMetadata(BaseModel):
    key: str
    value: str

class CollectedEvidence(BaseModel):
    id: str
    source: ConnectorType
    component: str
    severity: Severity = Severity.INFO
    timestamp: Optional[str] = None
    message: str
    metadata: List[EvidenceMetadata] = Field(default_factory=list)

class VisualSummary(BaseModel):
    headline: str = "Infrastructure analysis completed"
    likely_failure_path: List[str] = Field(default_factory=list)
    plain_english_summary: str = ""
    business_impact: str = ""
    fix_summary: str = ""

class ExecutableAction(BaseModel):
    id: str
    label: str
    action_type: ActionType
    target: str
    risk_level: str = "medium"
    preconditions: List[str] = Field(default_factory=list)
    source: ConnectorType

class ActionExecutionResponse(BaseModel):
    action_id: str
    status: str
    output: str = ""
    error: str = ""

class AnalysisResult(BaseModel):
    investigation_timeline: InvestigationTimeline
    root_cause: RootCauseSection
    mitigation_plan: MitigationPlan
    diagrams: Optional[AnalysisDiagrams] = None
    source_summary: List[SourceSummary] = Field(default_factory=list)
    affected_components: List[AffectedComponent] = Field(default_factory=list)
    severity: Severity = Severity.INFO
    confidence: float = Field(default=0.5, ge=0, le=1)
    evidence: List[CollectedEvidence] = Field(default_factory=list)
    visual_summary: VisualSummary = Field(default_factory=VisualSummary)
    recommended_actions: List[ExecutableAction] = Field(default_factory=list)

class LogAnalysisRequest(BaseModel):
    logs: str
    domain: str = "kubernetes"

class IncidentAnalysisRequest(BaseModel):
    sources: List[ConnectorType] = Field(default_factory=lambda: [ConnectorType.MANUAL])
    logs: Optional[str] = None
    domain: str = "infrastructure"

class LogAnalysisResponse(BaseModel):
    id: str
    organization_id: str
    user_id: str
    domain: str
    created_at: datetime
    status: str
    result: Optional[AnalysisResult] = None
    
    class Config:
        from_attributes = True

class IncidentAnalysisResponse(LogAnalysisResponse):
    pass
