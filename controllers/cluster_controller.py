from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from functions.decorators import require_login, require_admin
from services.cluster_service import ClusterService
from services.k8s_client_service import K8sClientService
import base64

cluster_bp = Blueprint('cluster', __name__, url_prefix='/clusters')

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

@cluster_bp.route('/add', methods=['GET', 'POST'])
@require_admin
def add_cluster():
    """Add new cluster"""
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            description = request.form.get('description')
            api_server_url = request.form.get('api_server_url')

            if not name or not api_server_url:
                flash('Cluster name and API server URL are required', 'danger')
                return render_template('clusters/add.html')

            # Handle kubeconfig file upload
            kubeconfig_content = None
            if 'kubeconfig_file' in request.files:
                file = request.files['kubeconfig_file']
                if file.filename:
                    kubeconfig_data = file.read()
                    kubeconfig_content = base64.b64encode(kubeconfig_data).decode('utf-8')

            # Handle SSH configuration
            ssh_config = None
            if request.form.get('use_ssh') == 'on':
                ssh_config = {
                    'host': request.form.get('ssh_host'),
                    'port': int(request.form.get('ssh_port', 22)),
                    'username': request.form.get('ssh_username'),
                    'password': request.form.get('ssh_password'),
                }

            # Add cluster
            cluster = ClusterService.add_cluster(
                name=name,
                api_server_url=api_server_url,
                kubeconfig_content=kubeconfig_content,
                description=description,
                ssh_config=ssh_config
            )

            flash(f'Cluster "{cluster.name}" added successfully!', 'success')
            return redirect(url_for('cluster.detail', cluster_id=cluster.id))

        except ValueError as e:
            flash(str(e), 'danger')
            return render_template('clusters/add.html')
        except Exception as e:
            flash(f'Error adding cluster: {str(e)}', 'danger')
            return render_template('clusters/add.html')

    return render_template('clusters/add.html')

@cluster_bp.route('/<int:cluster_id>')
@require_login
def detail(cluster_id):
    """Cluster detail view"""
    try:
        cluster = ClusterService.get_cluster(cluster_id)
        if not cluster:
            flash('Cluster not found', 'danger')
            return redirect(url_for('cluster.list_clusters'))

        # Get cluster nodes
        k8s_client = K8sClientService(cluster)

        # Get resources
        try:
            pods = k8s_client.get_pods()
            deployments = k8s_client.get_deployments()
            namespaces = k8s_client.get_namespaces()
        except Exception as e:
            flash(f'Error loading cluster resources: {str(e)}', 'warning')
            pods = []
            deployments = []
            namespaces = []

        return render_template('clusters/detail.html',
                             cluster=cluster,
                             pods=pods,
                             deployments=deployments,
                             namespaces=namespaces)

    except Exception as e:
        flash(f'Error loading cluster: {str(e)}', 'danger')
        return redirect(url_for('cluster.list_clusters'))

@cluster_bp.route('/<int:cluster_id>/test', methods=['POST'])
@require_admin
def test_connection(cluster_id):
    """Test cluster connectivity"""
    try:
        result = ClusterService.test_connection(cluster_id)

        if result['success']:
            flash(f"Connection successful! Version: {result.get('version')}, Nodes: {result.get('node_count')}", 'success')
        else:
            flash(f"Connection failed: {result.get('error')}", 'danger')

        return redirect(url_for('cluster.detail', cluster_id=cluster_id))

    except Exception as e:
        flash(f'Error testing connection: {str(e)}', 'danger')
        return redirect(url_for('cluster.detail', cluster_id=cluster_id))

@cluster_bp.route('/<int:cluster_id>/discover-nodes', methods=['POST'])
@require_admin
def discover_nodes(cluster_id):
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
def delete_cluster(cluster_id):
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

@cluster_bp.route('/<int:cluster_id>/pods')
@require_login
def pods(cluster_id):
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
def pod_logs(cluster_id, namespace, pod_name):
    """Get pod logs"""
    try:
        cluster = ClusterService.get_cluster(cluster_id)
        if not cluster:
            return jsonify({'error': 'Cluster not found'}), 404

        k8s_client = K8sClientService(cluster)
        tail_lines = int(request.args.get('tail', 100))

        logs = k8s_client.get_pod_logs(pod_name, namespace, tail_lines=tail_lines)
        return render_template('resources/logs.html',
                             cluster=cluster,
                             pod_name=pod_name,
                             namespace=namespace,
                             logs=logs)

    except Exception as e:
        flash(f'Error loading logs: {str(e)}', 'danger')
        return redirect(url_for('cluster.detail', cluster_id=cluster_id))
