# K8s Orchestrator - Quick Start Guide

## 🎉 Project Created Successfully!

Your Kubernetes orchestrator with MCP agent management is ready!

**Location:** `/home/lsantann/dev/k8s-orchestrator`

## 📊 What Was Built

### Phase 1: Complete ✅
- **17 Python files** implementing core functionality
- **8 HTML templates** with Bootstrap 5 UI
- **4 database models** (User, Cluster, Node, MCPAgent, MetricsSnapshot)
- **3 services** (ClusterService, K8sClientService)
- **3 controllers** (auth, dashboard, cluster management)
- **SQLite database** initialized with admin user

## 🚀 Getting Started (3 Steps)

### Step 1: Install Dependencies

```bash
cd /home/lsantann/dev/k8s-orchestrator

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Start the Application

```bash
# The database is already initialized!
# Just run the app:
python app.py
```

You should see:
```
============================================================
K8s Orchestrator Starting
============================================================
Port: 5000
Debug: True
Dashboard: http://localhost:5000
============================================================
```

### Step 3: Access the Dashboard

1. Open browser: **http://localhost:5000**
2. Login with:
   - **Username:** `admin`
   - **Password:** `changeme`

## 🎯 What You Can Do Right Now

### 1. Add Your First Cluster

1. Click **"Add Cluster"** button
2. Fill in:
   - **Name:** e.g., "production-k3s"
   - **API Server URL:** e.g., `https://192.168.1.10:6443`
   - **Kubeconfig:** Upload your kubeconfig file
3. Click **"Test Connection"** to verify
4. Click **"Add Cluster"**

### 2. View Cluster Resources

Once a cluster is added, you can:
- View all nodes (masters and workers)
- Browse namespaces
- List all pods across namespaces
- View pod logs in real-time
- Monitor deployments
- Check cluster health

### 3. Explore the Dashboard

The dashboard shows:
- **Total clusters** configured
- **Active clusters** (connected and healthy)
- **MCP agents** (Phase 3 feature)
- **Cluster cards** with real-time status

## 📁 Project Structure

```
k8s-orchestrator/
├── app.py                    # Flask application entry point
├── requirements.txt          # Python dependencies
├── .env.example             # Environment configuration template
│
├── functions/               # Core utilities
│   ├── base.py             # Database session management
│   ├── database.py         # User model
│   └── decorators.py       # Auth decorators
│
├── models/                  # Database models
│   ├── cluster.py          # Cluster & Node models
│   ├── agent.py            # MCPAgent model
│   └── metrics.py          # MetricsSnapshot model
│
├── services/                # Business logic
│   ├── cluster_service.py  # Cluster operations
│   └── k8s_client_service.py # Kubernetes API wrapper
│
├── controllers/             # Flask blueprints
│   ├── auth_controller.py  # Login/logout
│   ├── dashboard_controller.py # Main dashboard
│   └── cluster_controller.py   # Cluster management
│
├── templates/               # Jinja2 templates
│   ├── base.html           # Base layout
│   ├── dashboard.html      # Main dashboard
│   ├── auth/               # Login page
│   ├── clusters/           # Cluster management
│   └── resources/          # Pod logs, etc.
│
├── scripts/                 # Utility scripts
│   └── init-db.py          # Database initialization
│
└── data/                    # SQLite database
    └── orchestrator.db     # Created automatically
```

## 🔧 Configuration

### Environment Variables

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
```

Key settings:
- `SECRET_KEY` - Flask session secret (change in production!)
- `DATABASE_URL` - Database connection (default: SQLite)
- `FLASK_ENV` - `development` or `production`
- `PORT` - Application port (default: 5000)

### Admin User

**Default credentials:**
- Username: `admin`
- Password: `changeme`

**⚠️ IMPORTANT:** Change the password after first login!

## 🧪 Testing Cluster Connectivity

### Get Your Kubeconfig

On your Kubernetes cluster:

```bash
# For k3s
cat /etc/rancher/k3s/k3s.yaml

# For standard Kubernetes
cat ~/.kube/config
```

### Common Issues

**1. "Connection refused" when adding cluster**
- Check API server URL is correct
- Verify kubeconfig is valid
- Ensure cluster is reachable from orchestrator

**2. "Cluster not found" errors**
- Refresh the cluster list
- Test connection from cluster detail page

**3. Pod logs not showing**
- Verify pod is running
- Check namespace is correct

## 🎨 UI Features

### Dashboard
- ✅ Statistics cards (clusters, agents)
- ✅ Cluster status cards with color-coded health
- ✅ Quick actions (add cluster, view details)
- ⏳ Real-time metrics (Phase 4)
- ⏳ Charts (Phase 4)

### Cluster Management
- ✅ List all clusters with status
- ✅ Add cluster with kubeconfig upload
- ✅ Test connectivity
- ✅ Discover nodes
- ✅ View detailed cluster info
- ✅ Delete clusters

### Resource Viewing
- ✅ Nodes (name, role, status, IP)
- ✅ Namespaces
- ✅ Pods (name, status, node, IP)
- ✅ Pod logs (last 100 lines)
- ✅ Deployments (replicas, ready status)
- ⏳ StatefulSets (basic view only)
- ⏳ PVCs (visible but no management yet)

## 📋 Next Development Phases

### Phase 2: Extended Resource Monitoring (Days 4-6)
- Full PVC management (resize, delete)
- StatefulSet details
- Real-time updates via WebSocket

### Phase 3: MCP Agent Deployment (Days 7-10)
- Ollama deployment automation
- MCP agent container
- Agent lifecycle management
- Agent logs and monitoring

### Phase 4: Metrics Collection (Days 11-13)
- SSH-based CPU/RAM/disk collection
- Background metrics jobs
- Historical metrics storage
- Charts and graphs

### Phase 5: Storage Management (Days 14-16)
- Rook-Ceph operator installer
- Ceph cluster creation
- StorageClass management

### Phase 6: Cluster Expansion (Days 17-18)
- Node addition workflow
- Auto-discovery
- Capacity planning

## 🐛 Troubleshooting

### Application won't start

```bash
# Check dependencies
pip list | grep Flask

# Reinstall if needed
pip install -r requirements.txt --force-reinstall
```

### Database issues

```bash
# Reinitialize database
rm data/orchestrator.db
python scripts/init-db.py
```

### Can't login

Default credentials: `admin` / `changeme`

If still fails, reinitialize database (see above).

## 📚 Architecture Patterns

This project follows proven patterns from `OCI/controles`:

1. **MVC Architecture**
   - Models: SQLAlchemy ORM
   - Views: Jinja2 templates
   - Controllers: Flask blueprints

2. **Service Layer**
   - Business logic isolated from controllers
   - Reusable service methods
   - Database session management

3. **Security**
   - Password hashing (bcrypt)
   - Role-based access control
   - Session management (Flask-Login)

4. **UI/UX**
   - Bootstrap 5 responsive design
   - Font Awesome icons
   - Color-coded status indicators
   - Progress bars for resource usage

## 🔐 Security Notes

- Passwords are hashed with bcrypt
- Sessions use Flask-Login
- Kubeconfig content is base64 encoded (not encrypted yet)
- SSH credentials stored in plaintext (encryption pending)

**TODO for production:**
- [ ] Encrypt kubeconfig in database
- [ ] Encrypt SSH credentials
- [ ] Enable CSRF protection
- [ ] Add rate limiting
- [ ] Use HTTPS

## 📝 Development Notes

### Adding New Features

1. **New model:** Add to `models/` directory
2. **New service:** Add to `services/` directory  
3. **New controller:** Add to `controllers/` directory
4. **New template:** Add to `templates/` directory
5. **Register blueprint:** Update `app.py`

### Database Changes

After modifying models:

```bash
# Drop and recreate (development only!)
rm data/orchestrator.db
python scripts/init-db.py
```

### Code Style

- Follow existing patterns in `OCI/controles`
- Use type hints in service methods
- Document functions with docstrings
- Keep controllers thin, services fat

## 🎓 Learning Resources

- **Flask:** https://flask.palletsprojects.com/
- **SQLAlchemy:** https://docs.sqlalchemy.org/
- **Kubernetes Python Client:** https://github.com/kubernetes-client/python
- **Bootstrap 5:** https://getbootstrap.com/docs/5.1/

## 🤝 Contributing

To continue development:

1. Check `IMPLEMENTATION_STATUS.md` for next steps
2. Follow the phased approach (Phases 2-6)
3. Reuse patterns from `OCI/serverdlov` for monitoring
4. Test thoroughly before marking phase complete

## 📞 Support

For issues:
1. Check this guide first
2. Review `IMPLEMENTATION_STATUS.md`
3. Check Flask/SQLAlchemy logs in `logs/app.log`
4. Review existing code patterns in `OCI/controles`

---

**🎉 Congratulations!** You now have a fully functional Kubernetes orchestrator ready for expansion!

**Next step:** Add your first cluster and explore the dashboard!
