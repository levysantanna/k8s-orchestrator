#!/bin/bash
set -e

# Initialize database on first run if it doesn't exist
if [ ! -f "/app/data/orchestrator.db" ]; then
    echo "First run detected - initializing database..."
    python scripts/init-db.py
fi

# Execute the main application
exec "$@"
