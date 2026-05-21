#!/usr/bin/env python3
"""
Database initialization script
Creates all tables and optionally seeds initial data
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from functions.base import Base, engine, get_db_session
from functions.database import User
from models.cluster import Cluster, Node
from models.agent import MCPAgent
from models.metrics import MetricsSnapshot
from dotenv import load_dotenv

def init_database():
    """Initialize database tables"""
    print("Creating database tables...")
    Base.metadata.create_all(engine)
    print("✓ Tables created successfully")

def create_admin_user():
    """Create default admin user if not exists"""
    load_dotenv()

    admin_username = os.getenv('ADMIN_USERNAME', 'admin')
    admin_password = os.getenv('ADMIN_PASSWORD', 'changeme')

    db = get_db_session()
    try:
        # Check if admin exists
        existing_admin = db.query(User).filter_by(username=admin_username).first()
        if existing_admin:
            print(f"✓ Admin user '{admin_username}' already exists")
            return

        # Create admin user
        admin = User(
            username=admin_username,
            email=f"{admin_username}@localhost",
            role='admin',
            is_active=True
        )
        admin.set_password(admin_password)

        db.add(admin)
        db.commit()

        print(f"✓ Admin user created:")
        print(f"  Username: {admin_username}")
        print(f"  Password: {admin_password}")
        print(f"  IMPORTANT: Change this password after first login!")

    except Exception as e:
        print(f"✗ Error creating admin user: {e}")
        db.rollback()
    finally:
        db.close()

def main():
    """Main initialization function"""
    print("=" * 60)
    print("K8s Orchestrator - Database Initialization")
    print("=" * 60)
    print()

    try:
        init_database()
        create_admin_user()

        print()
        print("=" * 60)
        print("Database initialization complete!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("1. Start Redis: docker run -d -p 6379:6379 redis:alpine")
        print("2. Run application: python app.py")
        print("3. Access dashboard: http://localhost:5000")
        print()

    except Exception as e:
        print(f"\n✗ Error during initialization: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
