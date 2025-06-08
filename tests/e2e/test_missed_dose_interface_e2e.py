import pytest
import os
from playwright.sync_api import expect

class TestMissedDoseInterfaceE2E:
    """E2E test suite for missed dose interface"""
    
    def test_missed_dose_dashboard_shows_new_buttons(self, page):
        """Test that the missed dose dashboard shows Dose/Skip buttons instead of Approve/Reject"""
        base_url = os.getenv('TEST_BASE_URL', 'http://172.0.10.1:5001')
        page.goto(f"{base_url}/missed-dose/dashboard")
        page.wait_for_load_state('networkidle')
        
        # Check page loads correctly
        assert "Missed Dose Management" in page.title() or "ReefDB" in page.title()
        
        # Check for new interface elements
        page_content = page.content()
        
        # Should have new button text
        assert 'Dose' in page_content
        assert 'Skip' in page_content
        
        # Should NOT have old button text in the main content (excluding any labels/configs)
        missed_dose_section = page.locator('[data-request-id]').first
        if missed_dose_section.is_visible():
            # If there are missed dose requests, check button classes
            expect(page.locator('.dose-btn')).to_be_visible()
            expect(page.locator('.skip-btn')).to_be_visible()
            
            # Old button classes should not exist
            expect(page.locator('.approve-btn')).to_have_count(0)
            expect(page.locator('.reject-btn')).to_have_count(0)

    def test_missed_dose_modal_functionality(self, page):
        """Test that clicking buttons opens the correct modal"""
        base_url = os.getenv('TEST_BASE_URL', 'http://172.0.10.1:5001')
        page.goto(f"{base_url}/missed-dose/dashboard")
        page.wait_for_load_state('networkidle')
        
        # Check if there are any pending missed doses to test with
        dose_buttons = page.locator('.dose-btn')
        if dose_buttons.count() > 0:
            # Test dose button
            dose_buttons.first.click()
            page.wait_for_timeout(500)
            
            # Check modal opens with correct title
            modal = page.locator('#notesModal')
            expect(modal).to_be_visible()
            
            modal_title = page.locator('#notes-modal-title')
            expect(modal_title).to_contain_text('Dose Now')
            
            # Close modal
            page.locator('.btn-close').click()
            page.wait_for_timeout(500)
            
            # Test skip button
            skip_buttons = page.locator('.skip-btn')
            skip_buttons.first.click()
            page.wait_for_timeout(500)
            
            expect(modal).to_be_visible()
            expect(modal_title).to_contain_text('Skip')
            
        else:
            pytest.skip("No pending missed doses available for testing")

    def test_section_header_updated(self, page):
        """Test that the section header reflects new terminology"""
        base_url = os.getenv('TEST_BASE_URL', 'http://172.0.10.1:5001')
        page.goto(f"{base_url}/missed-dose/dashboard")
        page.wait_for_load_state('networkidle')
        
        page_content = page.content()
        
        # Check for updated section header
        assert 'Missed Doses Requiring Action' in page_content
        
        # Should not have old header text
        assert 'Pending Missed Dose Approvals' not in page_content
