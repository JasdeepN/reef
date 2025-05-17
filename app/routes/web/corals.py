from flask import Blueprint, jsonify, current_app
from app import db
from modules.models import Coral, Tank, Taxonomy
from datetime import datetime
import pytz

bp = Blueprint('coral_api', __name__, url_prefix='/corals')

@bp.route('/stats', methods=['GET'])
def get_coral_stats():
    # Optionally join with Tank and Taxonomy for more info
    corals = db.session.query(Coral, Tank, Taxonomy).\
        outerjoin(Tank, Coral.tank_id == Tank.id).\
        outerjoin(Taxonomy, Coral.taxonomy_id == Taxonomy.id).all()

    tzname = current_app.config.get('TIMEZONE', 'UTC')
    tz = pytz.timezone(tzname)
    stats = []

    for coral, tank, taxonomy in corals:
        stat = {}
        stat['card_title'] = ['Coral Name', coral.coral_name, coral.id]
        # stat['coral_type'] = ['Type', coral.coral_type, '']
        stat['species'] = ['Species', taxonomy.species if taxonomy else '', '']
        stat['common_name'] = ['Common Name', taxonomy.common_name if taxonomy else '', '']
        stat['date_acquired'] = [
            'Date Acquired',
            coral.date_acquired.strftime('%b %d %Y') if coral.date_acquired else None,
            ''
        ]
        stat['tank'] = ['Tank', tank.name if tank else '', '']
        # stat['lighting'] = ['Lighting', coral.lighting, '']
        stat['par'] = ['PAR', coral.par, '']
        stat['flow'] = ['Flow', coral.flow, '']
        # stat['feeding'] = ['Feeding', coral.feeding, '']
        stat['placement'] = ['Placement', coral.placement, '']
        stat['current_size'] = ['Current Size', coral.current_size, '']
        stat['color_morph'] = ['Color Morph', coral.color_morph.morph_name, '']
        stat['health_status'] = ['Health Status', coral.health_status, '']
        stat['frag_colony'] = ['Frag/Colony', coral.frag_colony, '']
        # stat['growth_rate'] = ['Growth Rate', coral.growth_rate, '']
        stat['last_fragged'] = [
            'Last Fragged',
            coral.last_fragged.strftime('%b %d %Y') if coral.last_fragged else None,
            ''
        ]
        # stat['origin'] = ['Origin', coral.origin, '']
        # stat['compatibility'] = ['Compatibility', coral.compatibility, '']
        stat['notes'] = ['Notes', coral.notes, '']
        # stat['created_at'] = [
        #     'Created',
        #     coral.created_at.astimezone(tz).strftime('%b %d %Y %H:%M:%S') if coral.created_at else None,
        #     ''
        # ]
        stat['updated_at'] = [
            'Updated',
            coral.updated_at.astimezone(tz).strftime('%b %d %Y %H:%M:%S') if coral.updated_at else None,
            ''
        ]
        stats.append(stat)
    return jsonify(stats)

@bp.route('/vendors/all', methods=['GET'])
def get_all_vendors():
    from modules.models import Vendors
    vendors = Vendors.query.order_by(Vendors.name).all()
    # print(f"Vendors: {vendors}")    
    return jsonify([{'id': v.id, 'name': v.name} for v in vendors])