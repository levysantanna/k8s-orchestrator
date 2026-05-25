"""
Service layer for Ingress management
Handles IngressTemplate CRs and related operations
"""
import yaml
import re
from typing import List, Dict, Optional
from functions.base import get_db_session
from models.cluster import Cluster
from services.k8s_client_service import K8sClientService


class IngressService:
    """Service for managing IngressTemplate custom resources"""

    CRD_GROUP = 'ingress.k8s-orchestrator.io'
    CRD_VERSION = 'v1'
    CRD_PLURAL = 'ingresstemplates'

    @staticmethod
    def validate_host(host: str) -> bool:
        """
        Validate hostname format

        Args:
            host: Hostname to validate

        Returns:
            bool: True if valid
        """
        # DNS-1123 subdomain pattern
        pattern = r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$'
        if not re.match(pattern, host):
            return False

        # Check length
        if len(host) > 253:
            return False

        # Check label lengths
        labels = host.split('.')
        for label in labels:
            if len(label) > 63:
                return False

        return True

    @staticmethod
    def generate_resource_name(host: str) -> str:
        """Generate Kubernetes resource name from hostname"""
        name = host.replace('.', '-').lower()
        # Truncate if too long
        if len(name) > 63:
            name = name[:63].rstrip('-')
        return name

    @staticmethod
    def get_ingress_templates(cluster_id: int, namespace: str = None) -> List[Dict]:
        """
        List IngressTemplate CRs in a cluster

        Args:
            cluster_id: Cluster ID
            namespace: Namespace filter (optional)

        Returns:
            List of IngressTemplate resources
        """
        db = get_db_session()
        try:
            cluster = db.query(Cluster).filter_by(id=cluster_id).first()
            if not cluster:
                raise Exception("Cluster not found")

            k8s_client = K8sClientService(
                kubeconfig_content=cluster.kubeconfig_content,
                cluster_name=cluster.name
            )

            templates = k8s_client.get_custom_resources(
                group=IngressService.CRD_GROUP,
                version=IngressService.CRD_VERSION,
                plural=IngressService.CRD_PLURAL,
                namespace=namespace
            )

            return templates
        finally:
            db.close()

    @staticmethod
    def get_ingress_template(cluster_id: int, namespace: str, name: str) -> Optional[Dict]:
        """
        Get a specific IngressTemplate

        Args:
            cluster_id: Cluster ID
            namespace: Namespace
            name: Template name

        Returns:
            IngressTemplate resource or None
        """
        templates = IngressService.get_ingress_templates(cluster_id, namespace)
        for template in templates:
            metadata = template.get('metadata', {})
            if metadata.get('name') == name and metadata.get('namespace') == namespace:
                return template
        return None

    @staticmethod
    def create_ingress_template(cluster_id: int, namespace: str, name: str, spec: Dict) -> Dict:
        """
        Create IngressTemplate CR

        Args:
            cluster_id: Cluster ID
            namespace: Namespace
            name: Template name
            spec: Template spec

        Returns:
            Created template
        """
        db = get_db_session()
        try:
            cluster = db.query(Cluster).filter_by(id=cluster_id).first()
            if not cluster:
                raise Exception("Cluster not found")

            # Validate spec
            if 'host' not in spec:
                raise ValueError("Missing required field: host")
            if not IngressService.validate_host(spec['host']):
                raise ValueError(f"Invalid hostname: {spec['host']}")

            if 'backend' not in spec:
                raise ValueError("Missing required field: backend")

            # Generate YAML
            yaml_content = IngressService.generate_template_yaml(name, namespace, spec)

            # Apply to cluster
            k8s_client = K8sClientService(
                kubeconfig_content=cluster.kubeconfig_content,
                cluster_name=cluster.name
            )

            k8s_client.apply_manifest(yaml_content, namespace)

            return {
                'name': name,
                'namespace': namespace,
                'spec': spec
            }
        finally:
            db.close()

    @staticmethod
    def delete_ingress_template(cluster_id: int, namespace: str, name: str) -> bool:
        """
        Delete IngressTemplate CR

        Args:
            cluster_id: Cluster ID
            namespace: Namespace
            name: Template name

        Returns:
            bool: Success
        """
        db = get_db_session()
        try:
            cluster = db.query(Cluster).filter_by(id=cluster_id).first()
            if not cluster:
                raise Exception("Cluster not found")

            k8s_client = K8sClientService(
                kubeconfig_content=cluster.kubeconfig_content,
                cluster_name=cluster.name
            )

            # Delete via kubectl-style command
            from kubernetes import client
            custom_api = client.CustomObjectsApi(k8s_client.api_client)

            custom_api.delete_namespaced_custom_object(
                group=IngressService.CRD_GROUP,
                version=IngressService.CRD_VERSION,
                namespace=namespace,
                plural=IngressService.CRD_PLURAL,
                name=name
            )

            return True
        except Exception as e:
            raise Exception(f"Failed to delete template: {str(e)}")
        finally:
            db.close()

    @staticmethod
    def toggle_template(cluster_id: int, namespace: str, name: str, enabled: bool) -> bool:
        """
        Enable or disable an IngressTemplate

        Args:
            cluster_id: Cluster ID
            namespace: Namespace
            name: Template name
            enabled: Enable state

        Returns:
            bool: Success
        """
        # Get current template
        template = IngressService.get_ingress_template(cluster_id, namespace, name)
        if not template:
            raise Exception("Template not found")

        spec = template.get('spec', {})
        spec['enabled'] = enabled

        # Update template
        db = get_db_session()
        try:
            cluster = db.query(Cluster).filter_by(id=cluster_id).first()
            if not cluster:
                raise Exception("Cluster not found")

            # Generate updated YAML
            yaml_content = IngressService.generate_template_yaml(name, namespace, spec)

            # Apply to cluster
            k8s_client = K8sClientService(
                kubeconfig_content=cluster.kubeconfig_content,
                cluster_name=cluster.name
            )

            k8s_client.apply_manifest(yaml_content, namespace)

            return True
        finally:
            db.close()

    @staticmethod
    def generate_template_yaml(name: str, namespace: str, spec: Dict) -> str:
        """
        Generate IngressTemplate YAML from spec

        Args:
            name: Resource name
            namespace: Namespace
            spec: Template spec

        Returns:
            str: YAML manifest
        """
        template = {
            'apiVersion': f'{IngressService.CRD_GROUP}/{IngressService.CRD_VERSION}',
            'kind': 'IngressTemplate',
            'metadata': {
                'name': name,
                'namespace': namespace,
                'labels': {
                    'app': name,
                    'managed-by': 'k8s-orchestrator'
                }
            },
            'spec': spec
        }

        return yaml.dump(template, default_flow_style=False)

    @staticmethod
    def get_available_services(cluster_id: int, namespace: str) -> List[Dict]:
        """
        List available services in a namespace

        Args:
            cluster_id: Cluster ID
            namespace: Namespace

        Returns:
            List of service dictionaries with name and ports
        """
        db = get_db_session()
        try:
            cluster = db.query(Cluster).filter_by(id=cluster_id).first()
            if not cluster:
                raise Exception("Cluster not found")

            k8s_client = K8sClientService(
                kubeconfig_content=cluster.kubeconfig_content,
                cluster_name=cluster.name
            )

            from kubernetes import client
            core_v1 = client.CoreV1Api(k8s_client.api_client)

            services = core_v1.list_namespaced_service(namespace)

            result = []
            for svc in services.items:
                ports = []
                if svc.spec.ports:
                    ports = [
                        {
                            'name': port.name or f'port-{port.port}',
                            'port': port.port,
                            'protocol': port.protocol
                        }
                        for port in svc.spec.ports
                    ]

                result.append({
                    'name': svc.metadata.name,
                    'namespace': svc.metadata.namespace,
                    'ports': ports,
                    'type': svc.spec.type
                })

            return result
        finally:
            db.close()

    @staticmethod
    def get_created_ingresses(cluster_id: int, namespace: str = None) -> List[Dict]:
        """
        List actual Ingress resources created by operator

        Args:
            cluster_id: Cluster ID
            namespace: Namespace filter (optional)

        Returns:
            List of Ingress resources
        """
        db = get_db_session()
        try:
            cluster = db.query(Cluster).filter_by(id=cluster_id).first()
            if not cluster:
                raise Exception("Cluster not found")

            k8s_client = K8sClientService(
                kubeconfig_content=cluster.kubeconfig_content,
                cluster_name=cluster.name
            )

            from kubernetes import client
            networking_v1 = client.NetworkingV1Api(k8s_client.api_client)

            if namespace:
                ingresses = networking_v1.list_namespaced_ingress(namespace)
            else:
                ingresses = networking_v1.list_ingress_for_all_namespaces()

            result = []
            for ingress in ingresses.items:
                # Filter only those managed by ingress-operator
                labels = ingress.metadata.labels or {}
                if labels.get('managed-by') != 'ingress-operator':
                    continue

                hosts = []
                tls_enabled = False
                if ingress.spec.rules:
                    hosts = [rule.host for rule in ingress.spec.rules if rule.host]
                if ingress.spec.tls:
                    tls_enabled = True

                result.append({
                    'name': ingress.metadata.name,
                    'namespace': ingress.metadata.namespace,
                    'hosts': hosts,
                    'tls': tls_enabled,
                    'ingressClass': ingress.spec.ingress_class_name,
                    'template': labels.get('ingress-template')
                })

            return result
        finally:
            db.close()

    @staticmethod
    def export_yaml(cluster_id: int, namespace: str, name: str) -> str:
        """
        Export IngressTemplate as YAML

        Args:
            cluster_id: Cluster ID
            namespace: Namespace
            name: Template name

        Returns:
            str: YAML content
        """
        template = IngressService.get_ingress_template(cluster_id, namespace, name)
        if not template:
            raise Exception("Template not found")

        return yaml.dump(template, default_flow_style=False)
