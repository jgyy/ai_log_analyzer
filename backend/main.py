from fastapi import FastAPI, Depends, HTTPException, status, Path
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta  # ← Added timedelta
import uuid
import os


from database import get_db, User, Organization, LogAnalysis, AuditLog
from schemas import (
    UserCreate, UserLogin, Token, UserResponse,
    OrganizationCreate, OrganizationResponse,
    LogAnalysisRequest, LogAnalysisResponse, AnalysisResult
)
from ai_service import AIService
from log_processor import preprocess_logs
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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
        role="admin" if is_first_user else user.role,  # ← Auto-promote first user
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
    db: Session = Depends(get_db)  # ← Proper FastAPI dependency
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

# @app.get("/api/org/{org_id}", response_model=OrganizationResponse)
# def get_organization(
#     org_id: str = Path(...),
#     current_user: UserResponse = Depends(get_current_user),
#     db: Session = Depends(get_db)
# ):
#     print(f"3. Entered /api/org/{org_id}")
#     # 🔐 Org-level access check
#     if current_user.organization_id != org_id:
#         raise HTTPException(status_code=403, detail="Access denied to this organization")
    
#     org = db.query(Organization).filter(Organization.id == org_id).first()
#     if not org:
#         raise HTTPException(status_code=404, detail="Organization not found")
#     return org

# @app.get("/api/org/{org_id}/users", response_model=List[UserResponse])
# def list_organization_users(
#     org_id: str = Path(...),
#     current_user: UserResponse = Depends(get_current_user),
#     db: Session = Depends(get_db)
# ):
#     print(f"2. Entered /api/org/{org_id}/users")
#     # 🔐 Admin or same-org check
#     if current_user.organization_id != org_id and current_user.role != "admin":
#         raise HTTPException(status_code=403, detail="Access denied")
        
#     users = db.query(User).filter(User.organization_id == org_id).all()
#     orgs = {o.id: o for o in db.query(Organization).all()}
    
#     return [
#         UserResponse(
#             id=u.id, email=u.email, full_name=u.full_name, role=u.role,
#             organization_id=u.organization_id,
#             organization_name=orgs[u.organization_id].name if u.organization_id in orgs else "Unknown"
#         ) for u in users
#     ]

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
    print(f"1. /org/users - user: {current_user}; db: {db}")
    """List all users in the current user's organization"""
    users = db.query(User).filter(User.organization_id == current_user.organization_id).all()
    print(f"users: {users}")
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
    role_update: dict,
    current_user: UserResponse = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    """Update user role (admin only)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Can only modify users from your organization")
    
    new_role = role_update.get("role")
    if new_role not in ["admin", "sre", "viewer"]:
        raise HTTPException(status_code=400, detail="Invalid role")
    
    user.role = new_role
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

# ============ HEALTH CHECK ============
@app.get("/health")
def health():
    return {"status": "healthy", "version": "1.0.0"}