# Ceph RBD Mirror Operator

Kubernetes operator for Ceph RBD mirroring between Rook-Ceph clusters using native Ceph replication.

## Features

- **Native Ceph RBD Mirroring** - Uses Ceph's built-in block device mirroring
- **Pool or Image Mode** - Mirror entire pools or specific images
- **One-way or Two-way Replication** - Support for both replication directions
- **Snapshot-based Mirroring** - Scheduled snapshots for async replication
- **Journaling-based Mirroring** - Real-time replication using RBD journaling
- **Multi-Cluster Support** - Replicate to multiple target Rook-Ceph clusters
- **Status Tracking** - Monitor replication health and image sync status
- **Kubernetes-native** - Custom Resource Definition with declarative configuration

## Prerequisites

- **Rook-Ceph** clusters deployed on source and target Kubernetes clusters
- **Rook Toolbox** pods running in each Rook-Ceph namespace
- **Network connectivity** between Ceph clusters (ports 6789, 6800-7300)
- **RBD pools** already created in source cluster

## How It Works

Unlike the rsync-based approach, this operator uses Ceph's native RBD mirroring:

1. **RBD Mirroring** - Ceph's built-in replication at the block device level
2. **Bootstrap Tokens** - Secure peer authentication between clusters
3. **Snapshot or Journal** - Two replication modes:
   - **Snapshot-based**: Periodic snapshots replicated on schedule
   - **Journal-based**: Real-time journaling for continuous replication
4. **Peer Configuration** - Automatic setup of mirror peers
5. **Health Monitoring** - Tracks sync status and replication health

### Architecture

```
Source Cluster (Rook-Ceph)             Target Cluster (Rook-Ceph)
┌─────────────────────────┐           ┌─────────────────────────┐
│  RBD Pool (replicapool) │           │  RBD Pool (replicapool) │
│  ├─ image-1            │◄──────────►│  ├─ image-1 (replica)  │
│  ├─ image-2            │  Mirroring │  ├─ image-2 (replica)  │
│  └─ image-3            │           │  └─ image-3 (replica)  │
└─────────────────────────┘           └─────────────────────────┘
         ▲                                      ▲
         │                                      │
   Bootstrap Token                        Import Token
         │                                      │
┌─────────────────────────┐           ┌─────────────────────────┐
│ Ceph Mirror Operator    │           │  (Target cluster peer)  │
│ - Creates bootstrap     │           │                         │
│ - Enables pool mirror   │           │                         │
│ - Configures peer       │           │                         │
│ - Monitors status       │           │                         │
└─────────────────────────┘           └─────────────────────────┘
```

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
kubectl get pods -n ceph-mirror-operator
kubectl get crd cephmirrors.storage.k8s-orchestrator.io
```

## Usage

### Create Target Cluster Kubeconfig Secret

First, create a secret with the target cluster's kubeconfig:

```bash
kubectl create secret generic kubeconfig-backup-cluster \
  --from-file=config=/path/to/target-kubeconfig.yaml \
  -n rook-ceph
```

### Create CephMirror Resource

```yaml
apiVersion: storage.k8s-orchestrator.io/v1
kind: CephMirror
metadata:
  name: production-mirror
  namespace: rook-ceph
spec:
  sourcePool: replicapool
  targetCluster:
    kubeconfig: kubeconfig-backup-cluster
    namespace: rook-ceph
  mirrorMode: pool  # or 'image' for per-image control
  direction: one-way  # or 'two-way' for bidirectional
  snapshotSchedule: "0 */6 * * *"  # Every 6 hours
  enabled: true
```

Apply it:

```bash
kubectl apply -f cephmirror.yaml
```

### Image-Mode Mirroring

For selective image mirroring with pattern matching:

```yaml
apiVersion: storage.k8s-orchestrator.io/v1
kind: CephMirror
metadata:
  name: selective-mirror
  namespace: rook-ceph
spec:
  sourcePool: replicapool
  targetCluster:
    kubeconfig: kubeconfig-backup-cluster
    namespace: rook-ceph
  mirrorMode: image
  imagePattern: "^pvc-.*"  # Only mirror PVCs
  direction: one-way
  snapshotSchedule: "0 */2 * * *"  # Every 2 hours
```

### Check Mirroring Status

```bash
# List all mirrors
kubectl get cephmirrors -n rook-ceph

# Get detailed status
kubectl describe cephmirror production-mirror -n rook-ceph

# Check RBD mirror status directly (in toolbox pod)
kubectl exec -n rook-ceph -it rook-ceph-tools-xxx -- rbd mirror pool status replicapool
```

## Configuration

### CephMirror Spec

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sourcePool` | string | Yes | Ceph RBD pool to mirror |
| `targetCluster.kubeconfig` | string | Yes | Secret containing target cluster kubeconfig |
| `targetCluster.namespace` | string | No | Rook-Ceph namespace in target (default: `rook-ceph`) |
| `mirrorMode` | string | No | `pool` (entire pool) or `image` (per-image) |
| `direction` | string | No | `one-way` or `two-way` (default: `one-way`) |
| `snapshotSchedule` | string | No | Cron schedule for snapshots |
| `imagePattern` | string | No | Regex to match images (image mode only) |
| `enabled` | boolean | No | Enable/disable mirroring (default: `true`) |

### Mirroring Modes

**Pool Mode** (`mirrorMode: pool`):
- Mirrors all RBD images in the pool
- Simpler configuration
- Automatic mirroring for new images

**Image Mode** (`mirrorMode: image`):
- Selective mirroring based on pattern
- Fine-grained control
- Must explicitly enable mirroring per image

### Replication Strategies

**Snapshot-based**:
- Periodic snapshots on schedule
- Lower network overhead
- Asynchronous with RPO based on schedule
- Good for disaster recovery

**Journal-based** (future):
- Real-time replication
- Near-zero RPO
- Higher network usage
- Good for high-availability scenarios

## Comparison: rsync vs Ceph RBD Mirroring

| Feature | rsync Approach | Ceph RBD Mirroring |
|---------|----------------|-------------------|
| **Performance** | Filesystem-level, slower | Block-level, faster |
| **Efficiency** | Full file scans | Incremental block changes |
| **Integration** | External tool | Native Ceph feature |
| **Consistency** | Application-dependent | Block-level consistency |
| **Network** | High bandwidth | Optimized transfers |
| **Setup** | Complex (pods, mounts) | Native Ceph commands |
| **Monitoring** | Custom scripts | Built-in Ceph tools |

## Troubleshooting

### Mirroring Not Starting

```bash
# Check operator logs
kubectl logs -n ceph-mirror-operator deployment/ceph-mirror-operator

# Check if pool mirroring is enabled
kubectl exec -n rook-ceph -it rook-ceph-tools-xxx -- rbd mirror pool info replicapool

# Verify peer configuration
kubectl exec -n rook-ceph -it rook-ceph-tools-xxx -- rbd mirror pool peer ls replicapool
```

### Mirror in Warning State

```bash
# Check mirror status
kubectl exec -n rook-ceph -it rook-ceph-tools-xxx -- rbd mirror pool status replicapool

# Check image status
kubectl exec -n rook-ceph -it rook-ceph-tools-xxx -- rbd mirror image status replicapool/image-name

# Common issues:
# - Network connectivity between clusters
# - Clock skew between clusters
# - Insufficient Ceph cluster capacity
```

### Bootstrap Token Issues

```bash
# Regenerate bootstrap token
kubectl exec -n rook-ceph -it rook-ceph-tools-xxx -- \
  rbd mirror pool peer bootstrap create replicapool

# Import token on target cluster
echo '<token>' | kubectl exec -n rook-ceph -it rook-ceph-tools-xxx -- \
  rbd mirror pool peer bootstrap import replicapool -
```

### Delete Mirror

```bash
# Delete CephMirror resource (disables mirroring)
kubectl delete cephmirror production-mirror -n rook-ceph

# Manually disable if needed
kubectl exec -n rook-ceph -it rook-ceph-tools-xxx -- \
  rbd mirror pool disable replicapool
```

## Use Cases

1. **Disaster Recovery** - Async replication to geographically distant cluster
2. **High Availability** - Two-way mirroring for active-active scenarios
3. **Data Migration** - Gradual migration between Ceph clusters
4. **Compliance** - Maintain data copies in different regions
5. **Testing** - Clone production storage to test environments

## Limitations

- Requires Rook-Ceph on both clusters
- Network connectivity between Ceph clusters required
- One-way mirroring cannot detect conflicts
- Snapshot schedule granularity limited by Ceph

## Security Considerations

- **Bootstrap Tokens** - Protect tokens, they grant replication access
- **Network Encryption** - Use Ceph's msgr2 protocol with encryption
- **RBAC** - Operator needs exec permissions on toolbox pods
- **Kubeconfig Secrets** - Store target kubeconfigssecurely

## Advanced Configuration

### Two-Way Mirroring

For active-active scenarios:

```yaml
spec:
  direction: two-way
  mirrorMode: pool
```

This creates bidirectional replication. **Warning**: No conflict resolution - last write wins.

### Custom Snapshot Retention

Configure snapshot lifecycle in Ceph:

```bash
# Set retention policy (keep last 10 snapshots)
kubectl exec -n rook-ceph -it rook-ceph-tools-xxx -- \
  rbd mirror snapshot schedule add --pool replicapool 6h --retention 10
```

## Future Enhancements

- [ ] Journal-based mirroring support
- [ ] Automatic failover/failback
- [ ] Metrics export to Prometheus
- [ ] Multi-site disaster recovery
- [ ] Conflict detection and resolution
- [ ] RGW (object storage) replication support

## License

GNU General Public License v3.0

See [LICENSE](../../LICENSE) for details.

## Contributing

Pull requests welcome! See main project [CONTRIBUTING.md](../../CONTRIBUTING.md).
