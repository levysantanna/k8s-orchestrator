"""
Cluster Management Service
Business logic for cluster operations
"""
import base64
from datetime import datetime
from typing import Dict, List, Optional
from functions.base import get_db_session
from models.cluster import Cluster, ClusterStatus, ClusterConnectionType, Node
from services.k8s_client_service import K8sClientService

class ClusterService:
    """Service for managing Kubernetes clusters"""

    @staticmethod
    def add_cluster(name: str, api_server_url: str, kubeconfig_content: Optional[str] = None,
                   description: Optional[str] = None, ssh_config: Optional[Dict] = None) -> Cluster:
        """
        Add new cluster to database

        Args:
            name: Cluster name
            api_server_url: Kubernetes API server URL
            kubeconfig_content: Base64 encoded kubeconfig (optional)
            description: Cluster description
            ssh_config: SSH configuration dict (optional)

        Returns:
            Cluster: Created cluster object
        """
        db = get_db_session()
        try:
            # Check if cluster already exists
            existing = db.query(Cluster).filter_by(name=name).first()
            if existing:
                raise ValueError(f"Cluster with name '{name}' already exists")

            # Create cluster
            cluster = Cluster(
                name=name,
                description=description,
                api_server_url=api_server_url,
                kubeconfig_content=kubeconfig_content,
                connection_type=ClusterConnectionType.KUBECONFIG if kubeconfig_content else ClusterConnectionType.SSH,
                status=ClusterStatus.INITIALIZING,
            )

            # Add SSH config if provided
            if ssh_config:
                cluster.ssh_host = ssh_config.get('host')
                cluster.ssh_port = ssh_config.get('port', 22)
                cluster.ssh_username = ssh_config.get('username')
                cluster.ssh_key_content = ssh_config.get('key_content')
                cluster.ssh_password = ssh_config.get('password')

            db.add(cluster)
            db.commit()
            db.refresh(cluster)

            # Test connection
            try:
                connection_result = ClusterService.test_connection(cluster.id)
                if connection_result['success']:
                    cluster.status = ClusterStatus.ACTIVE
                    cluster.health_status = 'healthy'
                    cluster.kubernetes_version = connection_result.get('version')
                    cluster.last_seen = datetime.utcnow()

                    # Discover nodes
                    ClusterService.discover_nodes(cluster.id)
                else:
                    cluster.status = ClusterStatus.ERROR
                    cluster.health_status = 'unreachable'

                db.commit()
            except Exception as e:
                cluster.status = ClusterStatus.ERROR
                db.commit()
                raise

            return cluster

        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def test_connection(cluster_id: int) -> Dict:
        """
        Test cluster connectivity

        Args:
            cluster_id: Cluster database ID

        Returns:
            dict: Connection test result
        """
        db = get_db_session()
        try:
            cluster = db.query(Cluster).get(cluster_id)
            if not cluster:
                return {'success': False, 'error': 'Cluster not found'}

            # Initialize K8s client
            k8s_client = K8sClientService(cluster)

            # Test connection
            result = k8s_client.test_connection()

            if result['success']:
                # Update cluster metadata
                cluster.last_seen = datetime.utcnow()
                cluster.kubernetes_version = result.get('version')
                cluster.node_count = result.get('node_count', 0)
                db.commit()

            return result

        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            db.close()

    @staticmethod
    def discover_nodes(cluster_id: int) -> List[Node]:
        """
        Discover and sync nodes from Kubernetes API

        Args:
            cluster_id: Cluster database ID

        Returns:
            list: List of discovered nodes
        """
        db = get_db_session()
        try:
            cluster = db.query(Cluster).get(cluster_id)
            if not cluster:
                raise ValueError('Cluster not found')

            # Get nodes from K8s API
            k8s_client = K8sClientService(cluster)
            api_nodes = k8s_client.get_nodes()

            discovered_nodes = []
            for node_data in api_nodes:
                # Check if node already exists
                existing_node = db.query(Node).filter_by(
                    cluster_id=cluster_id,
                    name=node_data['name']
                ).first()

                if existing_node:
                    # Update existing node
                    existing_node.ip_address = node_data['ip_address']
                    existing_node.role = node_data['role']
                    existing_node.status = node_data['status']
                    existing_node.kubelet_version = node_data['kubelet_version']
                    existing_node.cpu_cores = node_data['cpu_cores']
                    existing_node.memory_gb = node_data['memory_gb']
                    existing_node.last_seen = datetime.utcnow()
                    discovered_nodes.append(existing_node)
                else:
                    # Create new node
                    new_node = Node(
                        cluster_id=cluster_id,
                        name=node_data['name'],
                        ip_address=node_data['ip_address'],
                        role=node_data['role'],
                        status=node_data['status'],
                        kubelet_version=node_data['kubelet_version'],
                        cpu_cores=node_data['cpu_cores'],
                        memory_gb=node_data['memory_gb'],
                        last_seen=datetime.utcnow(),
                    )
                    db.add(new_node)
                    discovered_nodes.append(new_node)

            # Update cluster node count
            cluster.node_count = len(discovered_nodes)
            db.commit()

            return discovered_nodes

        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def get_all_clusters() -> List[Cluster]:
        """Get all clusters"""
        db = get_db_session()
        try:
            return db.query(Cluster).all()
        finally:
            db.close()

    @staticmethod
    def get_cluster(cluster_id: int) -> Optional[Cluster]:
        """Get cluster by ID"""
        db = get_db_session()
        try:
            return db.query(Cluster).get(cluster_id)
        finally:
            db.close()

    @staticmethod
    def delete_cluster(cluster_id: int) -> bool:
        """Delete cluster and all related data"""
        db = get_db_session()
        try:
            cluster = db.query(Cluster).get(cluster_id)
            if not cluster:
                return False

            db.delete(cluster)
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def update_cluster_status(cluster_id: int, status: ClusterStatus, health_status: Optional[str] = None):
        """Update cluster status"""
        db = get_db_session()
        try:
            cluster = db.query(Cluster).get(cluster_id)
            if cluster:
                cluster.status = status
                if health_status:
                    cluster.health_status = health_status
                cluster.last_seen = datetime.utcnow()
                db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
