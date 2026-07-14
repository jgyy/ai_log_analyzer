from sqlalchemy import create_engine, Column, String, DateTime, ForeignKey, Boolean, Text, Integer, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./devops_ai.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Organization(Base):
    __tablename__ = "organizations"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    users = relationship("User", back_populates="organization")
    logs = relationship("LogAnalysis", back_populates="organization")

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(String(20), nullable=False)  # admin, sre, viewer
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    
    organization = relationship("Organization", back_populates="users")

class LogAnalysis(Base):
    __tablename__ = "log_analyses"
    
    id = Column(String(36), primary_key=True)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    domain = Column(String(50), nullable=False)
    logs_preview = Column(Text)
    analysis_result = Column(Text)  # JSON string
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    status = Column(String(20), default="completed")  # pending, completed, failed
    
    organization = relationship("Organization", back_populates="logs")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(String(36), ForeignKey("organizations.id"))
    user_id = Column(String(36), ForeignKey("users.id"))
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50))
    resource_id = Column(String(36))
    details = Column(Text)
    ip_address = Column(String(45))
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

class VMCredential(Base):
    """
    Diagnostic-only guest OS credentials for a VirtualBox VM, used to run
    read-only checks via `VBoxManage guestcontrol` when a VM's network/
    display stack is too broken to reach any other way.
 
    Username/password are stored encrypted (see crypto_utils.py) — never
    stored or returned in plaintext. Scoped per-organization: one set of
    credentials per (organization_id, vm_name).
    """
    __tablename__ = "vm_credentials"
 
    id = Column(String(36), primary_key=True)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    vm_name = Column(String(255), nullable=False, index=True)
    encrypted_username = Column(Text, nullable=False)
    encrypted_password = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by_user_id = Column(String(36), ForeignKey("users.id"))
 
    __table_args__ = (
        UniqueConstraint("organization_id", "vm_name", name="uq_vm_credential_org_vm"),
    )

class RemoteTarget(Base):
    """
    A generic, reusable connection profile for a remote/external log source
    reachable over SSH — a bare-metal host, a cloud VM, a network device,
    etc. This is deliberately generic (host/port/username/auth_method +
    an encrypted secret) so future remote source types beyond SSH can
    reuse the same table by adding a new auth_method rather than a new
    model.

    The secret (password, or SSH private key contents when
    auth_method="ssh_key") is stored encrypted at rest via crypto_utils —
    never in plaintext, never returned by any endpoint.
    """
    __tablename__ = "remote_targets"

    id = Column(String(36), primary_key=True)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False, index=True)
    host = Column(String(255), nullable=False)
    port = Column(Integer, default=22)
    username = Column(String(255), nullable=False)
    auth_method = Column(String(20), nullable=False, default="password")  # password | ssh_key
    encrypted_secret = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by_user_id = Column(String(36), ForeignKey("users.id"))

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_remote_target_org_name"),
    )

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()