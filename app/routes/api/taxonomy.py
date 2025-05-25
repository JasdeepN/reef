from flask import Blueprint, jsonify, request
from modules.models import Taxonomy, Coral
from app import db

bp = Blueprint('taxonomy_api', __name__, url_prefix='/taxonomy')

DEFAULT_ORIGINS = [
    'Australia', 'Fiji', 'Indonesia', 'Solomon Islands', 'Tonga', 'Vietnam',
    'Philippines', 'Papua New Guinea', 'Marshall Islands', 'Vanuatu', 'Maldives',
    'Red Sea', 'Caribbean', 'Hawaii', 'Florida Keys', 'Kenya', 'Sri Lanka', 'Other'
]

@bp.route('/genus/all', methods=['GET'])
def get_all_genus():
    # Return all unique genus names, their type, and the lowest taxonomy.id for each genus
    genus_list = (
        db.session.query(
            Taxonomy.genus,
            Taxonomy.type,
            db.func.min(Taxonomy.id).label('id')
        )
        .group_by(Taxonomy.genus, Taxonomy.type)
        .order_by(Taxonomy.genus)
        .all()
    )
    return jsonify([{'genus': g[0], 'type': g[1], 'id': g[2]} for g in genus_list])

@bp.route('/species/by_genus', methods=['GET'])
def get_species_by_genus():
    genus = request.args.get('genus')
    if not genus:
        return jsonify([])

    species_list = (
        db.session.query(Taxonomy)
        .filter(Taxonomy.genus == genus)
        .order_by(Taxonomy.species)
        .all()
    )
    # Return taxonomy.id for use as taxonomy_id in the form
    return jsonify([
        {
            'id': s.id,
            'genus': s.genus,
            'species': s.species,
            'common_name': s.common_name
        }
        for s in species_list
    ])

@bp.route('/color_morphs/by_genus', methods=['GET'])
def get_color_morphs_by_genus():
    genus = request.args.get('genus')
    if not genus:
        return jsonify([])

    # Join Taxonomy and ColorMorphs via taxonomy.genus and color_morphs.taxonomy_id
    # Assumes ColorMorphs table has a taxonomy_id foreign key
    from modules.models import ColorMorphs, Taxonomy

    # Find all taxonomy IDs for this genus
    taxonomy_ids = db.session.query(Taxonomy.id).filter(Taxonomy.genus == genus).all()
    taxonomy_ids = [tid[0] for tid in taxonomy_ids]

    if not taxonomy_ids:
        return jsonify([])

    color_morphs = (
        db.session.query(ColorMorphs)
        .filter(ColorMorphs.taxonomy_id.in_(taxonomy_ids))
        .order_by(ColorMorphs.morph_name)
        .all()
    )
    return jsonify([
        {'id': cm.id, 'name': cm.morph_name}
        for cm in color_morphs
    ])

@bp.route('/genus/details/<genus>', methods=['GET'])
def get_genus_details(genus):
    print('get_genus_details', genus)
    if not genus:
        return jsonify({'species': [], 'color_morphs': []})

    # Get all species for this genus
    species_list = (
        db.session.query(Taxonomy)
        .filter(Taxonomy.genus == genus)
        .order_by(Taxonomy.species)
        .all()
    )
    species_data = [
        {
            'id': s.id,
            'species': s.species,
            'common_name': s.common_name
        }
        for s in species_list
    ]

    # Get all color morphs for this genus (include taxonomy_id for filtering)
    from modules.models import ColorMorphs
    taxonomy_ids = [s.id for s in species_list]
    color_morphs = []
    if taxonomy_ids:
        color_morphs = (
            db.session.query(ColorMorphs)
            .filter(ColorMorphs.taxonomy_id.in_(taxonomy_ids))
            .order_by(ColorMorphs.morph_name)
            .all()
        )
    color_morphs_data = [
        {
            'id': cm.id,
            'name': cm.morph_name,
            'taxonomy_id': cm.taxonomy_id  # <-- include taxonomy_id for dynamic filtering
        }
        for cm in color_morphs
    ]

    return jsonify({
        'species': species_data,
        'color_morphs': color_morphs_data
    })

