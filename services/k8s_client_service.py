"""
Kubernetes Client Service
Wrapper around Kubernetes Python client for cluster operations
"""
import base64
import tempfile
import os
from typing import List, Dict, Optional
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import yaml

class K8sClientService:
    """Kubernetes client wrapper for cluster operations"""

    def __init__(self, cluster):
        """
        Initialize K8s client from cluster configuration

        Args:
            cluster: Cluster model instance with kubeconfig_content
        """
        self.cluster = cluster
        self.api_client = None
        self.core_v1 = None
        self.apps_v1 = None
        self.batch_v1 = None
        self.storage_v1 = None

        self._initialize_client()

    def _initialize_client(self):
        """Initialize Kubernetes API client from cluster kubeconfig"""
        try:
            if self.cluster.kubeconfig_content:
                # Decode base64 kubeconfig
                kubeconfig_data = base64.b64decode(self.cluster.kubeconfig_content).decode('utf-8')

                # Write kubeconfig to temporary file
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.kubeconfig') as f:
                    f.write(kubeconfig_data)
                    kubeconfig_path = f.name

                # Load kubeconfig from file
                config.load_kube_config(config_file=kubeconfig_path)

                # Clean up temp file
                os.unlink(kubeconfig_path)

            else:
                # Try in-cluster config (if running in K8s)
                try:
                    config.load_incluster_config()
                except config.ConfigException:
                    # Fallback to default kubeconfig
                    config.load_kube_config()

            # Initialize API clients
            self.api_client = client.ApiClient()
            self.core_v1 = client.CoreV1Api(self.api_client)
            self.apps_v1 = client.AppsV1Api(self.api_client)
            self.batch_v1 = client.BatchV1Api(self.api_client)
            self.storage_v1 = client.StorageV1Api(self.api_client)

        except Exception as e:
            raise Exception(f"Failed to initialize K8s client: {str(e)}")

    def test_connection(self) -> Dict:
        """
        Test cluster connectivity and return cluster info

        Returns:
            dict: Cluster version and node count
        """
        try:
            # Get version info
            version_api = client.VersionApi(self.api_client)
            version_info = version_api.get_code()

            # Get node list
            nodes = self.core_v1.list_node()

            return {
                'success': True,
                'version': f"{version_info.major}.{version_info.minor}",
                'git_version': version_info.git_version,
                'node_count': len(nodes.items),
            }
        except ApiException as e:
            return {
                'success': False,
                'error': f"API Exception: {e.status} {e.reason}"
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def get_nodes(self) -> List[Dict]:
        """
        Get all nodes in the cluster

        Returns:
            list: List of node dictionaries
        """
        try:
            nodes = self.core_v1.list_node()
            result = []

            for node in nodes.items:
                # Determine role
                role = 'worker'
                if 'node-role.kubernetes.io/master' in node.metadata.labels or \
                   'node-role.kubernetes.io/control-plane' in node.metadata.labels:
                    role = 'master'

                # Get node status
                status = 'Unknown'
                for condition in node.status.conditions:
                    if condition.type == 'Ready':
                        status = 'Ready' if condition.status == 'True' else 'NotReady'

                # Get node addresses
                ip_address = None
                for address in node.status.addresses:
                    if address.type == 'InternalIP':
                        ip_address = address.address
                        break

                # Get capacity
                capacity = node.status.capacity
                cpu_cores = int(capacity.get('cpu', 0))
                memory_kb = capacity.get('memory', '0Ki')
                memory_gb = self._parse_memory(memory_kb)

                result.append({
                    'name': node.metadata.name,
                    'ip_address': ip_address,
                    'role': role,
                    'status': status,
                    'kubelet_version': node.status.node_info.kubelet_version,
                    'cpu_cores': cpu_cores,
                    'memory_gb': memory_gb,
                })

            return result
        except ApiException as e:
            raise Exception(f"Failed to get nodes: {e.reason}")

    def get_namespaces(self) -> List[str]:
        """Get all namespaces in the cluster"""
        try:
            namespaces = self.core_v1.list_namespace()
            return [ns.metadata.name for ns in namespaces.items]
        except ApiException as e:
            raise Exception(f"Failed to get namespaces: {e.reason}")

    def get_pods(self, namespace: Optional[str] = None) -> List[Dict]:
        """
        Get pods in cluster or specific namespace

        Args:
            namespace: Namespace filter (None = all namespaces)

        Returns:
            list: List of pod dictionaries
        """
        try:
            if namespace:
                pods = self.core_v1.list_namespaced_pod(namespace)
            else:
                pods = self.core_v1.list_pod_for_all_namespaces()

            result = []
            for pod in pods.items:
                # Container statuses
                container_statuses = []
                if pod.status.container_statuses:
                    for status in pod.status.container_statuses:
                        container_statuses.append({
                            'name': status.name,
                            'ready': status.ready,
                            'restart_count': status.restart_count,
                        })

                result.append({
                    'name': pod.metadata.name,
                    'namespace': pod.metadata.namespace,
                    'status': pod.status.phase,
                    'node': pod.spec.node_name,
                    'ip': pod.status.pod_ip,
                    'containers': container_statuses,
                })

            return result
        except ApiException as e:
            raise Exception(f"Failed to get pods: {e.reason}")

    def get_deployments(self, namespace: Optional[str] = None) -> List[Dict]:
        """Get deployments in cluster or specific namespace"""
        try:
            if namespace:
                deployments = self.apps_v1.list_namespaced_deployment(namespace)
            else:
                deployments = self.apps_v1.list_deployment_for_all_namespaces()

            result = []
            for deploy in deployments.items:
                result.append({
                    'name': deploy.metadata.name,
                    'namespace': deploy.metadata.namespace,
                    'replicas': deploy.spec.replicas,
                    'ready_replicas': deploy.status.ready_replicas or 0,
                    'available_replicas': deploy.status.available_replicas or 0,
                })

            return result
        except ApiException as e:
            raise Exception(f"Failed to get deployments: {e.reason}")

    def get_statefulsets(self, namespace: Optional[str] = None) -> List[Dict]:
        """Get statefulsets in cluster or specific namespace"""
        try:
            if namespace:
                statefulsets = self.apps_v1.list_namespaced_stateful_set(namespace)
            else:
                statefulsets = self.apps_v1.list_stateful_set_for_all_namespaces()

            result = []
            for sts in statefulsets.items:
                result.append({
                    'name': sts.metadata.name,
                    'namespace': sts.metadata.namespace,
                    'replicas': sts.spec.replicas,
                    'ready_replicas': sts.status.ready_replicas or 0,
                })

            return result
        except ApiException as e:
            raise Exception(f"Failed to get statefulsets: {e.reason}")

    def get_pvcs(self, namespace: Optional[str] = None) -> List[Dict]:
        """Get PersistentVolumeClaims in cluster or specific namespace"""
        try:
            if namespace:
                pvcs = self.core_v1.list_namespaced_persistent_volume_claim(namespace)
            else:
                pvcs = self.core_v1.list_persistent_volume_claim_for_all_namespaces()

            result = []
            for pvc in pvcs.items:
                result.append({
                    'name': pvc.metadata.name,
                    'namespace': pvc.metadata.namespace,
                    'status': pvc.status.phase,
                    'capacity': pvc.status.capacity.get('storage') if pvc.status.capacity else None,
                    'storage_class': pvc.spec.storage_class_name,
                })

            return result
        except ApiException as e:
            raise Exception(f"Failed to get PVCs: {e.reason}")

    def create_namespace(self, name: str) -> bool:
        """Create namespace if not exists"""
        try:
            # Check if namespace exists
            try:
                self.core_v1.read_namespace(name)
                return True  # Already exists
            except ApiException as e:
                if e.status != 404:
                    raise

            # Create namespace
            namespace = client.V1Namespace(
                metadata=client.V1ObjectMeta(name=name)
            )
            self.core_v1.create_namespace(namespace)
            return True
        except ApiException as e:
            raise Exception(f"Failed to create namespace: {e.reason}")

    def apply_manifest(self, yaml_content: str, namespace: str = 'default') -> bool:
        """
        Apply YAML manifest to cluster

        Args:
            yaml_content: YAML manifest as string
            namespace: Target namespace

        Returns:
            bool: Success status
        """
        try:
            # Parse YAML (may contain multiple documents)
            docs = yaml.safe_load_all(yaml_content)

            for doc in docs:
                if not doc:
                    continue

                kind = doc.get('kind')
                metadata = doc.get('metadata', {})
                name = metadata.get('name')
                ns = metadata.get('namespace', namespace)

                # Route to appropriate API based on kind
                if kind == 'Deployment':
                    body = self.api_client._ApiClient__deserialize(doc, 'V1Deployment')
                    try:
                        self.apps_v1.read_namespaced_deployment(name, ns)
                        self.apps_v1.patch_namespaced_deployment(name, ns, body)
                    except ApiException as e:
                        if e.status == 404:
                            self.apps_v1.create_namespaced_deployment(ns, body)

                elif kind == 'Service':
                    body = self.api_client._ApiClient__deserialize(doc, 'V1Service')
                    try:
                        self.core_v1.read_namespaced_service(name, ns)
                        self.core_v1.patch_namespaced_service(name, ns, body)
                    except ApiException as e:
                        if e.status == 404:
                            self.core_v1.create_namespaced_service(ns, body)

                # Add more kinds as needed

            return True
        except Exception as e:
            raise Exception(f"Failed to apply manifest: {str(e)}")

    def get_pod_logs(self, pod_name: str, namespace: str, tail_lines: int = 100) -> str:
        """Get logs from a pod"""
        try:
            logs = self.core_v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                tail_lines=tail_lines
            )
            return logs
        except ApiException as e:
            raise Exception(f"Failed to get pod logs: {e.reason}")

    def delete_deployment(self, name: str, namespace: str) -> bool:
        """Delete a deployment"""
        try:
            self.apps_v1.delete_namespaced_deployment(
                name=name,
                namespace=namespace
            )
            return True
        except ApiException as e:
            raise Exception(f"Failed to delete deployment: {e.reason}")

    def delete_pod(self, name: str, namespace: str) -> bool:
        """Delete a pod"""
        try:
            self.core_v1.delete_namespaced_pod(
                name=name,
                namespace=namespace
            )
            return True
        except ApiException as e:
            raise Exception(f"Failed to delete pod: {e.reason}")

    @staticmethod
    def _parse_memory(memory_str: str) -> float:
        """
        Parse Kubernetes memory string to GB

        Args:
            memory_str: Memory string like '4096Mi', '8Gi'

        Returns:
            float: Memory in GB
        """
        if not memory_str:
            return 0.0

        memory_str = memory_str.strip()
        units = {
            'Ki': 1024,
            'Mi': 1024 ** 2,
            'Gi': 1024 ** 3,
            'Ti': 1024 ** 4,
        }

        for unit, multiplier in units.items():
            if memory_str.endswith(unit):
                value = float(memory_str[:-len(unit)])
                return value * multiplier / (1024 ** 3)  # Convert to GB

        # Assume bytes if no unit
        return float(memory_str) / (1024 ** 3)

    def get_custom_resources(self, group: str, version: str, plural: str, namespace: str = None) -> list:
        """
        Get custom resources from the cluster

        Args:
            group: API group (e.g., 'ingress.k8s-orchestrator.io')
            version: API version (e.g., 'v1')
            plural: Resource plural (e.g., 'ingresstemplates')
            namespace: Namespace (optional, if None gets cluster-wide)

        Returns:
            list: List of custom resource objects
        """
        try:
            custom_api = client.CustomObjectsApi(self.api_client)

            if namespace:
                response = custom_api.list_namespaced_custom_object(
                    group=group,
                    version=version,
                    namespace=namespace,
                    plural=plural
                )
            else:
                response = custom_api.list_cluster_custom_object(
                    group=group,
                    version=version,
                    plural=plural
                )

            return response.get('items', [])
        except ApiException as e:
            if e.status == 404:
                return []
            raise Exception(f"Failed to list custom resources: {e.reason}")
