from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from functions.base import Base
import enum

class AgentStatus(enum.Enum):
    """MCP Agent status enumeration"""
    DEPLOYING = 'deploying'
    RUNNING = 'running'
    STOPPED = 'stopped'
    FAILED = 'failed'

class MCPAgent(Base):
    """MCP Agent deployment model"""
    __tablename__ = 'mcp_agents'

    id = Column(Integer, primary_key=True)
    cluster_id = Column(Integer, ForeignKey('clusters.id'), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    namespace = Column(String(100), default='mcp-agents')

    # LLM configuration
    llm_model = Column(String(100), default='llama3.2:1b')
    llm_endpoint = Column(String(255))  # http://ollama.ollama.svc:11434
    mcp_capabilities = Column(JSON)  # List of enabled MCP tools

    # Resource allocation
    cpu_request = Column(String(20), default='500m')
    memory_request = Column(String(20), default='1Gi')
    cpu_limit = Column(String(20), default='2000m')
    memory_limit = Column(String(20), default='4Gi')

    # Deployment status
    status = Column(SQLEnum(AgentStatus), default=AgentStatus.DEPLOYING)
    pod_name = Column(String(255))  # Current pod name
    deployment_name = Column(String(255))  # Deployment resource name
    last_deployment = Column(DateTime)
    error_message = Column(Text)  # Last error if failed

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    cluster = relationship('Cluster', back_populates='agents')

    def __repr__(self):
        return f'<MCPAgent {self.name} on {self.namespace} ({self.status.value})>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'cluster_id': self.cluster_id,
            'name': self.name,
            'namespace': self.namespace,
            'llm_model': self.llm_model,
            'llm_endpoint': self.llm_endpoint,
            'mcp_capabilities': self.mcp_capabilities,
            'cpu_request': self.cpu_request,
            'memory_request': self.memory_request,
            'cpu_limit': self.cpu_limit,
            'memory_limit': self.memory_limit,
            'status': self.status.value,
            'pod_name': self.pod_name,
            'deployment_name': self.deployment_name,
            'last_deployment': self.last_deployment.isoformat() if self.last_deployment else None,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat(),
        }
