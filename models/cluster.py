from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
from functions.base import Base
import enum

class ClusterStatus(enum.Enum):
    """Cluster status enumeration"""
    ACTIVE = 'active'
    UNREACHABLE = 'unreachable'
    INITIALIZING = 'initializing'
    ERROR = 'error'

class ClusterConnectionType(enum.Enum):
    """Connection type enumeration"""
    KUBECONFIG = 'kubeconfig'
    SSH = 'ssh'

class Cluster(Base):
    """Kubernetes cluster model"""
    __tablename__ = 'clusters'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(Text)
    api_server_url = Column(String(255), nullable=False)
    connection_type = Column(SQLEnum(ClusterConnectionType), default=ClusterConnectionType.KUBECONFIG)

    # Kubeconfig authentication
    kubeconfig_content = Column(Text)  # Base64 encoded

    # SSH authentication (fallback for metrics collection)
    ssh_host = Column(String(255))
    ssh_port = Column(Integer, default=22)
    ssh_username = Column(String(100))
    ssh_key_content = Column(Text)  # Encrypted private key
    ssh_password = Column(String(255))  # Encrypted password (fallback)

    # Status tracking
    status = Column(SQLEnum(ClusterStatus), default=ClusterStatus.INITIALIZING)
    last_seen = Column(DateTime)
    health_status = Column(String(50))  # healthy, degraded, critical

    # Cluster metadata
    kubernetes_version = Column(String(50))
    node_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    nodes = relationship('Node', back_populates='cluster', cascade='all, delete-orphan')
    agents = relationship('MCPAgent', back_populates='cluster', cascade='all, delete-orphan')
    metrics = relationship('MetricsSnapshot', back_populates='cluster', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Cluster {self.name} ({self.status.value})>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'api_server_url': self.api_server_url,
            'connection_type': self.connection_type.value,
            'status': self.status.value,
            'health_status': self.health_status,
            'kubernetes_version': self.kubernetes_version,
            'node_count': self.node_count,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'created_at': self.created_at.isoformat(),
        }

class Node(Base):
    """Kubernetes node model"""
    __tablename__ = 'nodes'

    id = Column(Integer, primary_key=True)
    cluster_id = Column(Integer, ForeignKey('clusters.id'), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    ip_address = Column(String(45))  # IPv4 or IPv6
    role = Column(String(50))  # master, worker

    # Hardware info
    cpu_cores = Column(Integer)
    memory_gb = Column(Float)
    disk_gb = Column(Float)

    # Status
    status = Column(String(50))  # Ready, NotReady, Unknown
    kubelet_version = Column(String(50))

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime)

    # Relationships
    cluster = relationship('Cluster', back_populates='nodes')

    def __repr__(self):
        return f'<Node {self.name} ({self.role})>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'cluster_id': self.cluster_id,
            'name': self.name,
            'ip_address': self.ip_address,
            'role': self.role,
            'cpu_cores': self.cpu_cores,
            'memory_gb': self.memory_gb,
            'disk_gb': self.disk_gb,
            'status': self.status,
            'kubelet_version': self.kubelet_version,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
        }
