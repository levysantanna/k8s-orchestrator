"""
K3s Deployment Controller
Handle remote k3s deployments via web interface

Copyright (C) 2026 K8s Orchestrator Contributors
Licensed under GPL-3.0
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from functions.decorators import require_login, require_admin
from services.k3s_deployment_service import K3sDeploymentService
import asyncio

deployment_bp = Blueprint('deployment', __name__, url_prefix='/deployment')

@deployment_bp.route('/k3s', methods=['GET'])
@require_admin
def k3s_deploy_form():
    """Show k3s deployment form"""
    return render_template('deployment/k3s_deploy.html')

@deployment_bp.route('/k3s', methods=['POST'])
@require_admin
def k3s_deploy():
    """Deploy k3s to remote server"""
    try:
        cluster_name = request.form.get('cluster_name')
        ssh_host = request.form.get('ssh_host')
        ssh_port = int(request.form.get('ssh_port', 22))
        ssh_username = request.form.get('ssh_username')
        ssh_password = request.form.get('ssh_password')
        k3s_version = request.form.get('k3s_version', 'stable')

        # Handle SSH key upload
        ssh_key_content = None
        if 'ssh_key_file' in request.files:
            key_file = request.files['ssh_key_file']
            if key_file.filename:
                ssh_key_content = key_file.read().decode('utf-8')
        else:
            # Use textarea input
            ssh_key_content = request.form.get('ssh_key_content')

        if not all([cluster_name, ssh_host, ssh_username, ssh_key_content]):
            flash('Please provide all required fields', 'danger')
            return render_template('deployment/k3s_deploy.html')

        # Run async deployment
        result = asyncio.run(
            K3sDeploymentService.deploy_k3s_server(
                cluster_name=cluster_name,
                ssh_host=ssh_host,
                ssh_port=ssh_port,
                ssh_username=ssh_username,
                ssh_private_key=ssh_key_content,
                ssh_password=ssh_password if ssh_password else None,
                k3s_version=k3s_version
            )
        )

        if result['success']:
            flash(f"k3s deployed successfully! Cluster '{cluster_name}' is ready.", 'success')
            return render_template('deployment/k3s_result.html', result=result)
        else:
            flash(f"Deployment failed: {result['error']}", 'danger')
            return render_template('deployment/k3s_deploy.html')

    except Exception as e:
        flash(f'Deployment error: {str(e)}', 'danger')
        return render_template('deployment/k3s_deploy.html')

@deployment_bp.route('/connect-ssh', methods=['GET'])
@require_admin
def connect_ssh_form():
    """Show SSH cluster connection form"""
    return render_template('deployment/connect_ssh.html')

@deployment_bp.route('/connect-ssh', methods=['POST'])
@require_admin
def connect_ssh():
    """Connect to existing cluster via SSH (retrieve kubeconfig)"""
    try:
        from services.cluster_service import ClusterService
        import base64

        cluster_name = request.form.get('cluster_name')
        ssh_host = request.form.get('ssh_host')
        ssh_port = int(request.form.get('ssh_port', 22))
        ssh_username = request.form.get('ssh_username')
        ssh_password = request.form.get('ssh_password')

        # Handle SSH key
        ssh_key_content = None
        if 'ssh_key_file' in request.files:
            key_file = request.files['ssh_key_file']
            if key_file.filename:
                ssh_key_content = key_file.read().decode('utf-8')
        else:
            ssh_key_content = request.form.get('ssh_key_content')

        if not all([cluster_name, ssh_host, ssh_username, ssh_key_content]):
            flash('Please provide all required fields', 'danger')
            return render_template('deployment/connect_ssh.html')

        # Connect and retrieve kubeconfig
        result = asyncio.run(
            K3sDeploymentService._connect_ssh(
                ssh_host, ssh_port, ssh_username, ssh_key_content, ssh_password
            )
        )

        if not result['success']:
            flash(result['error'], 'danger')
            return render_template('deployment/connect_ssh.html')

        conn = result['connection']

        # Try to get kubeconfig
        kubeconfig_result = asyncio.run(
            K3sDeploymentService._get_kubeconfig(conn, ssh_host)
        )

        asyncio.run(conn.close())

        if not kubeconfig_result['success']:
            flash(kubeconfig_result['error'], 'danger')
            return render_template('deployment/connect_ssh.html')

        # Encode kubeconfig
        kubeconfig_b64 = base64.b64encode(
            kubeconfig_result['kubeconfig'].encode('utf-8')
        ).decode('utf-8')

        # Add cluster to database
        cluster = ClusterService.add_cluster(
            name=cluster_name,
            api_server_url=f"https://{ssh_host}:6443",
            kubeconfig_content=kubeconfig_b64,
            description="Connected via SSH",
            ssh_config={
                'host': ssh_host,
                'port': ssh_port,
                'username': ssh_username,
                'key_content': ssh_key_content
            }
        )

        flash(f"Successfully connected to cluster '{cluster_name}'!", 'success')
        return redirect(url_for('cluster.detail', cluster_id=cluster.id))

    except Exception as e:
        flash(f'Connection error: {str(e)}', 'danger')
        return render_template('deployment/connect_ssh.html')
