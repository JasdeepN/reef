from flask import Blueprint
import modules
from .products import bp as products_bp
from .controller import bp as controller_bp
from .tests import bp as tests_bp
from .taxonomy import bp as taxonomy_bp
from .corals import bp as corals_bp
from .models import bp as alk

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')


api_bp.register_blueprint(products_bp)
api_bp.register_blueprint(controller_bp)
api_bp.register_blueprint(tests_bp)
api_bp.register_blueprint(taxonomy_bp)
api_bp.register_blueprint(corals_bp)
api_bp.register_blueprint(alk)

