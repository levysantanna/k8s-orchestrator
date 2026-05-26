"""
Policy Models for Quota Management and Lifecycle Automation
Supports CloudForms-like quota enforcement and resource retirement policies
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from functions.base import Base


class QuotaPolicy(Base):
    """
    Automated ResourceQuota management policy
    Defines quotas to be enforced on namespaces matching a pattern
    """
    __tablename__ = 'quota_policies'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)

    # Target configuration
    cluster_id = Column(Integer, ForeignKey('clusters.id'))
    namespace_pattern = Column(String(255))  # Regex or glob pattern (e.g., 'dev-*', 'team-.*')

    # Quota limits (Kubernetes ResourceQuota format)
    cpu_limit = Column(String(20))  # "10000m" = 10 cores
    memory_limit = Column(String(20))  # "20Gi"
    pods_limit = Column(Integer)  # Maximum number of pods
    pvc_limit = Column(Integer)  # Maximum number of PVCs
    services_limit = Column(Integer)  # Maximum number of services

    # Auto-enforcement flags
    auto_create = Column(Boolean, default=True)  # Automatically create ResourceQuota in K8s
    auto_update = Column(Boolean, default=True)  # Automatically update existing ResourceQuota

    # Priority (higher priority policies apply first)
    priority = Column(Integer, default=100)

    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)

    # Relationships
    cluster = relationship('Cluster')

    def __repr__(self):
        return f'<QuotaPolicy id={self.id} name={self.name} cluster_id={self.cluster_id}>'


class RetirementPolicy(Base):
    """
    Automated resource retirement/cleanup policy
    Defines conditions for retiring idle or old Kubernetes resources
    """
    __tablename__ = 'retirement_policies'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)

    # Targeting configuration
    cluster_id = Column(Integer, ForeignKey('clusters.id'))
    resource_type = Column(String(100))  # 'Deployment', 'StatefulSet', 'Pod', 'Service'
    namespace_pattern = Column(String(255))  # Regex or glob pattern
    label_selector = Column(String(255))  # K8s label selector (e.g., 'app=test,env=dev')

    # Retirement criteria
    idle_days = Column(Integer)  # Retire after N days of inactivity (no pod restarts/scaling)
    max_age_days = Column(Integer)  # Retire after N days regardless of activity

    # Grace period configuration
    warning_days = Column(Integer, default=7)  # Warn N days before retirement

    # Retirement action
    retirement_action = Column(String(50), default='delete')  # 'delete', 'scale_to_zero', 'move_to_archive'

    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)

    # Relationships
    cluster = relationship('Cluster')

    def __repr__(self):
        return f'<RetirementPolicy id={self.id} name={self.name} cluster_id={self.cluster_id}>'
