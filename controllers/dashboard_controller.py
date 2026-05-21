from flask import Blueprint, render_template, jsonify
from functions.decorators import require_login
from functions.base import get_db_session
from models.cluster import Cluster, ClusterStatus
from models.agent import MCPAgent
from models.metrics import MetricsSnapshot
from sqlalchemy import func, desc

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@require_login
def index():
    """Main dashboard view"""
    db = get_db_session()
    try:
        # Get cluster statistics
        total_clusters = db.query(func.count(Cluster.id)).scalar() or 0
        active_clusters = db.query(func.count(Cluster.id)).filter(
            Cluster.status == ClusterStatus.ACTIVE
        ).scalar() or 0

        # Get agent statistics
        total_agents = db.query(func.count(MCPAgent.id)).scalar() or 0
        running_agents = db.query(func.count(MCPAgent.id)).filter(
            MCPAgent.status == 'running'
        ).scalar() or 0

        # Get all clusters with latest metrics
        clusters = db.query(Cluster).all()
        cluster_data = []

        for cluster in clusters:
            # Get latest metrics for this cluster
            latest_metrics = db.query(MetricsSnapshot).filter(
                MetricsSnapshot.cluster_id == cluster.id
            ).order_by(desc(MetricsSnapshot.timestamp)).first()

            cluster_info = {
                'id': cluster.id,
                'name': cluster.name,
                'status': cluster.status.value,
                'health_status': cluster.health_status,
                'node_count': cluster.node_count,
                'kubernetes_version': cluster.kubernetes_version,
                'agents': db.query(func.count(MCPAgent.id)).filter(
                    MCPAgent.cluster_id == cluster.id
                ).scalar() or 0,
            }

            if latest_metrics:
                cluster_info['metrics'] = {
                    'cpu_percent': latest_metrics.cpu_percent,
                    'memory_percent': latest_metrics.memory_percent,
                    'disk_percent': latest_metrics.disk_percent,
                    'pod_running': latest_metrics.pod_running,
                    'pod_total': latest_metrics.pod_count,
                }
            else:
                cluster_info['metrics'] = None

            cluster_data.append(cluster_info)

        return render_template('dashboard.html',
                             total_clusters=total_clusters,
                             active_clusters=active_clusters,
                             total_agents=total_agents,
                             running_agents=running_agents,
                             clusters=cluster_data)

    except Exception as e:
        return render_template('dashboard.html',
                             total_clusters=0,
                             active_clusters=0,
                             total_agents=0,
                             running_agents=0,
                             clusters=[],
                             error=str(e))
    finally:
        db.close()

@dashboard_bp.route('/api/stats')
@require_login
def stats_api():
    """API endpoint for dashboard statistics (for real-time updates)"""
    db = get_db_session()
    try:
        total_clusters = db.query(func.count(Cluster.id)).scalar() or 0
        active_clusters = db.query(func.count(Cluster.id)).filter(
            Cluster.status == ClusterStatus.ACTIVE
        ).scalar() or 0
        total_agents = db.query(func.count(MCPAgent.id)).scalar() or 0
        running_agents = db.query(func.count(MCPAgent.id)).filter(
            MCPAgent.status == 'running'
        ).scalar() or 0

        return jsonify({
            'total_clusters': total_clusters,
            'active_clusters': active_clusters,
            'total_agents': total_agents,
            'running_agents': running_agents
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()
