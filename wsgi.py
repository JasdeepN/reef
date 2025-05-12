# Copyright (c) 2025 Jasdeep Nijjar
# All rights reserved.
# Commercial use, copying, or redistribution of this software or any substantial portion of it is strictly prohibited without the express written permission of the copyright holder. For commercial licensing, please contact jasdeepn4@gmail.com.
from app import app
import os
from config import Config



# Apply configuration from config.py
app.config.from_object(Config)

if __name__ == "__main__":
    app.run(host=Config.GUNICORN_BIND.split(":")[0], port=int(Config.GUNICORN_BIND.split(":")[1]))