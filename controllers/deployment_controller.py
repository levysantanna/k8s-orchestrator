"""
Deployment Controller
Handles k3s deployment to new servers

Copyright (C) 2026 K8s Orchestrator Contributors
Licensed under GPL-3.0
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from functions.decorators import require_login, require_admin
from services.k3s_deployment_service import K3sDeploymentService
from typing import Optional
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
    """Deploy k3s to a new server"""
    try:
        # Extract and validate form data
        deploy_params = _extract_deployment_parameters()

        if not deploy_params['valid']:
            flash(deploy_params['error'], 'danger')
            return render_template('deployment/k3s_deploy.html')

        # Execute deployment
        result = asyncio.run(
            K3sDeploymentService.deploy_k3s_server(
                cluster_name=deploy_params['cluster_name'],
                ssh_host=deploy_params['ssh_host'],
                ssh_port=deploy_params['ssh_port'],
                ssh_username=deploy_params['ssh_username'],
                ssh_private_key=deploy_params['ssh_private_key'],
                ssh_password=deploy_params.get('ssh_password'),
                k3s_version=deploy_params.get('k3s_version', 'stable')
            )
        )

        if result['success']:
            flash(
                f"k3s deployed successfully! Cluster '{deploy_params['cluster_name']}' is ready.",
                'success'
            )
            return render_template('deployment/k3s_result.html', result=result)
        else:
            flash(f"Deployment failed: {result['error']}", 'danger')
            return render_template('deployment/k3s_deploy.html')

    except Exception as e:
        flash(f'Deployment error: {str(e)}', 'danger')
        return render_template('deployment/k3s_deploy.html')


# ============================================================================
# LEGACY ROUTE - Redirect to new flow
# ============================================================================

@deployment_bp.route('/connect-ssh', methods=['GET'])
@require_admin
def connect_ssh_form():
    """Redirect to new add cluster flow"""
    flash('Please use "Add Existing Cluster via SSH" from the Clusters menu', 'info')
    return redirect(url_for('cluster.add_cluster', method='ssh'))


@deployment_bp.route('/connect-ssh', methods=['POST'])
@require_admin
def connect_ssh():
    """Redirect to new add cluster flow"""
    return redirect(url_for('cluster.add_via_ssh'))


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _extract_deployment_parameters() -> dict:
    """
    Extract and validate deployment parameters from form

    Returns:
        dict with validation status and parameters
    """
    cluster_name = request.form.get('cluster_name', '').strip()
    ssh_host = request.form.get('ssh_host', '').strip()
    ssh_username = request.form.get('ssh_username', '').strip()

    # Validate required fields
    if not all([cluster_name, ssh_host, ssh_username]):
        return {
            'valid': False,
            'error': 'Cluster name, SSH host, and username are required'
        }

    # Extract SSH authentication
    ssh_password = request.form.get('ssh_password', '').strip()
    ssh_private_key = _extract_ssh_key_from_form()

    if not ssh_private_key and not ssh_password:
        return {
            'valid': False,
            'error': 'Either private key or password must be provided'
        }

    # Extract optional parameters
    ssh_port = int(request.form.get('ssh_port', 22))
    k3s_version = request.form.get('k3s_version', 'stable').strip()

    return {
        'valid': True,
        'cluster_name': cluster_name,
        'ssh_host': ssh_host,
        'ssh_port': ssh_port,
        'ssh_username': ssh_username,
        'ssh_private_key': ssh_private_key,
        'ssh_password': ssh_password if ssh_password else None,
        'k3s_version': k3s_version
    }


def _extract_ssh_key_from_form() -> Optional[str]:
    """
    Extract SSH private key from file upload or textarea

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

    # Fall back to pasted content
    key_content = request.form.get('ssh_key_content', '').strip()
    return key_content if key_content else None
