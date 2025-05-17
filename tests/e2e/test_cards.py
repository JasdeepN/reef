import pytest
import time

def test_product_card_create_and_delete(page):
    # Set the test flag before page load to disable onbeforeunload
    # page.add_init_script("window.PLAYWRIGHT_TEST = true;")

    # Start your Flask app before running this test!
    page.goto("http://172.0.10.1:5000/doser/products")

    page.wait_for_selector('.card-data-body', timeout=30000)
    cards_before = page.locator('.card-data-body').count()

    # Add a new product
    page.click('#show-add-product-form')
    page.fill('#name', 'Playwright Test Product')
    page.fill('#total_volume', '123')
    page.fill('#current_avail', '45')
    page.fill('#dry_refill', '67')
    page.click('button[type="submit"]')

    # Wait for alert and accept it
    def handle_alert(dialog):
        dialog.accept()
    page.once("dialog", handle_alert)

    # Wait for reload and new card to appear
    page.wait_for_timeout(1500)
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

    # Click the delete button on the new card
    delete_btn = new_card.locator('.action-btn')
    page.once("dialog", handle_alert)
    delete_btn.click()

    # Wait for card to be removed
    page.wait_for_timeout(1000)
    cards_after_delete = page.locator('.card-data-body').count()
    assert cards_after_delete == cards_before