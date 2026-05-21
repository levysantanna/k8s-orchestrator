# K8s Orchestrator - Roadmap

## Completed Features (v1.0.0)

### Core Infrastructure ✅
- [x] Flask web application with Bootstrap 5 UI
- [x] SQLite/PostgreSQL database with SQLAlchemy ORM
- [x] User authentication and RBAC (admin/viewer roles)
- [x] Multi-cluster management
- [x] Container support (Podman/Docker)
- [x] GitHub Actions CI/CD
- [x] GPLv3 License

### Cluster Management ✅
- [x] Add clusters via kubeconfig upload
- [x] Test cluster connectivity
- [x] Auto-discover cluster nodes
- [x] Node scaling (join commands, drain, remove)
- [x] Capacity planning and recommendations

### Resource Monitoring ✅
- [x] View pods across all namespaces
- [x] View deployments and replicas
- [x] View statefulsets
- [x] View namespaces
- [x] View PersistentVolumeClaims
- [x] Pod logs viewer (last 100-500 lines)

### Storage Management ✅
- [x] Rook-Ceph operator installation
- [x] Ceph cluster creation
- [x] StorageClass management (block and filesystem)
- [x] Ceph health status monitoring

### Remote Deployment ✅
- [x] Deploy k3s to remote servers via SSH
- [x] Connect to existing clusters via SSH
- [x] Auto-retrieve kubeconfig from remote servers
- [x] Generate k3s join tokens

## Planned Features (Headlamp-Inspired)

### Phase 2: Advanced Resource Management
- [ ] **YAML Editor** for resources
  - In-browser YAML editing with syntax highlighting
  - Schema validation
  - Apply changes directly
  - Diff viewer for changes

- [ ] **Resource Creation Wizard**
  - Form-based resource creation (Deployment, Service, ConfigMap, Secret)
  - Template library
  - Quick deploy common applications

- [ ] **Resource Editing**
  - Edit resource YAML inline
  - Scale deployments with slider
  - Update environment variables
  - Manage labels and annotations

- [ ] **Events Viewer**
  - Real-time Kubernetes events
  - Filter by severity (Normal, Warning, Error)
  - Timeline view
  - Event search

### Phase 3: Interactive Features
- [ ] **Pod Terminal (Exec)**
  - Web-based terminal into pods
  - Container selection for multi-container pods
  - File upload/download
  - Terminal session persistence

- [ ] **Port Forwarding**
  - One-click port forwarding to pods/services
  - Browser-based access to forwarded ports
  - Port forward management

- [ ] **Log Streaming**
  - Real-time log streaming (not just last N lines)
  - Multi-pod log aggregation
  - Log search and filtering
  - Download logs as file
  - Follow mode with auto-scroll

- [ ] **Metrics Visualization**
  - CPU/Memory usage graphs (Chart.js)
  - Historical metrics (7-day retention)
  - Per-pod resource usage
  - Node metrics dashboard
  - Custom metric queries

### Phase 4: Advanced Kubernetes Features
- [ ] **Custom Resource Definitions (CRDs)**
  - Auto-discover CRDs in cluster
  - Generic resource viewer for CRDs
  - CRUD operations on custom resources

- [ ] **RBAC Visualization**
  - View Roles and RoleBindings
  - View ClusterRoles and ClusterRoleBindings
  - Permission matrix
  - User/ServiceAccount permissions viewer

- [ ] **ConfigMaps & Secrets**
  - View and edit ConfigMaps
  - View Secrets (masked by default)
  - Create from file upload
  - Use in deployments

- [ ] **Services & Ingress**
  - Service discovery
  - Endpoint visualization
  - Ingress route mapping
  - Service mesh integration (Istio, Linkerd)

- [ ] **Jobs & CronJobs**
  - View job status
  - Trigger manual job runs
  - CronJob schedule management
  - Job history

### Phase 5: MCP Agent Integration
- [ ] **Ollama Deployment**
  - One-click Ollama deployment to clusters
  - Model management (pull, list, remove)
  - GPU node detection and scheduling

- [ ] **MCP Agent Deployment**
  - Deploy MCP agents with LLM integration
  - Configure agent capabilities
  - Agent logs and monitoring
  - Agent restart/delete

- [ ] **Agent Dashboard**
  - Active agents list
  - Agent health status
  - LLM usage metrics
  - Agent conversation logs

### Phase 6: Observability
- [ ] **Metrics Collection Service**
  - Background SSH-based metrics collection
  - Kubernetes metrics API integration
  - Prometheus scraping (if available)
  - Metrics storage (Redis + DB)

- [ ] **Alerting**
  - Resource threshold alerts
  - Pod crash alerts
  - Node unreachable alerts
  - Email/Slack notifications

- [ ] **Dashboards**
  - Cluster overview dashboard
  - Node metrics dashboard
  - Pod metrics dashboard
  - Storage usage dashboard

### Phase 7: Multi-User Features
- [ ] **User Management**
  - Create/edit/delete users
  - Role assignment
  - Per-cluster access control
  - Audit logs

- [ ] **Team Workspaces**
  - Namespace-based workspaces
  - Team cluster assignments
  - Resource quotas per team

### Phase 8: Plugin System
- [ ] **Plugin Architecture**
  - Plugin API
  - UI extension points
  - Third-party plugin support
  - Plugin marketplace

### Phase 9: Advanced Deployment
- [ ] **Helm Integration**
  - Helm chart repository browser
  - Deploy charts via UI
  - Manage Helm releases
  - Chart values editor

- [ ] **GitOps Integration**
  - FluxCD/ArgoCD integration
  - Git repository monitoring
  - Automated deployments
  - Deployment history

- [ ] **Application Catalog**
  - Pre-configured application templates
  - One-click app deployment (WordPress, databases, etc.)
  - App marketplace

### Phase 10: Enterprise Features
- [ ] **Multi-Cluster Federation**
  - Cross-cluster resource management
  - Global load balancing
  - Cluster failover

- [ ] **Backup & Restore**
  - Cluster backup (Velero integration)
  - Resource backup
  - Disaster recovery
  - Backup scheduling

- [ ] **Cost Management**
  - Resource cost estimation
  - Usage optimization recommendations
  - Cost breakdown by namespace/team

## Headlamp Feature Comparison

| Feature | Headlamp | K8s Orchestrator | Status |
|---------|----------|------------------|--------|
| Multi-cluster support | ✅ | ✅ | Complete |
| Pod logs | ✅ | ✅ | Complete |
| Resource viewing | ✅ | ✅ | Complete |
| YAML editing | ✅ | ❌ | Phase 2 |
| Pod terminal | ✅ | ❌ | Phase 3 |
| Port forwarding | ✅ | ❌ | Phase 3 |
| Events viewer | ✅ | ❌ | Phase 2 |
| CRD support | ✅ | ❌ | Phase 4 |
| Metrics | ✅ | ⚠️ Partial | Phase 6 |
| RBAC viewer | ✅ | ❌ | Phase 4 |
| Plugin system | ✅ | ❌ | Phase 8 |
| **Remote deployment** | ❌ | ✅ | **Unique** |
| **Rook-Ceph integration** | ❌ | ✅ | **Unique** |
| **MCP Agents** | ❌ | ⚠️ Planned | **Unique** |
| **SSH cluster connection** | ❌ | ✅ | **Unique** |

## Unique Features (Not in Headlamp)

1. **Remote k3s Deployment** - Deploy clusters remotely via SSH
2. **Rook-Ceph Storage Management** - Full Ceph integration
3. **MCP Agent Farm** - LLM-powered agents running in clusters
4. **SSH-Only Connection** - No kubeconfig needed
5. **Node Scaling Automation** - Auto-generate join commands
6. **Capacity Planning** - Recommendations for scaling

## Implementation Priority

### High Priority (Next 2 Weeks)
1. YAML Editor
2. Pod Terminal (Exec)
3. Log Streaming (real-time)
4. Events Viewer
5. Resource Editing

### Medium Priority (Month 2)
1. Port Forwarding
2. Metrics Visualization
3. CRD Support
4. ConfigMaps & Secrets management
5. Services & Ingress viewer

### Low Priority (Month 3+)
1. RBAC Visualization
2. Helm Integration
3. Plugin System
4. Backup & Restore
5. Cost Management

## Technical Stack for New Features

- **YAML Editor**: CodeMirror or Monaco Editor
- **Terminal**: xterm.js + WebSocket
- **Log Streaming**: Server-Sent Events (SSE) or WebSocket
- **Metrics**: Chart.js for visualization
- **Real-time Updates**: WebSocket or SSE
- **Port Forwarding**: WebSocket tunnel

## License

All features remain under **GPL-3.0** license.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

**Current Version:** 1.0.0  
**Target Version:** 2.0.0 (with Headlamp feature parity)  
**Last Updated:** 2026-05-21
