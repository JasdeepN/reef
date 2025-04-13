import os
basedir = os.path.abspath(os.path.dirname(__file__))

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
    PYTHONGRID_DB_HOSTNAME = os.getenv("DB_HOST_ADDRESS")
    PYTHONGRID_DB_NAME = os.getenv("DB_NAME")
    PYTHONGRID_DB_USERNAME = os.getenv("DB_USER")
    PYTHONGRID_DB_PASSWORD = os.getenv("DB_PASS")
    PYTHONGRID_DB_TYPE = 'mysql+pymysql'
    PYTHONGRID_DB_SOCKET = os.getenv("DB_SOCKET")
    PYTHONGRID_DB_CHARSET = 'utf-8'

    # constant
    GRID_SESSION_KEY = '_oPYTHONGRID'
    JQGRID_ROWID_KEY = '_rowid'
    PK_DELIMITER = '---' # must be 3 characters


    ENGINE_STRING='mysql+pymysql://{0}:{1}@{2}:{3}/{4}'.format(os.getenv("DB_USER"), os.getenv("DB_PASS"), os.getenv("DB_HOST_ADDRESS"), os.getenv("DB_HOST_PORT"), os.getenv("DB_NAME"))
