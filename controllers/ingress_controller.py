"""
Ingress Controller
Handles web UI routes for IngressTemplate management
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from functions.auth import require_login, require_admin
from functions.base import get_db_session
from models.cluster import Cluster
from services.ingress_service import IngressService
from services.ingress_presets import get_preset_names, get_preset, merge_preset_with_values
import logging

logger = logging.getLogger(__name__)

ingress_bp = Blueprint('ingress', __name__, url_prefix='/ingress')


@ingress_bp.route('/')
@require_login
def list_all():
    """List all IngressTemplates across all clusters"""
    db = get_db_session()
    try:
        clusters = db.query(Cluster).all()

        # Aggregate templates from all clusters
        all_templates = []
        for cluster in clusters:
            try:
                templates = IngressService.get_ingress_templates(cluster.id)
                for template in templates:
                    template['cluster'] = {
                        'id': cluster.id,
                        'name': cluster.name
                    }
                    all_templates.append(template)
            except Exception as e:
                logger.error(f"Error fetching templates from cluster {cluster.name}: {e}")
                flash(f"Error fetching templates from {cluster.name}: {str(e)}", 'warning')

        return render_template('ingress/list.html', templates=all_templates, clusters=clusters)
    finally:
        db.close()


@ingress_bp.route('/cluster/<int:cluster_id>')
@require_login
def list_cluster(cluster_id):
    """List IngressTemplates for a specific cluster"""
    db = get_db_session()
    try:
        cluster = db.query(Cluster).filter_by(id=cluster_id).first()
        if not cluster:
            flash('Cluster not found', 'danger')
            return redirect(url_for('ingress.list_all'))

        templates = IngressService.get_ingress_templates(cluster_id)

        # Add cluster info to each template
        for template in templates:
            template['cluster'] = {
                'id': cluster.id,
                'name': cluster.name
            }

        return render_template('ingress/list.html', templates=templates, cluster=cluster)
    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        flash(f'Error listing templates: {str(e)}', 'danger')
        return redirect(url_for('dashboard.index'))
    finally:
        db.close()


@ingress_bp.route('/<int:cluster_id>/create', methods=['GET', 'POST'])
@require_admin
def create(cluster_id):
    """Create new IngressTemplate"""
    db = get_db_session()
    try:
        cluster = db.query(Cluster).filter_by(id=cluster_id).first()
        if not cluster:
            flash('Cluster not found', 'danger')
            return redirect(url_for('ingress.list_all'))

        if request.method == 'GET':
            # Get preset parameter
            preset_id = request.args.get('preset', 'standard-app-wildcard')
            preset = get_preset(preset_id) if preset_id else None

            # Get namespaces for dropdown
            from services.k8s_client_service import K8sClientService
            k8s_client = K8sClientService(
                kubeconfig_content=cluster.kubeconfig_content,
                cluster_name=cluster.name
            )
            namespaces = [ns['name'] for ns in k8s_client.get_namespaces()]

            return render_template(
                'ingress/create.html',
                cluster=cluster,
                namespaces=namespaces,
                presets=get_preset_names(),
                selected_preset=preset
            )

        # POST - Create template
        try:
            # Extract form data
            host = request.form.get('host', '').strip()
            namespace = request.form.get('namespace', 'default').strip()
            backend_type = request.form.get('backend_type', 'service')

            # Validation
            if not host:
                flash('Host is required', 'danger')
                return redirect(url_for('ingress.create', cluster_id=cluster_id))

            if not IngressService.validate_host(host):
                flash(f'Invalid hostname: {host}', 'danger')
                return redirect(url_for('ingress.create', cluster_id=cluster_id))

            # Generate resource name
            name = IngressService.generate_resource_name(host)

            # Build spec based on backend type
            spec = {
                'enabled': True,
                'host': host,
                'ingressClassName': request.form.get('ingress_class', 'traefik')
            }

            # TLS configuration
            tls_enabled = request.form.get('tls_enabled') == 'on'
            spec['tls'] = {'enabled': tls_enabled}

            if tls_enabled:
                use_wildcard = request.form.get('use_wildcard') == 'on'
                spec['tls']['useWildcard'] = use_wildcard

                if use_wildcard:
                    spec['tls']['wildcardSecretName'] = request.form.get(
                        'wildcard_secret',
                        'wildcard-comunatec-org-tls'
                    )
                else:
                    spec['tls']['clusterIssuer'] = request.form.get(
                        'cluster_issuer',
                        'letsencrypt-prod'
                    )

            # Backend configuration
            if backend_type == 'external':
                external_ip = request.form.get('external_ip', '').strip()
                if not external_ip:
                    flash('External IP is required for external backend', 'danger')
                    return redirect(url_for('ingress.create', cluster_id=cluster_id))

                spec['backend'] = {
                    'type': 'external',
                    'externalIP': external_ip,
                    'externalPort': int(request.form.get('external_port', 80)),
                }

                # Optional HTTPS port
                external_https_port = request.form.get('external_https_port')
                if external_https_port:
                    spec['backend']['externalHttpsPort'] = int(external_https_port)

            else:  # service
                service_name = request.form.get('service_name', '').strip()
                service_port = request.form.get('service_port')

                if not service_name or not service_port:
                    flash('Service name and port are required for service backend', 'danger')
                    return redirect(url_for('ingress.create', cluster_id=cluster_id))

                spec['backend'] = {
                    'type': 'service',
                    'serviceName': service_name,
                    'servicePort': int(service_port)
                }

            # Custom annotations
            custom_annotations = request.form.get('custom_annotations', '').strip()
            if custom_annotations:
                annotations = {}
                for line in custom_annotations.split('\n'):
                    line = line.strip()
                    if ':' in line:
                        key, value = line.split(':', 1)
                        annotations[key.strip()] = value.strip()
                spec['annotations'] = annotations
            else:
                # Default Traefik annotations
                spec['annotations'] = {
                    'traefik.ingress.kubernetes.io/router.entrypoints': 'web,websecure'
                }

            # Create template
            IngressService.create_ingress_template(cluster_id, namespace, name, spec)

            flash(f'IngressTemplate "{name}" created successfully in {namespace} namespace', 'success')
            return redirect(url_for('ingress.detail', cluster_id=cluster_id, namespace=namespace, name=name))

        except Exception as e:
            logger.error(f"Error creating ingress template: {e}")
            flash(f'Error creating template: {str(e)}', 'danger')
            return redirect(url_for('ingress.create', cluster_id=cluster_id))

    finally:
        db.close()


@ingress_bp.route('/<int:cluster_id>/<namespace>/<name>')
@require_login
def detail(cluster_id, namespace, name):
    """View IngressTemplate details"""
    db = get_db_session()
    try:
        cluster = db.query(Cluster).filter_by(id=cluster_id).first()
        if not cluster:
            flash('Cluster not found', 'danger')
            return redirect(url_for('ingress.list_all'))

        template = IngressService.get_ingress_template(cluster_id, namespace, name)
        if not template:
            flash('Template not found', 'danger')
            return redirect(url_for('ingress.list_cluster', cluster_id=cluster_id))

        # Get associated ingress
        ingresses = IngressService.get_created_ingresses(cluster_id, namespace)
        associated_ingress = None
        for ing in ingresses:
            if ing.get('template') == name:
                associated_ingress = ing
                break

        return render_template(
            'ingress/detail.html',
            cluster=cluster,
            template=template,
            ingress=associated_ingress
        )

    except Exception as e:
        logger.error(f"Error viewing template: {e}")
        flash(f'Error viewing template: {str(e)}', 'danger')
        return redirect(url_for('ingress.list_all'))
    finally:
        db.close()


@ingress_bp.route('/<int:cluster_id>/<namespace>/<name>/delete', methods=['POST'])
@require_admin
def delete(cluster_id, namespace, name):
    """Delete IngressTemplate"""
    try:
        IngressService.delete_ingress_template(cluster_id, namespace, name)
        flash(f'IngressTemplate "{name}" deleted successfully', 'success')
    except Exception as e:
        logger.error(f"Error deleting template: {e}")
        flash(f'Error deleting template: {str(e)}', 'danger')

    return redirect(url_for('ingress.list_cluster', cluster_id=cluster_id))


@ingress_bp.route('/<int:cluster_id>/<namespace>/<name>/toggle', methods=['POST'])
@require_admin
def toggle(cluster_id, namespace, name):
    """Enable or disable IngressTemplate"""
    try:
        enabled = request.form.get('enabled') == 'true'
        IngressService.toggle_template(cluster_id, namespace, name, enabled)

        status = 'enabled' if enabled else 'disabled'
        flash(f'IngressTemplate "{name}" {status} successfully', 'success')
    except Exception as e:
        logger.error(f"Error toggling template: {e}")
        flash(f'Error toggling template: {str(e)}', 'danger')

    return redirect(url_for('ingress.detail', cluster_id=cluster_id, namespace=namespace, name=name))


@ingress_bp.route('/<int:cluster_id>/<namespace>/<name>/yaml')
@require_login
def export_yaml(cluster_id, namespace, name):
    """Export IngressTemplate as YAML"""
    try:
        yaml_content = IngressService.export_yaml(cluster_id, namespace, name)
        return yaml_content, 200, {'Content-Type': 'text/plain; charset=utf-8'}
    except Exception as e:
        logger.error(f"Error exporting YAML: {e}")
        return f"Error: {str(e)}", 500


@ingress_bp.route('/api/clusters/<int:cluster_id>/namespaces/<namespace>/services')
@require_login
def api_list_services(cluster_id, namespace):
    """API endpoint to list services in a namespace (for AJAX)"""
    try:
        services = IngressService.get_available_services(cluster_id, namespace)
        return jsonify(services)
    except Exception as e:
        logger.error(f"Error listing services: {e}")
        return jsonify({'error': str(e)}), 500


@ingress_bp.route('/api/presets/<preset_id>')
@require_login
def api_get_preset(preset_id):
    """API endpoint to get preset configuration (for AJAX)"""
    try:
        preset = get_preset(preset_id)
        if not preset:
            return jsonify({'error': 'Preset not found'}), 404
        return jsonify(preset)
    except Exception as e:
        logger.error(f"Error getting preset: {e}")
        return jsonify({'error': str(e)}), 500
