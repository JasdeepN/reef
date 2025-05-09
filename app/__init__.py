from flask import Flask
from flask_bootstrap import Bootstrap5
import os
from flask_sqlalchemy import SQLAlchemy
from config import Config
from sqlalchemy import create_engine
from flask_session import Session
from prometheus_flask_exporter import PrometheusMetrics
import pytz
from datetime import datetime

UPLOAD_FOLDER = 'static/temp'
ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'])

app = Flask(__name__)
app.config['SECRET_KEY'] = b"f0-aTOho|y[PCk'KS6O(GH/CKCH15;"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

UPLOAD_FOLDER = 'static/temp'

bootstrap = Bootstrap5(app)

engine_string = "mysql+pymysql://{0}:{1}@{2}:{3}/{4}".format(
    os.getenv("DB_USER"), os.getenv("DB_PASS"), os.getenv("DB_HOST_ADDRESS"), os.getenv("DB_HOST_PORT"), os.getenv("DB_NAME")
)

app.config['SQLALCHEMY_DATABASE_URI'] = engine_string
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

app.config['DB_ENGINE'] = create_engine(engine_string)
app.config["SESSION_COOKIE_NAME"] = "session"
app.config.from_object(Config)

# tzname = app.config.get('TIMEZONE', 'UTC')
# tz = pytz.timezone(tzname)
# print("Timezone:", tz)
# print("Current time in timezone:", datetime.now(tz))

Session(app)

# Initialize Prometheus metrics
x_metrics = PrometheusMetrics(app)

# Optional: Add custom metrics
x_metrics.info('app_info', 'Application info', version='1.0.0')
x_metrics.counter('doser_requests_total', 'Total requests to the /doser endpoint') 
x_metrics.counter('timeline_requests_total', 'Total requests to the /timeline endpoint')
x_metrics.counter('api_requests_total', 'Total requests to the /api endpoint')
x_metrics.counter('home_requests_total', 'Total requests to the / endpoint')
x_metrics.counter('metrics_requests_total', 'Total requests to the /metrics endpoint')
x_metrics.counter('test_results_requests_total', 'Total requests to the /test_results endpoint')
# Import and register routes
from app.routes.api import api_bp
app.register_blueprint(api_bp)
from app.routes import corals, home, metrics, test, doser

import modules
