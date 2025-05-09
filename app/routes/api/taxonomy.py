from flask import Blueprint, jsonify, request
from modules.models import Taxonomy, Coral

bp = Blueprint('taxonomy_api', __name__)

DEFAULT_ORIGINS = [
    'Australia', 'Fiji', 'Indonesia', 'Solomon Islands', 'Tonga', 'Vietnam',
    'Philippines', 'Papua New Guinea', 'Marshall Islands', 'Vanuatu', 'Maldives',
    'Red Sea', 'Caribbean', 'Hawaii', 'Florida Keys', 'Kenya', 'Sri Lanka', 'Other'
]

@bp.route('/taxonomy/by_type')
def taxonomy_by_type():
    coral_type = request.args.get('type')
    if not coral_type:
        return jsonify([])
    rows = Taxonomy.query.filter_by(type=coral_type).all()
    return jsonify([{
        "id": t.id,
        "common_name": t.common_name,
        "species": t.species
    } for t in rows])


@bp.route('/taxonomy/origins/all')
def origins_all():
    origins = Coral.query.with_entities(Coral.origin).distinct().filter(
        Coral.origin.isnot(None), Coral.origin != ''
    ).all()
    origin_list = [o[0] for o in origins if o[0]]
    if not origin_list:
        origin_list = DEFAULT_ORIGINS
    return jsonify(origin_list)


