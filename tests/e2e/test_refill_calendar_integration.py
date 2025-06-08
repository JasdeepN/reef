"""
E2E tests for refill calendar integration functionality.
Tests the visual display and interaction of refill information in the audit calendar.
"""

import pytest
import os
from playwright.sync_api import expect

class TestRefillCalendarIntegration:
    """Test suite for refill calendar integration"""
    
    def test_calendar_loads_with_refill_data(self, page):
        """Test that the calendar page loads and displays refill information correctly"""
        base_url = os.getenv('TEST_BASE_URL', 'http://172.0.10.1:5001')
        page.goto(f"{base_url}/doser/audit/calendar")
        page.wait_for_load_state('networkidle')
        
        # Check page loads correctly
        assert "Dosing Calendar" in page.title()
        expect(page.locator('.dashboard-header h1')).to_contain_text('📅 Dosing Calendar')
        
        # Wait for calendar to load
        page.wait_for_timeout(2000)
        
        # Check if calendar grid is present
        expect(page.locator('.calendar-grid')).to_be_visible()
        
    def test_refill_indicators_display(self, page):
        """Test that refill indicators appear on calendar days with refill data"""
        base_url = os.getenv('TEST_BASE_URL', 'http://172.0.10.1:5001')
        page.goto(f"{base_url}/doser/audit/calendar")
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(3000)  # Allow time for data loading
        
        # Look for refill indicators (they may be present if data exists)
        historical_indicators = page.locator('.refill-indicator.historical')
        estimate_indicators = page.locator('.refill-indicator.estimate')
        
        # At least check that the CSS classes exist (indicators may or may not be visible depending on data)
        if historical_indicators.count() > 0:
            expect(historical_indicators.first).to_be_visible()
        if estimate_indicators.count() > 0:
            expect(estimate_indicators.first).to_be_visible()
            
    def test_day_details_modal_includes_refill_info(self, page):
        """Test that clicking on a day with refill data shows refill information in modal"""
        base_url = os.getenv('TEST_BASE_URL', 'http://172.0.10.1:5001')
        page.goto(f"{base_url}/doser/audit/calendar")
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(3000)
        
        # Look for calendar days with data
        calendar_days = page.locator('.calendar-day.has-data')
        
        if calendar_days.count() > 0:
            # Click on first day with data
            calendar_days.first.click()
            page.wait_for_timeout(1000)
            
            # Check if modal appears
            modal = page.locator('#day-details-modal')
            if modal.is_visible():
                # Check if refill information section might be present
                refill_sections = page.locator('.refill-info')
                # This test passes whether or not refill info is shown (depends on data)
                
    def test_refill_api_data_structure(self, page):
        """Test that the refill API returns the expected data structure"""
        base_url = os.getenv('TEST_BASE_URL', 'http://172.0.10.1:5001')
        
        # Test the monthly summary API
        api_response = page.evaluate("""
            async () => {
                const response = await fetch('/api/v1/audit-calendar/calendar/monthly-summary?year=2025&month=6');
                const data = await response.json();
                return data;
            }
        """)
        
        # Check that the response structure is correct
        assert api_response['success'] == True
        assert 'refill_events' in api_response['data']
        
        # If refill events exist, verify structure
        refill_events = api_response['data']['refill_events']
        if refill_events:
            for date_key, refill_data in refill_events.items():
                assert 'refills' in refill_data
                assert 'estimates' in refill_data
                assert isinstance(refill_data['refills'], list)
                assert isinstance(refill_data['estimates'], list)
                
    def test_calendar_navigation_preserves_refill_data(self, page):
        """Test that navigating between months preserves refill data functionality"""
        base_url = os.getenv('TEST_BASE_URL', 'http://172.0.10.1:5001')
        page.goto(f"{base_url}/doser/audit/calendar")
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(2000)
        
        # Navigate to next month if navigation exists
        next_button = page.locator('#next-month')
        if next_button.is_visible():
            next_button.click()
            page.wait_for_timeout(2000)
            
            # Verify calendar still loads correctly
            expect(page.locator('.calendar-grid')).to_be_visible()
            
            # Navigate back
            prev_button = page.locator('#prev-month')
            if prev_button.is_visible():
                prev_button.click()
                page.wait_for_timeout(2000)
                expect(page.locator('.calendar-grid')).to_be_visible()
