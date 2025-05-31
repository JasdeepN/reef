"""
Flask extensions initialization.
This module initializes Flask extensions to avoid circular imports.
"""

from flask_sqlalchemy import SQLAlchemy

# Initialize extensions
db = SQLAlchemy()
