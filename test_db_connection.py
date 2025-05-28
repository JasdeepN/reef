#!/usr/bin/env python3
"""
Database connection test script
Tests if the Flask app can connect to the database with the current configuration
"""

import os
import sys

# Add the current directory to Python path
sys.path.insert(0, '/home/admin/dockers/reef/reefdb/web')

# Set environment variables from production config
os.environ['DB_USER'] = 'admin'
os.environ['DB_PASS'] = 'adminpassword'
os.environ['DB_HOST'] = 'reefdb-database'
os.environ['DB_PORT'] = '3306'
os.environ['DB_NAME'] = 'reef'
os.environ['FLASK_ENV'] = 'production'

print("=== Database Connection Test ===")
print(f"DB_USER: {os.environ.get('DB_USER')}")
print(f"DB_PASS: {os.environ.get('DB_PASS')}")
print(f"DB_HOST: {os.environ.get('DB_HOST')}")
print(f"DB_PORT: {os.environ.get('DB_PORT')}")
print(f"DB_NAME: {os.environ.get('DB_NAME')}")

try:
    # Import the Flask app
    from app import app, db
    
    print(f"\n✓ Flask app imported successfully")
    print(f"Database URI: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
    
    # Test database connection
    with app.app_context():
        result = db.session.execute("SELECT 1").scalar()
        print(f"✓ Database connection successful: SELECT 1 returned {result}")
        
        # Test if tables exist
        tables = db.session.execute("SHOW TABLES").fetchall()
        print(f"✓ Found {len(tables)} tables in database")
        if tables:
            print("Tables:", [table[0] for table in tables[:5]])  # Show first 5 tables
            
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
