#!/usr/bin/env python3
"""
Test script to verify CI environment variable override behavior
"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

# Load test environment
from dotenv import load_dotenv
load_dotenv(os.path.join("tests", ".env.test"))

print("=== BEFORE CI OVERRIDE ===")
print(f"DB_HOST_ADDRESS: {os.getenv('DB_HOST_ADDRESS')}")
print(f"DB_HOST: {os.getenv('DB_HOST')}")
print(f"CI: {os.getenv('CI')}")

# Simulate CI environment
os.environ["CI"] = "true"

# Force DB_HOST_ADDRESS to 127.0.0.1 in CI to match MySQL service (like conftest.py does)
if os.getenv("CI"):
    os.environ["DB_HOST_ADDRESS"] = "127.0.0.1"

print("\n=== AFTER CI OVERRIDE ===")
print(f"DB_HOST_ADDRESS: {os.getenv('DB_HOST_ADDRESS')}")
print(f"DB_HOST: {os.getenv('DB_HOST')}")
print(f"CI: {os.getenv('CI')}")

# Test the database connection string
db_url = f"mysql+pymysql://{os.getenv('DB_USER', 'testuser')}:{os.getenv('DB_PASS')}@{os.getenv('DB_HOST_ADDRESS', '127.0.0.1')}:{os.getenv('DB_PORT', '3310')}/{os.getenv('DB_NAME', 'reef_test')}"
print(f"\nConnection string: {db_url}")
