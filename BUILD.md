# Building K8s Orchestrator Container

## Prerequisites

- **Podman** or **Docker** installed
- **podman-compose** or **docker-compose** (for multi-container setup)

### Install Podman (Fedora/RHEL/AlmaLinux)

```bash
sudo dnf install -y podman podman-compose
```

### Install Docker (Alternative)

```bash
sudo dnf install -y docker docker-compose
sudo systemctl enable --now docker
```

## Quick Start with Makefile

The project includes a comprehensive Makefile for easy container management:

```bash
# Show all available commands
make help

# Build container image
make build

# Run orchestrator
make run

# View logs
make logs

# Stop container
make stop

# Deploy (build + run)
make deploy

# Start with docker-compose (orchestrator + Redis)
make compose-up
```

## Manual Build and Run

### Option 1: Single Container (SQLite only)

```bash
# Build image
podman build -t k8s-orchestrator:latest .

# Run container
podman run -d \
  --name k8s-orchestrator \
  -p 5000:5000 \
  -e SECRET_KEY=your-secret-key-here \
  -v k8s-orchestrator-data:/app/data \
  -v k8s-orchestrator-logs:/app/logs \
  k8s-orchestrator:latest

# Check logs
podman logs -f k8s-orchestrator

# Access dashboard
# Open browser: http://localhost:5000
# Login: admin / changeme
```

### Option 2: Multi-Container with Redis (Recommended)

```bash
# Start all services (orchestrator + Redis)
podman-compose up -d

# View logs
podman-compose logs -f

# Stop all services
podman-compose down
```

## Container Configuration

### Environment Variables

Create a `.env` file for configuration:

```bash
# Flask Configuration
SECRET_KEY=change-me-in-production
FLASK_ENV=production
PORT=5000

# Database
DATABASE_URL=sqlite:///data/orchestrator.db

# Redis
REDIS_URL=redis://redis:6379/0

# Admin User
ADMIN_USERNAME=admin
ADMIN_PASSWORD=changeme

# Metrics
METRICS_INTERVAL=60
METRICS_RETENTION_HOURS=168
```

### Volume Mounts

**Persistent Data:**
- `/app/data` - SQLite database
- `/app/logs` - Application logs

**Optional:**
- `/home/appuser/.kube` - Mount kubeconfig for local K8s access

### Port Mapping

- `5000` - Web dashboard
- `6379` - Redis (in docker-compose setup)

## Advanced Usage

### Custom Build

```bash
# Build with specific Python version
podman build --build-arg PYTHON_VERSION=3.11 -t k8s-orchestrator:latest .

# Build without cache
podman build --no-cache -t k8s-orchestrator:latest .

# Build for multi-arch (amd64 + arm64)
podman build --platform linux/amd64,linux/arm64 -t k8s-orchestrator:latest .
```

### Development Mode

Run with live code reloading:

```bash
podman run -it --rm \
  --name k8s-orchestrator-dev \
  -p 5000:5000 \
  -e FLASK_ENV=development \
  -v $(pwd):/app \
  -v k8s-orchestrator-data:/app/data \
  k8s-orchestrator:latest
```

### Access Container Shell

```bash
# Podman
podman exec -it k8s-orchestrator /bin/bash

# Or with Makefile
make shell
```

### Initialize Database Manually

```bash
# Inside container
podman exec k8s-orchestrator python scripts/init-db.py

# Or with Makefile
make init-db
```

## Kubernetes Deployment

### Deploy to k3s/Kubernetes

```bash
# Create namespace
kubectl create namespace k8s-orchestrator

# Create deployment (assuming image in registry)
kubectl apply -f k8s/deployment.yaml

# Or use the deployment script (TODO)
./scripts/deploy-to-k3s.sh
```

## Troubleshooting

### Container won't start

```bash
# Check logs
podman logs k8s-orchestrator

# Check if port is in use
sudo lsof -i :5000

# Recreate container
podman stop k8s-orchestrator
podman rm k8s-orchestrator
make run
```

### Database issues

```bash
# Reset database
podman exec k8s-orchestrator rm -f /app/data/orchestrator.db
podman exec k8s-orchestrator python scripts/init-db.py
podman restart k8s-orchestrator
```

### Permission errors

```bash
# Check volume permissions
podman volume inspect k8s-orchestrator-data

# Fix permissions
podman exec k8s-orchestrator chown -R appuser:appuser /app/data
```

### Redis connection failed

```bash
# Check Redis container
podman ps | grep redis

# Start Redis if using docker-compose
podman-compose up -d redis

# Check Redis logs
podman logs k8s-orchestrator-redis
```

## Image Registry

### Push to Registry

```bash
# Tag image
podman tag k8s-orchestrator:latest registry.example.com/k8s-orchestrator:latest

# Push to registry
podman push registry.example.com/k8s-orchestrator:latest

# Or use Makefile
make push REGISTRY=registry.example.com
```

### Pull from Registry

```bash
podman pull registry.example.com/k8s-orchestrator:latest
```

## Security Considerations

### Production Deployment

1. **Change default passwords**
   ```bash
   ADMIN_PASSWORD=$(openssl rand -base64 32)
   ```

2. **Use proper SECRET_KEY**
   ```bash
   SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')
   ```

3. **Enable HTTPS** - Use reverse proxy (Traefik, Nginx)

4. **Limit container capabilities**
   ```bash
   podman run --cap-drop=ALL --cap-add=NET_BIND_SERVICE ...
   ```

5. **Use read-only root filesystem**
   ```bash
   podman run --read-only -v /app/data:/app/data -v /app/logs:/app/logs ...
   ```

## Health Checks

The container includes built-in health checks:

```bash
# Check container health
podman inspect k8s-orchestrator | grep -A 10 Health

# Manual health check
curl -f http://localhost:5000/ || echo "Service unhealthy"
```

## Performance Tuning

### Gunicorn Workers (Production)

For production, consider using Gunicorn:

```dockerfile
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "app:create_app()"]
```

### Resource Limits

```bash
# Set CPU and memory limits
podman run -d \
  --cpus="2.0" \
  --memory="2g" \
  --name k8s-orchestrator \
  k8s-orchestrator:latest
```

## License

This container and all code within is licensed under **GNU General Public License v3.0**.
See LICENSE file for details.

## Support

For issues and questions:
- GitHub Issues: https://github.com/levysantanna/k8s-orchestrator/issues
- Documentation: See README.md and QUICKSTART.md
