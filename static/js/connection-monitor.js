/**
 * Connection Monitor
 * Real-time connection monitoring panel with SSE
 *
 * Copyright (C) 2026 K8s Orchestrator Contributors
 * Licensed under GPL-3.0
 */

class ConnectionMonitor {
    constructor() {
        this.panel = null;
        this.logContainer = null;
        this.eventSource = null;
        this.isEnabled = false;
        this.maxLogLines = 200;
        this.autoScroll = true;

        this.init();
    }

    init() {
        // Create panel HTML
        this.createPanel();

        // Check if enabled from localStorage
        const enabled = localStorage.getItem('connectionMonitorEnabled') === 'true';
        if (enabled) {
            this.enable();
        }

        // Setup toggle button listener
        const toggleBtn = document.getElementById('toggleConnectionMonitor');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggle();
            });
        }
    }

    createPanel() {
        // Create panel container
        const panel = document.createElement('div');
        panel.id = 'connection-monitor-panel';
        panel.className = 'connection-monitor-panel';
        panel.style.display = 'none';

        panel.innerHTML = `
            <div class="monitor-header">
                <div class="monitor-title">
                    <i class="fas fa-broadcast-tower"></i>
                    <span>Connection Monitor</span>
                    <span class="badge bg-primary ms-2" id="monitor-event-count">0</span>
                </div>
                <div class="monitor-controls">
                    <button class="btn btn-sm btn-outline-light" id="monitor-autoscroll" title="Auto-scroll">
                        <i class="fas fa-arrow-down"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-light" id="monitor-clear" title="Clear">
                        <i class="fas fa-trash"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-light" id="monitor-close" title="Close">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
            <div class="monitor-stats" id="monitor-stats">
                <span class="stat-item">
                    <i class="fas fa-plug text-success"></i>
                    Active: <strong id="stat-active">0</strong>
                </span>
                <span class="stat-item">
                    <i class="fas fa-key text-info"></i>
                    SSH: <strong id="stat-ssh">0</strong>
                </span>
                <span class="stat-item">
                    <i class="fas fa-dharmachakra text-primary"></i>
                    K8s: <strong id="stat-k8s">0</strong>
                </span>
                <span class="stat-item">
                    <i class="fas fa-exclamation-triangle text-warning"></i>
                    Errors: <strong id="stat-errors">0</strong>
                </span>
            </div>
            <div class="monitor-logs" id="monitor-logs"></div>
        `;

        document.body.appendChild(panel);
        this.panel = panel;
        this.logContainer = panel.querySelector('#monitor-logs');

        // Setup control listeners
        this.setupControls();
    }

    setupControls() {
        // Auto-scroll toggle
        const autoScrollBtn = this.panel.querySelector('#monitor-autoscroll');
        autoScrollBtn.classList.add('active');
        autoScrollBtn.addEventListener('click', () => {
            this.autoScroll = !this.autoScroll;
            autoScrollBtn.classList.toggle('active', this.autoScroll);
        });

        // Clear button
        this.panel.querySelector('#monitor-clear').addEventListener('click', () => {
            this.clearLogs();
        });

        // Close button
        this.panel.querySelector('#monitor-close').addEventListener('click', () => {
            this.disable();
        });

        // Make logs scrollable and detect manual scroll
        this.logContainer.addEventListener('scroll', () => {
            const isScrolledToBottom =
                this.logContainer.scrollHeight - this.logContainer.scrollTop <=
                this.logContainer.clientHeight + 50;

            if (!isScrolledToBottom) {
                this.autoScroll = false;
                autoScrollBtn.classList.remove('active');
            }
        });
    }

    toggle() {
        if (this.isEnabled) {
            this.disable();
        } else {
            this.enable();
        }
    }

    enable() {
        this.isEnabled = true;
        this.panel.style.display = 'flex';
        localStorage.setItem('connectionMonitorEnabled', 'true');

        // Update menu item
        const menuItem = document.getElementById('toggleConnectionMonitor');
        if (menuItem) {
            menuItem.innerHTML = '<i class="fas fa-eye-slash"></i> Hide Connection Monitor';
        }

        // Add body class to adjust layout
        document.body.classList.add('monitor-enabled');

        // Start SSE connection
        this.startEventStream();

        // Load stats
        this.updateStats();
        this.statsInterval = setInterval(() => this.updateStats(), 5000);
    }

    disable() {
        this.isEnabled = false;
        this.panel.style.display = 'none';
        localStorage.setItem('connectionMonitorEnabled', 'false');

        // Update menu item
        const menuItem = document.getElementById('toggleConnectionMonitor');
        if (menuItem) {
            menuItem.innerHTML = '<i class="fas fa-eye"></i> Show Connection Monitor';
        }

        // Remove body class
        document.body.classList.remove('monitor-enabled');

        // Stop SSE connection
        this.stopEventStream();

        // Stop stats updates
        if (this.statsInterval) {
            clearInterval(this.statsInterval);
        }
    }

    startEventStream() {
        if (this.eventSource) {
            this.eventSource.close();
        }

        this.eventSource = new EventSource('/monitor/events/stream');

        this.eventSource.onmessage = (e) => {
            try {
                const event = JSON.parse(e.data);
                this.addLogEntry(event);
            } catch (err) {
                console.error('Error parsing SSE event:', err);
            }
        };

        this.eventSource.onerror = (err) => {
            console.error('SSE connection error:', err);
            this.addSystemMessage('Connection lost. Reconnecting...', 'error');

            // Auto-reconnect after 3 seconds
            setTimeout(() => {
                if (this.isEnabled) {
                    this.startEventStream();
                }
            }, 3000);
        };

        this.addSystemMessage('Monitor connected', 'success');
    }

    stopEventStream() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }

    addLogEntry(event) {
        const logLine = document.createElement('div');
        logLine.className = `log-entry log-${event.status}`;

        const statusIcon = {
            'info': 'ℹ️',
            'success': '✅',
            'warning': '⚠️',
            'error': '❌'
        }[event.status] || 'ℹ️';

        const typeIcon = {
            'ssh': '🔑',
            'k8s': '☸️'
        }[event.connection_type] || '🔌';

        const userPart = event.username ? `${event.username}@` : '';

        logLine.innerHTML = `
            <span class="log-time">[${event.timestamp}]</span>
            <span class="log-icons">${statusIcon} ${typeIcon}</span>
            <span class="log-event">${event.event_type.toUpperCase()}:</span>
            <span class="log-target">${userPart}${event.host}</span>
            <span class="log-message">- ${event.message}</span>
        `;

        this.logContainer.appendChild(logLine);

        // Update event count
        const count = this.logContainer.children.length;
        document.getElementById('monitor-event-count').textContent = count;

        // Limit log lines
        while (this.logContainer.children.length > this.maxLogLines) {
            this.logContainer.removeChild(this.logContainer.firstChild);
        }

        // Auto-scroll if enabled
        if (this.autoScroll) {
            this.logContainer.scrollTop = this.logContainer.scrollHeight;
        }
    }

    addSystemMessage(message, status = 'info') {
        this.addLogEntry({
            timestamp: new Date().toLocaleTimeString(),
            event_type: 'system',
            connection_type: 'monitor',
            host: 'localhost',
            username: null,
            message: message,
            status: status
        });
    }

    async updateStats() {
        try {
            const response = await fetch('/monitor/api/stats');
            const data = await response.json();

            document.getElementById('stat-active').textContent = data.stats.active_connections;
            document.getElementById('stat-ssh').textContent = data.stats.ssh_connections;
            document.getElementById('stat-k8s').textContent = data.stats.k8s_connections;
            document.getElementById('stat-errors').textContent = data.stats.recent_errors;
        } catch (err) {
            console.error('Error fetching stats:', err);
        }
    }

    clearLogs() {
        if (confirm('Clear all log entries from display?')) {
            this.logContainer.innerHTML = '';
            document.getElementById('monitor-event-count').textContent = '0';
            this.addSystemMessage('Logs cleared', 'info');
        }
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    window.connectionMonitor = new ConnectionMonitor();
});
