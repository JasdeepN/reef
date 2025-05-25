# Copyright (c) 2025 Jasdeep Nijjar
# All rights reserved.
# Commercial use, copying, or redistribution of this software or any substantial portion of it is strictly prohibited without the express written permission of the copyright holder. For commercial licensing, please contact jasdeepn4@gmail.com.
import os
from dotenv import load_dotenv
import tzlocal  # pip install tzlocal

import logging
logging.basicConfig(level=logging.INFO)

basedir = os.path.abspath(os.path.dirname(__file__))
# Load environment variables from .flaskenv
dotenv_path = os.path.join(os.path.dirname(__file__), '.flaskenv')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

# Automatically determine system timezone
try:
    SYSTEM_TIMEZONE = tzlocal.get_localzone_name()
except Exception:
    SYSTEM_TIMEZONE = 'UTC'

class Config(object):

    ABS_PATH = '/'

    # constant
    GRID_SESSION_KEY = '_oPYTHONGRID'
    JQGRID_ROWID_KEY = '_rowid'
    PK_DELIMITER = '---' # must be 3 characters

    GUNICORN_WORKERS = 4  # Number of worker processes
    GUNICORN_BIND = "0.0.0.0:5000"  # Bind address
    GUNICORN_WORKER_CLASS = "gevent"  # Use Gevent worker class

    # Add timezone config
    TIMEZONE = os.getenv("TIMEZONE", SYSTEM_TIMEZONE)
