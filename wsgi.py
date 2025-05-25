# Copyright (c) 2025 Jasdeep Nijjar
# All rights reserved.
# Commercial use, copying, or redistribution of this software or any substantial portion of it is strictly prohibited without the express written permission of the copyright holder. For commercial licensing, please contact jasdeepn4@gmail.com.
import os, sys
print("[DEBUG] wsgi.py: importing app", file=sys.stderr, flush=True)
from app import app
print("[DEBUG] wsgi.py: app imported", file=sys.stderr, flush=True)

if __name__ == "__main__":
    app.run()