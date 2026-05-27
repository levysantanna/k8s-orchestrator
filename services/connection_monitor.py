"""
Connection Monitor Service
Tracks all SSH and K8s connections in real-time

Copyright (C) 2026 K8s Orchestrator Contributors
Licensed under GPL-3.0
"""
import threading
from datetime import datetime
from typing import Dict, List, Optional
from collections import deque


class ConnectionEvent:
    """Represents a connection event"""

    def __init__(
        self,
        event_type: str,
        connection_type: str,
        host: str,
        username: Optional[str] = None,
        message: str = "",
        status: str = "info"
    ):
        self.timestamp = datetime.utcnow()
        self.event_type = event_type  # connect, disconnect, error, info
        self.connection_type = connection_type  # ssh, k8s
        self.host = host
        self.username = username
        self.message = message
        self.status = status  # info, success, warning, error

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'event_type': self.event_type,
            'connection_type': self.connection_type,
            'host': self.host,
            'username': self.username,
            'message': self.message,
            'status': self.status
        }

    def to_log_line(self) -> str:
        """Format as console log line"""
        time_str = self.timestamp.strftime('%H:%M:%S')
        user_part = f"{self.username}@" if self.username else ""
        type_icon = {
            'ssh': '🔑',
            'k8s': '☸️'
        }.get(self.connection_type, '🔌')

        status_icon = {
            'info': 'ℹ️',
            'success': '✅',
            'warning': '⚠️',
            'error': '❌'
        }.get(self.status, 'ℹ️')

        return f"[{time_str}] {status_icon} {type_icon} {self.event_type.upper()}: {user_part}{self.host} - {self.message}"


class ConnectionMonitor:
    """Singleton service to track all connections"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self.events = deque(maxlen=500)  # Keep last 500 events
        self.active_connections: Dict[str, Dict] = {}
        self.listeners = []  # SSE listeners
        self.event_lock = threading.Lock()

    def log_event(
        self,
        event_type: str,
        connection_type: str,
        host: str,
        username: Optional[str] = None,
        message: str = "",
        status: str = "info"
    ):
        """Log a connection event"""
        event = ConnectionEvent(
            event_type=event_type,
            connection_type=connection_type,
            host=host,
            username=username,
            message=message,
            status=status
        )

        with self.event_lock:
            self.events.append(event)

            # Update active connections tracking
            conn_key = f"{connection_type}:{username}@{host}" if username else f"{connection_type}:{host}"

            if event_type == 'connect':
                self.active_connections[conn_key] = {
                    'type': connection_type,
                    'host': host,
                    'username': username,
                    'status': 'connected',
                    'connected_at': event.timestamp
                }
            elif event_type == 'disconnect':
                if conn_key in self.active_connections:
                    del self.active_connections[conn_key]
            elif event_type == 'error':
                if conn_key in self.active_connections:
                    self.active_connections[conn_key]['status'] = 'error'

        # Notify SSE listeners
        self._notify_listeners(event)

    def _notify_listeners(self, event: ConnectionEvent):
        """Notify all SSE listeners of new event"""
        # Will be implemented by SSE endpoint
        pass

    def get_recent_events(self, limit: int = 100) -> List[Dict]:
        """Get recent events"""
        with self.event_lock:
            events_list = list(self.events)
            return [e.to_dict() for e in events_list[-limit:]]

    def get_recent_log_lines(self, limit: int = 50) -> List[str]:
        """Get recent events as formatted log lines"""
        with self.event_lock:
            events_list = list(self.events)
            return [e.to_log_line() for e in events_list[-limit:]]

    def get_active_connections(self) -> List[Dict]:
        """Get list of currently active connections"""
        with self.event_lock:
            return [
                {
                    'key': key,
                    **conn,
                    'connected_at': conn['connected_at'].strftime('%Y-%m-%d %H:%M:%S')
                }
                for key, conn in self.active_connections.items()
            ]

    def get_stats(self) -> Dict:
        """Get connection statistics"""
        with self.event_lock:
            total_events = len(self.events)
            active_count = len(self.active_connections)

            ssh_count = sum(1 for c in self.active_connections.values() if c['type'] == 'ssh')
            k8s_count = sum(1 for c in self.active_connections.values() if c['type'] == 'k8s')

            error_count = sum(1 for e in list(self.events)[-100:] if e.status == 'error')

            return {
                'total_events': total_events,
                'active_connections': active_count,
                'ssh_connections': ssh_count,
                'k8s_connections': k8s_count,
                'recent_errors': error_count
            }

    def clear_history(self):
        """Clear event history (keeps active connections)"""
        with self.event_lock:
            self.events.clear()


# Global singleton instance
connection_monitor = ConnectionMonitor()
