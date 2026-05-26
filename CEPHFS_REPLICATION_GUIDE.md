# CephFS Replication with rsync Operator

**Date:** 2026-05-26  
**Purpose:** Guide for replicating CephFS volumes using the rsync-based PVC replicator

---

## Overview

CephFS (Ceph Filesystem) is a POSIX-compliant shared filesystem provided by Rook-Ceph. Unlike RBD (block storage), **CephFS does not have native mirroring capabilities**, so we use the **rsync operator** for cross-cluster replication.

### Why rsync for CephFS?

**CephFS Limitations:**
- ❌ No native mirroring (unlike RBD which has `rbd mirror`)
- ❌ Shared filesystem semantics incompatible with block-level replication
- ❌ Multiple pods can mount RW simultaneously - needs filesystem-aware replication

**rsync Solution:**
- ✅ Filesystem-level replication preserves POSIX metadata
- ✅ Handles symlinks, permissions, hardlinks correctly
- ✅ Incremental transfers reduce network bandwidth
- ✅ Cron-based scheduling for predictable replication windows
- ✅ Works with any Kubernetes PVC (not just CephFS)

---

## Architecture

```
Source Cluster                          Target Cluster
┌─────────────────────────┐            ┌─────────────────────────┐
│  CephFS PVC             │            │  CephFS PVC             │
│  (myapp-data)           │            │  (myapp-data-replica)   │
│                         │            │                         │
│  /mnt/data/             │            │  /mnt/data/             │
│  ├── config/            │            │  ├── config/            │
│  ├── logs/              │◄──────────►│  ├── logs/              │
│  └── uploads/           │   rsync    │  └── uploads/           │
└─────────────────────────┘            └─────────────────────────┘
         ▲                                       ▲
         │                                       │
   ┌─────────────────────┐              ┌─────────────────┐
   │ PVCReplication CR   │              │ Target Secret   │
   │ (schedule: cron)    │              │ (kubeconfig)    │
   └─────────────────────┘              └─────────────────┘
         │
         ▼
   ┌─────────────────────┐
   │ CronJob             │
   │ - Mounts source PVC │
   │ - Runs rsync pod    │
   │ - Syncs to target   │
   └─────────────────────┘
```

---

## Prerequisites

### 1. Rook-Ceph Deployed on Both Clusters

**Source and target clusters must have:**
- ✅ Rook-Ceph operator installed
- ✅ CephCluster created
- ✅ CephFS filesystem created
- ✅ CephFS StorageClass available

Verify CephFS is ready:
```bash
# Check CephFilesystem
kubectl get cephfilesystem -n rook-ceph

# Check CephFS StorageClass
kubectl get sc | grep cephfs

# Expected output:
# rook-cephfs   rook-ceph.cephfs.csi.ceph.com   Delete   Immediate   true   5d
```

### 2. PVC Replicator Operator Installed

**On source cluster:**
```bash
# Install CRD
kubectl apply -f operators/pvc-replicator/crd.yaml

# Deploy operator
kubectl apply -f operators/pvc-replicator/deployment.yaml

# Verify
kubectl get pods -n pvc-replicator
```

### 3. Target Cluster Kubeconfig Secret

Create a secret containing target cluster's kubeconfig:

```bash
# Get target cluster kubeconfig
export TARGET_KUBECONFIG=/path/to/target-cluster-kubeconfig.yaml

# Create secret in source namespace
kubectl create secret generic kubeconfig-target-cluster \
  --from-file=config=$TARGET_KUBECONFIG \
  -n myapp-namespace
```

---

## Creating a CephFS Filesystem

If CephFS is not yet created in your Rook-Ceph cluster:

### 1. Create CephFilesystem

```yaml
apiVersion: ceph.rook.io/v1
kind: CephFilesystem
metadata:
  name: myfs
  namespace: rook-ceph
spec:
  metadataPool:
    replicated:
      size: 3
  dataPools:
    - name: replicated
      replicated:
        size: 3
  preserveFilesystemOnDelete: true
  metadataServer:
    activeCount: 1
    activeStandby: true
```

Apply:
```bash
kubectl apply -f cephfs.yaml
```

### 2. Create CephFS StorageClass

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: rook-cephfs
provisioner: rook-ceph.cephfs.csi.ceph.com
parameters:
  clusterID: rook-ceph
  fsName: myfs
  pool: myfs-replicated
  csi.storage.k8s.io/provisioner-secret-name: rook-csi-cephfs-provisioner
  csi.storage.k8s.io/provisioner-secret-namespace: rook-ceph
  csi.storage.k8s.io/controller-expand-secret-name: rook-csi-cephfs-provisioner
  csi.storage.k8s.io/controller-expand-secret-namespace: rook-ceph
  csi.storage.k8s.io/node-stage-secret-name: rook-csi-cephfs-node
  csi.storage.k8s.io/node-stage-secret-namespace: rook-ceph
allowVolumeExpansion: true
reclaimPolicy: Delete
```

Apply:
```bash
kubectl apply -f storageclass-cephfs.yaml
```

### 3. Create Test PVC

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: myapp-data
  namespace: myapp-namespace
spec:
  accessModes:
    - ReadWriteMany  # CephFS supports RWX
  storageClassName: rook-cephfs
  resources:
    requests:
      storage: 10Gi
```

Apply:
```bash
kubectl apply -f pvc-cephfs.yaml
```

---

## Configuring CephFS Replication

### 1. Create PVCReplication Custom Resource

```yaml
apiVersion: pvcreplicator.k8s-orchestrator.io/v1
kind: PVCReplication
metadata:
  name: myapp-cephfs-replication
  namespace: myapp-namespace
spec:
  # Source PVC to replicate
  sourcePVC: myapp-data
  
  # Target cluster (must have kubeconfig secret)
  targetCluster: target-cluster
  
  # Target namespace (create if doesn't exist)
  targetNamespace: myapp-namespace-replica
  
  # Cron schedule (every 6 hours)
  schedule: "0 */6 * * *"
  
  # rsync options
  # -a: archive mode (preserves permissions, timestamps, symlinks)
  # -v: verbose
  # -z: compress during transfer
  # --delete: delete files in target that don't exist in source
  rsyncOptions: "-avz --delete --exclude='.snapshot'"
  
  # Enable replication
  enabled: true
```

**Important rsync Options for CephFS:**
- `--exclude='.snapshot'` - Exclude CephFS snapshot directory
- `--delete` - Keep target in sync (removes deleted files)
- `-a` - Preserve all file attributes
- `-z` - Compress transfers (reduces network usage)

Apply:
```bash
kubectl apply -f pvcreplication-cephfs.yaml
```

### 2. Verify Replication Setup

```bash
# Check PVCReplication resource
kubectl get pvcreplication -n myapp-namespace

# Check CronJob was created
kubectl get cronjobs -n myapp-namespace -l app=pvc-replicator

# Expected output:
# NAME                                  SCHEDULE      SUSPEND   ACTIVE   LAST SCHEDULE   AGE
# pvc-replicator-myapp-cephfs-replication   0 */6 * * *   False     0        <none>          10s
```

### 3. Manual Trigger (Test Replication)

```bash
# Create a job from the CronJob for immediate execution
kubectl create job --from=cronjob/pvc-replicator-myapp-cephfs-replication \
  test-sync-1 -n myapp-namespace

# Watch job execution
kubectl get jobs -n myapp-namespace -w

# View logs
kubectl logs job/test-sync-1 -n myapp-namespace
```

### 4. Check Replication Status

```bash
# Get detailed status
kubectl describe pvcreplication myapp-cephfs-replication -n myapp-namespace

# Check recent jobs
kubectl get jobs -n myapp-namespace -l app=pvc-replicator --sort-by=.metadata.creationTimestamp

# View failed job logs (if any)
kubectl logs -l app=pvc-replicator -n myapp-namespace --tail=100
```

---

## Schedule Examples

### Common Schedules

```yaml
# Every 6 hours (recommended for disaster recovery)
schedule: "0 */6 * * *"

# Every 2 hours (more frequent sync)
schedule: "0 */2 * * *"

# Daily at 2 AM
schedule: "0 2 * * *"

# Every 15 minutes (near-real-time, high network usage)
schedule: "*/15 * * * *"

# Hourly on the hour
schedule: "0 * * * *"

# Weekly on Sunday at midnight
schedule: "0 0 * * 0"
```

### Schedule Selection Guidelines

| Use Case | RPO Target | Recommended Schedule | Network Impact |
|----------|-----------|---------------------|----------------|
| **Disaster Recovery** | 6 hours | `0 */6 * * *` | Low |
| **High Availability** | 1 hour | `0 * * * *` | Medium |
| **Near Real-time** | 15 minutes | `*/15 * * * *` | High |
| **Backup** | 24 hours | `0 2 * * *` | Very Low |
| **Dev/Test Sync** | Weekly | `0 0 * * 0` | Very Low |

**RPO (Recovery Point Objective):** Maximum acceptable data loss in time

---

## Advanced Configuration

### Selective File Exclusion

Exclude temporary files, logs, or large directories:

```yaml
spec:
  rsyncOptions: >-
    -avz --delete
    --exclude='.snapshot'
    --exclude='*.tmp'
    --exclude='*.log'
    --exclude='cache/*'
    --exclude='temp/*'
```

### Bandwidth Limiting

Prevent replication from saturating network:

```yaml
spec:
  rsyncOptions: "-avz --delete --bwlimit=10000"  # Limit to 10 MB/s
```

### Dry-Run Mode (Test Without Changes)

```yaml
spec:
  rsyncOptions: "-avz --delete --dry-run"
```

Check logs to see what would be transferred without actually copying.

### Progress Reporting

```yaml
spec:
  rsyncOptions: "-avz --delete --progress --stats"
```

### Preserve Hard Links

For filesystems with hard links:

```yaml
spec:
  rsyncOptions: "-avzH --delete"  # -H preserves hard links
```

---

## Monitoring and Troubleshooting

### Check Replication Health

```bash
# Get all replications
kubectl get pvcreplication --all-namespaces

# Check specific replication
kubectl describe pvcreplication myapp-cephfs-replication -n myapp-namespace

# Look for status conditions:
# - Type: Ready, Status: True
# - Type: Syncing, Status: False (when not running)
```

### View Replication Logs

```bash
# Get recent job
LATEST_JOB=$(kubectl get jobs -n myapp-namespace -l app=pvc-replicator \
  --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}')

# View logs
kubectl logs job/$LATEST_JOB -n myapp-namespace

# Expected output:
# sending incremental file list
# ./
# config/app.yaml
# uploads/file1.txt
# sent 1,234 bytes  received 56 bytes  258.00 bytes/sec
# total size is 10,234  speedup is 7.94
```

### Common Issues

#### 1. Target PVC Not Found

**Error:** `rsync: failed to connect to target`

**Solution:**
- Ensure target namespace exists
- Target PVC must be pre-created with same size
- Verify kubeconfig secret is correct

```bash
# Pre-create target PVC
kubectl create namespace myapp-namespace-replica --context=target-cluster
kubectl apply -f pvc-cephfs.yaml --context=target-cluster
```

#### 2. Permission Denied

**Error:** `rsync: opendir "/mnt/data" failed: Permission denied`

**Solution:**
- Ensure rsync pod has correct security context
- CephFS may require specific UID/GID
- Add `fsGroup` to replication spec (future enhancement)

#### 3. Network Connectivity

**Error:** `Failed to connect to target cluster`

**Solution:**
- Verify network connectivity between clusters
- Check kubeconfig secret is valid
- Ensure target cluster API is accessible from source

```bash
# Test from source cluster
kubectl run test --rm -it --image=alpine -- sh
wget https://target-cluster-api-server:6443  # Should connect
```

#### 4. Slow Replication

**Symptoms:** Jobs take hours to complete

**Solutions:**
- Add `--compress` flag if not already present
- Increase bandwidth limit if set
- Schedule during off-peak hours
- Consider splitting large directories into multiple PVCReplications

---

## Use Cases

### 1. Disaster Recovery

**Scenario:** Replicate production CephFS volumes to DR site

```yaml
apiVersion: pvcreplicator.k8s-orchestrator.io/v1
kind: PVCReplication
metadata:
  name: production-dr
  namespace: production
spec:
  sourcePVC: app-data
  targetCluster: dr-cluster
  targetNamespace: production
  schedule: "0 */6 * * *"  # Every 6 hours
  rsyncOptions: "-avz --delete --exclude='.snapshot'"
  enabled: true
```

### 2. Multi-Region Deployment

**Scenario:** Sync shared configuration files across regions

```yaml
apiVersion: pvcreplicator.k8s-orchestrator.io/v1
kind: PVCReplication
metadata:
  name: config-sync-us-to-eu
  namespace: config
spec:
  sourcePVC: global-config
  targetCluster: eu-cluster
  targetNamespace: config
  schedule: "*/30 * * * *"  # Every 30 minutes
  rsyncOptions: "-avz --exclude='*.local'"
  enabled: true
```

### 3. Development Environment Refresh

**Scenario:** Weekly sync of production data to staging

```yaml
apiVersion: pvcreplicator.k8s-orchestrator.io/v1
kind: PVCReplication
metadata:
  name: prod-to-staging
  namespace: production
spec:
  sourcePVC: customer-uploads
  targetCluster: staging-cluster
  targetNamespace: staging
  schedule: "0 2 * * 0"  # Sunday at 2 AM
  rsyncOptions: "-avz --delete"
  enabled: true
```

---

## Performance Tuning

### Large Datasets

For PVCs with millions of files:

```yaml
spec:
  rsyncOptions: >-
    -avz --delete
    --exclude='.snapshot'
    --itemize-changes
    --out-format='%n%L'
    --max-delete=1000
```

- `--max-delete=1000`: Prevent accidental mass deletion
- `--itemize-changes`: Detailed change reporting

### Network Optimization

For slow or unreliable networks:

```yaml
spec:
  rsyncOptions: >-
    -avz --delete
    --timeout=3600
    --contimeout=60
    --partial
    --partial-dir=.rsync-partial
```

- `--timeout=3600`: Kill transfer if stalled for 1 hour
- `--partial`: Keep partially transferred files
- `--partial-dir`: Store partials in dedicated directory

---

## Migration from Other Storage

If migrating from non-Ceph storage to CephFS:

1. **Create CephFS PVC** (target)
2. **Create PVCReplication** pointing to old PVC
3. **Run manual sync** to populate CephFS
4. **Switch application** to use CephFS PVC
5. **Continue replication** as backup

---

## Security Considerations

### 1. Kubeconfig Protection

```bash
# Use RBAC to restrict secret access
kubectl create role pvc-replicator-secrets \
  --verb=get --resource=secrets \
  --resource-name=kubeconfig-target-cluster

kubectl create rolebinding pvc-replicator-secrets \
  --role=pvc-replicator-secrets \
  --serviceaccount=pvc-replicator:pvc-replicator
```

### 2. Network Policies

Restrict rsync pod network access:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: pvc-replicator-egress
  namespace: myapp-namespace
spec:
  podSelector:
    matchLabels:
      app: pvc-replicator
  policyTypes:
  - Egress
  egress:
  - to:
    - podSelector: {}  # Allow to all pods in namespace
  - to:
    - namespaceSelector:
        matchLabels:
          name: kube-system  # Allow DNS
    ports:
    - protocol: UDP
      port: 53
```

### 3. Encryption in Transit

For sensitive data, use SSH tunneling:

```yaml
spec:
  rsyncOptions: "-avz --delete -e 'ssh -i /keys/id_rsa'"
```

---

## Comparison: CephFS vs RBD Replication

| Aspect | CephFS (rsync) | RBD (native mirror) |
|--------|----------------|---------------------|
| **Replication Level** | Filesystem | Block device |
| **Access Mode** | ReadWriteMany (RWX) | ReadWriteOnce (RWO) |
| **Use Case** | Shared files, configs | Databases, block volumes |
| **Efficiency** | File-level (slower) | Block-level (faster) |
| **Network Usage** | Medium | Low (incremental blocks) |
| **Setup Complexity** | Simple (CronJob) | Complex (bootstrap tokens) |
| **Multi-Pod Access** | ✅ Yes | ❌ No |
| **Real-time Replication** | ❌ No (cron-based) | ⚠️ Future (journal mode) |

**Use CephFS replication when:**
- ✅ Multiple pods need RWX access
- ✅ Sharing configuration files
- ✅ Storing application uploads/assets
- ✅ Collaborative editing scenarios

**Use RBD replication when:**
- ✅ Single-pod RWO volumes (databases)
- ✅ Block storage performance critical
- ✅ Lower network overhead required

---

## Future Enhancements

- [ ] Dashboard UI for PVCReplication management
- [ ] Automatic target PVC creation
- [ ] Bidirectional sync support
- [ ] Conflict resolution for RWX scenarios
- [ ] Metrics export to Prometheus
- [ ] Email/Slack notifications on failure
- [ ] Web UI for replication logs

---

## References

- [Rook-Ceph CephFS Documentation](https://rook.io/docs/rook/latest/Storage-Configuration/Shared-Filesystem-CephFS/ceph-filesystem/)
- [rsync Man Page](https://linux.die.net/man/1/rsync)
- [PVC Replicator Operator README](operators/pvc-replicator/README.md)
- [Ceph RBD Mirror Operator README](operators/ceph-mirror-operator/README.md)

---

**Document Version:** 1.0  
**Last Updated:** 2026-05-26
