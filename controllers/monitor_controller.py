"""
Connection Monitor Controller
Provides real-time connection monitoring UI and SSE stream

Copyright (C) 2026 K8s Orchestrator Contributors
Licensed under GPL-3.0
"""
from flask import Blueprint, Response, jsonify, stream_with_context, request
from functions.decorators import require_login
from services.connection_monitor import connection_monitor
import json
import time

monitor_bp = Blueprint('monitor', __name__, url_prefix='/monitor')


@monitor_bp.route('/events/stream')
@require_login
def event_stream():
    """Server-Sent Events stream for real-time connection logs"""

    def generate():
        """Generate SSE events"""
        # Send initial history
        recent_events = connection_monitor.get_recent_events(limit=50)
        for event in recent_events:
            yield f"data: {json.dumps(event)}\n\n"

        # Keep connection alive and send new events
        last_count = len(connection_monitor.events)
        while True:
            time.sleep(0.5)  # Poll every 500ms

            current_count = len(connection_monitor.events)
            if current_count > last_count:
                # New events arrived
                new_events = connection_monitor.get_recent_events(limit=current_count - last_count)
                for event in new_events:
                    yield f"data: {json.dumps(event)}\n\n"

                last_count = current_count

            # Send keepalive ping every 15 seconds
            yield f": keepalive\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


@monitor_bp.route('/api/stats')
@require_login
def get_stats():
    """Get connection statistics"""
    stats = connection_monitor.get_stats()
    active = connection_monitor.get_active_connections()

    return jsonify({
        'stats': stats,
        'active_connections': active
    })


@monitor_bp.route('/api/recent')
@require_login
def get_recent():
    """Get recent events as JSON"""
    limit = int(request.args.get('limit', 50))
    events = connection_monitor.get_recent_events(limit=limit)

    return jsonify({
        'events': events,
        'count': len(events)
    })


@monitor_bp.route('/api/clear', methods=['POST'])
@require_login
def clear_history():
    """Clear event history"""
    connection_monitor.clear_history()

    return jsonify({
        'success': True,
        'message': 'Event history cleared'
    })
