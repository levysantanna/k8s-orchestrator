#!/usr/bin/env python3
"""
Test script to generate connection monitor events

Copyright (C) 2026 K8s Orchestrator Contributors
Licensed under GPL-3.0
"""
from services.connection_monitor import connection_monitor
import time

def test_monitor():
    """Generate sample connection events"""

    print("Generating connection monitor events...")

    # SSH connection attempt
    connection_monitor.log_event(
        event_type='connect',
        connection_type='ssh',
        host='192.168.1.10',
        username='root',
        message='Attempting SSH connection (port 22)',
        status='info'
    )
    time.sleep(0.5)

    # SSH connection success
    connection_monitor.log_event(
        event_type='connect',
        connection_type='ssh',
        host='192.168.1.10',
        username='root',
        message='SSH connection established successfully',
        status='success'
    )
    time.sleep(0.5)

    # Kubeconfig retrieval
    connection_monitor.log_event(
        event_type='info',
        connection_type='ssh',
        host='192.168.1.10',
        username='root',
        message='Kubeconfig retrieved successfully from /etc/rancher/k3s/k3s.yaml',
        status='success'
    )
    time.sleep(0.5)

    # SSH disconnect
    connection_monitor.log_event(
        event_type='disconnect',
        connection_type='ssh',
        host='192.168.1.10',
        username='root',
        message='SSH connection closed',
        status='info'
    )
    time.sleep(0.5)

    # K8s connection
    connection_monitor.log_event(
        event_type='connect',
        connection_type='k8s',
        host='production-cluster',
        username=None,
        message='Connecting to Kubernetes API',
        status='info'
    )
    time.sleep(0.5)

    connection_monitor.log_event(
        event_type='connect',
        connection_type='k8s',
        host='production-cluster',
        username=None,
        message='Kubernetes API connection established',
        status='success'
    )
    time.sleep(0.5)

    # Failed SSH connection
    connection_monitor.log_event(
        event_type='error',
        connection_type='ssh',
        host='192.168.1.20',
        username='admin',
        message='Authentication failed - check credentials',
        status='error'
    )
    time.sleep(0.5)

    # Network error
    connection_monitor.log_event(
        event_type='error',
        connection_type='ssh',
        host='192.168.1.30',
        username='root',
        message='Network error: Cannot reach 192.168.1.30:22',
        status='error'
    )

    # Print statistics
    print("\nConnection Statistics:")
    stats = connection_monitor.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print("\nActive Connections:")
    active = connection_monitor.get_active_connections()
    for conn in active:
        print(f"  - {conn['type']}: {conn.get('username', '')}@{conn['host']} (since {conn['connected_at']})")

    print("\nRecent Log Lines:")
    logs = connection_monitor.get_recent_log_lines(limit=10)
    for log in logs:
        print(f"  {log}")

if __name__ == '__main__':
    test_monitor()
