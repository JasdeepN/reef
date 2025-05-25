import pytest
import os
import subprocess
import time
import requests
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import sqlalchemy

# Set the default asyncio fixture loop scope explicitly to avoid warnings
pytest_plugins = ["pytest_asyncio"]

# Load test environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '.env.test'))

# Detect environment and set appropriate database host
# Priority: explicit env vars > ACT detection > CI detection > default
if not os.getenv("DB_HOST_ADDRESS"):
    if os.getenv("ACT") == "true":
        # Running in act (local GitHub Actions runner) - use MySQL container name
        os.environ["DB_HOST_ADDRESS"] = "mysql"
        os.environ["DB_HOST"] = "mysql"
        print("[conftest] Detected ACT environment, using MySQL container name")
    elif os.getenv("CI") or os.getenv("GITHUB_ACTIONS"):
        # Running in real CI - use localhost
        os.environ["DB_HOST_ADDRESS"] = "127.0.0.1"
        os.environ["DB_HOST"] = "127.0.0.1"
        print("[conftest] Detected CI environment, using localhost")
    else:
        # Local development - use configured value from .env.test
        print("[conftest] Local development environment detected")

MYSQL_SCRIPT_ENV = os.getenv('MYSQL_SCRIPT')
if MYSQL_SCRIPT_ENV:
    if os.path.isabs(MYSQL_SCRIPT_ENV):
        MYSQL_SCRIPT = MYSQL_SCRIPT_ENV
    else:
        MYSQL_SCRIPT = os.path.join(os.path.dirname(__file__), MYSQL_SCRIPT_ENV)
else:
    MYSQL_SCRIPT = os.path.join(os.path.dirname(__file__), 'scripts', 'test_mysql_ephemeral.sh')
if not os.path.isfile(MYSQL_SCRIPT):
    raise FileNotFoundError(f"Ephemeral MySQL script not found: {MYSQL_SCRIPT}")

TEST_BASE_URL = os.getenv('TEST_BASE_URL')
TEST_DB_PORT = os.getenv('DB_PORT', '3310')

_test_tank_id = None

def check_flask_server(base_url, max_retries=3, retry_delay=2):
    """Check if Flask server is running and accessible."""
    if not base_url:
        return False, "TEST_BASE_URL not configured"
    
    for attempt in range(max_retries):
        try:
            response = requests.get(f"{base_url}/", timeout=5)
            if response.status_code == 200:
                return True, f"Flask server is running at {base_url}"
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                print(f"[pytest] Flask server check attempt {attempt + 1} failed: {e}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                return False, f"Flask server not accessible after {max_retries} attempts: {e}"
    
    return False, f"Flask server at {base_url} returned non-200 status"

@pytest.fixture(scope="session", autouse=True)
def global_setup_and_teardown():
    print("[pytest] Global setup for ReefDB E2E tests")
    # Only start/stop ephemeral MySQL if not running in CI
    if not os.getenv("CI"):  # CI is set in GitHub Actions and act
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
    
    # Ensure database tables are created using SQLAlchemy models
    from app import app, db
    
    print("[pytest] Creating database tables using SQLAlchemy...")
    with app.app_context():
        # Import models after app context is established to avoid circular imports
        from modules.models import Tank
        
        # Create all tables defined in SQLAlchemy models
        db.create_all()
        print("[pytest] Database tables created successfully")
        
        # Insert a new test tank and use its ID for the rest of the tests
        try:
            test_tank = Tank(name="pytest-tank")
            db.session.add(test_tank)
            db.session.commit()
            tank_id = test_tank.id
            print(f"[pytest] Inserted test tank with id={tank_id}")
            
            # Verify tank was inserted
            all_tanks = Tank.query.all()
            tank_names = [(tank.id, tank.name) for tank in all_tanks]
            print(f"[pytest] All tanks in DB: {tank_names}")
        except Exception as e:
            db.session.rollback()
            print(f"[pytest] Error inserting test tank: {e}")
            raise
    global _test_tank_id
    _test_tank_id = int(tank_id)

    # Only make HTTP requests for E2E tests, not unit tests
    # Check if this is an E2E test session by examining pytest arguments
    import sys
    # Check if we're running E2E tests specifically (not just ignoring them)
    is_e2e_session = any("tests/e2e" in arg or "/e2e/" in arg for arg in sys.argv) and not any("--ignore" in arg and "e2e" in arg for arg in sys.argv)
    
    if is_e2e_session:
        print("[pytest] Detected E2E test session - checking Flask server...")
        # Check if Flask server is running before proceeding with E2E tests
        server_ok, message = check_flask_server(TEST_BASE_URL)
        if not server_ok:
            print(f"[pytest] ❌ {message}")
            print("[pytest] 💡 To start the Flask server, run: make start-test")
            print("[pytest] 💡 Or use: flask run --host=127.0.0.1 --port=5001")
            raise RuntimeError(f"Flask server required for E2E tests: {message}")
        else:
            print(f"[pytest] ✅ {message}")
        
        # Call the set_tank endpoint to set the context using POST with JSON payload
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
    else:
        print(f"[pytest] Skipping HTTP requests for unit tests. Test tank id: {_test_tank_id}")

    yield
    print("[pytest] Global teardown for ReefDB E2E tests")
    # Only stop ephemeral MySQL if not running in CI
    if not os.getenv("CI"):
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

def pytest_configure(config):
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/../'))
    from app import app
    print("[TEST CONTEXT] SQLALCHEMY_DATABASE_URI: {}".format(app.config['SQLALCHEMY_DATABASE_URI']), file=sys.stderr, flush=True)
    print("[TEST CONTEXT] DB ENVIRONMENT:", file=sys.stderr, flush=True)
    for k, v in os.environ.items():
        if k.startswith("DB_") or k == "TEST_BASE_URL":
            print(f"  {k}={v}", file=sys.stderr, flush=True)
    print("[TEST CONTEXT] app.config DB/SQLALCHEMY KEYS:", file=sys.stderr, flush=True)
    for k, v in app.config.items():
        if "DB" in k or "SQLALCHEMY" in k:
            print(f"  {k}={v}", file=sys.stderr, flush=True)
    sys.stderr.flush()
    sys.stdout.flush()
