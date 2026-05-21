"""
Cluster Controller
Handles cluster management routes

Copyright (C) 2026 K8s Orchestrator Contributors
Licensed under GPL-3.0
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from functions.decorators import require_login, require_admin
from services.cluster_service import ClusterService
from services.k8s_client_service import K8sClientService
from services.ssh_cluster_connector import SSHClusterConnector
from typing import Optional
import base64

cluster_bp = Blueprint('cluster', __name__, url_prefix='/clusters')


# ============================================================================
# CLUSTER LISTING
# ============================================================================

@cluster_bp.route('/')
@require_login
def list_clusters():
    """List all clusters"""
    try:
        clusters = ClusterService.get_all_clusters()
        return render_template('clusters/list.html', clusters=clusters)
    except Exception as e:
        flash(f'Error loading clusters: {str(e)}', 'danger')
        return render_template('clusters/list.html', clusters=[])


# ============================================================================
# ADD CLUSTER - ROUTING
# ============================================================================

@cluster_bp.route('/add', methods=['GET'])
@require_admin
def add_cluster():
    """Route to appropriate add cluster form based on method parameter"""
    method = request.args.get('method', 'kubeconfig')

    if method == 'ssh':
        return render_template('clusters/add_ssh.html')
    else:
        return render_template('clusters/add_kubeconfig.html')


@cluster_bp.route('/add/kubeconfig', methods=['POST'])
@require_admin
def add_via_kubeconfig():
    """Add cluster via kubeconfig file upload"""
    try:
        # Validate required fields
        cluster_name = request.form.get('name', '').strip()
        if not cluster_name:
            flash('Cluster name is required', 'danger')
            return redirect(url_for('cluster.add_cluster', method='kubeconfig'))

        # Get kubeconfig from file upload
        kubeconfig_content = _extract_kubeconfig_from_upload()
        if not kubeconfig_content:
            flash('Please upload a valid kubeconfig file', 'danger')
            return redirect(url_for('cluster.add_cluster', method='kubeconfig'))

        # Extract API server URL from kubeconfig
        api_server_url = _extract_api_server_url(kubeconfig_content)

        # Create cluster
        description = request.form.get('description', '').strip()
        cluster = ClusterService.add_cluster(
            name=cluster_name,
            api_server_url=api_server_url,
            kubeconfig_content=kubeconfig_content,
            description=description or f"Added via kubeconfig"
        )

        flash(f'Cluster "{cluster.name}" added successfully!', 'success')
        return redirect(url_for('cluster.detail', cluster_id=cluster.id))

    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('cluster.add_cluster', method='kubeconfig'))
    except Exception as e:
        flash(f'Error adding cluster: {str(e)}', 'danger')
        return redirect(url_for('cluster.add_cluster', method='kubeconfig'))


@cluster_bp.route('/add/ssh', methods=['POST'])
@require_admin
def add_via_ssh():
    """Add cluster via SSH connection"""
    try:
        # Validate required fields
        cluster_name = request.form.get('name', '').strip()
        ssh_host = request.form.get('ssh_host', '').strip()
        ssh_username = request.form.get('ssh_username', '').strip()

        if not all([cluster_name, ssh_host, ssh_username]):
            flash('Cluster name, SSH host, and username are required', 'danger')
            return redirect(url_for('cluster.add_cluster', method='ssh'))

        # Get SSH credentials
        ssh_port = int(request.form.get('ssh_port', 22))
        auth_method = request.form.get('auth_method', 'key')

        ssh_password = None
        ssh_key_content = None

        if auth_method == 'key':
            ssh_key_content = _extract_ssh_private_key()
            if not ssh_key_content:
                flash('Private key is required for key-based authentication', 'danger')
                return redirect(url_for('cluster.add_cluster', method='ssh'))
        else:
            ssh_password = request.form.get('ssh_password', '').strip()
            if not ssh_password:
                flash('Password is required for password authentication', 'danger')
                return redirect(url_for('cluster.add_cluster', method='ssh'))

        # Get kubeconfig path
        kubeconfig_path = _get_kubeconfig_path_from_form()

        # Connect via SSH and retrieve kubeconfig
        connector = SSHClusterConnector(
            host=ssh_host,
            port=ssh_port,
            username=ssh_username,
            private_key=ssh_key_content,
            password=ssh_password
        )

        connection_result = connector.connect_and_retrieve_kubeconfig(
            kubeconfig_path=kubeconfig_path
        )

        if not connection_result['success']:
            flash(f"Connection failed: {connection_result['error']}", 'danger')
            return redirect(url_for('cluster.add_cluster', method='ssh'))

        # Encode kubeconfig
        kubeconfig_content = base64.b64encode(
            connection_result['kubeconfig'].encode('utf-8')
        ).decode('utf-8')

        # Create cluster
        description = request.form.get('description', '').strip()
        cluster = ClusterService.add_cluster(
            name=cluster_name,
            api_server_url=f"https://{ssh_host}:6443",
            kubeconfig_content=kubeconfig_content,
            description=description or f"Connected via SSH from {ssh_host}",
            ssh_config={
                'host': ssh_host,
                'port': ssh_port,
                'username': ssh_username,
                'key_content': ssh_key_content,
                'password': ssh_password
            }
        )

        flash(f'Cluster "{cluster.name}" connected successfully!', 'success')
        return redirect(url_for('cluster.detail', cluster_id=cluster.id))

    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('cluster.add_cluster', method='ssh'))
    except Exception as e:
        flash(f'Error connecting to cluster: {str(e)}', 'danger')
        return redirect(url_for('cluster.add_cluster', method='ssh'))


# ============================================================================
# CLUSTER DETAIL & OPERATIONS
# ============================================================================

@cluster_bp.route('/<int:cluster_id>')
@require_login
def detail(cluster_id: int):
    """Cluster detail view"""
    try:
        cluster = ClusterService.get_cluster(cluster_id)
        if not cluster:
            flash('Cluster not found', 'danger')
            return redirect(url_for('cluster.list_clusters'))

        # Get cluster resources
        k8s_client = K8sClientService(cluster)

        try:
            pods = k8s_client.get_pods()
            deployments = k8s_client.get_deployments()
            namespaces = k8s_client.get_namespaces()
        except Exception as e:
            flash(f'Error loading cluster resources: {str(e)}', 'warning')
            pods = []
            deployments = []
            namespaces = []

        return render_template(
            'clusters/detail.html',
            cluster=cluster,
            pods=pods,
            deployments=deployments,
            namespaces=namespaces
        )

    except Exception as e:
        flash(f'Error loading cluster: {str(e)}', 'danger')
        return redirect(url_for('cluster.list_clusters'))


@cluster_bp.route('/<int:cluster_id>/test', methods=['POST'])
@require_admin
def test_connection(cluster_id: int):
    """Test cluster connectivity"""
    try:
        result = ClusterService.test_connection(cluster_id)

        if result['success']:
            flash(
                f"Connection successful! Version: {result.get('version')}, "
                f"Nodes: {result.get('node_count')}",
                'success'
            )
        else:
            flash(f"Connection failed: {result.get('error')}", 'danger')

        return redirect(url_for('cluster.detail', cluster_id=cluster_id))

    except Exception as e:
        flash(f'Error testing connection: {str(e)}', 'danger')
        return redirect(url_for('cluster.detail', cluster_id=cluster_id))


@cluster_bp.route('/<int:cluster_id>/discover-nodes', methods=['POST'])
@require_admin
def discover_nodes(cluster_id: int):
    """Discover cluster nodes"""
    try:
        nodes = ClusterService.discover_nodes(cluster_id)
        flash(f'Discovered {len(nodes)} node(s)', 'success')
        return redirect(url_for('cluster.detail', cluster_id=cluster_id))

    except Exception as e:
        flash(f'Error discovering nodes: {str(e)}', 'danger')
        return redirect(url_for('cluster.detail', cluster_id=cluster_id))


@cluster_bp.route('/<int:cluster_id>/delete', methods=['POST'])
@require_admin
def delete_cluster(cluster_id: int):
    """Delete cluster"""
    try:
        cluster = ClusterService.get_cluster(cluster_id)
        if not cluster:
            flash('Cluster not found', 'danger')
            return redirect(url_for('cluster.list_clusters'))

        cluster_name = cluster.name
        ClusterService.delete_cluster(cluster_id)

        flash(f'Cluster "{cluster_name}" deleted successfully', 'success')
        return redirect(url_for('cluster.list_clusters'))

    except Exception as e:
        flash(f'Error deleting cluster: {str(e)}', 'danger')
        return redirect(url_for('cluster.list_clusters'))


# ============================================================================
# RESOURCE VIEWS
# ============================================================================

@cluster_bp.route('/<int:cluster_id>/pods')
@require_login
def pods(cluster_id: int):
    """List cluster pods"""
    try:
        cluster = ClusterService.get_cluster(cluster_id)
        if not cluster:
            return jsonify({'error': 'Cluster not found'}), 404

        k8s_client = K8sClientService(cluster)
        namespace = request.args.get('namespace')

        pods = k8s_client.get_pods(namespace=namespace)
        return render_template('resources/pods.html', cluster=cluster, pods=pods)

    except Exception as e:
        flash(f'Error loading pods: {str(e)}', 'danger')
        return redirect(url_for('cluster.detail', cluster_id=cluster_id))


@cluster_bp.route('/<int:cluster_id>/pods/<namespace>/<pod_name>/logs')
@require_login
def pod_logs(cluster_id: int, namespace: str, pod_name: str):
    """Get pod logs"""
    try:
        cluster = ClusterService.get_cluster(cluster_id)
        if not cluster:
            return jsonify({'error': 'Cluster not found'}), 404

        k8s_client = K8sClientService(cluster)
        tail_lines = int(request.args.get('tail', 100))

        logs = k8s_client.get_pod_logs(pod_name, namespace, tail_lines=tail_lines)
        return render_template(
            'resources/logs.html',
            cluster=cluster,
            pod_name=pod_name,
            namespace=namespace,
            logs=logs
        )

    except Exception as e:
        flash(f'Error loading logs: {str(e)}', 'danger')
        return redirect(url_for('cluster.detail', cluster_id=cluster_id))


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _extract_kubeconfig_from_upload() -> Optional[str]:
    """
    Extract kubeconfig content from file upload

    Returns:
        Base64 encoded kubeconfig or None
    """
    if 'kubeconfig_file' not in request.files:
        return None

    file = request.files['kubeconfig_file']
    if not file.filename:
        return None

    try:
        kubeconfig_data = file.read()
        return base64.b64encode(kubeconfig_data).decode('utf-8')
    except Exception:
        return None


def _extract_ssh_private_key() -> Optional[str]:
    """
    Extract SSH private key from file upload or text area

    Returns:
        Private key content or None
    """
    # Try file upload first
    if 'ssh_key_file' in request.files:
        file = request.files['ssh_key_file']
        if file.filename:
            try:
                return file.read().decode('utf-8')
            except Exception:
                pass

    # Fall back to pasted text
    key_text = request.form.get('ssh_key_text', '').strip()
    return key_text if key_text else None


def _get_kubeconfig_path_from_form() -> str:
    """
    Get kubeconfig path from form, handling custom paths

    Returns:
        Kubeconfig file path
    """
    path = request.form.get('kubeconfig_path', '/etc/rancher/k3s/k3s.yaml')

    if path == 'custom':
        custom_path = request.form.get('custom_kubeconfig_path', '').strip()
        if not custom_path:
            raise ValueError('Custom kubeconfig path cannot be empty')
        return custom_path

    return path


def _extract_api_server_url(kubeconfig_b64: str) -> str:
    """
    Extract API server URL from kubeconfig

    Args:
        kubeconfig_b64: Base64 encoded kubeconfig

    Returns:
        API server URL
    """
    try:
        import yaml
        kubeconfig_yaml = base64.b64decode(kubeconfig_b64).decode('utf-8')
        kubeconfig_dict = yaml.safe_load(kubeconfig_yaml)

        if 'clusters' in kubeconfig_dict and len(kubeconfig_dict['clusters']) > 0:
            return kubeconfig_dict['clusters'][0]['cluster']['server']

        return 'https://kubernetes:6443'  # fallback
    except Exception:
        return 'https://kubernetes:6443'  # fallback
