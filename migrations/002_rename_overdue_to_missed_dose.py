#!/usr/bin/env python3
"""
Migration: Rename "overdue" terminology to "missed dose" throughout the system
This migration renames database columns and enum values to use "missed_dose" terminology
for better clarity and to prevent dangerous parameter swings in reef tanks.
"""

import mysql.connector
from mysql.connector import Error
import sys
import os

# Add the parent directory to the path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

def get_connection():
    """Get database connection using config settings"""
    try:
        connection = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            database=Config.MYSQL_DATABASE,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        sys.exit(1)

def execute_query(connection, query, description):
    """Execute a SQL query with error handling"""
    try:
        cursor = connection.cursor()
        print(f"Executing: {description}")
        cursor.execute(query)
        connection.commit()
        print(f"✅ Success: {description}")
        cursor.close()
    except Error as e:
        print(f"❌ Error executing {description}: {e}")
        return False
    return True

def main():
    """Main migration function"""
    print("🔄 Starting migration: Rename overdue to missed_dose terminology")
    
    connection = get_connection()
    
    try:
        # Step 1: Rename the main enum column and update enum values
        migrations = [
            {
                'query': """
                    ALTER TABLE d_schedule 
                    CHANGE COLUMN overdue_handling missed_dose_handling 
                    ENUM('alert_only', 'grace_period', 'manual_approval') 
                    DEFAULT 'alert_only' NOT NULL
                """,
                'description': "Rename overdue_handling to missed_dose_handling and remove catch_up option"
            },
            
            # Step 2: Rename grace period column
            {
                'query': """
                    ALTER TABLE d_schedule 
                    CHANGE COLUMN grace_period_hours missed_dose_grace_period_hours 
                    INT DEFAULT 12
                """,
                'description': "Rename grace_period_hours to missed_dose_grace_period_hours"
            },
            
            # Step 3: Rename notification column  
            {
                'query': """
                    ALTER TABLE d_schedule 
                    CHANGE COLUMN overdue_notification_enabled missed_dose_notification_enabled 
                    TINYINT(1) DEFAULT 1
                """,
                'description': "Rename overdue_notification_enabled to missed_dose_notification_enabled"
            },
            
            # Step 4: Drop the dangerous catch-up related columns to prevent parameter swings
            {
                'query': "ALTER TABLE d_schedule DROP COLUMN max_catch_up_doses",
                'description': "Remove max_catch_up_doses column (dangerous for reef tanks)"
            },
            
            {
                'query': "ALTER TABLE d_schedule DROP COLUMN catch_up_window_hours", 
                'description': "Remove catch_up_window_hours column (dangerous for reef tanks)"
            },
            
            # Step 5: Rename overdue_dose_requests table to missed_dose_requests
            {
                'query': "RENAME TABLE overdue_dose_requests TO missed_dose_requests",
                'description': "Rename overdue_dose_requests table to missed_dose_requests"
            },
            
            # Step 6: Update the missed_dose_time column name for clarity
            {
                'query': """
                    ALTER TABLE missed_dose_requests 
                    CHANGE COLUMN hours_overdue hours_missed 
                    FLOAT(12) NOT NULL
                """,
                'description': "Rename hours_overdue to hours_missed in missed_dose_requests table"
            }
        ]
        
        # Execute all migrations
        success_count = 0
        for migration in migrations:
            if execute_query(connection, migration['query'], migration['description']):
                success_count += 1
            else:
                print(f"⚠️  Migration failed, stopping at: {migration['description']}")
                break
        
        print(f"\n✅ Migration completed successfully! {success_count}/{len(migrations)} steps completed.")
        print("\n📊 Updated schema summary:")
        print("   • overdue_handling → missed_dose_handling (enum: alert_only, grace_period, manual_approval)")
        print("   • grace_period_hours → missed_dose_grace_period_hours") 
        print("   • overdue_notification_enabled → missed_dose_notification_enabled")
        print("   • ❌ Removed max_catch_up_doses (prevents dangerous parameter swings)")
        print("   • ❌ Removed catch_up_window_hours (prevents dangerous parameter swings)")
        print("   • overdue_dose_requests → missed_dose_requests")
        print("   • hours_overdue → hours_missed")
        
    except Exception as e:
        print(f"❌ Migration failed with error: {e}")
        sys.exit(1)
    finally:
        if connection.is_connected():
            connection.close()
            print("🔌 Database connection closed")

if __name__ == "__main__":
    main()
