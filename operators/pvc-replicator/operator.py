#!/usr/bin/env python3
"""
PVC Replicator Operator
Kubernetes operator to replicate Persistent Volume Claims across clusters using rsync

Copyright (C) 2026 K8s Orchestrator Contributors
Licensed under GPL-3.0
"""
import kopf
import kubernetes
import asyncio
import logging
from typing import Dict, Any
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@kopf.on.create('pvcreplicator.k8s-orchestrator.io', 'v1', 'pvcreplications')
async def create_pvc_replication(spec, name, namespace, **kwargs):
    """
    Handle creation of PVCReplication custom resource

    Args:
        spec: PVCReplication spec from CRD
        name: Name of the PVCReplication resource
        namespace: Namespace
    """
    logger.info(f"Creating PVC replication: {namespace}/{name}")

    source_pvc = spec.get('sourcePVC')
    target_cluster = spec.get('targetCluster')
    target_namespace = spec.get('targetNamespace', namespace)
    schedule = spec.get('schedule', '0 */6 * * *')  # Default: every 6 hours

    try:
        # Create replication job
        await create_replication_cronjob(
            name=name,
            namespace=namespace,
            source_pvc=source_pvc,
            target_cluster=target_cluster,
            target_namespace=target_namespace,
            schedule=schedule
        )

        return {'message': f'PVC replication {name} created successfully'}

    except Exception as e:
        logger.error(f"Failed to create PVC replication: {e}")
        raise kopf.PermanentError(f"Creation failed: {str(e)}")


@kopf.on.update('pvcreplicator.k8s-orchestrator.io', 'v1', 'pvcreplications')
async def update_pvc_replication(spec, name, namespace, **kwargs):
    """Handle PVCReplication updates"""
    logger.info(f"Updating PVC replication: {namespace}/{name}")

    # Delete old CronJob
    await delete_replication_cronjob(name, namespace)

    # Recreate with new spec
    await create_pvc_replication(spec, name, namespace, **kwargs)

    return {'message': f'PVC replication {name} updated successfully'}


@kopf.on.delete('pvcreplicator.k8s-orchestrator.io', 'v1', 'pvcreplications')
async def delete_pvc_replication(spec, name, namespace, **kwargs):
    """Handle PVCReplication deletion"""
    logger.info(f"Deleting PVC replication: {namespace}/{name}")

    try:
        await delete_replication_cronjob(name, namespace)
        return {'message': f'PVC replication {name} deleted successfully'}

    except Exception as e:
        logger.error(f"Failed to delete PVC replication: {e}")
        raise


async def create_replication_cronjob(
    name: str,
    namespace: str,
    source_pvc: str,
    target_cluster: str,
    target_namespace: str,
    schedule: str
):
    """
    Create CronJob for periodic PVC replication

    Args:
        name: Replication name
        namespace: Source namespace
        source_pvc: Source PVC name
        target_cluster: Target cluster name/kubeconfig
        target_namespace: Target namespace
        schedule: Cron schedule
    """
    batch_api = kubernetes.client.BatchV1Api()

    cronjob_manifest = {
        'apiVersion': 'batch/v1',
        'kind': 'CronJob',
        'metadata': {
            'name': f'pvc-replicator-{name}',
            'namespace': namespace,
            'labels': {
                'app': 'pvc-replicator',
                'replication': name
            }
        },
        'spec': {
            'schedule': schedule,
            'concurrencyPolicy': 'Forbid',  # Prevent concurrent runs
            'successfulJobsHistoryLimit': 3,
            'failedJobsHistoryLimit': 3,
            'jobTemplate': {
                'spec': {
                    'template': {
                        'metadata': {
                            'labels': {
                                'app': 'pvc-replicator',
                                'replication': name
                            }
                        },
                        'spec': {
                            'restartPolicy': 'OnFailure',
                            'volumes': [
                                {
                                    'name': 'source-pvc',
                                    'persistentVolumeClaim': {
                                        'claimName': source_pvc
                                    }
                                },
                                {
                                    'name': 'target-kubeconfig',
                                    'secret': {
                                        'secretName': f'kubeconfig-{target_cluster}'
                                    }
                                }
                            ],
                            'containers': [
                                {
                                    'name': 'rsync-replicator',
                                    'image': 'instrumentisto/rsync-ssh:latest',
                                    'command': ['/bin/sh', '-c'],
                                    'args': [
                                        f'''
                                        # Export target kubeconfig
                                        export KUBECONFIG=/target-kubeconfig/config

                                        # Get target PVC pod
                                        TARGET_POD=$(kubectl get pod -n {target_namespace} -l pvc-replicator-target={source_pvc} -o jsonpath='{{.items[0].metadata.name}}')

                                        if [ -z "$TARGET_POD" ]; then
                                            echo "Error: Target pod not found"
                                            exit 1
                                        fi

                                        # Perform rsync
                                        echo "Starting rsync: {source_pvc} -> {target_cluster}/{target_namespace}"
                                        rsync -avz --delete /source-data/ /target-data/

                                        echo "Replication completed at $(date)"
                                        '''
                                    ],
                                    'volumeMounts': [
                                        {
                                            'name': 'source-pvc',
                                            'mountPath': '/source-data'
                                        },
                                        {
                                            'name': 'target-kubeconfig',
                                            'mountPath': '/target-kubeconfig',
                                            'readOnly': True
                                        }
                                    ],
                                    'env': [
                                        {
                                            'name': 'SOURCE_PVC',
                                            'value': source_pvc
                                        },
                                        {
                                            'name': 'TARGET_CLUSTER',
                                            'value': target_cluster
                                        },
                                        {
                                            'name': 'TARGET_NAMESPACE',
                                            'value': target_namespace
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                }
            }
        }
    }

    batch_api.create_namespaced_cron_job(
        namespace=namespace,
        body=cronjob_manifest
    )

    logger.info(f"Created CronJob: pvc-replicator-{name}")


async def delete_replication_cronjob(name: str, namespace: str):
    """Delete replication CronJob"""
    batch_api = kubernetes.client.BatchV1Api()

    try:
        batch_api.delete_namespaced_cron_job(
            name=f'pvc-replicator-{name}',
            namespace=namespace
        )
        logger.info(f"Deleted CronJob: pvc-replicator-{name}")

    except kubernetes.client.rest.ApiException as e:
        if e.status != 404:
            raise


@kopf.timer('pvcreplicator.k8s-orchestrator.io', 'v1', 'pvcreplications', interval=300)
async def check_replication_status(spec, status, name, namespace, **kwargs):
    """
    Periodic status check for replication

    Runs every 5 minutes to update status
    """
    batch_api = kubernetes.client.BatchV1Api()

    try:
        cronjob = batch_api.read_namespaced_cron_job(
            name=f'pvc-replicator-{name}',
            namespace=namespace
        )

        # Update status
        last_schedule = cronjob.status.last_schedule_time
        last_successful = cronjob.status.last_successful_time

        return {
            'lastScheduleTime': str(last_schedule) if last_schedule else None,
            'lastSuccessfulTime': str(last_successful) if last_successful else None,
            'active': len(cronjob.status.active or []),
            'state': 'Active' if cronjob.status.active else 'Idle'
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
