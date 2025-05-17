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

    # postgres
    """
    PYTHONGRID_DB_HOSTNAME = 'localhost'
    PYTHONGRID_DB_NAME = 'sampledb'
    PYTHONGRID_DB_USERNAME = 'root'
    PYTHONGRID_DB_PASSWORD = 'root'
    PYTHONGRID_DB_TYPE = 'postgres+psycopg2'
    PYTHONGRID_DB_SOCKET = ''
    PYTHONGRID_DB_CHARSET = 'utf-8'
    """
    
    # mysql 
    # PYTHONGRID_DB_HOSTNAME = os.getenv("DB_HOST_ADDRESS")
    # PYTHONGRID_DB_NAME = os.getenv("DB_NAME")
    # PYTHONGRID_DB_USERNAME = os.getenv("DB_USER")
    # PYTHONGRID_DB_PASSWORD = os.getenv("DB_PASS")
    # PYTHONGRID_DB_TYPE = 'mysql+pymysql'
    # PYTHONGRID_DB_SOCKET = os.getenv("DB_SOCKET")
    # PYTHONGRID_DB_CHARSET = 'utf-8'

    # constant
    GRID_SESSION_KEY = '_oPYTHONGRID'
    JQGRID_ROWID_KEY = '_rowid'
    PK_DELIMITER = '---' # must be 3 characters

    GUNICORN_WORKERS = 4  # Number of worker processes
    GUNICORN_BIND = "0.0.0.0:5000"  # Bind address
    GUNICORN_WORKER_CLASS = "gevent"  # Use Gevent worker class

    ENGINE_STRING = 'mysql+pymysql://{0}:{1}@{2}:{3}/{4}'.format(
        os.getenv("DB_USER"), os.getenv("DB_PASS"), os.getenv("DB_HOST_ADDRESS"), os.getenv("DB_HOST_PORT"), os.getenv("DB_NAME")
    )

    # Add timezone config
    TIMEZONE = os.getenv("TIMEZONE", SYSTEM_TIMEZONE)
