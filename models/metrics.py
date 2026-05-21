from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from functions.base import Base

class MetricsSnapshot(Base):
    """Metrics snapshot for cluster/node monitoring"""
    __tablename__ = 'metrics_snapshots'

    id = Column(Integer, primary_key=True)
    cluster_id = Column(Integer, ForeignKey('clusters.id'), nullable=False, index=True)
    node_name = Column(String(255), index=True)  # Optional: per-node metrics

    # Hardware metrics
    cpu_percent = Column(Float)
    memory_used_gb = Column(Float)
    memory_total_gb = Column(Float)
    memory_percent = Column(Float)
    disk_used_gb = Column(Float)
    disk_total_gb = Column(Float)
    disk_percent = Column(Float)
    load_avg_1 = Column(Float)
    load_avg_5 = Column(Float)
    load_avg_15 = Column(Float)

    # Kubernetes specific metrics
    pod_count = Column(Integer)
    pod_running = Column(Integer)
    pod_pending = Column(Integer)
    pod_failed = Column(Integer)

    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    cluster = relationship('Cluster', back_populates='metrics')

    def __repr__(self):
        return f'<MetricsSnapshot cluster={self.cluster_id} node={self.node_name} time={self.timestamp}>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'cluster_id': self.cluster_id,
            'node_name': self.node_name,
            'cpu_percent': self.cpu_percent,
            'memory_used_gb': self.memory_used_gb,
            'memory_total_gb': self.memory_total_gb,
            'memory_percent': self.memory_percent,
            'disk_used_gb': self.disk_used_gb,
            'disk_total_gb': self.disk_total_gb,
            'disk_percent': self.disk_percent,
            'load_avg_1': self.load_avg_1,
            'load_avg_5': self.load_avg_5,
            'load_avg_15': self.load_avg_15,
            'pod_count': self.pod_count,
            'pod_running': self.pod_running,
            'pod_pending': self.pod_pending,
            'pod_failed': self.pod_failed,
            'timestamp': self.timestamp.isoformat(),
        }
