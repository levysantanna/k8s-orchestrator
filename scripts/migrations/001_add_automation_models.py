#!/usr/bin/env python3
"""
Database Migration: Add CloudForms automation models
Creates tables for provisioning requests, approvals, catalog, and policies

Run with: python scripts/migrations/001_add_automation_models.py
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from functions.base import engine, Base
from functions.database import User  # Import User model for foreign key reference
from models.cluster import Cluster  # Import Cluster model for foreign key reference
from models.automation import ProvisioningRequest, ApprovalRecord, BackgroundTask
from models.catalog import ServiceCatalogItem, ServiceDialog, DeployedService
from models.policy import QuotaPolicy, RetirementPolicy


def migrate():
    """Run migration to create all automation tables"""
    print("=" * 60)
    print("CloudForms Automation Models Migration")
    print("=" * 60)

    print("\n📦 Creating automation tables...")
    print("  - provisioning_requests")
    print("  - approval_records")
    print("  - background_tasks")
    print("  - service_catalog_items")
    print("  - service_dialogs")
    print("  - deployed_services")
    print("  - quota_policies")
    print("  - retirement_policies")

    try:
        # Create all tables defined in Base metadata
        Base.metadata.create_all(bind=engine)
        print("\n✅ Migration completed successfully!")
        print("\nNext steps:")
        print("  1. Run app to verify tables are accessible")
        print("  2. Seed catalog with: python scripts/seed_catalog.py")
        print("  3. Initialize scheduler in app.py")

    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    migrate()
