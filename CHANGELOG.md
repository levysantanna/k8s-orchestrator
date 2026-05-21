# Changelog

All notable changes to K8s Orchestrator will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- GitHub Actions CI/CD workflows
- Container image publishing to GitHub Container Registry
- Multi-architecture support (amd64, arm64)
- Security scanning with Trivy
- SBOM generation

## [1.0.0] - 2026-05-21

### Added
- Initial release of K8s Orchestrator
- Flask web dashboard with Bootstrap 5 UI
- Multi-cluster Kubernetes management
- Cluster connectivity testing and node discovery
- Resource monitoring (pods, deployments, namespaces, PVCs)
- Pod log viewing
- User authentication with role-based access (admin/viewer)
- Node scaling capabilities
  - Generate join commands for k3s and kubeadm
  - Node draining and removal
  - Capacity planning and recommendations
- Rook-Ceph storage management
  - Operator installation
  - Ceph cluster creation
  - StorageClass management (block and filesystem)
  - Health status monitoring
- Container support
  - Production-ready Dockerfile
  - Docker Compose setup with Redis
  - Comprehensive Makefile with 30+ commands
  - Support for both Podman and Docker
- Documentation
  - README with quick start guide
  - QUICKSTART guide for developers
  - BUILD guide for containers
  - IMPLEMENTATION_STATUS tracking
- GPLv3 license
- SQLite database with SQLAlchemy ORM
- MCP agent models (deployment ready for Phase 3)
- Metrics snapshot models (ready for Phase 4)

### Security
- Non-root container user
- Health checks built-in
- Environment variable configuration
- Bcrypt password hashing
- Session management with Flask-Login

## [0.1.0] - Development

### Added
- Project scaffolding
- Database models
- Basic Flask application structure
- Service layer architecture

---

## Version Format

- **Major.Minor.Patch** (e.g., 1.0.0)
  - **Major**: Breaking changes
  - **Minor**: New features (backward compatible)
  - **Patch**: Bug fixes (backward compatible)

## Links

- [Repository](https://github.com/levysantanna/k8s-orchestrator)
- [Issues](https://github.com/levysantanna/k8s-orchestrator/issues)
- [Releases](https://github.com/levysantanna/k8s-orchestrator/releases)
