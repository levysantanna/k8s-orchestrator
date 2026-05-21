# PVC Replicator Operator

Kubernetes operator to replicate Persistent Volume Claims across clusters using rsync.

## Features

- **Cross-Cluster PVC Replication** - Sync PVCs between Kubernetes clusters
- **Scheduled Syncs** - Cron-based periodic replication
- **rsync-Based** - Efficient incremental transfers
- **Multi-Cluster Support** - Replicate to multiple target clusters
- **Status Tracking** - Monitor replication status
- **Custom Resource Definition** - Kubernetes-native configuration

## Installation

### 1. Install CRD

```bash
kubectl apply -f crd.yaml
```

### 2. Deploy Operator

```bash
kubectl apply -f deployment.yaml
```

### 3. Verify Installation

```bash
kubectl get pods -n pvc-replicator
kubectl get crd pvcreplications.pvcreplicator.k8s-orchestrator.io
```

## Usage

### Create Target Cluster Kubeconfig Secret

First, create a secret with the target cluster's kubeconfig:

```bash
kubectl create secret generic kubeconfig-prod \
  --from-file=config=/path/to/target-kubeconfig.yaml \
  -n my-namespace
```

### Create PVCReplication Resource

```yaml
apiVersion: pvcreplicator.k8s-orchestrator.io/v1
kind: PVCReplication
metadata:
  name: database-replication
  namespace: production
spec:
  sourcePVC: postgres-data
  targetCluster: backup-cluster
  targetNamespace: production-backup
  schedule: "0 */6 * * *"  # Every 6 hours
  rsyncOptions: "-avz --delete"
  enabled: true
```

Apply it:

```bash
kubectl apply -f pvcreplication.yaml
```

### Check Replication Status

```bash
# List all replications
kubectl get pvcreplications

# Get detailed status
kubectl describe pvcreplication database-replication

# View replication jobs
kubectl get cronjobs -l app=pvc-replicator
kubectl get jobs -l app=pvc-replicator
```

## Configuration

### PVCReplication Spec

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sourcePVC` | string | Yes | Name of the source PVC to replicate |
| `targetCluster` | string | Yes | Target cluster name (kubeconfig secret must exist) |
| `targetNamespace` | string | No | Target namespace (defaults to source namespace) |
| `schedule` | string | No | Cron schedule (default: `0 */6 * * *`) |
| `rsyncOptions` | string | No | Additional rsync options (default: `-avz --delete`) |
| `enabled` | boolean | No | Enable/disable replication (default: `true`) |

### Schedule Examples

```yaml
schedule: "0 */6 * * *"   # Every 6 hours
schedule: "0 0 * * *"     # Daily at midnight
schedule: "0 2 * * 0"     # Weekly on Sunday at 2 AM
schedule: "*/15 * * * *"  # Every 15 minutes
```

## How It Works

1. **CRD Creation** - User creates a `PVCReplication` custom resource
2. **Operator Detection** - Kopf operator detects the new resource
3. **CronJob Creation** - Operator creates a CronJob for periodic syncing
4. **Rsync Execution** - CronJob runs rsync container on schedule
5. **Status Update** - Operator updates replication status

### Replication Flow

```
Source PVC (Cluster A)
   ↓
Rsync Container
   ↓
Target PVC (Cluster B)
```

## Architecture

```
┌─────────────────────────────────────┐
│  PVCReplication CR                  │
│  (User creates this)                │
└─────────────────┬───────────────────┘
                  │
                  ↓
┌─────────────────────────────────────┐
│  PVC Replicator Operator            │
│  (Kopf-based, watches CRs)          │
└─────────────────┬───────────────────┘
                  │
                  ↓
┌─────────────────────────────────────┐
│  CronJob                            │
│  (Created by operator)              │
└─────────────────┬───────────────────┘
                  │
                  ↓
┌─────────────────────────────────────┐
│  Rsync Pod                          │
│  (Runs on schedule)                 │
│  - Mounts source PVC                │
│  - Connects to target cluster       │
│  - Runs rsync                       │
└─────────────────────────────────────┘
```

## Building the Operator

```bash
# Build container image
docker build -t pvc-replicator:latest .

# Tag for registry
docker tag pvc-replicator:latest ghcr.io/levysantanna/pvc-replicator:latest

# Push to registry
docker push ghcr.io/levysantanna/pvc-replicator:latest
```

## Troubleshooting

### Replication Not Running

```bash
# Check operator logs
kubectl logs -n pvc-replicator deployment/pvc-replicator

# Check CronJob
kubectl get cronjobs -l app=pvc-replicator

# Check recent jobs
kubectl get jobs -l app=pvc-replicator --sort-by=.metadata.creationTimestamp
```

### Failed Replication

```bash
# Get failed job logs
kubectl logs job/pvc-replicator-database-replication-<timestamp>

# Common issues:
# - Target kubeconfig secret missing
# - Source PVC not mounted
# - Network connectivity to target cluster
# - Permission denied on target
```

### Delete Replication

```bash
# Delete PVCReplication (CronJob will be auto-deleted)
kubectl delete pvcreplication database-replication
```

## Use Cases

1. **Disaster Recovery** - Replicate production PVCs to backup cluster
2. **Multi-Region** - Sync data between geo-distributed clusters
3. **Dev/Staging** - Copy production data to lower environments
4. **Backup** - Periodic backup of critical PVCs
5. **Migration** - Gradual data migration between clusters

## Limitations

- Requires SSH access between clusters (or shared network)
- One-way replication only (source → target)
- No conflict resolution (target is overwritten)
- Rsync runs in cluster, not as sidecar

## Security Considerations

- **Kubeconfig Secrets** - Store target kubeconfigssecurely
- **Network Policies** - Restrict rsync pod network access
- **RBAC** - Operator needs broad permissions
- **Encryption** - Consider encrypting data in transit

## License

GNU General Public License v3.0

See [LICENSE](../../LICENSE) for details.

## Contributing

Pull requests welcome! See main project [CONTRIBUTING.md](../../CONTRIBUTING.md).
