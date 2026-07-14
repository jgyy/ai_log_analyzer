from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta
import uuid
import os


from database import get_db, User, Organization, LogAnalysis, AuditLog, VMCredential
from schemas import (
    UserCreate, UserLogin, Token, UserResponse, UserRoleUpdate,
    OrganizationCreate, OrganizationResponse,
    LogAnalysisRequest, LogAnalysisResponse, AnalysisResult,
    IncidentAnalysisRequest, IncidentAnalysisResponse, ActionExecutionResponse,
    ActionExecutionRequest, VMInfo, VMCredentialCreate, VMCredentialStatus, ActionType
)
from ai_service import AIService
from log_processor import preprocess_logs
from connectors import collect_sources
from connectors_vm import list_vms as vboxmanage_list_vms, get_vm_info
from crypto_utils import encrypt_value, CredentialEncryptionError
from actions import execute_allowlisted_action, find_action
from auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, require_role,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from dotenv import load_dotenv
import logging

logging.basicConfig(
    level = logging.INFO,
    format = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI(title="DevOps AI Analyzer - Enterprise")

# Allowed CORS origins are configurable via the CORS_ORIGINS env var
# (comma-separated), so the frontend's deployed URL (e.g. Vercel) can talk to
# this backend without code changes. Defaults to the local Next.js dev server
# so `uvicorn main:app --reload` keeps working out of the box.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ai = AIService()

# ============ AUTH ENDPOINTS ============
@app.post("/api/auth/register", response_model=UserResponse)
def register(user: UserCreate, db: Session = Depends(get_db)):
    # Check if user exists
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create org if not provided
    is_new_org = not user.organization_id
    if is_new_org:
        org_id = str(uuid.uuid4())
        org = Organization(
            id=org_id,
            name=f"{user.full_name}'s Organization",
            slug=f"org-{org_id[:8]}"
        )
        db.add(org)
        db.commit()
        user.organization_id = org_id

    # First user in an organization becomes its admin
    org_user_count = db.query(User).filter(User.organization_id == user.organization_id).count()
    is_first_user = is_new_org or org_user_count == 0

    # Create user - FIRST USER IS AUTO-ADMIN
    user_id = str(uuid.uuid4())
    db_user = User(
        id=user_id,
        email=user.email,
        hashed_password=hash_password(user.password),
        full_name=user.full_name,
        role="admin" if is_first_user else user.role,  
        organization_id=user.organization_id
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Audit log
    audit = AuditLog(
        organization_id=user.organization_id,
        user_id=user_id,
        action="USER_REGISTERED",
        resource_type="user",
        resource_id=user_id,
        details=f"First user: {is_first_user}, Role: {db_user.role}"
    )
    db.add(audit)
    db.commit()
    
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    return UserResponse(
        id=db_user.id,
        email=db_user.email,
        full_name=db_user.full_name,
        role=db_user.role,
        organization_id=db_user.organization_id,
        organization_name=org.name if org else "Unknown"
    )

@app.post("/api/auth/login", response_model=Token)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    access_token = create_access_token(
        data={"sub": user.id},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            organization_id=user.organization_id,
            organization_name=org.name if org else "Unknown"
        )
    )

@app.get("/api/auth/me", response_model=UserResponse)
def get_me(current_user: UserResponse = Depends(get_current_user)):
    return current_user

# ============ ORGANIZATION ENDPOINTS ============
@app.post("/api/org", response_model=OrganizationResponse)
def create_organization(
    org: OrganizationCreate,
    current_user: UserResponse = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)  
):
    org_id = str(uuid.uuid4())
    
    db_org = Organization(
        id=org_id,
        name=org.name,
        slug=org.slug
    )
    
    # Update current user's org
    user = db.query(User).filter(User.id == current_user.id).first()
    user.organization_id = org_id
    
    db.add(db_org)
    db.commit()
    db.refresh(db_org)
    
    return OrganizationResponse(
        id=db_org.id,
        name=db_org.name,
        slug=db_org.slug,
        created_at=db_org.created_at,
        is_active=db_org.is_active
    )

# ============ LOG ANALYSIS ENDPOINTS ============
@app.post("/api/analyze", response_model=LogAnalysisResponse)
async def analyze_logs(
    request: LogAnalysisRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    logger.info("Analyze request received")
    if current_user.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewers cannot run analysis")
    
    analysis_id = str(uuid.uuid4())
    db_analysis = LogAnalysis(
        id=analysis_id,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        domain=request.domain,
        logs_preview=request.logs[:1000],
        status="processing"
    )
    db.add(db_analysis)
    db.commit()
    
    logger.info(f"db_analysis: {db_analysis} for id: {analysis_id}")
    try:
        cleaned = preprocess_logs(request.logs)
        logger.info(f"cleaned_logs: {cleaned}")
        
        result = await ai.analyze_logs(cleaned, request.domain)
        
        logger.info(f"ai_analysis: {result}")
        db_analysis.status = "completed"
        db_analysis.analysis_result = result.model_dump_json()
        db.commit()
        
        # Audit log
        audit = AuditLog(
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            action="LOG_ANALYSIS_COMPLETED",
            resource_type="log_analysis",
            resource_id=analysis_id,
            details=f"Domain: {request.domain}"
        )
        db.add(audit)
        db.commit()
        
        logger.info(f"audit: {audit}")
        return LogAnalysisResponse(
            id=analysis_id,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            domain=request.domain,
            created_at=db_analysis.created_at,
            status="completed",
            result=result
        )
    except Exception as e:
        logger.exception(f"error: {e}")
        db_analysis.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/incidents/analyze", response_model=IncidentAnalysisResponse)
async def analyze_incident(
    request: IncidentAnalysisRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    logger.info("Incident analyze request received")
    if current_user.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewers cannot run analysis")

    if not request.sources:
        raise HTTPException(status_code=400, detail="Select at least one source")

    analysis_id = str(uuid.uuid4())
    db_analysis = LogAnalysis(
        id=analysis_id,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        domain=request.domain,
        logs_preview=(request.logs or "")[:1000],
        status="processing"
    )
    db.add(db_analysis)
    db.commit()

    try:
        collected = collect_sources(request.sources, request.logs,
                    vm_targets=request.vm_targets,
                    db=db,
                    organization_id=current_user.organization_id)
        result = await ai.analyze_incident(collected, request.domain)

        db_analysis.status = "completed"
        db_analysis.analysis_result = result.model_dump_json()
        db.commit()

        audit = AuditLog(
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            action="INCIDENT_ANALYSIS_COMPLETED",
            resource_type="log_analysis",
            resource_id=analysis_id,
            details=f"Domain: {request.domain}, Sources: {[source.value for source in request.sources]}"
        )
        db.add(audit)
        db.commit()

        return IncidentAnalysisResponse(
            id=analysis_id,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            domain=request.domain,
            created_at=db_analysis.created_at,
            status="completed",
            result=result
        )
    except Exception as e:
        logger.exception(f"incident analysis error: {e}")
        db_analysis.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/actions/{action_id}/execute", response_model=ActionExecutionResponse)
def execute_action(
    action_id: str,
    request: ActionExecutionRequest = ActionExecutionRequest(),
    current_user: UserResponse = Depends(require_role(["admin", "sre"])),
    db: Session = Depends(get_db)
):
    analyses = db.query(LogAnalysis).filter(
        LogAnalysis.organization_id == current_user.organization_id,
        LogAnalysis.analysis_result.isnot(None)
    ).order_by(LogAnalysis.created_at.desc()).limit(50).all()

    matched_action = None
    matched_analysis = None
    for analysis in analyses:
        try:
            result = AnalysisResult.model_validate_json(analysis.analysis_result)
        except Exception:
            continue
        matched_action = find_action(action_id, result.recommended_actions)
        if matched_action:
            matched_analysis = analysis
            break

    if not matched_action:
        raise HTTPException(status_code=404, detail="Allowlisted action not found for this organization")
    # Destructive/VM lifecycle actions get an extra, fresh existence check
    # right before execution — a matched action could reference a VM that
    # was since renamed or deleted since the analysis that produced it.
    vm_action_types = {
        ActionType.START_VM, ActionType.STOP_VM,
        ActionType.RESTART_VM, ActionType.RESTORE_VM_SNAPSHOT,
    }
    if matched_action.action_type in vm_action_types:
        if get_vm_info(matched_action.target) is None:
            raise HTTPException(status_code=404, detail=f"VM '{matched_action.target}' no longer exists on this host")

    execution = execute_allowlisted_action(matched_action)
    audit = AuditLog(
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action="REMEDIATION_ACTION_EXECUTED",
        resource_type="log_analysis",
        resource_id=matched_analysis.id if matched_analysis else None,
        details=(
            f"Action: {matched_action.id}, Type: {matched_action.action_type}, "
            f"Target: {matched_action.target}, Status: {execution.status}"
        )
    )
    db.add(audit)
    db.commit()
    return execution

@app.get("/api/analyses", response_model=List[LogAnalysisResponse])
def list_analyses(
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    analyses = db.query(LogAnalysis).filter(
        LogAnalysis.organization_id == current_user.organization_id
    ).order_by(LogAnalysis.created_at.desc()).limit(50).all()
    
    return [
        LogAnalysisResponse(
            id=a.id,
            organization_id=a.organization_id,
            user_id=a.user_id,
            domain=a.domain,
            created_at=a.created_at,
            status=a.status,
            result=AnalysisResult.model_validate_json(a.analysis_result) if a.analysis_result else None
        )
        for a in analyses
    ]

@app.get("/api/org/users", response_model=List[UserResponse])
def list_org_users(
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all users in the current user's organization"""
    users = db.query(User).filter(User.organization_id == current_user.organization_id).all()
    return [
        UserResponse(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            role=u.role,
            organization_id=u.organization_id,
            organization_name=current_user.organization_name,
            is_active=u.is_active,
            last_login=u.last_login
        )
        for u in users
    ]

@app.delete("/api/users/{user_id}")
def delete_user(
    user_id: str,
    current_user: UserResponse = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    """Delete a user (admin only)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Can only delete users from your organization")
    
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    db.delete(user)
    db.commit()
    
    return {"message": "User deleted successfully"}

@app.put("/api/users/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: str,
    role_update: UserRoleUpdate,
    current_user: UserResponse = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    """Update user role (admin only)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Can only modify users from your organization")

    user.role = role_update.role.value
    db.commit()
    db.refresh(user)
    
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        organization_id=user.organization_id,
        organization_name=org.name if org else "Unknown"
    )

@app.get("/api/analyses/{analysis_id}", response_model=LogAnalysisResponse)
def get_analysis_by_id(
    analysis_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get specific analysis by ID"""
    analysis = db.query(LogAnalysis).filter(
        LogAnalysis.id == analysis_id,
        LogAnalysis.organization_id == current_user.organization_id
    ).first()
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    return LogAnalysisResponse(
        id=analysis.id,
        organization_id=analysis.organization_id,
        user_id=analysis.user_id,
        domain=analysis.domain,
        created_at=analysis.created_at,
        status=analysis.status,
        result=AnalysisResult.model_validate_json(analysis.analysis_result) if analysis.analysis_result else None
    )

@app.post("/api/users", response_model=UserResponse)
def create_user(
    user_data: UserCreate,
    current_user: UserResponse = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    """Admin creates a new user in their organization"""
    
    # Check if email exists
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_user_id = str(uuid.uuid4())
    
    # Create user in the Admin's organization
    new_user = User(
        id=new_user_id,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name,
        role=user_data.role,
        organization_id=current_user.organization_id  # Force same org
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return UserResponse(
        id=new_user.id,
        email=new_user.email,
        full_name=new_user.full_name,
        role=new_user.role,
        organization_id=new_user.organization_id,
        organization_name=current_user.organization_name
    )


@app.get("/api/vms", response_model=List[VMInfo])
def list_vms(
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List VirtualBox VMs registered on this host, with credential status per org."""
    vms = []
    for entry in vboxmanage_list_vms():
        info = get_vm_info(entry["name"]) or {}
        has_cred = db.query(VMCredential).filter(
            VMCredential.organization_id == current_user.organization_id,
            VMCredential.vm_name == entry["name"],
        ).first() is not None
        vms.append(VMInfo(
            name=entry["name"],
            uuid=entry.get("uuid", info.get("uuid", "")),
            state=info.get("state", entry.get("state", "unknown")),
            guest_additions_running=info.get("guest_additions_running", False),
            has_credentials=has_cred,
            snapshot_count=info.get("snapshot_count", 0),
        ))
    return vms
 
@app.post("/api/vms/{vm_name}/credentials", response_model=VMCredentialStatus)
def set_vm_credentials(
    vm_name: str,
    credentials: VMCredentialCreate,
    current_user: UserResponse = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    """
    Register (or replace) diagnostic-only guest OS credentials for a VM.
    Credentials are encrypted at rest and never returned in plaintext by
    any endpoint. Use a low-privilege account scoped to read-only
    diagnostics — not a full admin/root guest account.
    """
    try:
        encrypted_username = encrypt_value(credentials.username)
        encrypted_password = encrypt_value(credentials.password)
    except CredentialEncryptionError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
 
    existing = db.query(VMCredential).filter(
        VMCredential.organization_id == current_user.organization_id,
        VMCredential.vm_name == vm_name,
    ).first()
 
    if existing:
        existing.encrypted_username = encrypted_username
        existing.encrypted_password = encrypted_password
        existing.created_by_user_id = current_user.id
        existing.created_at = datetime.utcnow()
        record = existing
    else:
        record = VMCredential(
            id=str(uuid.uuid4()),
            organization_id=current_user.organization_id,
            vm_name=vm_name,
            encrypted_username=encrypted_username,
            encrypted_password=encrypted_password,
            created_by_user_id=current_user.id,
        )
        db.add(record)
 
    db.commit()
    db.refresh(record)
 
    audit = AuditLog(
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action="VM_CREDENTIALS_SET",
        resource_type="vm_credential",
        resource_id=record.id,
        details=f"VM: {vm_name}",
    )
    db.add(audit)
    db.commit()
 
    return VMCredentialStatus(vm_name=vm_name, configured=True, created_at=record.created_at)
 
@app.delete("/api/vms/{vm_name}/credentials")
def delete_vm_credentials(
    vm_name: str,
    current_user: UserResponse = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    """Remove diagnostic credentials for a VM (admin only)."""
    existing = db.query(VMCredential).filter(
        VMCredential.organization_id == current_user.organization_id,
        VMCredential.vm_name == vm_name,
    ).first()
    if not existing:
        raise HTTPException(status_code=404, detail="No credentials configured for this VM")
 
    db.delete(existing)
    db.commit()
 
    audit = AuditLog(
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action="VM_CREDENTIALS_DELETED",
        resource_type="vm_credential",
        resource_id=None,
        details=f"VM: {vm_name}",
    )
    db.add(audit)
    db.commit()
 
    return {"message": "Credentials removed"}

# ============ HEALTH CHECK ============
@app.get("/health")
def health():
    return {"status": "healthy", "version": "1.0.0"}
