from flask import Blueprint
import modules
from .products import bp as products_bp
from .controller import bp as controller_bp
from .tests import bp as tests_bp
from .taxonomy import bp as taxonomy_bp
from .corals import bp as corals_bp
from .models import bp as alk
from .scheduler import bp as scheduler_bp
from .home import bp as home_bp
from .timeline import bp as timeline_bp
from .tanks import tanks_api
from .audit import bp as audit_bp
from .audit_calendar import bp as audit_calendar_bp

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')


api_bp.register_blueprint(products_bp)
api_bp.register_blueprint(controller_bp)
api_bp.register_blueprint(tests_bp)
api_bp.register_blueprint(taxonomy_bp)
api_bp.register_blueprint(corals_bp)
api_bp.register_blueprint(alk)
api_bp.register_blueprint(scheduler_bp)
api_bp.register_blueprint(home_bp)
api_bp.register_blueprint(timeline_bp)
api_bp.register_blueprint(tanks_api)
api_bp.register_blueprint(audit_bp, url_prefix='/audit')
api_bp.register_blueprint(audit_calendar_bp, url_prefix='/audit-calendar')

