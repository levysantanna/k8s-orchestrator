"""
Service Catalog Models for CloudForms-like Self-Service Provisioning
Supports Helm charts, Kubernetes templates, and application bundles
"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from functions.base import Base


class CatalogItemType(enum.Enum):
    """Types of catalog items"""
    HELM_CHART = 'helm_chart'
    KUBERNETES_TEMPLATE = 'kubernetes_template'
    KUSTOMIZE_APP = 'kustomize_app'
    BUNDLE = 'bundle'  # Multiple items deployed together


class ServiceCatalogItem(Base):
    """
    Service catalog item - pre-configured application template
    Similar to CloudForms service catalog for self-service deployment
    """
    __tablename__ = 'service_catalog_items'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    display_name = Column(String(255))
    description = Column(Text)

    # Catalog organization
    catalog_category = Column(String(100))  # 'Databases', 'Web Apps', 'Monitoring', 'Storage'
    item_type = Column(SQLEnum(CatalogItemType), nullable=False)

    # Icon/visual representation
    icon_class = Column(String(100))  # FontAwesome icon class (e.g., 'fas fa-database')

    # Template/chart configuration
    template_content = Column(Text)  # YAML template or Helm values file
    helm_chart_repo = Column(String(255))  # Helm repository URL
    helm_chart_name = Column(String(255))  # Chart name (e.g., 'bitnami/postgresql')
    helm_chart_version = Column(String(50))  # Chart version

    # Form definition for user input
    service_dialog_id = Column(Integer, ForeignKey('service_dialogs.id'))

    # Defaults
    default_namespace = Column(String(100))
    requires_approval = Column(Boolean, default=False)

    # Resource estimates
    estimated_cpu = Column(String(20))  # "1000m"
    estimated_memory = Column(String(20))  # "2Gi"

    # Ordering and visibility
    is_active = Column(Boolean, default=True)
    order_index = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)

    # Relationships
    service_dialog = relationship('ServiceDialog')
    deployed_services = relationship('DeployedService', back_populates='catalog_item')

    def __repr__(self):
        return f'<ServiceCatalogItem id={self.id} name={self.name} type={self.item_type.value}>'


class DialogFieldType(enum.Enum):
    """Form field types for service dialogs"""
    TEXT = 'text'
    TEXTAREA = 'textarea'
    NUMBER = 'number'
    DROPDOWN = 'dropdown'
    CHECKBOX = 'checkbox'
    RADIO = 'radio'
    TAG_SELECTOR = 'tag_selector'
    PASSWORD = 'password'


class ServiceDialog(Base):
    """
    Dynamic form builder for service catalog items
    Similar to CloudForms service dialogs with custom fields
    """
    __tablename__ = 'service_dialogs'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    label = Column(String(255))
    description = Column(Text)

    # Form fields definition (JSON array)
    # Example: [
    #   {
    #     "name": "database_name",
    #     "label": "Database Name",
    #     "type": "text",
    #     "required": true,
    #     "default": "mydb",
    #     "placeholder": "Enter database name",
    #     "validation": {"pattern": "^[a-z0-9-]+$"}
    #   },
    #   {
    #     "name": "version",
    #     "label": "PostgreSQL Version",
    #     "type": "dropdown",
    #     "required": true,
    #     "options": ["15", "14", "13"],
    #     "default": "15"
    #   }
    # ]
    fields = Column(JSON, nullable=False)

    # Validation schema (JSON Schema format)
    validation_schema = Column(JSON)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<ServiceDialog id={self.id} name={self.name}>'


class ServiceState(enum.Enum):
    """Deployed service lifecycle states"""
    PROVISIONING = 'provisioning'
    ACTIVE = 'active'
    STOPPING = 'stopping'
    STOPPED = 'stopped'
    RETIRING = 'retiring'
    RETIRED = 'retired'
    FAILED = 'failed'


class DeployedService(Base):
    """
    Tracking of deployed catalog items
    Links catalog items to actual running Kubernetes resources
    """
    __tablename__ = 'deployed_services'

    id = Column(Integer, primary_key=True)
    catalog_item_id = Column(Integer, ForeignKey('service_catalog_items.id'), nullable=False)
    cluster_id = Column(Integer, ForeignKey('clusters.id'), nullable=False)

    # Deployment information
    service_name = Column(String(255), nullable=False)
    namespace = Column(String(100), nullable=False)
    state = Column(SQLEnum(ServiceState), default=ServiceState.PROVISIONING, nullable=False)

    # User inputs from service dialog (JSON)
    dialog_values = Column(JSON)

    # Kubernetes resources created (JSON array)
    # Example: [
    #   {"kind": "Deployment", "name": "postgres", "namespace": "default"},
    #   {"kind": "Service", "name": "postgres", "namespace": "default"},
    #   {"kind": "PersistentVolumeClaim", "name": "postgres-data", "namespace": "default"}
    # ]
    resources = Column(JSON)

    # Lifecycle tracking
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    provisioned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_reconfigured_at = Column(DateTime)
    retirement_scheduled_at = Column(DateTime)
    retired_at = Column(DateTime)

    # Relationships
    catalog_item = relationship('ServiceCatalogItem', back_populates='deployed_services')
    cluster = relationship('Cluster')
    owner = relationship('User')

    def __repr__(self):
        return f'<DeployedService id={self.id} name={self.service_name} state={self.state.value}>'
