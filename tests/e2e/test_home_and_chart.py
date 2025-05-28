import pytest
import time
import os
import json

def test_home_page_loads_correctly(page):
    """Test that home page loads with all expected elements"""
    base_url = os.getenv('TEST_BASE_URL', 'http://localhost:5001')
    page.goto(f"{base_url}/")
    page.wait_for_load_state('networkidle')
    
    # Check page title
    assert "Tank Dashboard - ReefDB" in page.title()
    
    # Check main heading
    heading = page.locator('h1').inner_text()
    assert "Tank Dashboard" in heading
    
    # Check subtitle
    subtitle = page.locator('.subtitle').inner_text()
    assert "Welcome to your reef tank management system" in subtitle
    
    # Check that all cards are present
    assert page.locator('.dashboard-card').filter(has_text="Test Results Chart").is_visible()
    assert page.locator('.dashboard-card').filter(has_text="Quick Actions").is_visible()
    assert page.locator('.dashboard-card').filter(has_text="System").is_visible()
    assert page.locator('.dashboard-card').filter(has_text="AI Models").is_visible()
    assert page.locator('.dashboard-card').filter(has_text="Data").is_visible()

def test_home_page_card_links(page):
    """Test that home page card links work correctly"""
    base_url = os.getenv('TEST_BASE_URL', 'http://localhost:5001')
    page.goto(f"{base_url}/")
    page.wait_for_load_state('networkidle')
    
    # Test Chart link
    chart_link = page.locator('a[href="/chart"]')
    assert chart_link.is_visible()
    
    # Test Quick Actions links
    assert page.locator('a[href="/test/add"]').is_visible()
    assert page.locator('a[href="/test"]').is_visible()
    assert page.locator('a[href="/coral/add"]').is_visible()
    
    # Test other links
    assert page.locator('a[href="/metrics"]').is_visible()
    assert page.locator('a[href="/models/view"]').is_visible()

def test_navigation_to_chart_page(page):
    """Test navigation from home to chart page"""
    base_url = os.getenv('TEST_BASE_URL', 'http://localhost:5001')
    page.goto(f"{base_url}/")
    page.wait_for_load_state('networkidle')
    
    # Click on chart link
    page.click('a[href="/chart"]')
    page.wait_for_load_state('networkidle')
    
    # Should be redirected to home if no tank selected
    # Or should see chart page if tank is selected
    current_url = page.url
    assert current_url.endswith('/') or current_url.endswith('/chart')

def test_chart_page_with_tank_selection(page):
    """Test chart page functionality with tank selection"""
    base_url = os.getenv('TEST_BASE_URL', 'http://localhost:5001')
    page.goto(f"{base_url}/")
    page.wait_for_load_state('networkidle')
    
    # First, check if there's a tank selector
    tank_selector = page.locator('select[name="tank_id"]')
    if tank_selector.is_visible():
        # Select first available tank
        tank_selector.select_option(index=1)  # Skip "Select a tank" option
        page.wait_for_timeout(1000)
    
    # Now navigate to chart
    page.goto(f"{base_url}/chart")
    page.wait_for_load_state('networkidle')
    
    # If redirected back to home, it means no tank is selected
    if page.url.endswith('/'):
        pytest.skip("No tank available for testing chart functionality")
    
    # Check chart page elements
    assert "Test Results Chart - ReefDB" in page.title()
    heading = page.locator('h1').inner_text()
    assert "Test Results Chart" in heading
    subtitle = page.locator('.subtitle').inner_text()
    assert "Interactive water parameter visualization" in subtitle

def test_chart_page_layout_structure(page):
    """Test that chart page has correct layout structure"""
    base_url = os.getenv('TEST_BASE_URL', 'http://localhost:5001')
    # Try to access chart page directly
    page.goto(f"{base_url}/chart")
    page.wait_for_load_state('networkidle')
    
    # If redirected, skip this test
    if page.url.endswith('/'):
        pytest.skip("No tank selected, cannot test chart layout")
    
    # Check for main layout elements
    assert page.locator('.chart-page').is_visible()
    assert page.locator('.chart-layout').is_visible()
    assert page.locator('.controls-left').is_visible()
    assert page.locator('.chart-main').is_visible()
    assert page.locator('.controls-right').is_visible()

def test_chart_parameter_controls(page):
    """Test chart parameter control checkboxes"""
    base_url = os.getenv('TEST_BASE_URL', 'http://localhost:5001')
    page.goto(f"{base_url}/chart")
    page.wait_for_load_state('networkidle')
    
    if page.url.endswith('/'):
        pytest.skip("No tank selected, cannot test parameter controls")
    
    # Check for parameter checkboxes
    parameters = ['alk', 'cal', 'mg', 'po4', 'no3', 'sg']
    
    for param in parameters:
        # Original data checkbox
        original_checkbox = page.locator(f'#show-{param}')
        assert original_checkbox.is_visible()
        
        # Interpolated data checkbox
        interp_checkbox = page.locator(f'#show-{param}-interp')
        assert interp_checkbox.is_visible()

def test_chart_parameter_toggle_interaction(page):
    """Test that parameter checkboxes can be toggled"""
    base_url = os.getenv('TEST_BASE_URL', 'http://localhost:5001')
    page.goto(f"{base_url}/chart")
    page.wait_for_load_state('networkidle')
    
    if page.url.endswith('/'):
        pytest.skip("No tank selected, cannot test parameter interactions")
    
    # Wait for chart to load
    page.wait_for_selector('#testResultsChart', timeout=10000)
    
    # Test toggling alkalinity checkbox
    alk_checkbox = page.locator('#show-alk')
    
    # Get initial state
    is_initially_checked = alk_checkbox.is_checked()
    
    # Toggle the checkbox
    alk_checkbox.click()
    page.wait_for_timeout(500)  # Wait for chart update
    
    # Verify state changed
    assert alk_checkbox.is_checked() != is_initially_checked
    
    # Toggle back
    alk_checkbox.click()
    page.wait_for_timeout(500)
    
    # Verify back to original state
    assert alk_checkbox.is_checked() == is_initially_checked

def test_chart_canvas_exists(page):
    """Test that chart canvas is present and rendered"""
    base_url = os.getenv('TEST_BASE_URL', 'http://localhost:5001')
    page.goto(f"{base_url}/chart")
    page.wait_for_load_state('networkidle')
    
    if page.url.endswith('/'):
        pytest.skip("No tank selected, cannot test chart canvas")
    
    # Wait for chart canvas to be present
    chart_canvas = page.locator('#testResultsChart')
    assert chart_canvas.is_visible()
    
    # Verify it's a canvas element
    assert chart_canvas.get_attribute('tagName').lower() == 'canvas'

def test_api_endpoint_accessibility(page):
    """Test that API endpoints are accessible via JavaScript"""
    base_url = os.getenv('TEST_BASE_URL', 'http://localhost:5001')
    page.goto(f"{base_url}/chart")
    page.wait_for_load_state('networkidle')
    
    if page.url.endswith('/'):
        pytest.skip("No tank selected, cannot test API endpoints")
    
    # Test API endpoint via JavaScript
    api_response = page.evaluate("""
        async () => {
            try {
                const response = await fetch('/api/test-results-data');
                const data = await response.json();
                return {
                    status: response.status,
                    hasLabels: 'labels' in data,
                    hasDatasets: 'datasets' in data,
                    datasetCount: data.datasets ? data.datasets.length : 0
                };
            } catch (error) {
                return { error: error.message };
            }
        }
    """)
    
    # If we have data, verify structure
    if 'error' not in api_response:
        assert api_response['status'] == 200
        assert api_response['hasLabels'] == True
        assert api_response['hasDatasets'] == True
        # Should have 12 datasets (6 parameters × 2 types)
        assert api_response['datasetCount'] == 12

def test_responsive_layout_mobile(page):
    """Test responsive layout on mobile viewport"""
    base_url = os.getenv('TEST_BASE_URL', 'http://localhost:5001')
    # Set mobile viewport
    page.set_viewport_size({"width": 375, "height": 667})
    
    page.goto(f"{base_url}/")
    page.wait_for_load_state('networkidle')
    
    # Check that cards stack properly on mobile
    dashboard_grid = page.locator('.dashboard-grid')
    assert dashboard_grid.is_visible()
    
    # Cards should be visible and stacked
    cards = page.locator('.dashboard-card')
    card_count = cards.count()
    assert card_count >= 5  # Should have at least 5 cards

def test_responsive_layout_tablet(page):
    """Test responsive layout on tablet viewport"""
    base_url = os.getenv('TEST_BASE_URL', 'http://localhost:5001')
    # Set tablet viewport
    page.set_viewport_size({"width": 768, "height": 1024})
    
    page.goto(f"{base_url}/")
    page.wait_for_load_state('networkidle')
    
    # Check layout adapts to tablet size
    dashboard_grid = page.locator('.dashboard-grid')
    assert dashboard_grid.is_visible()

def test_chart_responsive_layout(page):
    """Test chart page responsive layout"""
    base_url = os.getenv('TEST_BASE_URL', 'http://localhost:5001')
    page.goto(f"{base_url}/chart")
    page.wait_for_load_state('networkidle')
    
    if page.url.endswith('/'):
        pytest.skip("No tank selected, cannot test chart responsive layout")
    
    # Test desktop layout
    page.set_viewport_size({"width": 1200, "height": 800})
    page.wait_for_timeout(500)
    
    chart_layout = page.locator('.chart-layout')
    assert chart_layout.is_visible()
    
    # Test mobile layout
    page.set_viewport_size({"width": 375, "height": 667})
    page.wait_for_timeout(500)
    
    # Chart should still be visible but layout may change
    assert chart_layout.is_visible()

def test_font_loading(page):
    """Test that Inter font loads correctly"""
    base_url = os.getenv('TEST_BASE_URL', 'http://localhost:5001')
    page.goto(f"{base_url}/")
    page.wait_for_load_state('networkidle')
    
    # Check that Inter font is applied
    body_font = page.evaluate("getComputedStyle(document.body).fontFamily")
    assert "Inter" in body_font or "sans-serif" in body_font

def test_css_variables_loaded(page):
    """Test that CSS variables are properly loaded"""
    base_url = os.getenv('TEST_BASE_URL', 'http://localhost:5001')
    page.goto(f"{base_url}/")
    page.wait_for_load_state('networkidle')
    
    # Check CSS variables
    alice_blue = page.evaluate("""
        getComputedStyle(document.documentElement).getPropertyValue('--alice-blue')
    """)
    
    powder_blue = page.evaluate("""
        getComputedStyle(document.documentElement).getPropertyValue('--powder-blue')
    """)
    
    # Variables should be defined (not empty)
    assert alice_blue.strip() != ""
    assert powder_blue.strip() != ""

def test_page_performance(page):
    """Test basic page performance metrics"""
    base_url = os.getenv('TEST_BASE_URL', 'http://localhost:5001')
    # Start performance timing
    page.goto(f"{base_url}/")
    
    # Wait for page to fully load
    page.wait_for_load_state('networkidle')
    
    # Get performance metrics
    performance_data = page.evaluate("""
        () => {
            const perfData = performance.getEntriesByType('navigation')[0];
            return {
                loadTime: perfData.loadEventEnd - perfData.loadEventStart,
                domContentLoaded: perfData.domContentLoadedEventEnd - perfData.domContentLoadedEventStart,
                totalTime: perfData.loadEventEnd - perfData.fetchStart
            };
        }
    """)
    
    # Basic performance assertions (adjust thresholds as needed)
    assert performance_data['totalTime'] < 10000  # Less than 10 seconds total
    assert performance_data['loadTime'] >= 0  # Load time should be non-negative
