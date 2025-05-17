import pytest
from playwright.sync_api import sync_playwright
import subprocess
import time
import os
from dotenv import load_dotenv
import sqlalchemy

# Set the default asyncio fixture loop scope explicitly to avoid warnings
pytest_plugins = ["pytest_asyncio"]

# Load test environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '.env.test'))

MYSQL_SCRIPT_ENV = os.getenv('MYSQL_SCRIPT')
if MYSQL_SCRIPT_ENV:
    if os.path.isabs(MYSQL_SCRIPT_ENV):
        MYSQL_SCRIPT = MYSQL_SCRIPT_ENV
    else:
        MYSQL_SCRIPT = os.path.join(os.path.dirname(__file__), MYSQL_SCRIPT_ENV)
else:
    MYSQL_SCRIPT = os.path.join(os.path.dirname(__file__), 'test_mysql_ephemeral.sh')
if not os.path.isfile(MYSQL_SCRIPT):
    raise FileNotFoundError(f"Ephemeral MySQL script not found: {MYSQL_SCRIPT}")

TEST_BASE_URL = os.getenv('TEST_BASE_URL')
TEST_DB_PORT = os.getenv('PORT', '3310')

_test_tank_id = None

@pytest.fixture(scope="session", autouse=True)
def global_setup_and_teardown():
    print("[pytest] Global setup for ReefDB E2E tests")
    # Start ephemeral MySQL test DB
    subprocess.run(["bash", MYSQL_SCRIPT, "start"], check=True)
    # Wait for DB to be ready using the status command
    max_wait = 30  # seconds
    for _ in range(max_wait):
        status = subprocess.run(["bash", MYSQL_SCRIPT, "status"], capture_output=True)
        if status.returncode == 0:
            print("[pytest] Ephemeral MySQL test DB is ready.")
            break
        time.sleep(1)
    else:
        raise RuntimeError("Ephemeral MySQL test DB did not become ready in time.")
    
    # Insert a new test tank and use its ID for the rest of the tests
    from sqlalchemy import create_engine, text
    db_url = f"mysql+pymysql://{os.getenv('DB_USER', 'testuser')}:{os.getenv('DB_PASS')}@{os.getenv('DB_HOST_ADDRESS', '127.0.0.1')}:{os.getenv('TEST_DB_PORT', '3310')}/{os.getenv('DB_NAME', 'reef_test')}"
    print(f"[pytest] Connecting to DB: {db_url}")
    engine = create_engine(db_url)
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            result = conn.execute(text("INSERT INTO tanks (name) VALUES (:name)"), {"name": "pytest-tank"})
            tank_id = result.lastrowid
            print(f"[pytest] Inserted test tank with id={tank_id}")
            tanks = conn.execute(text("SELECT id, name FROM tanks")).fetchall()
            print(f"[pytest] All tanks in DB: {tanks}")
            trans.commit()
        except Exception:
            trans.rollback()
            raise
    global _test_tank_id
    _test_tank_id = int(tank_id)

    # Call the set_tank endpoint to set the context using POST with JSON payload
    import requests
    set_tank_url = f"{TEST_BASE_URL}/set_tank"
    try:
        resp = requests.post(
            set_tank_url,
            json={"tank_id": _test_tank_id},
            headers={"Referer": TEST_BASE_URL + "/"}
        )
        print(f"[pytest] POSTed to set_tank endpoint: {set_tank_url}, payload={{'tank_id': {_test_tank_id}}}, status={resp.status_code}")
    except Exception as e:
        print(f"[pytest] Failed to POST to set_tank endpoint: {e}")

    yield
    print("[pytest] Global teardown for ReefDB E2E tests")
    # Stop ephemeral MySQL test DB
    subprocess.run(["bash", MYSQL_SCRIPT, "stop"], check=True)

@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()

@pytest.fixture(scope="session")
def context(browser):
    context = browser.new_context()
    def auto_accept_dialog(dialog):
        dialog.accept()
    context.on("dialog", auto_accept_dialog)
    yield context
    context.close()

@pytest.fixture(scope="function")
def page(context, test_tank_id):
    page = context.new_page()
    assert TEST_BASE_URL and TEST_BASE_URL.startswith("http"), f"Invalid TEST_BASE_URL: {TEST_BASE_URL}"
    # Set tank context in the browser session using POST
    page.goto(f"{TEST_BASE_URL}/")
    page.evaluate(
        '''(tank_id) => {
            fetch("/set_tank", {
                method: "POST",
                headers: {"Content-Type": "application/x-www-form-urlencoded"},
                body: "tank_id=" + encodeURIComponent(tank_id)
            });
        }''',
        test_tank_id
    )
    page.wait_for_timeout(500)  # Give the server a moment to set the session
    yield page
    page.close()

@pytest.fixture(scope="session")
def test_tank_id():
    global _test_tank_id
    return _test_tank_id
