## web model functons 
## view models
## update models
## etc.

from app import db
from flask import Blueprint, jsonify, request

bp = Blueprint('models_web', __name__, url_prefix='/models')