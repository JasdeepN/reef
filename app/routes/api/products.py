from flask import Blueprint, jsonify, current_app
from app import db
from datetime import datetime, timedelta
from sqlalchemy import text
import pytz

bp = Blueprint('product_api', __name__)

@bp.route('/products/all', methods=['GET']) 
def get_all_products():
    # Import locally to avoid circular import
    from modules.models import Products
    
    products = db.session.query(
        Products.id,
        Products.name,
        Products.total_volume,
        Products.current_avail,
        Products.dry_refill
    ).order_by(Products.name).all()
    
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'total_volume': p.total_volume,
        'current_avail': p.current_avail,
        'dry_refill': p.dry_refill
    } for p in products])