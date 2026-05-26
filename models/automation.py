"""
Automation Models for CloudForms-like Request/Approval Workflows
Supports provisioning requests, multi-tier approvals, and background task tracking
"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from functions.base import Base


class RequestStatus(enum.Enum):
    """Provisioning request lifecycle states"""
    PENDING = 'pending'
    APPROVED = 'approved'
    DENIED = 'denied'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class RequestType(enum.Enum):
    """Types of provisioning requests"""
    DEPLOYMENT = 'deployment'
    SERVICE_CATALOG = 'service_catalog'
    SCALING = 'scaling'
    RETIREMENT = 'retirement'
    RECONFIGURATION = 'reconfiguration'


class ProvisioningRequest(Base):
    """
    CloudForms-style provisioning request for Kubernetes resources
    Tracks deployment requests from submission through approval to execution
    """
    __tablename__ = 'provisioning_requests'

    id = Column(Integer, primary_key=True)
    request_type = Column(SQLEnum(RequestType), nullable=False)
    status = Column(SQLEnum(RequestStatus), default=RequestStatus.PENDING, nullable=False)

    # Requester information
    requester_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    cluster_id = Column(Integer, ForeignKey('clusters.id'), nullable=False)

    # Request details (stored as JSON for flexibility)
    request_data = Column(JSON, nullable=False)  # Deployment spec, catalog params, etc.
    namespace = Column(String(100))
    resource_name = Column(String(255))

    # Approval tracking
    requires_approval = Column(Boolean, default=True)
    approval_state = Column(String(50), default='pending_approval')  # 'pending_approval', 'approved', 'denied'

    # Execution
    task_id = Column(Integer, ForeignKey('background_tasks.id'))
    result_data = Column(JSON)  # Created resource IDs, errors, etc.
    error_message = Column(Text)

    # Lifecycle timestamps
    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    approved_at = Column(DateTime)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    # Relationships
    requester = relationship('User', foreign_keys=[requester_id])
    cluster = relationship('Cluster')
    approvals = relationship('ApprovalRecord', back_populates='request', cascade='all, delete-orphan')
    task = relationship('BackgroundTask', foreign_keys=[task_id])

    def __repr__(self):
        return f'<ProvisioningRequest id={self.id} type={self.request_type.value} status={self.status.value}>'


class ApprovalDecision(enum.Enum):
    """Approval decision states"""
    PENDING = 'pending'
    APPROVED = 'approved'
    DENIED = 'denied'


class ApprovalRecord(Base):
    """
    Multi-tier approval chain tracking
    Supports sequential approval workflows (tier 1 → tier 2 → tier 3)
    """
    __tablename__ = 'approval_records'

    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, ForeignKey('provisioning_requests.id'), nullable=False)

    # Approval tier (1 = first approval, 2 = second, etc.)
    tier = Column(Integer, default=1, nullable=False)
    approver_role = Column(String(50))  # 'admin', 'cluster_admin', 'namespace_admin'

    # Decision
    approver_id = Column(Integer, ForeignKey('users.id'))
    decision = Column(SQLEnum(ApprovalDecision), default=ApprovalDecision.PENDING, nullable=False)
    comments = Column(Text)
    decided_at = Column(DateTime)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    request = relationship('ProvisioningRequest', back_populates='approvals')
    approver = relationship('User')

    def __repr__(self):
        return f'<ApprovalRecord id={self.id} tier={self.tier} decision={self.decision.value}>'


class TaskStatus(enum.Enum):
    """Background task execution states"""
    QUEUED = 'queued'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class BackgroundTask(Base):
    """
    APScheduler job tracking for asynchronous operations
    Stores task state, parameters, and results
    """
    __tablename__ = 'background_tasks'

    id = Column(Integer, primary_key=True)
    task_name = Column(String(255), nullable=False)
    task_type = Column(String(100))  # 'deployment', 'metrics_collection', 'cleanup', 'retirement_scan'

    status = Column(SQLEnum(TaskStatus), default=TaskStatus.QUEUED, nullable=False)

    # Execution parameters
    cluster_id = Column(Integer, ForeignKey('clusters.id'))
    parameters = Column(JSON)  # Task-specific parameters

    # Scheduling
    scheduled_at = Column(DateTime)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    # Results
    result = Column(JSON)
    error_message = Column(Text)

    # APScheduler job ID for tracking
    scheduler_job_id = Column(String(255))

    # Relationships
    cluster = relationship('Cluster')

    def __repr__(self):
        return f'<BackgroundTask id={self.id} type={self.task_type} status={self.status.value}>'
