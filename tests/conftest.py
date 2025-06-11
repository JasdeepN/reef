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

# Load test environment variables with override=True to ensure test values take precedence
load_dotenv(os.path.join(os.path.dirname(__file__), '.env.test'), override=True)

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

_test_system_id = None

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
    """Global setup for test session with improved error handling"""
    print("[pytest] Global setup for ReefDB tests")
    
    # Start ephemeral MySQL if not in CI
    if not os.getenv("CI"):
        subprocess.run(["bash", MYSQL_SCRIPT, "start"], check=True)
        # Wait for DB readiness
        _wait_for_database_ready()
    
    # Setup test system ID
    global _test_system_id
    _test_system_id = _setup_test_system()
    
    # Handle E2E-specific setup
    if _is_e2e_session():
        _setup_e2e_environment()
    
    yield
    
    # Cleanup
    print("[pytest] Global teardown for ReefDB tests")
    if not os.getenv("CI"):
        subprocess.run(["bash", MYSQL_SCRIPT, "stop"], check=False)

@pytest.fixture(scope="session", autouse=True)
def fix_flask_session_permissions():
    """Ensure flask_session directory and files are readable/writable for all tests (unit and E2E)."""
    session_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../flask_session'))
    if os.path.exists(session_dir):
        try:
            import stat
            # Set owner to current user and permissions to u+rwX
            for root, dirs, files in os.walk(session_dir):
                for d in dirs:
                    os.chmod(os.path.join(root, d), 0o700)
                for f in files:
                    os.chmod(os.path.join(root, f), 0o600)
            os.chmod(session_dir, 0o700)
        except Exception as e:
            print(f"[pytest setup] Warning: Could not fix flask_session permissions: {e}")

def _wait_for_database_ready():
    """Wait for database to be ready with proper timeout"""
    max_wait = 30
    for _ in range(max_wait):
        status = subprocess.run(["bash", MYSQL_SCRIPT, "status"], capture_output=True)
        if status.returncode == 0:
            print("[pytest] Ephemeral MySQL test DB is ready.")
            return
        time.sleep(1)
    raise RuntimeError("Ephemeral MySQL test DB did not become ready in time.")

def _setup_test_system():
    """Setup test system with fallback to existing data"""
    from app import app, db
    from modules.models import Tank, TankSystem
    
    print("[pytest] Setting up test system...")
    with app.app_context():
        try:
            # First, try to use existing tanks and their systems from dev data
            existing_tanks = Tank.query.filter(Tank.tank_system_id.isnot(None)).limit(1).all()
            if existing_tanks:
                system_id = existing_tanks[0].tank_system_id
                print(f"[pytest] Using existing system with id={system_id} from tank {existing_tanks[0].id}")
                return system_id
            
            # If no tanks with systems exist, check for standalone systems
            existing_systems = TankSystem.query.limit(1).all()
            if existing_systems:
                system_id = existing_systems[0].id
                print(f"[pytest] Using existing system with id={system_id}")
                return system_id
        except Exception as e:
            print(f"[pytest] Could not query existing systems/tanks: {e}")
        
        # Fallback to default system ID
        print("[pytest] Using fallback system_id=1")
        return 1

def _is_e2e_session():
    """Check if this is an E2E test session"""
    import sys
    return any("tests/e2e" in arg or "/e2e/" in arg for arg in sys.argv) and \
           not any("--ignore" in arg and "e2e" in arg for arg in sys.argv)

def _setup_e2e_environment():
    """Setup E2E environment with Flask server checks"""
    test_base_url = os.getenv('TEST_BASE_URL', 'http://172.0.10.1:5001')
    print(f"[pytest] E2E setup - checking Flask server at {test_base_url}")
    
    try:
        response = requests.get(f"{test_base_url}/", timeout=10)
        if response.status_code == 200:
            print("[pytest] Flask server is ready for E2E tests")
        else:
            print(f"[pytest] Flask server returned status {response.status_code}")
    except Exception as e:
        print(f"[pytest] Flask server not ready: {e}")
        print("[pytest] E2E tests may fail if Flask server is not running")
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
        
        # Call the set_system endpoint to set the context using POST with JSON payload
        set_system_url = f"{TEST_BASE_URL}/set_system"
        try:
            resp = requests.post(
                set_system_url,
                json={"system_id": _test_system_id},
                headers={"Referer": TEST_BASE_URL + "/"}
            )
            print(f"[pytest] POSTed to set_system endpoint: {set_system_url}, payload={{'system_id': {_test_system_id}}}, status={resp.status_code}")
        except Exception as e:
            print(f"[pytest] Failed to POST to set_system endpoint: {e}")
    else:
        print(f"[pytest] Skipping HTTP requests for unit tests. Test system id: {_test_system_id}")

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
def page(context, test_system_id):
    page = context.new_page()
    assert TEST_BASE_URL and TEST_BASE_URL.startswith("http"), f"Invalid TEST_BASE_URL: {TEST_BASE_URL}"
    # Set system context in the browser session using POST
    page.goto(f"{TEST_BASE_URL}/")
    page.evaluate(
        '''(system_id) => {
            fetch("/set_system", {
                method: "POST",
                headers: {"Content-Type": "application/x-www-form-urlencoded"},
                body: "system_id=" + encodeURIComponent(system_id)
            });
        }''',
        test_system_id
    )
    page.wait_for_timeout(500)  # Give the server a moment to set the session
    yield page
    page.close()

@pytest.fixture(scope="session")
def test_system_id():
    global _test_system_id
    return _test_system_id

@pytest.fixture(scope="session")
def test_tank_id():
    """Backward compatibility fixture that returns first tank from system"""
    global _test_system_id
    from app import app, db
    from modules.models import Tank
    
    with app.app_context():
        try:
            # Find first tank in the test system
            tank = Tank.query.filter_by(tank_system_id=_test_system_id).first()
            if tank:
                return tank.id
        except Exception as e:
            print(f"[pytest] Could not get tank from system {_test_system_id}: {e}")
        
        # Fallback to tank id 1
        return 1

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
