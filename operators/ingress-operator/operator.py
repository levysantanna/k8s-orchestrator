#!/usr/bin/env python3
"""
Ingress Operator for k8s-orchestrator
Automatically creates and manages Kubernetes Ingress resources based on IngressTemplate CRs
and Service annotations
"""
import kopf
import kubernetes
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import yaml
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load Kubernetes configuration
try:
    config.load_incluster_config()
    logger.info("Loaded in-cluster Kubernetes configuration")
except config.ConfigException:
    config.load_kube_config()
    logger.info("Loaded kubeconfig from file")

# Initialize Kubernetes API clients
core_v1 = client.CoreV1Api()
networking_v1 = client.NetworkingV1Api()
custom_api = client.CustomObjectsApi()


def generate_resource_name(host: str) -> str:
    """Generate resource name from hostname"""
    # Replace dots with dashes and ensure DNS-1123 compliance
    name = host.replace('.', '-').lower()
    # Truncate if too long (max 63 chars for Kubernetes names)
    if len(name) > 63:
        name = name[:63].rstrip('-')
    return name


def create_external_backend(namespace: str, name: str, external_ip: str,
                            http_port: int, https_port: Optional[int] = None) -> Dict:
    """
    Create Service and Endpoints for external backend
    Returns dict with service and endpoints names
    """
    service_name = f"{name}-external"

    # Define ports
    ports = [
        client.V1ServicePort(
            name='http',
            port=http_port,
            target_port=http_port,
            protocol='TCP'
        )
    ]

    if https_port:
        ports.append(
            client.V1ServicePort(
                name='https',
                port=https_port,
                target_port=https_port,
                protocol='TCP'
            )
        )

    # Create headless service (no selector)
    service = client.V1Service(
        api_version='v1',
        kind='Service',
        metadata=client.V1ObjectMeta(
            name=service_name,
            namespace=namespace,
            labels={'app': name, 'managed-by': 'ingress-operator'}
        ),
        spec=client.V1ServiceSpec(
            ports=ports
        )
    )

    # Create manual endpoints
    endpoint_ports = [
        client.V1EndpointPort(
            name='http',
            port=http_port,
            protocol='TCP'
        )
    ]

    if https_port:
        endpoint_ports.append(
            client.V1EndpointPort(
                name='https',
                port=https_port,
                protocol='TCP'
            )
        )

    endpoints = client.V1Endpoints(
        api_version='v1',
        kind='Endpoints',
        metadata=client.V1ObjectMeta(
            name=service_name,
            namespace=namespace,
            labels={'app': name, 'managed-by': 'ingress-operator'}
        ),
        subsets=[
            client.V1EndpointSubset(
                addresses=[client.V1EndpointAddress(ip=external_ip)],
                ports=endpoint_ports
            )
        ]
    )

    # Create or update service
    try:
        core_v1.create_namespaced_service(namespace=namespace, body=service)
        logger.info(f"Created external service: {service_name}")
    except ApiException as e:
        if e.status == 409:  # Already exists
            core_v1.patch_namespaced_service(name=service_name, namespace=namespace, body=service)
            logger.info(f"Updated external service: {service_name}")
        else:
            raise

    # Create or update endpoints
    try:
        core_v1.create_namespaced_endpoints(namespace=namespace, body=endpoints)
        logger.info(f"Created external endpoints: {service_name}")
    except ApiException as e:
        if e.status == 409:  # Already exists
            core_v1.patch_namespaced_endpoints(name=service_name, namespace=namespace, body=endpoints)
            logger.info(f"Updated external endpoints: {service_name}")
        else:
            raise

    return {'service': service_name, 'endpoints': service_name}


def generate_ingress_manifest(name: str, namespace: str, spec: Dict[str, Any]) -> client.V1Ingress:
    """Generate Ingress manifest from IngressTemplate spec"""
    host = spec['host']
    backend_config = spec['backend']
    tls_config = spec.get('tls', {})
    paths_config = spec.get('paths', [])
    annotations = spec.get('annotations', {})
    ingress_class = spec.get('ingressClassName', 'traefik')

    # Default Traefik annotations
    default_annotations = {
        'traefik.ingress.kubernetes.io/router.entrypoints': 'web,websecure'
    }

    # Merge custom annotations
    final_annotations = {**default_annotations, **annotations}

    # Determine backend service
    if backend_config['type'] == 'external':
        backend_service = f"{name}-external"
        backend_port = backend_config.get('externalPort', 80)
    else:
        backend_service = backend_config['serviceName']
        backend_port = backend_config['servicePort']

    # Build path rules
    if paths_config:
        # Multi-path routing
        http_paths = []
        for path_rule in paths_config:
            path_service = path_rule.get('serviceName', backend_service)
            path_port = path_rule.get('servicePort', backend_port)

            http_paths.append(
                client.V1HTTPIngressPath(
                    path=path_rule['path'],
                    path_type=path_rule.get('pathType', 'Prefix'),
                    backend=client.V1IngressBackend(
                        service=client.V1IngressServiceBackend(
                            name=path_service,
                            port=client.V1ServiceBackendPort(number=path_port)
                        )
                    )
                )
            )

            # Add priority annotation if specified
            priority = path_rule.get('priority')
            if priority:
                final_annotations[f'traefik.ingress.kubernetes.io/router.priority'] = str(priority)
    else:
        # Single path
        http_paths = [
            client.V1HTTPIngressPath(
                path='/',
                path_type='Prefix',
                backend=client.V1IngressBackend(
                    service=client.V1IngressServiceBackend(
                        name=backend_service,
                        port=client.V1ServiceBackendPort(number=backend_port)
                    )
                )
            )
        ]

    # Build TLS configuration
    tls_list = []
    if tls_config.get('enabled', False):
        if tls_config.get('useWildcard', False):
            # Use existing wildcard certificate
            secret_name = tls_config.get('wildcardSecretName', 'wildcard-comunatec-org-tls')
        else:
            # Generate cert via cert-manager
            secret_name = tls_config.get('secretName', f"{name}-tls")
            cluster_issuer = tls_config.get('clusterIssuer', 'letsencrypt-prod')
            final_annotations['cert-manager.io/cluster-issuer'] = cluster_issuer

        tls_list.append(
            client.V1IngressTLS(
                hosts=[host],
                secret_name=secret_name
            )
        )

    # Create Ingress object
    ingress = client.V1Ingress(
        api_version='networking.k8s.io/v1',
        kind='Ingress',
        metadata=client.V1ObjectMeta(
            name=name,
            namespace=namespace,
            labels={
                'app': name,
                'managed-by': 'ingress-operator',
                'ingress-template': name
            },
            annotations=final_annotations
        ),
        spec=client.V1IngressSpec(
            ingress_class_name=ingress_class,
            tls=tls_list if tls_list else None,
            rules=[
                client.V1IngressRule(
                    host=host,
                    http=client.V1HTTPIngressRuleValue(paths=http_paths)
                )
            ]
        )
    )

    return ingress


def update_status(namespace: str, name: str, status_data: Dict[str, Any]):
    """Update IngressTemplate status"""
    try:
        custom_api.patch_namespaced_custom_object_status(
            group='ingress.k8s-orchestrator.io',
            version='v1',
            namespace=namespace,
            plural='ingresstemplates',
            name=name,
            body={'status': status_data}
        )
        logger.info(f"Updated status for IngressTemplate: {name}")
    except ApiException as e:
        logger.error(f"Failed to update status for {name}: {e}")


@kopf.on.create('ingress templates.ingress.k8s-orchestrator.io')
def create_ingress_template(spec, name, namespace, **kwargs):
    """
    Handle IngressTemplate creation
    Creates corresponding Ingress resource and external backend if needed
    """
    logger.info(f"Creating IngressTemplate: {namespace}/{name}")

    # Check if enabled
    if not spec.get('enabled', True):
        logger.info(f"IngressTemplate {name} is disabled, skipping ingress creation")
        return {'message': 'Template disabled'}

    # Validate required fields
    if 'host' not in spec:
        raise kopf.PermanentError("Missing required field: host")
    if 'backend' not in spec:
        raise kopf.PermanentError("Missing required field: backend")

    backend = spec['backend']
    if backend['type'] not in ['service', 'external']:
        raise kopf.PermanentError(f"Invalid backend type: {backend['type']}")

    # Validate backend configuration
    if backend['type'] == 'service':
        if 'serviceName' not in backend or 'servicePort' not in backend:
            raise kopf.PermanentError("serviceName and servicePort required for type=service")
    elif backend['type'] == 'external':
        if 'externalIP' not in backend:
            raise kopf.PermanentError("externalIP required for type=external")

    try:
        # Create external backend if needed
        service_name = None
        endpoints_name = None
        if backend['type'] == 'external':
            external_ip = backend['externalIP']
            external_port = backend.get('externalPort', 80)
            external_https_port = backend.get('externalHttpsPort')

            result = create_external_backend(
                namespace=namespace,
                name=name,
                external_ip=external_ip,
                http_port=external_port,
                https_port=external_https_port
            )
            service_name = result['service']
            endpoints_name = result['endpoints']
            logger.info(f"Created external backend for {name}: {service_name}")

        # Generate and create Ingress
        ingress = generate_ingress_manifest(name, namespace, spec)

        try:
            networking_v1.create_namespaced_ingress(namespace=namespace, body=ingress)
            logger.info(f"Created Ingress: {namespace}/{name}")
        except ApiException as e:
            if e.status == 409:  # Already exists
                networking_v1.patch_namespaced_ingress(name=name, namespace=namespace, body=ingress)
                logger.info(f"Updated existing Ingress: {namespace}/{name}")
            else:
                raise

        # Update status
        status_data = {
            'ingressName': name,
            'created': datetime.utcnow().isoformat() + 'Z',
            'lastUpdated': datetime.utcnow().isoformat() + 'Z',
            'conditions': [
                {
                    'type': 'Ready',
                    'status': 'True',
                    'reason': 'IngressCreated',
                    'message': f'Ingress {name} created successfully',
                    'lastTransitionTime': datetime.utcnow().isoformat() + 'Z'
                }
            ]
        }

        if service_name:
            status_data['serviceName'] = service_name
            status_data['endpointsName'] = endpoints_name

        update_status(namespace, name, status_data)

        return {'message': f'Ingress {name} created successfully'}

    except Exception as e:
        logger.error(f"Error creating ingress for {name}: {e}")

        # Update status with error
        status_data = {
            'conditions': [
                {
                    'type': 'Ready',
                    'status': 'False',
                    'reason': 'CreationFailed',
                    'message': str(e),
                    'lastTransitionTime': datetime.utcnow().isoformat() + 'Z'
                }
            ]
        }
        update_status(namespace, name, status_data)

        raise kopf.TemporaryError(f"Failed to create ingress: {e}", delay=30)


@kopf.on.update('ingresstemplates.ingress.k8s-orchestrator.io')
def update_ingress_template(spec, name, namespace, old, new, **kwargs):
    """
    Handle IngressTemplate updates
    Recreates Ingress if spec changed
    """
    logger.info(f"Updating IngressTemplate: {namespace}/{name}")

    # Check if spec changed
    old_spec = old.get('spec', {})
    new_spec = new.get('spec', {})

    if old_spec == new_spec:
        logger.info(f"No spec changes for {name}, skipping update")
        return {'message': 'No changes'}

    # If disabled, delete ingress
    if not spec.get('enabled', True):
        logger.info(f"IngressTemplate {name} disabled, deleting ingress")
        try:
            networking_v1.delete_namespaced_ingress(name=name, namespace=namespace)
            logger.info(f"Deleted Ingress: {namespace}/{name}")
        except ApiException as e:
            if e.status != 404:
                raise

        # Update status
        status_data = {
            'lastUpdated': datetime.utcnow().isoformat() + 'Z',
            'conditions': [
                {
                    'type': 'Ready',
                    'status': 'False',
                    'reason': 'Disabled',
                    'message': 'Template disabled, ingress deleted',
                    'lastTransitionTime': datetime.utcnow().isoformat() + 'Z'
                }
            ]
        }
        update_status(namespace, name, status_data)
        return {'message': 'Template disabled'}

    # Recreate ingress (simpler than patching)
    return create_ingress_template(spec=spec, name=name, namespace=namespace, **kwargs)


@kopf.on.delete('ingresstemplates.ingress.k8s-orchestrator.io')
def delete_ingress_template(spec, name, namespace, **kwargs):
    """
    Handle IngressTemplate deletion
    Deletes associated Ingress and external backend resources
    """
    logger.info(f"Deleting IngressTemplate: {namespace}/{name}")

    try:
        # Delete Ingress
        try:
            networking_v1.delete_namespaced_ingress(name=name, namespace=namespace)
            logger.info(f"Deleted Ingress: {namespace}/{name}")
        except ApiException as e:
            if e.status != 404:
                logger.warning(f"Could not delete ingress {name}: {e}")

        # Delete external backend if it exists
        backend = spec.get('backend', {})
        if backend.get('type') == 'external':
            service_name = f"{name}-external"

            try:
                core_v1.delete_namespaced_service(name=service_name, namespace=namespace)
                logger.info(f"Deleted external service: {service_name}")
            except ApiException as e:
                if e.status != 404:
                    logger.warning(f"Could not delete service {service_name}: {e}")

            try:
                core_v1.delete_namespaced_endpoints(name=service_name, namespace=namespace)
                logger.info(f"Deleted external endpoints: {service_name}")
            except ApiException as e:
                if e.status != 404:
                    logger.warning(f"Could not delete endpoints {service_name}: {e}")

        return {'message': f'IngressTemplate {name} and associated resources deleted'}

    except Exception as e:
        logger.error(f"Error deleting resources for {name}: {e}")
        raise


@kopf.on.create('', 'v1', 'services')
@kopf.on.update('', 'v1', 'services')
def handle_service_annotations(spec, meta, name, namespace, annotations, **kwargs):
    """
    Watch Services for auto-ingress annotations
    Creates IngressTemplate automatically if annotations present
    """
    if not annotations:
        return

    # Check for auto-create annotation
    auto_create = annotations.get('ingress.k8s-orchestrator.io/auto-create', '').lower()
    if auto_create not in ['true', '1', 'yes']:
        return

    logger.info(f"Auto-creating ingress for Service: {namespace}/{name}")

    # Extract configuration from annotations
    host = annotations.get('ingress.k8s-orchestrator.io/host')
    if not host:
        logger.warning(f"Service {name} has auto-create but no host annotation, skipping")
        return

    tls_enabled = annotations.get('ingress.k8s-orchestrator.io/tls', 'false').lower() in ['true', '1', 'yes']
    cluster_issuer = annotations.get('ingress.k8s-orchestrator.io/cluster-issuer', 'letsencrypt-prod')
    use_wildcard = annotations.get('ingress.k8s-orchestrator.io/use-wildcard', 'false').lower() in ['true', '1', 'yes']

    # Get service port (use first port if not specified)
    service_port = None
    port_annotation = annotations.get('ingress.k8s-orchestrator.io/service-port')
    if port_annotation:
        service_port = int(port_annotation)
    elif spec.get('ports'):
        service_port = spec['ports'][0].get('port', 80)
    else:
        logger.warning(f"Could not determine service port for {name}, skipping")
        return

    # Build IngressTemplate spec
    template_spec = {
        'enabled': True,
        'host': host,
        'backend': {
            'type': 'service',
            'serviceName': name,
            'servicePort': service_port
        },
        'tls': {
            'enabled': tls_enabled,
            'clusterIssuer': cluster_issuer,
            'useWildcard': use_wildcard
        },
        'ingressClassName': 'traefik'
    }

    # Create IngressTemplate CR
    template_name = generate_resource_name(host)
    template = {
        'apiVersion': 'ingress.k8s-orchestrator.io/v1',
        'kind': 'IngressTemplate',
        'metadata': {
            'name': template_name,
            'namespace': namespace,
            'labels': {
                'auto-created': 'true',
                'source-service': name
            }
        },
        'spec': template_spec
    }

    try:
        custom_api.create_namespaced_custom_object(
            group='ingress.k8s-orchestrator.io',
            version='v1',
            namespace=namespace,
            plural='ingresstemplates',
            body=template
        )
        logger.info(f"Created IngressTemplate {template_name} for Service {name}")
    except ApiException as e:
        if e.status == 409:
            # Already exists, update it
            custom_api.patch_namespaced_custom_object(
                group='ingress.k8s-orchestrator.io',
                version='v1',
                namespace=namespace,
                plural='ingresstemplates',
                name=template_name,
                body=template
            )
            logger.info(f"Updated IngressTemplate {template_name} for Service {name}")
        else:
            logger.error(f"Failed to create IngressTemplate: {e}")
            raise


if __name__ == '__main__':
    logger.info("Starting Ingress Operator")
