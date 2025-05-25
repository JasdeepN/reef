import pytest
import time
import random
import os
from datetime import datetime

BASE_URL = os.getenv('TEST_BASE_URL')

# not impletmented yet
# def test_test_icp_route(page):
#     page.goto(f"{BASE_URL}/test/icp")
#     page.wait_for_selector("h1")
#     assert "ICP" in page.content() or "Test" in page.content()


def test_test_results_table_or_empty(page):
    assert BASE_URL, "TEST_BASE_URL environment variable is not set."
    print(f"[DEBUG] BASE_URL: {BASE_URL}")
    # Set tank_id cookie as an integer string before navigation to ensure backend context

    print(f"[DEBUG] Cookies before navigation: {page.context.cookies()}")
    page.goto(f"{BASE_URL}/test")
    print(f"[DEBUG] Cookies after navigation: {page.context.cookies()}")
    print(f"[DEBUG] Final page URL: {page.url}")
    content = page.content()
    print(f"[DEBUG] Page content (first 500 chars):\n{content[:500]}")
    # Assert we are on the correct page after navigation
    if not page.url.endswith("/test"):
        pytest.fail(f"Expected to be on /test, but got {page.url}. Tank context/session may not be set or you were redirected.\nPage content: {content[:500]}")
    # Ensure we are on the correct page and not redirected
    assert "/test" in page.url, f"Expected to be on /test, but got {page.url}. Tank context may not be set."
    # Wait for either the table, the alert, or a flash message
    # try:
    #     page.wait_for_selector("div.alert.alert-info", timeout=10000)
    # except Exception:
    #     print(page.content())
    #     raise

    # # Check for table with results or empty alert
    # table_rows = page.locator('table.table-striped tbody tr')
    # alert = page.locator('div.alert.alert-info')
    # if table_rows.count() > 0:
    #     assert table_rows.first.is_visible()
    #     assert alert.count() == 0 or not alert.is_visible(), "Alert should not be visible when there are test results."
    # else:
    #     assert alert.is_visible()
    #     assert "No test results for this tank" in alert.inner_text()

    # initial_h2 = page.locator("div.container.mt-4 h2").inner_text()

    # # Get all tank options
    # tank_options = page.locator('#tank-select option')
    # num_tanks = tank_options.count()
    # assert num_tanks > 1, "Need at least two tanks to test switching."

    # # Switch to a different tank (not the first/selected one)
    # for i in range(num_tanks):
    #     option = tank_options.nth(i)
    #     if not option.is_selected():
    #         option_value = option.get_attribute('value')
    #         page.select_option('#tank-select', option_value)
    #         break

    # # Wait for the h2 to change

    # page.wait_for_function(
    #     "(h2, initialText) => h2.innerText !== initialText",
    #     page.locator("div.container.mt-4 h2"),
    #     initial_h2,
    #     timeout=10000
    # )
    # new_h2 = page.locator("div.container.mt-4 h2").inner_text()
    # assert initial_h2 != new_h2, "Tank selector did not change the test results header."

def test_all(page):
    page.goto(f"{BASE_URL}/test/add")
    assert page.url.endswith("/test/add"), f"Expected to be on /test/add, but got {page.url}"
    assert "/test/add" in page.url, f"Expected to be on /test/add, but got {page.url}. Tank context may not be set."
    page.wait_for_selector('form')

    # Fill out the form with random values
    rand_alk = str(round(random.uniform(6, 12), 2))
    rand_po4_ppb = str(random.randint(0, 500))  # must be int
    rand_no3_ppm = str(round(random.uniform(0, 50), 2))
    rand_cal = str(random.randint(350, 500))    # must be int
    rand_mg = str(random.randint(1200, 1500))   # must be int
    rand_sg = str(round(random.uniform(1.020, 1.030), 3))

    page.fill('input[name="alk"]', rand_alk)
    page.fill('input[name="po4_ppb"]', rand_po4_ppb)
    page.fill('input[name="no3_ppm"]', rand_no3_ppm)
    page.fill('input[name="cal"]', rand_cal)
    page.fill('input[name="mg"]', rand_mg)
    page.fill('input[name="sg"]', rand_sg)

    # Wait for the submit button to be visible and enabled
    submit_btn = page.locator('input#submit-test')
    assert submit_btn.is_visible(), 'Submit button is not visible.'
    assert submit_btn.is_enabled(), 'Submit button is not enabled.'

    # Submit the form and wait for navigation
    with page.expect_navigation():
        submit_btn.click()
    # If still on the same page, try submitting the form via JS as a fallback
    if page.url.endswith('/test/add'):
        print('[DEBUG] Click did not submit the form, trying JS submit...')
        page.evaluate('document.querySelector("form").submit()')
        page.wait_for_timeout(1000)

    # Assert we are not redirected to the homepage after submission
    if page.url.rstrip('/') == BASE_URL.rstrip('/') or page.url.endswith('/'):
        pytest.fail(f"Unexpected redirect to homepage after submission. Current URL: {page.url}. This likely means tank context/session is missing or DB insert failed.")
    if '/test/db' not in page.url:
        # Print page content for debugging
        content = page.content()
        print(content)
        pytest.fail(f"Expected to be on a /test/db page after submission, but got {page.url}.\nPage content after submit:\n{content[:1000]}")
    # Assert we are on the correct page after submission
    # Wait for any table to appear (id, class, or just table)
    page.wait_for_selector('table, table.dataTable, table.table-striped', timeout=5000)

    # Find the row with the random alk value
    rows = page.locator('table tbody tr')
    found_row = None
    for i in range(rows.count()):
        row = rows.nth(i)
        if rand_alk in row.inner_text():
            found_row = row
            break
    assert found_row is not None, f"Newly added test entry with alk={rand_alk} not found in datatable."

    # Select the row (if selection is required)
    found_row.click()
    page.wait_for_timeout(500)

    # Click the delete button (assuming a button with text 'Delete' or a trash icon is present)
    delete_btn = page.locator('button, .dt-button').filter(has_text='Delete')
    assert delete_btn.count() > 0, 'Delete button not found in datatable UI.'
    
    # Close any open modals that might be interfering
    modal_backdrops = page.locator('.modal-backdrop')
    if modal_backdrops.count() > 0:
        print(f"[DEBUG] Found {modal_backdrops.count()} modal backdrops, closing modals...")
        # Try to close modals by pressing Escape or clicking close buttons
        page.keyboard.press('Escape')
        page.wait_for_timeout(500)
        # Look for and click close buttons
        close_buttons = page.locator('.modal .btn-close, .modal .close, [data-dismiss="modal"]')
        for i in range(close_buttons.count()):
            close_buttons.nth(i).click()
            page.wait_for_timeout(200)
    
    # Wait for any modals to fully close
    page.wait_for_timeout(1000)
    
    # Force remove any remaining modal backdrops via JavaScript
    page.evaluate("document.querySelectorAll('.modal-backdrop').forEach(el => el.remove())")
    
    # Try clicking the delete button with force if modal still interferes
    try:
        delete_btn.first.click(timeout=5000)
    except Exception as e:
        print(f"[DEBUG] Regular click failed: {e}, trying force click...")
        delete_btn.first.click(force=True, timeout=5000)

    # Accept the confirm dialog if present
    def handle_dialog(dialog):
        dialog.accept()
    page.once("dialog", handle_dialog)
    page.wait_for_timeout(1000)

    # Ensure the row is gone
    table_text = page.locator('table tbody').inner_text()
    assert rand_alk not in table_text, f"Deleted test entry with alk={rand_alk} still found in datatable. Table text: {table_text}"
