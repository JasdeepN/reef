# Copyright (c) 2025 Jasdeep Nijjar
# All rights reserved.
# Commercial use, copying, or redistribution of this software or any substantial portion of it is strictly prohibited without the express written permission of the copyright holder. For commercial licensing, please contact jasdeepn4@gmail.com.
from flask import Flask, session
from flask_bootstrap import Bootstrap5
import os
import sys
from flask_sqlalchemy import SQLAlchemy
from config import Config
from sqlalchemy import create_engine
from flask_session import Session
from prometheus_flask_exporter import PrometheusMetrics
import pytz
from datetime import datetime

print("[DEBUG] ENV DUMP:", file=sys.stderr, flush=True)
for k, v in os.environ.items():
    if k.startswith("DB_") or k == "TEST_BASE_URL":
        print(f"{k}={v}", file=sys.stderr, flush=True)
sys.stderr.flush()
sys.stdout.flush()

UPLOAD_FOLDER = 'static/temp'
ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'])

app = Flask(__name__)
app.config['SECRET_KEY'] = b"f0-aTOho|y[PCk'KS6O(GH/CKCH15;"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config['TEMPLATES_AUTO_RELOAD'] = True  # Force template reloading

UPLOAD_FOLDER = 'static/temp'

bootstrap = Bootstrap5(app)

app.config.from_object(Config)

# Import db from extensions to avoid circular imports
from extensions import db

# Check if we're in unit testing mode (should use SQLite instead of MySQL)
if os.getenv("TESTING") == "true" and os.getenv("SQLALCHEMY_DATABASE_URI"):
    print("[app/__init__.py] Unit testing mode detected - using provided SQLALCHEMY_DATABASE_URI", file=sys.stderr, flush=True)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("SQLALCHEMY_DATABASE_URI")
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    
    # Skip MySQL configuration and go straight to SQLAlchemy setup
    app.config['DB_ENGINE'] = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
    app.config["SESSION_COOKIE_NAME"] = "session"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    Session(app)
    print(f"[app/__init__.py] Unit test setup complete with: {app.config['SQLALCHEMY_DATABASE_URI']}", file=sys.stderr, flush=True)
else:

    # Set DB config at runtime, after env vars are set
    _db_user = os.getenv("DB_USER", "testuser")
    _db_pass = os.getenv("DB_PASS", "testpass")

    # Apply CI environment detection (same logic as conftest.py)
    if os.getenv("ACT"):
        # Running in ACT - use MySQL container name
        _db_host = "mysql"
        print("[app/__init__.py] Detected ACT environment, using MySQL container name", file=sys.stderr, flush=True)
    elif os.getenv("CI") or os.getenv("GITHUB_ACTIONS"):
        # Running in real CI - use localhost
        _db_host = "127.0.0.1" 
        print("[app/__init__.py] Detected CI environment, using localhost", file=sys.stderr, flush=True)
    else:
        # Local development - use configured value from env
        _db_host = os.getenv("DB_HOST_ADDRESS", os.getenv("DB_HOST", "127.0.0.1"))
        print("[app/__init__.py] Local development environment detected", file=sys.stderr, flush=True)

    _db_port = os.getenv("DB_PORT", "3310")
    print(f"[DEBUG] _db_port value: {_db_port} (type: {type(_db_port)})", file=sys.stderr, flush=True)
    if _db_port == "None":
        raise RuntimeError("DB_PORT environment variable is set to the string 'None'. Please set it to a valid port number.")
    _db_name = os.getenv("DB_NAME", "reef_test")
    print(f"[app/__init__.py] DB_USER={_db_user} DB_PASS={_db_pass} DB_HOST={_db_host} DB_PORT={_db_port} DB_NAME={_db_name}", file=sys.stderr, flush=True)
    if not all([_db_user, _db_pass, _db_host, _db_port, _db_name]):
        raise RuntimeError(f"Missing DB env var: DB_USER={_db_user}, DB_PASS={_db_pass}, DB_HOST={_db_host}, DB_PORT={_db_port}, DB_NAME={_db_name}")
    app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{_db_user}:{_db_pass}@{_db_host}:{_db_port}/{_db_name}"
    if ":None/" in app.config['SQLALCHEMY_DATABASE_URI']:
        raise RuntimeError(f"SQLALCHEMY_DATABASE_URI contains ':None/': {app.config['SQLALCHEMY_DATABASE_URI']}")
    print(f"[app/__init__.py] SQLALCHEMY_DATABASE_URI: {app.config['SQLALCHEMY_DATABASE_URI']}", file=sys.stderr, flush=True)

    # Configure MySQL connection pool options for better stability
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_recycle': 300,  # Recycle connections every 5 minutes
        'pool_pre_ping': True,  # Verify connections before use
        'pool_timeout': 20,  # Timeout for getting connection from pool
        'max_overflow': 0,  # Don't allow overflow connections
        'echo': False,  # Set to True for SQL debugging
        'connect_args': {
            'connect_timeout': 10,  # Connection timeout
            'read_timeout': 30,     # Read timeout
            'write_timeout': 30,    # Write timeout
            'charset': 'utf8mb4'    # Proper UTF-8 support
        }
    }

    app.config['DB_ENGINE'] = create_engine(app.config['SQLALCHEMY_DATABASE_URI'], **app.config['SQLALCHEMY_ENGINE_OPTIONS'])
    app.config["SESSION_COOKIE_NAME"] = "session"

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    Session(app)

# Initialize Prometheus metrics (only if not already initialized)
if not hasattr(app, '_metrics_initialized'):
    x_metrics = PrometheusMetrics(app)
    
    # Optional: Add custom metrics
    x_metrics.info('app_info', 'Application info', version='1.0.0')
    x_metrics.counter('doser_requests_total', 'Total requests to the /doser endpoint') 
    x_metrics.counter('timeline_requests_total', 'Total requests to the /timeline endpoint')
    x_metrics.counter('api_requests_total', 'Total requests to the /api endpoint')
    x_metrics.counter('home_requests_total', 'Total requests to the / endpoint')
    x_metrics.counter('metrics_requests_total', 'Total requests to the /metrics endpoint')
    x_metrics.counter('test_results_requests_total', 'Total requests to the /test_results endpoint')
    
    app._metrics_initialized = True

# Initialize Dosing Scheduler (only in non-testing mode)
dosing_scheduler = None
if not app.config.get('TESTING'):
    try:
        from modules.dosing_scheduler import DosingScheduler
        
        # Configure scheduler settings
        app.config['SCHEDULER_ENABLED'] = os.getenv('SCHEDULER_ENABLED', 'true').lower() == 'true'
        app.config['SCHEDULER_AUTOSTART'] = os.getenv('SCHEDULER_AUTOSTART', 'true').lower() == 'true'
        app.config['SCHEDULER_CHECK_INTERVAL'] = int(os.getenv('SCHEDULER_CHECK_INTERVAL', '60'))  # seconds
        app.config['SCHEDULER_TIMEZONE'] = os.getenv('SCHEDULER_TIMEZONE', 'UTC')
        app.config['SCHEDULER_BASE_URL'] = os.getenv('SCHEDULER_BASE_URL', 'http://localhost:5000')
        
        if app.config['SCHEDULER_ENABLED']:
            dosing_scheduler = DosingScheduler(app, app.config['SCHEDULER_BASE_URL'])
            app.dosing_scheduler = dosing_scheduler  # Make it accessible through app
            
            # Auto-start if enabled
            if app.config['SCHEDULER_AUTOSTART']:
                try:
                    dosing_scheduler.start()
                    print("[app/__init__.py] Dosing scheduler initialized and started", file=sys.stderr, flush=True)
                except Exception as start_error:
                    print(f"[app/__init__.py] Warning: Failed to auto-start dosing scheduler: {start_error}", file=sys.stderr, flush=True)
            else:
                print("[app/__init__.py] Dosing scheduler initialized (auto-start disabled)", file=sys.stderr, flush=True)
        else:
            print("[app/__init__.py] Dosing scheduler disabled by configuration", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"[app/__init__.py] Warning: Failed to initialize dosing scheduler: {e}", file=sys.stderr, flush=True)

# Import and register routes
from app.routes.api import api_bp
from app.routes.web import web_fn
app.register_blueprint(api_bp)
app.register_blueprint(web_fn)
from app.routes import corals, home, metrics, test, doser, models, scheduler, missed_dose, tanks
import modules

# Move context processor registration here to avoid circular import
from modules.models import Tank
from modules.tank_context import get_current_tank_id
from flask import request

@app.context_processor
def inject_tank_context():
    # For unit tests without database, provide default values
    if app.config.get('TESTING') and not app.config.get('SQLALCHEMY_DATABASE_URI', '').startswith('mysql'):
        return dict(tanks=[], tank_id=1, is_vscode_browser=False)
    
    try:
        tanks = Tank.query.all()
        tank_id = get_current_tank_id()
        
        # Detect VS Code Simple Browser
        user_agent = request.headers.get('User-Agent', '')
        is_vscode_browser = 'vscode simple browser' in user_agent.lower() or 'vs code' in user_agent.lower()
        
        return dict(tanks=tanks, tank_id=tank_id, is_vscode_browser=is_vscode_browser)
    except Exception as e:
        # If database is not available during testing, provide defaults
        if app.config.get('TESTING'):
            print(f"[inject_tank_context] Database not available during testing, using defaults: {e}")
            return dict(tanks=[], tank_id=1, is_vscode_browser=False)
        raise

# FINAL FAIL-FAST CHECK
print(f"[FINAL CHECK] SQLALCHEMY_DATABASE_URI: {app.config['SQLALCHEMY_DATABASE_URI']}", file=sys.stderr, flush=True)
if ':None/' in app.config['SQLALCHEMY_DATABASE_URI']:
    raise RuntimeError(f"[FINAL CHECK] SQLALCHEMY_DATABASE_URI contains ':None/': {app.config['SQLALCHEMY_DATABASE_URI']}")
