from flask import Flask
from flask_bootstrap import Bootstrap5
import os
from flask_sqlalchemy import SQLAlchemy
from config import Config
from sqlalchemy import create_engine
from flask import Flask, session
from flask_session import Session

UPLOAD_FOLDER = 'static/temp'
ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'])

app = Flask(__name__)
app.config['SECRET_KEY'] = b"f0-aTOho|y[PCk'KS6O(GH/CKCH15;"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

UPLOAD_FOLDER = 'static/temp'

bootstrap = Bootstrap5(app)

engine_string="mysql+pymysql://{0}:{1}@{2}:{3}/{4}".format(os.getenv("DB_USER"), os.getenv("DB_PASS"), os.getenv("DB_HOST_ADDRESS"), os.getenv("DB_HOST_PORT"), os.getenv("DB_NAME"))

app.config['SQLALCHEMY_DATABASE_URI'] = engine_string
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

app.config['DB_ENGINE'] = create_engine(engine_string)
app.config["SESSION_COOKIE_NAME"] = "session"
app.config.from_object(Config)

Session(app)

# Import and register routes
from app.routes import home, test, doser, timeline, api
import modules    