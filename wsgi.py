from app import app
import os
from config import Config



# Apply configuration from config.py
app.config.from_object(Config)

if __name__ == "__main__":
    app.run(host=Config.GUNICORN_BIND.split(":")[0], port=int(Config.GUNICORN_BIND.split(":")[1]))