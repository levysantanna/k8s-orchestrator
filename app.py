#!/usr/bin/env python3
"""
Kubernetes Orchestrator with MCP Agent Management
Flask application factory

Copyright (C) 2026 K8s Orchestrator Contributors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
import os
import secrets
import logging
from pathlib import Path
from flask import Flask
from flask_bootstrap import Bootstrap5
from flask_login import LoginManager
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler

# Load environment variables
load_dotenv(Path(__file__).resolve().parent / ".env")

from functions.database import User
from functions.base import get_db_session

# Import blueprints
from controllers.auth_controller import auth_bp
from controllers.dashboard_controller import dashboard_bp
from controllers.cluster_controller import cluster_bp
from controllers.deployment_controller import deployment_bp

def setup_logging(app):
    """Configure logging for the application"""
    if not app.debug and not app.testing:
        # Create logs directory
        log_dir = Path(__file__).resolve().parent / 'logs'
        log_dir.mkdir(exist_ok=True)

        # File handler for general logs
        file_handler = RotatingFileHandler(
            log_dir / 'app.log',
            maxBytes=10240000,
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)

        app.logger.setLevel(logging.INFO)
        app.logger.info('K8s Orchestrator startup')

def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)
    app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(16))

    # Setup logging
    setup_logging(app)

    # Configure Bootstrap
    Bootstrap5(app)

    # Configure Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please login to access this page.'
    login_manager.login_message_category = 'info'

    @login_manager.user_loader
    def load_user(user_id):
        """Load user by ID for Flask-Login"""
        db = get_db_session()
        try:
            return db.query(User).get(int(user_id))
        except Exception:
            return None
        finally:
            db.close()

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(cluster_bp)
    app.register_blueprint(deployment_bp)

    # Add template filters
    @app.template_filter('status_color')
    def status_color(status):
        """Return Bootstrap color class for status"""
        colors = {
            'active': 'success',
            'running': 'success',
            'unreachable': 'danger',
            'error': 'danger',
            'failed': 'danger',
            'initializing': 'warning',
            'deploying': 'info',
            'stopped': 'secondary',
        }
        return colors.get(status.lower(), 'secondary')

    return app

if __name__ == '__main__':
    app = create_app()
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') == 'development'

    print("=" * 60)
    print("K8s Orchestrator Starting")
    print("=" * 60)
    print(f"Port: {port}")
    print(f"Debug: {debug}")
    print(f"Dashboard: http://localhost:{port}")
    print("=" * 60)

    app.run(host='0.0.0.0', port=port, debug=debug)
