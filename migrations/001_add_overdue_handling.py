#!/usr/bin/env python3
"""
Migration script to add overdue handling columns to dosing_schedule table.
This script safely adds columns only if they don't already exist.
"""

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from config import Config
import pymysql
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_column_exists(cursor, table_name, column_name):
    """Check if a column exists in a table."""
    try:
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = %s 
            AND COLUMN_NAME = %s
        """, (table_name, column_name))
        result = cursor.fetchone()
        return result[0] > 0
    except Exception as e:
        logger.error(f"Error checking column existence: {e}")
        return False

def add_overdue_handling_columns():
    """Add overdue handling columns to dosing_schedule table."""
    
    # Create Flask app context to access config
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Database connection parameters
    db_config = {
        'host': app.config.get('MYSQL_HOST', 'localhost'),
        'user': app.config.get('MYSQL_USER', 'root'),
        'password': app.config.get('MYSQL_PASSWORD', ''),
        'database': app.config.get('MYSQL_DATABASE', 'reef'),
        'charset': 'utf8mb4'
    }
    
    connection = None
    
    try:
        # Connect to database
        logger.info("Connecting to database...")
        connection = pymysql.connect(**db_config)
        cursor = connection.cursor()
        
        # Define columns to add
        columns_to_add = [
            {
                'name': 'overdue_strategy',
                'definition': "overdue_strategy ENUM('alert_only', 'grace_period', 'catch_up', 'manual_approval') DEFAULT 'alert_only'"
            },
            {
                'name': 'grace_period_hours',
                'definition': "grace_period_hours INT DEFAULT 24"
            },
            {
                'name': 'max_catch_up_doses',
                'definition': "max_catch_up_doses INT DEFAULT 3"
            },
            {
                'name': 'catch_up_window_hours',
                'definition': "catch_up_window_hours INT DEFAULT 72"
            },
            {
                'name': 'notify_overdue',
                'definition': "notify_overdue BOOLEAN DEFAULT TRUE"
            }
        ]
        
        logger.info("Checking existing columns in dosing_schedule table...")
        
        # Check which columns already exist
        existing_columns = []
        missing_columns = []
        
        for column in columns_to_add:
            if check_column_exists(cursor, 'dosing_schedule', column['name']):
                existing_columns.append(column['name'])
                logger.info(f"Column '{column['name']}' already exists - skipping")
            else:
                missing_columns.append(column)
                logger.info(f"Column '{column['name']}' needs to be added")
        
        if not missing_columns:
            logger.info("All overdue handling columns already exist. Migration not needed.")
            return True
        
        # Add missing columns
        logger.info(f"Adding {len(missing_columns)} missing columns...")
        
        for column in missing_columns:
            try:
                sql = f"ALTER TABLE dosing_schedule ADD COLUMN {column['definition']}"
                logger.info(f"Executing: {sql}")
                cursor.execute(sql)
                logger.info(f"Successfully added column '{column['name']}'")
            except Exception as e:
                logger.error(f"Error adding column '{column['name']}': {e}")
                raise
        
        # Add constraints if needed
        logger.info("Adding constraints...")
        
        constraints = [
            {
                'name': 'grace_period_hours_range',
                'sql': "ALTER TABLE dosing_schedule ADD CONSTRAINT chk_grace_period_hours CHECK (grace_period_hours >= 1 AND grace_period_hours <= 72)",
                'column': 'grace_period_hours'
            },
            {
                'name': 'max_catch_up_doses_range', 
                'sql': "ALTER TABLE dosing_schedule ADD CONSTRAINT chk_max_catch_up_doses CHECK (max_catch_up_doses >= 1 AND max_catch_up_doses <= 10)",
                'column': 'max_catch_up_doses'
            },
            {
                'name': 'catch_up_window_hours_range',
                'sql': "ALTER TABLE dosing_schedule ADD CONSTRAINT chk_catch_up_window_hours CHECK (catch_up_window_hours >= 1 AND catch_up_window_hours <= 168)",
                'column': 'catch_up_window_hours'
            }
        ]
        
        for constraint in constraints:
            # Only add constraint if the column was added in this migration
            column_added = any(col['name'] == constraint['column'] for col in missing_columns)
            if column_added:
                try:
                    cursor.execute(constraint['sql'])
                    logger.info(f"Added constraint '{constraint['name']}'")
                except pymysql.Error as e:
                    # Constraint might already exist, which is okay
                    if "Duplicate key name" in str(e) or "already exists" in str(e):
                        logger.info(f"Constraint '{constraint['name']}' already exists - skipping")
                    else:
                        logger.warning(f"Could not add constraint '{constraint['name']}': {e}")
        
        # Commit changes
        connection.commit()
        logger.info("Migration completed successfully!")
        
        # Verify the migration
        logger.info("Verifying migration...")
        for column in columns_to_add:
            if check_column_exists(cursor, 'dosing_schedule', column['name']):
                logger.info(f"✓ Column '{column['name']}' verified")
            else:
                logger.error(f"✗ Column '{column['name']}' missing after migration")
                return False
        
        logger.info("All columns verified successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        if connection:
            connection.rollback()
            logger.info("Changes rolled back")
        return False
        
    finally:
        if connection:
            connection.close()
            logger.info("Database connection closed")

def rollback_migration():
    """Rollback the migration by removing added columns."""
    
    # Create Flask app context to access config
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Database connection parameters
    db_config = {
        'host': app.config.get('MYSQL_HOST', 'localhost'),
        'user': app.config.get('MYSQL_USER', 'root'),
        'password': app.config.get('MYSQL_PASSWORD', ''),
        'database': app.config.get('MYSQL_DATABASE', 'reef'),
        'charset': 'utf8mb4'
    }
    
    connection = None
    
    try:
        # Connect to database
        logger.info("Connecting to database for rollback...")
        connection = pymysql.connect(**db_config)
        cursor = connection.cursor()
        
        # Columns to remove
        columns_to_remove = [
            'overdue_strategy',
            'grace_period_hours', 
            'max_catch_up_doses',
            'catch_up_window_hours',
            'notify_overdue'
        ]
        
        logger.info("Rolling back overdue handling columns...")
        
        for column in columns_to_remove:
            if check_column_exists(cursor, 'dosing_schedule', column):
                try:
                    sql = f"ALTER TABLE dosing_schedule DROP COLUMN {column}"
                    logger.info(f"Executing: {sql}")
                    cursor.execute(sql)
                    logger.info(f"Removed column '{column}'")
                except Exception as e:
                    logger.error(f"Error removing column '{column}': {e}")
                    raise
            else:
                logger.info(f"Column '{column}' doesn't exist - skipping")
        
        # Commit changes
        connection.commit()
        logger.info("Rollback completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        if connection:
            connection.rollback()
        return False
        
    finally:
        if connection:
            connection.close()
            logger.info("Database connection closed")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Overdue handling migration script')
    parser.add_argument('--rollback', action='store_true', help='Rollback the migration')
    args = parser.parse_args()
    
    if args.rollback:
        logger.info("Starting migration rollback...")
        success = rollback_migration()
    else:
        logger.info("Starting migration...")
        success = add_overdue_handling_columns()
    
    if success:
        logger.info("Operation completed successfully!")
        sys.exit(0)
    else:
        logger.error("Operation failed!")
        sys.exit(1)