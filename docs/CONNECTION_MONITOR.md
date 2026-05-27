# Connection Monitor

Real-time connection monitoring panel for SSH and Kubernetes connections.

**Date:** 2026-05-27  
**Version:** 1.0.0

---

## Overview

The Connection Monitor is a bottom-docked console panel that displays real-time SSH and Kubernetes connection logs in a live stream. It helps administrators track connection activity, troubleshoot authentication issues, and monitor cluster access.

### Features

- ✅ **Real-time event streaming** via Server-Sent Events (SSE)
- ✅ **Live connection statistics** (active connections, errors)
- ✅ **SSH connection tracking** (connect, authenticate, disconnect)
- ✅ **Kubernetes API connection tracking**
- ✅ **Color-coded status indicators** (success, error, warning, info)
- ✅ **Auto-scroll with manual override**
- ✅ **Persistent preferences** (remembers enabled/disabled state)
- ✅ **Event filtering and search** (future enhancement)

---

## User Interface

### Accessing the Monitor

1. **Open the dashboard** - Navigate to http://localhost:5000
2. **Click "Tools" menu** in top navigation bar
3. **Select "Show Connection Monitor"**

The monitor panel will appear docked at the bottom of the page.

### Panel Components

#### Header
- **Title with event count badge** - Shows total events in current session
- **Control buttons:**
  - `↓` Auto-scroll toggle
  - `🗑️` Clear logs
  - `✕` Close panel

#### Statistics Bar
Shows real-time connection metrics:
- **Active** - Total active connections
- **SSH** - Active SSH connections
- **K8s** - Active Kubernetes connections
- **Errors** - Recent errors (last 100 events)

#### Logs Container
Displays real-time connection events with:
- **Timestamp** - When the event occurred
- **Icons** - Status icon (✅/❌/⚠️/ℹ️) and connection type (🔑/☸️)
- **Event type** - CONNECT, DISCONNECT, ERROR, INFO
- **Target** - username@host or cluster name
- **Message** - Detailed event description

---

## Event Types

### SSH Connection Events

#### CONNECT (Attempt)
```
[13:45:12] ℹ️ 🔑 CONNECT: root@192.168.1.10 - Attempting SSH connection (port 22)
```

#### CONNECT (Success)
```
[13:45:13] ✅ 🔑 CONNECT: root@192.168.1.10 - SSH connection established successfully
```

#### INFO (Kubeconfig Retrieval)
```
[13:45:14] ✅ 🔑 INFO: root@192.168.1.10 - Kubeconfig retrieved successfully from /etc/rancher/k3s/k3s.yaml
```

#### DISCONNECT
```
[13:45:15] ℹ️ 🔑 DISCONNECT: root@192.168.1.10 - SSH connection closed
```

#### ERROR (Authentication)
```
[13:45:16] ❌ 🔑 ERROR: admin@192.168.1.20 - Authentication failed - check credentials
```

#### ERROR (Network)
```
[13:45:17] ❌ 🔑 ERROR: root@192.168.1.30 - Network error: Cannot reach 192.168.1.30:22
```

### Kubernetes Connection Events

#### CONNECT (Attempt)
```
[13:45:18] ℹ️ ☸️ CONNECT: production-cluster - Connecting to Kubernetes API
```

#### CONNECT (Success)
```
[13:45:19] ✅ ☸️ CONNECT: production-cluster - Kubernetes API connection established
```

#### ERROR
```
[13:45:20] ❌ ☸️ ERROR: staging-cluster - Connection timeout to API server
```

---

## Architecture

### Backend Components

#### 1. Connection Monitor Service
**File:** `services/connection_monitor.py`

Singleton service that tracks all connection events:
- **ConnectionEvent class** - Represents a single event
- **ConnectionMonitor class** - Global event tracker
- **Methods:**
  - `log_event()` - Record a new event
  - `get_recent_events()` - Retrieve recent events
  - `get_active_connections()` - List active connections
  - `get_stats()` - Get connection statistics

**Event Storage:**
- Circular buffer (deque) with max 500 events
- Thread-safe with locks
- In-memory only (no database persistence)

#### 2. Monitor Controller
**File:** `controllers/monitor_controller.py`

Flask blueprint providing REST and SSE endpoints:
- `GET /monitor/events/stream` - Server-Sent Events stream
- `GET /monitor/api/stats` - Connection statistics
- `GET /monitor/api/recent` - Recent events (JSON)
- `POST /monitor/api/clear` - Clear event history

**SSE Implementation:**
- Polls for new events every 500ms
- Sends keepalive ping every 15 seconds
- Auto-reconnects on connection loss

#### 3. SSH Cluster Connector Integration
**File:** `services/ssh_cluster_connector.py`

Logs events at key stages:
- Connection attempt
- Authentication success/failure
- Kubeconfig retrieval success/failure
- Connection closure

**Example Integration:**
```python
from services.connection_monitor import connection_monitor

# Log connection attempt
connection_monitor.log_event(
    event_type='connect',
    connection_type='ssh',
    host='192.168.1.10',
    username='root',
    message='Attempting SSH connection (port 22)',
    status='info'
)

# Log success
connection_monitor.log_event(
    event_type='connect',
    connection_type='ssh',
    host='192.168.1.10',
    username='root',
    message='SSH connection established successfully',
    status='success'
)
```

### Frontend Components

#### 1. Connection Monitor JavaScript
**File:** `static/js/connection-monitor.js`

**ConnectionMonitor class:**
- Manages panel state (enabled/disabled)
- Creates and controls UI elements
- Consumes SSE stream
- Updates statistics every 5 seconds
- Handles auto-scroll logic
- Persists preferences to localStorage

**Key Methods:**
- `enable()` - Show panel and start SSE
- `disable()` - Hide panel and stop SSE
- `toggle()` - Toggle panel visibility
- `addLogEntry(event)` - Append event to log container
- `updateStats()` - Refresh connection statistics
- `clearLogs()` - Clear displayed logs

#### 2. Connection Monitor CSS
**File:** `static/css/connection-monitor.css`

**Panel Styling:**
- Fixed bottom position
- 300px height (200px on mobile)
- Dark theme (VS Code-inspired)
- Monospace font (Courier New)
- Color-coded log entries by status
- Custom scrollbar styling
- Slide-in animation for new entries

**Body Adjustment:**
```css
body.monitor-enabled {
    padding-bottom: 300px;
}
```

Prevents content from being hidden behind the panel.

---

## Developer Guide

### Adding Connection Events

To add connection monitoring to any service:

#### 1. Import the connection monitor
```python
from services.connection_monitor import connection_monitor
```

#### 2. Log events at key stages
```python
# Connection attempt
connection_monitor.log_event(
    event_type='connect',      # connect, disconnect, error, info
    connection_type='ssh',     # ssh, k8s
    host='192.168.1.10',
    username='root',           # Optional
    message='Attempting connection',
    status='info'              # info, success, warning, error
)

# Connection success
connection_monitor.log_event(
    event_type='connect',
    connection_type='ssh',
    host='192.168.1.10',
    username='root',
    message='Connection established',
    status='success'
)

# Connection error
connection_monitor.log_event(
    event_type='error',
    connection_type='ssh',
    host='192.168.1.10',
    username='root',
    message='Authentication failed',
    status='error'
)

# Disconnection
connection_monitor.log_event(
    event_type='disconnect',
    connection_type='ssh',
    host='192.168.1.10',
    username='root',
    message='Connection closed',
    status='info'
)
```

#### 3. Common Patterns

**Try-except wrapper:**
```python
try:
    connection_monitor.log_event('connect', 'ssh', host, username, 'Connecting...', 'info')
    
    # Perform connection
    result = establish_connection()
    
    connection_monitor.log_event('connect', 'ssh', host, username, 'Connected', 'success')
    return result
    
except AuthenticationError as e:
    connection_monitor.log_event('error', 'ssh', host, username, f'Auth failed: {e}', 'error')
    raise
    
finally:
    connection_monitor.log_event('disconnect', 'ssh', host, username, 'Closed', 'info')
```

### Extending Event Types

To add a new connection type (e.g., 'database'):

#### 1. Update JavaScript icon mapping
**File:** `static/js/connection-monitor.js`
```javascript
const typeIcon = {
    'ssh': '🔑',
    'k8s': '☸️',
    'database': '🗄️'  // Add new type
}[event.connection_type] || '🔌';
```

#### 2. Update CSS if needed
**File:** `static/css/connection-monitor.css`
```css
/* Add specific styling for database connections */
.log-entry[data-connection-type="database"] {
    /* Custom styling */
}
```

#### 3. Log events with new type
```python
connection_monitor.log_event(
    event_type='connect',
    connection_type='database',  # New type
    host='postgres.example.com',
    username='dbadmin',
    message='Connecting to PostgreSQL',
    status='info'
)
```

---

## Configuration

### localStorage Settings

The monitor uses localStorage to persist user preferences:

| Key | Value | Description |
|-----|-------|-------------|
| `connectionMonitorEnabled` | `"true"` / `"false"` | Panel visibility state |

**Reset preferences:**
```javascript
localStorage.removeItem('connectionMonitorEnabled');
```

### Customization

#### Change Panel Height
**File:** `static/css/connection-monitor.css`
```css
.connection-monitor-panel {
    height: 400px;  /* Default: 300px */
}

body.monitor-enabled {
    padding-bottom: 400px;  /* Match panel height */
}
```

#### Change Maximum Log Lines
**File:** `static/js/connection-monitor.js`
```javascript
constructor() {
    this.maxLogLines = 500;  // Default: 200
}
```

#### Change Event Retention
**File:** `services/connection_monitor.py`
```python
def __init__(self):
    self.events = deque(maxlen=1000)  # Default: 500
```

---

## Testing

### Manual Testing

#### 1. Generate Test Events
```bash
python test_connection_monitor.py
```

This generates sample SSH and K8s connection events.

#### 2. Test SSH Connection
1. Navigate to "Clusters" → "Add via SSH"
2. Fill in connection details (can use fake credentials to test errors)
3. Enable connection monitor (Tools → Show Connection Monitor)
4. Submit form
5. Observe real-time connection events in monitor panel

#### 3. Test Auto-scroll
1. Generate many events (run test script multiple times)
2. Scroll up manually
3. Verify auto-scroll button becomes inactive
4. Scroll to bottom
5. Verify auto-scroll reactivates

#### 4. Test SSE Reconnection
1. Enable monitor
2. Restart application
3. Verify monitor shows "Connection lost. Reconnecting..."
4. Verify monitor reconnects automatically

### API Testing

#### Get Statistics
```bash
curl -b cookies.txt http://localhost:5000/monitor/api/stats
```

**Response:**
```json
{
  "stats": {
    "total_events": 8,
    "active_connections": 1,
    "ssh_connections": 0,
    "k8s_connections": 1,
    "recent_errors": 2
  },
  "active_connections": [
    {
      "key": "k8s:production-cluster",
      "type": "k8s",
      "host": "production-cluster",
      "username": null,
      "status": "connected",
      "connected_at": "2026-05-27 16:46:03"
    }
  ]
}
```

#### Get Recent Events
```bash
curl -b cookies.txt http://localhost:5000/monitor/api/recent?limit=10
```

#### Clear History
```bash
curl -X POST -b cookies.txt http://localhost:5000/monitor/api/clear
```

---

## Troubleshooting

### Monitor Not Appearing

**Check:**
1. JavaScript loaded: Open browser console, look for errors
2. Blueprint registered: Check `app.py` has `app.register_blueprint(monitor_bp)`
3. CSS loaded: View page source, verify `connection-monitor.css` included

**Solution:**
```bash
# Restart application
pkill -f "python app.py"
python app.py
```

### SSE Connection Failing

**Symptoms:**
- Monitor shows "Connection lost. Reconnecting..."
- No events appearing in panel

**Check:**
1. Flask route accessible: `curl http://localhost:5000/monitor/events/stream`
2. Authentication: Ensure user is logged in
3. Browser console: Check for CORS or network errors

**Solution:**
```bash
# Check application logs
tail -f logs/app.log

# Verify route is registered
curl http://localhost:5000/monitor/api/stats
```

### Events Not Logging

**Check:**
1. Connection monitor imported: `from services.connection_monitor import connection_monitor`
2. Events being logged: Add print statements or check with test script
3. SSE stream working: Verify stats endpoint returns events

**Debug:**
```python
# In your service
from services.connection_monitor import connection_monitor
import sys

connection_monitor.log_event('test', 'ssh', 'test-host', 'test-user', 'Testing', 'info')
print("Event logged", file=sys.stderr)

# Check recent events
events = connection_monitor.get_recent_events()
print(f"Total events: {len(events)}", file=sys.stderr)
```

### High Memory Usage

**Cause:** Too many events stored in memory

**Solution:**
Reduce max events in `services/connection_monitor.py`:
```python
self.events = deque(maxlen=100)  # Reduce from 500
```

---

## Security Considerations

### Authentication

All monitor endpoints require authentication:
```python
@monitor_bp.route('/events/stream')
@require_login  # User must be logged in
def event_stream():
    ...
```

### Sensitive Data

**⚠️ IMPORTANT:** Events may contain sensitive information:
- Hostnames and IP addresses
- Usernames
- Error messages with path information

**Best Practices:**
1. **Do not log passwords or keys**
2. **Sanitize error messages** before logging
3. **Limit event retention** (default: 500 events, no database persistence)
4. **Restrict monitor access** to admin users only (future enhancement)

**Example - Sanitizing errors:**
```python
try:
    connect(password=secret_password)
except Exception as e:
    # BAD: Logs full error which might contain password
    connection_monitor.log_event('error', 'ssh', host, user, str(e), 'error')
    
    # GOOD: Generic error message
    connection_monitor.log_event('error', 'ssh', host, user, 'Authentication failed', 'error')
```

---

## Future Enhancements

### Planned Features

- [ ] **Event filtering** by connection type, host, status
- [ ] **Search functionality** to find specific events
- [ ] **Export logs** to file (JSON, CSV)
- [ ] **Admin-only access** with RBAC integration
- [ ] **Resizable panel** with drag handle
- [ ] **Event notifications** (browser notifications for errors)
- [ ] **Detailed event view** with modal popup
- [ ] **Connection duration tracking**
- [ ] **Historical metrics** (connections per hour chart)
- [ ] **Database persistence** (optional for audit trail)

### Enhancement Ideas

#### 1. Event Filtering
```javascript
// Add filter controls
<select id="monitor-filter-type">
  <option value="">All Types</option>
  <option value="ssh">SSH Only</option>
  <option value="k8s">K8s Only</option>
</select>

<select id="monitor-filter-status">
  <option value="">All Status</option>
  <option value="error">Errors Only</option>
  <option value="success">Success Only</option>
</select>
```

#### 2. Export Logs
```javascript
downloadLogs() {
    const events = this.getAllVisibleEvents();
    const blob = new Blob([JSON.stringify(events, null, 2)], {
        type: 'application/json'
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `connection-logs-${new Date().toISOString()}.json`;
    a.click();
}
```

#### 3. Connection Duration
Track time between CONNECT and DISCONNECT events:
```python
class ConnectionMonitor:
    def calculate_duration(self, conn_key):
        events = [e for e in self.events if self._matches_connection(e, conn_key)]
        connect_time = next((e.timestamp for e in events if e.event_type == 'connect'), None)
        disconnect_time = next((e.timestamp for e in reversed(events) if e.event_type == 'disconnect'), None)
        
        if connect_time and disconnect_time:
            return (disconnect_time - connect_time).total_seconds()
        return None
```

---

## Performance

### Metrics

**Memory Usage:**
- ~2KB per event
- Max 500 events = ~1MB max memory
- Circular buffer prevents unbounded growth

**Network:**
- SSE keepalive: 15 seconds
- Event payload: ~200-500 bytes per event
- Stats update: ~500 bytes every 5 seconds

**CPU:**
- SSE polling: 500ms interval (minimal CPU)
- Stats calculation: O(n) on active connections (typically < 10)

### Optimization Tips

1. **Reduce max events** if memory is constrained
2. **Increase SSE poll interval** for lower network usage
3. **Disable auto-scroll** when viewing historical events
4. **Clear logs regularly** to improve rendering performance

---

## License

GPL-3.0

Copyright (C) 2026 K8s Orchestrator Contributors

---

## Changelog

### Version 1.0.0 (2026-05-27)

**Initial Release:**
- Real-time connection monitoring panel
- SSE-based event streaming
- SSH connection tracking
- Kubernetes connection tracking
- Auto-scroll with manual override
- Connection statistics dashboard
- Persistent preferences via localStorage
- VS Code-inspired dark theme

---

**For questions or issues, please open a GitHub issue.**
