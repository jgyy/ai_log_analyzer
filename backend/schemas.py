from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    SRE = "sre"
    VIEWER = "viewer"

# Auth Schemas
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: UserRole = UserRole.VIEWER
    organization_id: Optional[str] = None

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

class AnalysisResult(BaseModel):
    investigation_timeline: InvestigationTimeline
    root_cause: RootCauseSection
    mitigation_plan: MitigationPlan
    diagrams: Optional[AnalysisDiagrams] = None

class LogAnalysisRequest(BaseModel):
    logs: str
    domain: str = "kubernetes"

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