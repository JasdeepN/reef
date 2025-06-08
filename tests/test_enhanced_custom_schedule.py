#!/usr/bin/env python3
"""
Test the enhanced custom schedule functionality.
This tests the _calculate_custom_schedule function and form data processing.
"""

import sys
import os
sys.path.append('/home/admin/dockers/reef/reefdb/web')

def test_calculate_custom_schedule():
    """Test the enhanced _calculate_custom_schedule function"""
    # Import the function
    from app.routes.doser import _calculate_custom_schedule
    print("Testing enhanced _calculate_custom_schedule function...")
    # Test 1: Day-based scheduling
    test_data_1 = {
        'repeat_every_n_days': '2',
        'custom_time': '14:30'
    }
    result_1 = _calculate_custom_schedule(test_data_1)
    expected_1 = 2 * 24 * 3600  # 2 days in seconds
    print(f"Test 1 - Day-based (2 days): {result_1} == {expected_1} : {'✅' if result_1 == expected_1 else '❌'}")
    # Test 2: Second-based scheduling
    test_data_2 = {
        'custom_seconds': '7200'  # 2 hours
    }
    result_2 = _calculate_custom_schedule(test_data_2)
    expected_2 = 7200
    print(f"Test 2 - Second-based (2 hours): {result_2} == {expected_2} : {'✅' if result_2 == expected_2 else '❌'}")
    # Test 3: Invalid day range (too high)
    test_data_3 = {
        'repeat_every_n_days': '400',
        'custom_time': '09:00'
    }
    result_3 = _calculate_custom_schedule(test_data_3)
    print(f"Test 3 - Invalid day range (400): {result_3} is None : {'✅' if result_3 is None else '❌'}")
    # Test 4: Invalid second range (too low)
    test_data_4 = {
        'custom_seconds': '30'  # Below minimum 60
    }
    result_4 = _calculate_custom_schedule(test_data_4)
    print(f"Test 4 - Invalid seconds (30): {result_4} is None : {'✅' if result_4 is None else '❌'}")
    # Test 5: Missing both
    test_data_5 = {}
    result_5 = _calculate_custom_schedule(test_data_5)
    print(f"Test 5 - Missing both: {result_5} is None : {'✅' if result_5 is None else '❌'}")
    # Test 6: Priority test (day-based should take precedence)
    test_data_6 = {
        'repeat_every_n_days': '1',
        'custom_time': '10:00',
        'custom_seconds': '3600'
    }
    result_6 = _calculate_custom_schedule(test_data_6)
    expected_6 = 1 * 24 * 3600  # 1 day in seconds (should prioritize day-based)
    print(f"Test 6 - Priority (day-based wins): {result_6} == {expected_6} : {'✅' if result_6 == expected_6 else '❌'}")

def test_database_connection():
    """Test database connection and query existing schedule"""
    try:
        from extensions import db
        from modules.models import DSchedule
        print("\nTesting database integration...")
        # Query existing schedule ID 1
        schedule = DSchedule.query.filter_by(id=1).first()
        if schedule:
            print(f"✅ Found existing schedule: ID {schedule.id}, interval {schedule.trigger_interval}s")
            print(f"   - Product ID: {schedule.product_id}")
            print(f"   - Amount: {schedule.amount}ml")
            print(f"   - Schedule Type: {schedule.schedule_type}")
            print(f"   - Repeat Every N Days: {schedule.repeat_every_n_days}")
            print(f"   - Trigger Time: {schedule.trigger_time}")
            print(f"   - Doser ID: {schedule.doser_id}")
        else:
            print("❌ Could not find schedule ID 1")
    except Exception as e:
        print(f"❌ Database connection error: {e}")

if __name__ == "__main__":
    print("🧪 Enhanced Custom Schedule Test Suite")
    print("=" * 50)
    test_calculate_custom_schedule()
    test_database_connection()
    print("\n✅ Test suite completed!")
