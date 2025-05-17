from flask import Blueprint, jsonify, current_app
from app import db
from modules.models import Coral, Tank, Taxonomy
from datetime import datetime
import pytz

bp = Blueprint('coral_api', __name__, url_prefix='/corals')


@bp.route('/vendors/all', methods=['GET'])
def get_all_vendors():
    from modules.models import Vendors
    vendors = Vendors.query.order_by(Vendors.name).all()
    # print(f"Vendors: {vendors}")    
    return jsonify([{'id': v.id, 'name': v.name} for v in vendors])