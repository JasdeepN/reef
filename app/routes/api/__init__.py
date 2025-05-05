from flask import Blueprint
import modules
from .products import bp as products_bp
from .scheduler import bp as schedule_bp
from .advanced_join import bp as advanced_join_bp
from .table_ops import bp as table_ops_bp
from .controller import bp as controller_bp

api_bp = Blueprint('api', __name__, url_prefix='/api')


api_bp.register_blueprint(table_ops_bp)
api_bp.register_blueprint(schedule_bp)
api_bp.register_blueprint(products_bp)
api_bp.register_blueprint(advanced_join_bp)
api_bp.register_blueprint(controller_bp)