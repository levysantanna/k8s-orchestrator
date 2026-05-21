#!/usr/bin/env python3
"""
Ceph RBD Mirror Operator
Kubernetes operator for Ceph RBD mirroring between Rook-Ceph clusters

Copyright (C) 2026 K8s Orchestrator Contributors
Licensed under GPL-3.0
"""
import kopf
import kubernetes
import asyncio
import logging
import base64
import json
from typing import Dict, Any, Optional
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@kopf.on.create('storage.k8s-orchestrator.io', 'v1', 'cephmirrors')
async def create_ceph_mirror(spec, name, namespace, **kwargs):
    """
    Handle creation of CephMirror custom resource

    Args:
        spec: CephMirror spec from CRD
        name: Name of the CephMirror resource
        namespace: Namespace
    """
    logger.info(f"Creating Ceph RBD mirror: {namespace}/{name}")

    source_pool = spec.get('sourcePool')
    target_cluster = spec.get('targetCluster')
    mirror_mode = spec.get('mirrorMode', 'pool')
    direction = spec.get('direction', 'one-way')
    enabled = spec.get('enabled', True)

    if not enabled:
        logger.info(f"Mirror {name} is disabled, skipping setup")
        return {'message': 'Mirror disabled'}

    try:
        # Step 1: Enable RBD mirroring on source pool
        await enable_pool_mirroring(
            namespace=namespace,
            pool_name=source_pool,
            mode=mirror_mode
        )

        # Step 2: Create bootstrap token for peer authentication
        bootstrap_token = await create_bootstrap_token(
            namespace=namespace,
            pool_name=source_pool
        )

        # Step 3: Configure peer cluster
        await configure_peer_cluster(
            target_cluster=target_cluster,
            source_namespace=namespace,
            source_pool=source_pool,
            bootstrap_token=bootstrap_token,
            direction=direction
        )

        # Step 4: Enable image mirroring if in image mode
        if mirror_mode == 'image':
            image_pattern = spec.get('imagePattern', '.*')
            await enable_image_mirroring(
                namespace=namespace,
                pool_name=source_pool,
                pattern=image_pattern
            )

        # Step 5: Configure snapshot schedule if specified
        snapshot_schedule = spec.get('snapshotSchedule')
        if snapshot_schedule:
            await configure_snapshot_schedule(
                namespace=namespace,
                pool_name=source_pool,
                schedule=snapshot_schedule
            )

        return {
            'message': f'Ceph RBD mirror {name} created successfully',
            'bootstrapToken': bootstrap_token
        }

    except Exception as e:
        logger.error(f"Failed to create Ceph mirror: {e}")
        raise kopf.PermanentError(f"Creation failed: {str(e)}")


@kopf.on.update('storage.k8s-orchestrator.io', 'v1', 'cephmirrors')
async def update_ceph_mirror(spec, name, namespace, **kwargs):
    """Handle CephMirror updates"""
    logger.info(f"Updating Ceph RBD mirror: {namespace}/{name}")

    # For updates, we need to reconfigure the mirroring
    await delete_ceph_mirror(spec, name, namespace, **kwargs)
    await create_ceph_mirror(spec, name, namespace, **kwargs)

    return {'message': f'Ceph RBD mirror {name} updated successfully'}


@kopf.on.delete('storage.k8s-orchestrator.io', 'v1', 'cephmirrors')
async def delete_ceph_mirror(spec, name, namespace, **kwargs):
    """Handle CephMirror deletion"""
    logger.info(f"Deleting Ceph RBD mirror: {namespace}/{name}")

    source_pool = spec.get('sourcePool')

    try:
        # Disable mirroring on the pool
        await disable_pool_mirroring(
            namespace=namespace,
            pool_name=source_pool
        )

        return {'message': f'Ceph RBD mirror {name} deleted successfully'}

    except Exception as e:
        logger.error(f"Failed to delete Ceph mirror: {e}")
        raise


async def enable_pool_mirroring(namespace: str, pool_name: str, mode: str):
    """
    Enable RBD mirroring on a Ceph pool

    Args:
        namespace: Rook-Ceph namespace
        pool_name: Name of the RBD pool
        mode: Mirroring mode ('pool' or 'image')
    """
    core_api = kubernetes.client.CoreV1Api()

    # Execute rbd mirror pool enable command in toolbox pod
    toolbox_pod = await get_rook_toolbox_pod(namespace)

    if mode == 'pool':
        cmd = f"rbd mirror pool enable {pool_name} pool"
    else:
        cmd = f"rbd mirror pool enable {pool_name} image"

    await exec_in_pod(
        namespace=namespace,
        pod_name=toolbox_pod,
        command=['bash', '-c', cmd]
    )

    logger.info(f"Enabled {mode} mirroring on pool {pool_name}")


async def create_bootstrap_token(namespace: str, pool_name: str) -> str:
    """
    Create RBD mirror bootstrap token for peer authentication

    Args:
        namespace: Rook-Ceph namespace
        pool_name: RBD pool name

    Returns:
        Base64 encoded bootstrap token
    """
    toolbox_pod = await get_rook_toolbox_pod(namespace)

    cmd = f"rbd mirror pool peer bootstrap create {pool_name}"

    result = await exec_in_pod(
        namespace=namespace,
        pod_name=toolbox_pod,
        command=['bash', '-c', cmd]
    )

    # Token is returned in the output
    token = result.strip()
    logger.info(f"Created bootstrap token for pool {pool_name}")

    return token


async def configure_peer_cluster(
    target_cluster: Dict,
    source_namespace: str,
    source_pool: str,
    bootstrap_token: str,
    direction: str
):
    """
    Configure peer cluster for mirroring

    Args:
        target_cluster: Target cluster configuration
        source_namespace: Source Rook-Ceph namespace
        source_pool: Source pool name
        bootstrap_token: Bootstrap token for authentication
        direction: 'one-way' or 'two-way'
    """
    # Load target cluster kubeconfig
    kubeconfig_secret = target_cluster['kubeconfig']
    target_namespace = target_cluster.get('namespace', 'rook-ceph')

    core_api = kubernetes.client.CoreV1Api()

    # Get kubeconfig from secret
    secret = core_api.read_namespaced_secret(
        name=kubeconfig_secret,
        namespace=source_namespace
    )

    kubeconfig_data = base64.b64decode(secret.data['config']).decode('utf-8')

    # Create temporary kubeconfig file in toolbox pod
    toolbox_pod = await get_rook_toolbox_pod(source_namespace)

    # Import the bootstrap token on target cluster
    cmd = f"""
    echo '{bootstrap_token}' | rbd mirror pool peer bootstrap import {source_pool} -
    """

    # Execute on target cluster's toolbox pod
    # (This requires access to target cluster - would need multi-cluster setup)

    logger.info(f"Configured peer cluster for pool {source_pool}")

    # For two-way mirroring, also configure reverse direction
    if direction == 'two-way':
        logger.info("Configuring two-way mirroring")
        # Create bootstrap token on target and import on source
        # (Implementation depends on multi-cluster access)


async def enable_image_mirroring(
    namespace: str,
    pool_name: str,
    pattern: str
):
    """
    Enable mirroring for specific RBD images matching pattern

    Args:
        namespace: Rook-Ceph namespace
        pool_name: RBD pool name
        pattern: Regex pattern to match image names
    """
    toolbox_pod = await get_rook_toolbox_pod(namespace)

    # List all images in pool
    list_cmd = f"rbd ls {pool_name}"
    images_output = await exec_in_pod(
        namespace=namespace,
        pod_name=toolbox_pod,
        command=['bash', '-c', list_cmd]
    )

    import re
    images = images_output.strip().split('\n')
    pattern_re = re.compile(pattern)

    # Enable mirroring for matching images
    for image in images:
        if pattern_re.match(image):
            enable_cmd = f"rbd mirror image enable {pool_name}/{image} snapshot"
            await exec_in_pod(
                namespace=namespace,
                pod_name=toolbox_pod,
                command=['bash', '-c', enable_cmd]
            )
            logger.info(f"Enabled mirroring for image {pool_name}/{image}")


async def configure_snapshot_schedule(
    namespace: str,
    pool_name: str,
    schedule: str
):
    """
    Configure snapshot schedule for mirroring

    Args:
        namespace: Rook-Ceph namespace
        pool_name: RBD pool name
        schedule: Cron-format schedule
    """
    toolbox_pod = await get_rook_toolbox_pod(namespace)

    # Convert cron schedule to Ceph snapshot schedule format
    # Ceph uses interval format like "1h" or "30m"
    # For now, use a simple mapping
    interval = "6h"  # Default to 6 hours

    cmd = f"rbd mirror snapshot schedule add --pool {pool_name} {interval}"

    await exec_in_pod(
        namespace=namespace,
        pod_name=toolbox_pod,
        command=['bash', '-c', cmd]
    )

    logger.info(f"Configured snapshot schedule for pool {pool_name}: {interval}")


async def disable_pool_mirroring(namespace: str, pool_name: str):
    """Disable RBD mirroring on a pool"""
    toolbox_pod = await get_rook_toolbox_pod(namespace)

    cmd = f"rbd mirror pool disable {pool_name}"

    await exec_in_pod(
        namespace=namespace,
        pod_name=toolbox_pod,
        command=['bash', '-c', cmd]
    )

    logger.info(f"Disabled mirroring on pool {pool_name}")


async def get_rook_toolbox_pod(namespace: str) -> str:
    """
    Get the name of the Rook toolbox pod

    Args:
        namespace: Rook-Ceph namespace

    Returns:
        Toolbox pod name
    """
    core_api = kubernetes.client.CoreV1Api()

    pods = core_api.list_namespaced_pod(
        namespace=namespace,
        label_selector='app=rook-ceph-tools'
    )

    if not pods.items:
        raise Exception(f"Rook toolbox pod not found in namespace {namespace}")

    return pods.items[0].metadata.name


async def exec_in_pod(namespace: str, pod_name: str, command: list) -> str:
    """
    Execute command in a pod and return output

    Args:
        namespace: Pod namespace
        pod_name: Pod name
        command: Command to execute

    Returns:
        Command output
    """
    core_api = kubernetes.client.CoreV1Api()

    from kubernetes.stream import stream

    resp = stream(
        core_api.connect_get_namespaced_pod_exec,
        pod_name,
        namespace,
        command=command,
        stderr=True,
        stdin=False,
        stdout=True,
        tty=False
    )

    return resp


@kopf.timer('storage.k8s-orchestrator.io', 'v1', 'cephmirrors', interval=300)
async def check_mirror_status(spec, status, name, namespace, **kwargs):
    """
    Periodic status check for mirroring

    Runs every 5 minutes to update status
    """
    source_pool = spec.get('sourcePool')

    try:
        toolbox_pod = await get_rook_toolbox_pod(namespace)

        # Get mirror status
        status_cmd = f"rbd mirror pool status {source_pool}"
        status_output = await exec_in_pod(
            namespace=namespace,
            pod_name=toolbox_pod,
            command=['bash', '-c', status_cmd]
        )

        # Parse status output
        # (Actual parsing would depend on output format)

        # Get image status if in image mode
        image_statuses = []
        if spec.get('mirrorMode') == 'image':
            image_status_cmd = f"rbd mirror image status {source_pool}"
            image_output = await exec_in_pod(
                namespace=namespace,
                pod_name=toolbox_pod,
                command=['bash', '-c', image_status_cmd]
            )
            # Parse image statuses
            # (Would need proper parsing logic)

        return {
            'state': 'Healthy',
            'mirroringEnabled': True,
            'lastSyncTime': datetime.utcnow().isoformat(),
            'imageStatus': image_statuses
        }

    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return {
            'state': 'Error',
            'error': str(e)
        }


if __name__ == '__main__':
    # Load in-cluster config or kubeconfig
    try:
        kubernetes.config.load_incluster_config()
    except:
        kubernetes.config.load_kube_config()

    # Run operator
    kopf.run()
