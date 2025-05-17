import os

BASE_URL = os.getenv('TEST_BASE_URL')


def test_home_nav_tank_footer(page):
    page.goto(f"{BASE_URL}/")
    # Check title
    assert "test" in page.title() or "reef" in page.title().lower(), "Page title missing or incorrect"
    # Check h1, h2, or h3 title exists and is visible
    heading = None
    for tag in ['h1', 'h2', 'h3']:
        el = page.locator(tag)
        if el.count() > 0 and el.first.is_visible():
            heading = el.first
            break
    assert heading is not None, "No visible H1, H2, or H3 title found"
    assert heading.inner_text().strip() != "", "Heading is empty"

    # Check for div with class 'app container'
    app_container = page.locator('div.app-container')
    assert app_container.is_visible(), "Div with class 'app container' not visible"
    # Check navbar exists
    assert page.locator('nav.navbar').is_visible(), "Navbar not visible"
    # Check tank dropdown exists and has at least one option
    tank_select = page.locator('#tank-select')
    assert tank_select.is_visible(), "Tank dropdown not visible"
    assert tank_select.locator('option').count() > 0, "No tanks in dropdown"
    # Check footer exists and contains expected text
    footer = page.locator('footer')
    assert footer.is_visible(), "Footer not visible"
    assert "footer" in footer.inner_text().lower(), "Footer text missing or incorrect"
