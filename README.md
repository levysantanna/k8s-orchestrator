# Kubernetes Orchestrator with MCP Agent Management

A Flask-based web dashboard for managing multiple Kubernetes clusters, deploying MCP agents with LLM integration, and monitoring cluster resources and metrics.

## Features

- **Multi-Cluster Management**: Add and manage multiple Kubernetes clusters from a single dashboard
- **MCP Agent Farm**: Deploy and manage MCP server agents with Ollama LLM integration
- **Resource Monitoring**: View pods, deployments, statefulsets, and persistent storage across clusters
- **Metrics Collection**: Real-time CPU, RAM, and disk metrics via SSH and Kubernetes API
- **Storage Management**: Install and configure Rook-Ceph distributed storage
- **Cluster Expansion**: Auto-discovery and addition of new nodes

## Architecture

- **Backend**: Flask 3.0 with SQLAlchemy ORM
- **Database**: SQLite (development) / PostgreSQL (production)
- **Cache**: Redis for metrics and status caching
- **K8s Client**: Python Kubernetes client library
- **LLM**: Ollama with llama3.2:1b model
- **MCP**: Python MCP SDK for agent implementation

## Quick Start

### Local Development

```bash
# Clone and setup
cd /home/lsantann/dev/k8s-orchestrator
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Initialize database
python scripts/init-db.py

# Start Redis (via Docker)
docker run -d -p 6379:6379 --name redis redis:alpine

# Run application
python app.py
```

Access dashboard at http://localhost:5000

### Deploy to K3s

```bash
# Build and deploy
./scripts/deploy-to-k3s.sh
```

## Project Structure

```
k8s-orchestrator/
├── app.py                  # Flask application factory
├── functions/              # Core utilities
├── models/                 # Database models
├── services/               # Business logic
├── controllers/            # Flask blueprints
├── templates/              # Jinja2 templates
├── static/                 # CSS, JavaScript
├── k8s/                    # Kubernetes manifests
└── scripts/                # Deployment scripts
```

## Configuration

All configuration via environment variables in `.env`:

- **DATABASE_URL**: SQLAlchemy database connection string
- **REDIS_URL**: Redis connection URL
- **METRICS_INTERVAL**: Metrics collection interval (seconds)
- **DEFAULT_LLM_MODEL**: Ollama model for MCP agents

## Usage

### Adding a Cluster

1. Navigate to **Clusters** → **Add Cluster**
2. Enter cluster name and API server URL
3. Upload kubeconfig or provide SSH credentials
4. Click **Test Connection** to verify
5. Click **Add Cluster**

### Deploying MCP Agents

1. Navigate to **Agents** → **Deploy Agent**
2. Select target cluster
3. Choose LLM model and capabilities
4. Click **Deploy**

### Monitoring Metrics

- **Dashboard**: Real-time cluster status cards with CPU/RAM/disk usage
- **Cluster Detail**: Per-node metrics and historical charts

### Managing Storage

1. Navigate to **Storage** → **Install Rook-Ceph**
2. Click **Install Operator**
3. Configure Ceph cluster settings
4. Click **Create Cluster**

## Development

### Running Tests

```bash
pytest tests/
```

### Database Migrations

```bash
# Create new migration
python scripts/migrate.py create "description"

# Apply migrations
python scripts/migrate.py upgrade
```

## License

MIT License

## Support

For issues and questions, contact the development team.
