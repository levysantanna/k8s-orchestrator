"""
Node Scaling Service
Manage Kubernetes cluster node scaling operations
"""
from typing import Dict, Optional
from datetime import datetime
from functions.base import get_db_session
from models.cluster import Cluster, Node
from services.k8s_client_service import K8sClientService
import base64

class NodeService:
    """Service for managing cluster node scaling"""

    @staticmethod
    def generate_join_command(cluster_id: int, role: str = 'worker') -> Dict:
        """
        Generate command to join a new node to the cluster

        Args:
            cluster_id: Cluster database ID
            role: Node role (master or worker)

        Returns:
            dict: Join command and token information
        """
        db = get_db_session()
        try:
            cluster = db.query(Cluster).get(cluster_id)
            if not cluster:
                return {'success': False, 'error': 'Cluster not found'}

            # Initialize K8s client
            k8s_client = K8sClientService(cluster)

            # Try to detect cluster type (k3s, kubeadm, etc.)
            cluster_type = NodeService._detect_cluster_type(k8s_client)

            if cluster_type == 'k3s':
                return NodeService._generate_k3s_join_command(cluster, role)
            elif cluster_type == 'kubeadm':
                return NodeService._generate_kubeadm_join_command(k8s_client, role)
            else:
                return {
                    'success': False,
                    'error': 'Unknown cluster type. Manual join required.'
                }

        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            db.close()

    @staticmethod
    def _detect_cluster_type(k8s_client: K8sClientService) -> str:
        """
        Detect Kubernetes distribution type

        Args:
            k8s_client: Kubernetes client service

        Returns:
            str: Cluster type (k3s, kubeadm, unknown)
        """
        try:
            # Check nodes for k3s labels
            nodes = k8s_client.get_nodes()
            if nodes and any('k3s' in node.get('kubelet_version', '').lower() for node in nodes):
                return 'k3s'

            # Check for kubeadm config
            namespaces = k8s_client.get_namespaces()
            if 'kube-public' in namespaces:
                return 'kubeadm'

            return 'unknown'
        except Exception:
            return 'unknown'

    @staticmethod
    def _generate_k3s_join_command(cluster: Cluster, role: str = 'worker') -> Dict:
        """
        Generate k3s join command

        Args:
            cluster: Cluster model
            role: Node role (master or worker)

        Returns:
            dict: Join command information
        """
        # Extract server URL from API server
        server_url = cluster.api_server_url.replace(':6443', ':6443')

        if role == 'master':
            command = f"""# K3s Server (Control Plane) Join Command
# Run this on the new master node:

curl -sfL https://get.k3s.io | K3S_URL={server_url} K3S_TOKEN=<YOUR_K3S_TOKEN> sh -s - server

# To get your K3S_TOKEN, run on existing master:
# sudo cat /var/lib/rancher/k3s/server/node-token
"""
        else:
            command = f"""# K3s Agent (Worker) Join Command
# Run this on the new worker node:

curl -sfL https://get.k3s.io | K3S_URL={server_url} K3S_TOKEN=<YOUR_K3S_TOKEN> sh -

# To get your K3S_TOKEN, run on master node:
# sudo cat /var/lib/rancher/k3s/server/node-token
"""

        return {
            'success': True,
            'cluster_type': 'k3s',
            'role': role,
            'command': command,
            'server_url': server_url,
            'instructions': [
                '1. Get K3S_TOKEN from master node: sudo cat /var/lib/rancher/k3s/server/node-token',
                '2. Replace <YOUR_K3S_TOKEN> in the command with the actual token',
                '3. Run the command on the new node',
                '4. Wait 30-60 seconds for the node to appear in the cluster',
                '5. Click "Discover Nodes" to sync the new node to the orchestrator'
            ]
        }

    @staticmethod
    def _generate_kubeadm_join_command(k8s_client: K8sClientService, role: str = 'worker') -> Dict:
        """
        Generate kubeadm join command

        Args:
            k8s_client: Kubernetes client service
            role: Node role (master or worker)

        Returns:
            dict: Join command information
        """
        command = f"""# Kubeadm Join Command
# Generate the actual join command on the master node:

# For worker nodes:
kubeadm token create --print-join-command

# For control plane nodes:
kubeadm token create --print-join-command --certificate-key $(kubeadm init phase upload-certs --upload-certs | tail -1)

# Then run the generated command on the new node
"""

        return {
            'success': True,
            'cluster_type': 'kubeadm',
            'role': role,
            'command': command,
            'instructions': [
                '1. SSH to an existing master node',
                '2. Run the kubeadm command shown above to generate the join command',
                '3. Copy the generated join command',
                '4. Run it on the new node',
                '5. Wait for the node to join (30-60 seconds)',
                '6. Click "Discover Nodes" to sync the new node'
            ]
        }

    @staticmethod
    def drain_node(cluster_id: int, node_name: str, force: bool = False) -> Dict:
        """
        Drain a node (prepare for removal)

        Args:
            cluster_id: Cluster database ID
            node_name: Node name to drain
            force: Force drain (ignore daemonsets)

        Returns:
            dict: Operation result
        """
        db = get_db_session()
        try:
            cluster = db.query(Cluster).get(cluster_id)
            if not cluster:
                return {'success': False, 'error': 'Cluster not found'}

            k8s_client = K8sClientService(cluster)

            # Cordon the node (mark as unschedulable)
            try:
                node = k8s_client.core_v1.read_node(node_name)
                node.spec.unschedulable = True
                k8s_client.core_v1.patch_node(node_name, node)
            except Exception as e:
                return {'success': False, 'error': f'Failed to cordon node: {str(e)}'}

            # Note: Actual pod eviction would require more complex logic
            # For now, we just cordon the node and provide instructions

            return {
                'success': True,
                'message': f'Node {node_name} cordoned successfully',
                'instructions': [
                    'Node is now cordoned (marked unschedulable)',
                    'To complete draining, run on cluster master:',
                    f'kubectl drain {node_name} --ignore-daemonsets --delete-emptydir-data',
                    'After pods are evicted, you can safely remove the node'
                ]
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            db.close()

    @staticmethod
    def remove_node(cluster_id: int, node_name: str) -> Dict:
        """
        Remove a node from the cluster

        Args:
            cluster_id: Cluster database ID
            node_name: Node name to remove

        Returns:
            dict: Operation result
        """
        db = get_db_session()
        try:
            cluster = db.query(Cluster).get(cluster_id)
            if not cluster:
                return {'success': False, 'error': 'Cluster not found'}

            k8s_client = K8sClientService(cluster)

            # Delete node from Kubernetes
            try:
                k8s_client.core_v1.delete_node(node_name)
            except Exception as e:
                return {'success': False, 'error': f'Failed to delete node from cluster: {str(e)}'}

            # Remove from database
            db_node = db.query(Node).filter_by(cluster_id=cluster_id, name=node_name).first()
            if db_node:
                db.delete(db_node)

            # Update cluster node count
            cluster.node_count = db.query(Node).filter_by(cluster_id=cluster_id).count()
            db.commit()

            return {
                'success': True,
                'message': f'Node {node_name} removed successfully',
                'instructions': [
                    'Node removed from Kubernetes cluster',
                    'On the removed node, clean up k3s/kubeadm:',
                    'For k3s: /usr/local/bin/k3s-agent-uninstall.sh (or k3s-uninstall.sh)',
                    'For kubeadm: kubeadm reset'
                ]
            }

        except Exception as e:
            db.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            db.close()

    @staticmethod
    def get_capacity_info(cluster_id: int) -> Dict:
        """
        Get cluster capacity and resource utilization

        Args:
            cluster_id: Cluster database ID

        Returns:
            dict: Capacity information
        """
        db = get_db_session()
        try:
            cluster = db.query(Cluster).get(cluster_id)
            if not cluster:
                return {'success': False, 'error': 'Cluster not found'}

            k8s_client = K8sClientService(cluster)
            nodes = k8s_client.get_nodes()

            total_cpu = sum(node.get('cpu_cores', 0) for node in nodes)
            total_memory_gb = sum(node.get('memory_gb', 0) for node in nodes)

            # Get pod count
            pods = k8s_client.get_pods()
            total_pods = len(pods)
            running_pods = len([p for p in pods if p['status'] == 'Running'])

            # Calculate pod density
            pod_density = total_pods / len(nodes) if nodes else 0

            # Simple capacity recommendation
            recommend_scale = False
            recommendation = ''

            if pod_density > 30:
                recommend_scale = True
                recommendation = 'High pod density detected. Consider adding nodes.'
            elif total_pods > (len(nodes) * 110):  # Default max pods per node is 110
                recommend_scale = True
                recommendation = 'Approaching pod limit. Add nodes to increase capacity.'

            return {
                'success': True,
                'total_nodes': len(nodes),
                'total_cpu_cores': total_cpu,
                'total_memory_gb': round(total_memory_gb, 2),
                'total_pods': total_pods,
                'running_pods': running_pods,
                'pod_density': round(pod_density, 2),
                'recommend_scale': recommend_scale,
                'recommendation': recommendation
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            db.close()
