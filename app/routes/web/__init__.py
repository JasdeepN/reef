from flask import Blueprint
import modules
from .products import bp as products_web
from .schedule import bp as schedule_web
from .advanced_join import bp as advanced_join_web
from .table_ops import bp as table_ops_web
from .timeline import bp as timeline_web
from .tests import bp as tests_web
from .taxonomy import bp as taxonomy_web
from .corals import bp as corals_web
from .models import bp as alk_W

web_fn = Blueprint('web_fn', __name__, url_prefix='/web/fn')


web_fn.register_blueprint(table_ops_web)
web_fn.register_blueprint(schedule_web)
web_fn.register_blueprint(products_web)
web_fn.register_blueprint(advanced_join_web)
web_fn.register_blueprint(timeline_web)
web_fn.register_blueprint(tests_web)
web_fn.register_blueprint(taxonomy_web)
web_fn.register_blueprint(corals_web)
web_fn.register_blueprint(alk_W)

