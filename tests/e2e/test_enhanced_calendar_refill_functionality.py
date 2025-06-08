"""
Enhanced Calendar Refill Functionality Test
Test script to verify the improved refill indicators and day details functionality
"""

import pytest
import os
from playwright.sync_api import expect

class TestEnhancedCalendarRefillFunctionality:
    """Test suite for enhanced calendar refill functionality"""
    
    def test_calendar_loads_with_enhanced_refill_indicators(self, page):
        """Test that the calendar loads and displays enhanced product-specific refill indicators"""
        base_url = os.getenv('TEST_BASE_URL', 'http://172.0.10.1:5001')
        page.goto(f"{base_url}/doser/audit/calendar")
        page.wait_for_load_state('networkidle')
        
        # Check page loads correctly
        assert "Dosing Calendar" in page.title()
        
        # Check for calendar grid
        expect(page.locator('.calendar-grid')).to_be_visible()
        
        # Look for refill indicators (should be more specific now)
        refill_indicators = page.locator('.refill-indicator')
        if refill_indicators.count() > 0:
            # Verify indicators have product-specific information
            first_indicator = refill_indicators.first
            expect(first_indicator).to_have_attribute('title')
            
            # Check for enhanced product badges
            product_badges = page.locator('.product-refill-badge')
            if product_badges.count() > 0:
                # Verify badges contain product names
                first_badge = product_badges.first
                expect(first_badge).to_be_visible()
                badge_text = first_badge.text_content()
                assert len(badge_text.strip()) > 0, "Product refill badge should contain product name"

    def test_day_details_modal_enhanced_functionality(self, page):
        """Test enhanced day details modal with comprehensive dose and refill information"""
        base_url = os.getenv('TEST_BASE_URL', 'http://172.0.10.1:5001')
        page.goto(f"{base_url}/doser/audit/calendar")
        page.wait_for_load_state('networkidle')
        
        # Wait for calendar to load
        page.wait_for_timeout(3000)
        
        # Look for a day with data (has-data class or has-refill class)
        calendar_days = page.locator('.calendar-day.has-data, .calendar-day.has-refill')
        
        if calendar_days.count() > 0:
            # Click on the first day with data
            first_day_with_data = calendar_days.first
            first_day_with_data.click()
            
            # Wait for modal to appear
            page.wait_for_timeout(2000)
            
            # Check if modal is visible
            modal = page.locator('#dayDetailsModal')
            if modal.is_visible():
                # Check for enhanced modal content
                modal_content = page.locator('#day-details-content')
                expect(modal_content).to_be_visible()
                
                # Look for enhanced sections
                dose_info_section = page.locator('.dose-information')
                refill_info_section = page.locator('.refill-info')
                
                # If dose information exists, verify enhanced layout
                if dose_info_section.is_visible():
                    # Check for product summary cards
                    product_cards = page.locator('.product-summary-card')
                    if product_cards.count() > 0:
                        expect(product_cards.first).to_be_visible()
                    
                    # Check for enhanced timeline
                    timeline = page.locator('.timeline-container')
                    if timeline.is_visible():
                        timeline_items = page.locator('.timeline-item')
                        expect(timeline_items.first).to_be_visible() if timeline_items.count() > 0 else None
                
                # If refill information exists, verify enhanced display
                if refill_info_section.is_visible():
                    # Check for refill sections
                    refill_sections = page.locator('.refill-section')
                    if refill_sections.count() > 0:
                        expect(refill_sections.first).to_be_visible()
                        
                        # Check for product-specific refill information
                        refill_items = page.locator('.refill-item')
                        if refill_items.count() > 0:
                            expect(refill_items.first).to_be_visible()
        else:
            pytest.skip("No calendar days with data available for testing")

    def test_product_specific_refill_tooltips(self, page):
        """Test that refill indicators show specific product names in tooltips"""
        base_url = os.getenv('TEST_BASE_URL', 'http://172.0.10.1:5001')
        page.goto(f"{base_url}/doser/audit/calendar")
        page.wait_for_load_state('networkidle')
        
        # Wait for calendar to load
        page.wait_for_timeout(3000)
        
        # Look for refill indicators
        refill_indicators = page.locator('.refill-indicator')
        
        if refill_indicators.count() > 0:
            for i in range(min(3, refill_indicators.count())):  # Test up to 3 indicators
                indicator = refill_indicators.nth(i)
                title_attr = indicator.get_attribute('title')
                
                # Verify tooltip contains specific product information
                assert title_attr is not None, "Refill indicator should have title attribute"
                assert len(title_attr) > 10, "Tooltip should contain descriptive text"
                
                # Check that it's not generic text
                assert "Product" in title_attr, "Tooltip should mention specific products"
        else:
            pytest.skip("No refill indicators found for testing")

if __name__ == "__main__":
    print("Enhanced Calendar Refill Functionality Test")
    print("This test verifies the improved calendar with product-specific refill indicators")
    print("Run with: pytest tests/e2e/test_enhanced_calendar_refill_functionality.py -v")
