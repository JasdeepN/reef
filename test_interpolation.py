#!/usr/bin/env python3
"""
Test script for interpolation functionality
"""

from app import app, db
from modules.models import TestResults, Tank
from datetime import datetime, date, time
import random

def create_test_data_with_gaps():
    """Create test data with some missing values to test interpolation"""
    
    with app.app_context():
        # Get the first tank or create one
        tank = Tank.query.first()
        if not tank:
            tank = Tank(name="Test Tank", volume=100, volume_unit="gallons")
            db.session.add(tank)
            db.session.commit()
        
        tank_id = tank.id
        
        # Clear existing test data for this tank
        TestResults.query.filter_by(tank_id=tank_id).delete()
        
        # Create test data with gaps
        base_date = date(2024, 1, 1)
        test_time = time(10, 0)
        
        # Generate some test results with intentional gaps
        test_data = [
            # Day 1 - all values
            {"alk": 8.5, "cal": 420, "mg": 1350, "po4_ppm": 0.03, "no3_ppm": 5, "sg": 1.025},
            # Day 2 - missing some values
            {"alk": None, "cal": 430, "mg": None, "po4_ppm": 0.04, "no3_ppm": None, "sg": 1.025},
            # Day 3 - missing different values
            {"alk": 8.3, "cal": None, "mg": 1360, "po4_ppm": None, "no3_ppm": 8, "sg": None},
            # Day 4 - all values
            {"alk": 8.2, "cal": 440, "mg": 1370, "po4_ppm": 0.05, "no3_ppm": 10, "sg": 1.026},
            # Day 5 - missing some values
            {"alk": None, "cal": None, "mg": 1380, "po4_ppm": 0.06, "no3_ppm": None, "sg": 1.026},
            # Day 6 - all values
            {"alk": 8.0, "cal": 450, "mg": 1390, "po4_ppm": 0.07, "no3_ppm": 12, "sg": 1.027},
        ]
        
        for i, data in enumerate(test_data):
            test_date = date(2024, 1, i + 1)
            
            test = TestResults(
                test_date=test_date,
                test_time=test_time,
                tank_id=tank_id,
                alk=data["alk"],
                cal=data["cal"],
                mg=data["mg"],
                po4_ppm=data["po4_ppm"],
                no3_ppm=data["no3_ppm"],
                sg=data["sg"]
            )
            db.session.add(test)
        
        db.session.commit()
        print(f"Created {len(test_data)} test results with gaps for tank {tank_id}")
        
        # Print the data to verify
        tests = TestResults.query.filter_by(tank_id=tank_id).order_by(TestResults.test_date).all()
        print("\nTest data created:")
        print("Date\t\tAlk\tCal\tMg\tPO4\tNO3\tSG")
        for test in tests:
            print(f"{test.test_date}\t{test.alk}\t{test.cal}\t{test.mg}\t{test.po4_ppm}\t{test.no3_ppm}\t{test.sg}")

def test_interpolation_functions():
    """Test the interpolation functions directly"""
    
    # Import the functions we want to test
    from app.routes.home import _interpolate_missing_values, _find_surrounding_values
    
    # Test data with gaps
    test_values = [8.5, None, 8.3, 8.2, None, 8.0]
    
    print(f"\nOriginal values: {test_values}")
    
    # Test interpolation
    interpolated = _interpolate_missing_values(test_values)
    print(f"Interpolated values: {interpolated}")
    
    # Test find surrounding values
    prev_val, prev_idx, next_val, next_idx = _find_surrounding_values(test_values, 1)
    print(f"For index 1: prev={prev_val} (idx {prev_idx}), next={next_val} (idx {next_idx})")
    
    prev_val, prev_idx, next_val, next_idx = _find_surrounding_values(test_values, 4)
    print(f"For index 4: prev={prev_val} (idx {prev_idx}), next={next_val} (idx {next_idx})")

if __name__ == "__main__":
    print("Testing interpolation functionality...")
    create_test_data_with_gaps()
    test_interpolation_functions()
    print("\nTest completed! You can now visit /chart to see the interpolated data.")
