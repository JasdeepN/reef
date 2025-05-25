import pytest
import time
import os

def cleanup_existing_test_products(page):
    """Clean up any existing test products before running tests"""
    cards = page.locator('.card-data-body')
    cards_count = cards.count()
    
    for i in range(cards_count - 1, -1, -1):  # Iterate backwards to avoid index issues
        card = cards.nth(i)
        card_text = card.inner_text()
        if 'Playwright Test Product' in card_text:
            print(f"[DEBUG] Found existing test product, removing...")
            delete_btn = card.locator('.action-btn')
            delete_btn.click()
            page.wait_for_timeout(1000)  # Wait for deletion
    
    # Wait a bit more for any remaining deletions to complete
    page.wait_for_timeout(1000)

def test_product_card_create_and_delete(page):
    # Get base URL from environment variable
    BASE_URL = os.getenv('TEST_BASE_URL', 'http://localhost:5001')
    print(f"[DEBUG] Using BASE_URL: {BASE_URL}")
    
    # Start your Flask app before running this test!
    page.goto(f"{BASE_URL}/doser/products")

    page.wait_for_selector('.card-data-body', timeout=30000)
    
    # Clean up any existing "Playwright Test Product" cards first
    print("[DEBUG] Cleaning up any existing test products...")
    cleanup_existing_test_products(page)
    
    # Get count after cleanup
    cards_before = page.locator('.card-data-body').count()
    print(f"[DEBUG] Cards before test: {cards_before}")

    # Set up dialog handler before any action that might trigger a dialog
    dialog_handled = False
    def handle_alert(dialog):
        nonlocal dialog_handled
        if not dialog_handled:
            dialog.accept()
            dialog_handled = True
    
    page.on("dialog", handle_alert)

    # Add a new product
    page.click('#show-add-product-form')
    page.fill('#name', 'Playwright Test Product')
    page.fill('#total_volume', '123')
    page.fill('#current_avail', '45')
    page.fill('#dry_refill', '67')
    page.click('button[type="submit"]')

    # Wait for reload and new card to appear
    page.wait_for_timeout(3000)  # Increased wait time
    cards_after_add = page.locator('.card-data-body').count()
    assert cards_after_add == cards_before + 1

    # Find the new card by product name
    new_card = None
    for i in range(cards_after_add):
        card = page.locator('.card-data-body').nth(i)
        if 'Playwright Test Product' in card.inner_text():
            new_card = card
            break
    assert new_card is not None, 'Newly created product card not found.'

    # Reset dialog handler for deletion
    dialog_handled = False
    
    # Click the delete button on the new card
    delete_btn = new_card.locator('.action-btn')
    delete_btn.click()

    # Wait for card to be removed
    page.wait_for_timeout(2000)
    cards_after_delete = page.locator('.card-data-body').count()
    assert cards_after_delete == cards_before