"""
Storage Management Service
Manage Rook-Ceph storage deployment and operations
"""
from typing import Dict, Optional, List
from functions.base import get_db_session
from models.cluster import Cluster
from services.k8s_client_service import K8sClientService
import yaml

class StorageService:
    """Service for managing Rook-Ceph storage"""

    # Rook-Ceph operator version
    ROOK_VERSION = 'v1.13.7'

    @staticmethod
    def install_rook_operator(cluster_id: int) -> Dict:
        """
        Install Rook-Ceph operator on cluster

        Args:
            cluster_id: Cluster database ID

        Returns:
            dict: Installation result
        """
        db = get_db_session()
        try:
            cluster = db.query(Cluster).get(cluster_id)
            if not cluster:
                return {'success': False, 'error': 'Cluster not found'}

            k8s_client = K8sClientService(cluster)

            # Check if rook-ceph namespace already exists
            namespaces = k8s_client.get_namespaces()
            if 'rook-ceph' in namespaces:
                return {
                    'success': False,
                    'error': 'Rook-Ceph operator already installed (namespace exists)'
                }

            # Create rook-ceph namespace
            k8s_client.create_namespace('rook-ceph')

            # Generate Rook operator manifests
            operator_yaml = StorageService._generate_rook_operator_yaml()

            # Apply operator manifests
            try:
                k8s_client.apply_manifest(operator_yaml, namespace='rook-ceph')
            except Exception as e:
                return {
                    'success': False,
                    'error': f'Failed to apply operator manifests: {str(e)}'
                }

            return {
                'success': True,
                'message': 'Rook-Ceph operator installation initiated',
                'instructions': [
                    'Operator deployment started in namespace "rook-ceph"',
                    'Wait 2-3 minutes for operator pods to be ready',
                    'Check status: kubectl get pods -n rook-ceph',
                    'Once operator is ready, create a Ceph cluster'
                ],
                'namespace': 'rook-ceph',
                'version': StorageService.ROOK_VERSION
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            db.close()

    @staticmethod
    def _generate_rook_operator_yaml() -> str:
        """Generate Rook operator YAML manifest"""
        return f"""---
apiVersion: v1
kind: Namespace
metadata:
  name: rook-ceph
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: rook-ceph-operator
  namespace: rook-ceph
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: rook-ceph-operator
rules:
- apiGroups: [""]
  resources: ["pods", "nodes", "nodes/proxy", "services", "endpoints", "persistentvolumes", "persistentvolumeclaims", "events", "configmaps", "secrets", "namespaces"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
- apiGroups: ["storage.k8s.io"]
  resources: ["storageclasses"]
  verbs: ["get", "list", "watch", "create", "update", "delete"]
- apiGroups: ["apps"]
  resources: ["deployments", "daemonsets", "statefulsets"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: rook-ceph-operator
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: rook-ceph-operator
subjects:
- kind: ServiceAccount
  name: rook-ceph-operator
  namespace: rook-ceph
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rook-ceph-operator
  namespace: rook-ceph
  labels:
    app: rook-ceph-operator
spec:
  replicas: 1
  selector:
    matchLabels:
      app: rook-ceph-operator
  template:
    metadata:
      labels:
        app: rook-ceph-operator
    spec:
      serviceAccountName: rook-ceph-operator
      containers:
      - name: rook-ceph-operator
        image: rook/ceph:{StorageService.ROOK_VERSION}
        args: ["ceph", "operator"]
        env:
        - name: ROOK_CURRENT_NAMESPACE_ONLY
          value: "false"
        - name: ROOK_LOG_LEVEL
          value: "INFO"
        - name: ROOK_ENABLE_DISCOVERY_DAEMON
          value: "true"
"""

    @staticmethod
    def create_ceph_cluster(cluster_id: int, config: Dict) -> Dict:
        """
        Create Ceph cluster

        Args:
            cluster_id: Cluster database ID
            config: Ceph cluster configuration

        Returns:
            dict: Creation result
        """
        db = get_db_session()
        try:
            cluster = db.query(Cluster).get(cluster_id)
            if not cluster:
                return {'success': False, 'error': 'Cluster not found'}

            k8s_client = K8sClientService(cluster)

            # Check if operator is installed
            namespaces = k8s_client.get_namespaces()
            if 'rook-ceph' not in namespaces:
                return {
                    'success': False,
                    'error': 'Rook operator not installed. Install operator first.'
                }

            # Generate Ceph cluster manifest
            ceph_cluster_yaml = StorageService._generate_ceph_cluster_yaml(config)

            # Apply Ceph cluster manifest
            try:
                k8s_client.apply_manifest(ceph_cluster_yaml, namespace='rook-ceph')
            except Exception as e:
                return {
                    'success': False,
                    'error': f'Failed to create Ceph cluster: {str(e)}'
                }

            return {
                'success': True,
                'message': 'Ceph cluster creation initiated',
                'instructions': [
                    'Ceph cluster deployment started',
                    'Wait 5-10 minutes for Ceph components to initialize',
                    'Check status: kubectl get cephcluster -n rook-ceph',
                    'Monitor pods: kubectl get pods -n rook-ceph',
                    'Once ready, create storage classes'
                ]
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            db.close()

    @staticmethod
    def _generate_ceph_cluster_yaml(config: Dict) -> str:
        """Generate Ceph cluster YAML manifest"""
        mon_count = config.get('mon_count', 3)
        use_all_devices = config.get('use_all_devices', True)

        return f"""---
apiVersion: ceph.rook.io/v1
kind: CephCluster
metadata:
  name: rook-ceph
  namespace: rook-ceph
spec:
  cephVersion:
    image: quay.io/ceph/ceph:v18.2.0
    allowUnsupported: false
  dataDirHostPath: /var/lib/rook
  mon:
    count: {mon_count}
    allowMultiplePerNode: false
  mgr:
    count: 2
    allowMultiplePerNode: false
  dashboard:
    enabled: true
    ssl: false
  storage:
    useAllNodes: true
    useAllDevices: {str(use_all_devices).lower()}
    deviceFilter: ""
  healthCheck:
    daemonHealth:
      mon:
        interval: 45s
      osd:
        interval: 60s
"""

    @staticmethod
    def get_ceph_status(cluster_id: int) -> Dict:
        """
        Get Ceph cluster health status

        Args:
            cluster_id: Cluster database ID

        Returns:
            dict: Ceph health status
        """
        db = get_db_session()
        try:
            cluster = db.query(Cluster).get(cluster_id)
            if not cluster:
                return {'success': False, 'error': 'Cluster not found'}

            k8s_client = K8sClientService(cluster)

            # Check if Ceph toolbox pod exists
            pods = k8s_client.get_pods(namespace='rook-ceph')
            toolbox_pod = None
            for pod in pods:
                if 'toolbox' in pod['name']:
                    toolbox_pod = pod['name']
                    break

            if not toolbox_pod:
                return {
                    'success': False,
                    'error': 'Ceph toolbox not found. Deploy toolbox to check status.',
                    'instructions': [
                        'Deploy Ceph toolbox:',
                        'kubectl apply -f https://raw.githubusercontent.com/rook/rook/master/deploy/examples/toolbox.yaml',
                        'Wait for toolbox pod to be ready',
                        'Then check status again'
                    ]
                }

            # For now, return basic status
            # In a full implementation, we'd exec into the toolbox and run 'ceph status'
            return {
                'success': True,
                'toolbox_pod': toolbox_pod,
                'message': 'Ceph cluster detected',
                'instructions': [
                    f'To check Ceph status manually:',
                    f'kubectl exec -n rook-ceph {toolbox_pod} -- ceph status',
                    f'kubectl exec -n rook-ceph {toolbox_pod} -- ceph osd status',
                    f'kubectl exec -n rook-ceph {toolbox_pod} -- ceph df'
                ]
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            db.close()

    @staticmethod
    def create_storage_class(cluster_id: int, name: str, storage_type: str = 'block') -> Dict:
        """
        Create Ceph-backed StorageClass

        Args:
            cluster_id: Cluster database ID
            name: StorageClass name
            storage_type: Type (block, filesystem)

        Returns:
            dict: Creation result
        """
        db = get_db_session()
        try:
            cluster = db.query(Cluster).get(cluster_id)
            if not cluster:
                return {'success': False, 'error': 'Cluster not found'}

            k8s_client = K8sClientService(cluster)

            if storage_type == 'block':
                sc_yaml = StorageService._generate_block_storage_class_yaml(name)
            elif storage_type == 'filesystem':
                sc_yaml = StorageService._generate_filesystem_storage_class_yaml(name)
            else:
                return {'success': False, 'error': 'Invalid storage type. Use "block" or "filesystem"'}

            # Apply StorageClass
            try:
                k8s_client.apply_manifest(sc_yaml)
            except Exception as e:
                return {
                    'success': False,
                    'error': f'Failed to create StorageClass: {str(e)}'
                }

            return {
                'success': True,
                'message': f'StorageClass "{name}" created successfully',
                'storage_class': name,
                'type': storage_type
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            db.close()

    @staticmethod
    def _generate_block_storage_class_yaml(name: str) -> str:
        """Generate block StorageClass YAML"""
        return f"""---
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: {name}
provisioner: rook-ceph.rbd.csi.ceph.com
parameters:
  clusterID: rook-ceph
  pool: replicapool
  imageFormat: "2"
  imageFeatures: layering
  csi.storage.k8s.io/provisioner-secret-name: rook-csi-rbd-provisioner
  csi.storage.k8s.io/provisioner-secret-namespace: rook-ceph
  csi.storage.k8s.io/controller-expand-secret-name: rook-csi-rbd-provisioner
  csi.storage.k8s.io/controller-expand-secret-namespace: rook-ceph
  csi.storage.k8s.io/node-stage-secret-name: rook-csi-rbd-node
  csi.storage.k8s.io/node-stage-secret-namespace: rook-ceph
  csi.storage.k8s.io/fstype: ext4
allowVolumeExpansion: true
reclaimPolicy: Delete
"""

    @staticmethod
    def _generate_filesystem_storage_class_yaml(name: str) -> str:
        """Generate filesystem StorageClass YAML"""
        return f"""---
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: {name}
provisioner: rook-ceph.cephfs.csi.ceph.com
parameters:
  clusterID: rook-ceph
  fsName: myfs
  pool: myfs-data0
  csi.storage.k8s.io/provisioner-secret-name: rook-csi-cephfs-provisioner
  csi.storage.k8s.io/provisioner-secret-namespace: rook-ceph
  csi.storage.k8s.io/controller-expand-secret-name: rook-csi-cephfs-provisioner
  csi.storage.k8s.io/controller-expand-secret-namespace: rook-ceph
  csi.storage.k8s.io/node-stage-secret-name: rook-csi-cephfs-node
  csi.storage.k8s.io/node-stage-secret-namespace: rook-ceph
allowVolumeExpansion: true
reclaimPolicy: Delete
"""

    @staticmethod
    def list_storage_classes(cluster_id: int) -> Dict:
        """
        List all StorageClasses in cluster

        Args:
            cluster_id: Cluster database ID

        Returns:
            dict: List of storage classes
        """
        db = get_db_session()
        try:
            cluster = db.query(Cluster).get(cluster_id)
            if not cluster:
                return {'success': False, 'error': 'Cluster not found'}

            k8s_client = K8sClientService(cluster)

            # Get storage classes
            try:
                storage_classes = k8s_client.storage_v1.list_storage_class()
                sc_list = []

                for sc in storage_classes.items:
                    sc_list.append({
                        'name': sc.metadata.name,
                        'provisioner': sc.provisioner,
                        'reclaim_policy': sc.reclaim_policy,
                        'volume_binding_mode': sc.volume_binding_mode,
                        'allow_volume_expansion': sc.allow_volume_expansion
                    })

                return {
                    'success': True,
                    'storage_classes': sc_list
                }

            except Exception as e:
                return {
                    'success': False,
                    'error': f'Failed to list storage classes: {str(e)}'
                }

        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            db.close()
